"""External cellular-abundance calibration CLI across 11 ProteinGym Expression DMS proteins.

Frozen protocol: ``ressources/track2/it6/abundance_calibration/protocol.md``.

    uv run python tools/abundance_calibration.py evaluate

Reads cached ProteinGym v1 ``Expression`` DMS substitution tables and AlphaFold DB structures
from ``build/abundance_calibration/raw``, joins Modal T4 ThermoMPNN scans from
``build/it4/track2-e1/thermompnn/<UNIPROT>.tsv``, writes ``scores.parquet``,
``evaluation.json``, ``manifest.json``, ``scores.provenance.json``, and renders
``figures/it6/abundance-calibration.svg``.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq

from mva.drugs import decision_avoid, decision_config, provenance
from mva.drugs.abundance_calibration import (
    BURIED_PLDDT_MIN,
    BURIED_RSA_MAX,
    CANDIDATE_ASSAYS,
    evaluate_calibration,
)
from mva.drugs.abundance_calibration_plot import render_svg
from mva.drugs.decision_io import expand_aliases, read_candidates, read_safety
from mva.drugs.unified_sensitivity import evaluate as evaluate_decision
from mva.drugs.variant_atlas import labelled_rows
from mva.drugs.variant_atlas_sources import alphafold_pdb, residues_from_pdb

RAW = Path("build/abundance_calibration/raw")
THERMO = Path("build/it4/track2-e1/thermompnn")
OUT = Path("ressources/track2/it6/abundance_calibration")
PROTOCOL = OUT / "protocol.md"
ATLAS = Path("ressources/track2/bub1b_atlas.parquet")
LABELS = Path("ressources/track2/bub1b_published_alleles.tsv")
FIG_SVG = Path("figures/it6/abundance-calibration.svg")
FIG_PROV = Path("figures/it6/abundance-calibration.provenance.json")


def _load_dms_single_mutants() -> dict[str, list[tuple[str, float, int]]]:
    shards = [
        pq.read_table(
            RAW / f"train-0000{i}-of-00005.parquet",
            columns=["DMS_id", "mutant", "DMS_score", "DMS_score_bin"],
        )
        for i in range(5)
    ]
    full_tbl = pa.concat_tables(shards).to_pydict()
    by_dms: dict[str, list[tuple[str, float, int]]] = {}
    for dms_id, mut, score, sbin in zip(
        full_tbl["DMS_id"],
        full_tbl["mutant"],
        full_tbl["DMS_score"],
        full_tbl["DMS_score_bin"],
        strict=True,
    ):
        if ":" not in mut:
            by_dms.setdefault(str(dms_id), []).append((str(mut), float(score), int(sbin)))
    return by_dms


def _build_scores_dataframe(by_dms: dict[str, list[tuple[str, float, int]]]) -> pl.DataFrame:
    records: list[dict[str, Any]] = []
    for spec in CANDIDATE_ASSAYS:
        pdb_path = alphafold_pdb(spec.uniprot, RAW / spec.uniprot)
        res_map = {r.position: r for r in residues_from_pdb(pdb_path.read_text())}
        tsv_path = THERMO / f"{spec.uniprot}.tsv"
        ddg_map: dict[tuple[int, str, str], float] = {}
        if tsv_path.exists():
            with tsv_path.open() as handle:
                for row in csv.DictReader(handle, delimiter="\t"):
                    ddg_map[(int(row["position"]), row["wt"], row["alt"])] = float(row["ddg"])

        for mut, score, sbin in by_dms.get(spec.dms_id, []):
            wt, pos, alt = mut[0], int(mut[1:-1]), mut[-1]
            r = res_map.get(pos)
            ddg = ddg_map.get((pos, wt, alt))
            if r is None or ddg is None:
                continue
            records.append(
                {
                    "dms_id": spec.dms_id,
                    "uniprot": spec.uniprot,
                    "gene": spec.gene,
                    "assay_kind": spec.assay_kind,
                    "intracellular_abundance": spec.intracellular_abundance,
                    "position": pos,
                    "wt": wt,
                    "alt": alt,
                    "change": mut,
                    "dms_score": score,
                    "dms_score_bin": sbin,
                    "y_low_abundance": 1 if sbin == 0 else 0,
                    "ddg": ddg,
                    "rsa": float(r.rsa),
                    "plddt": float(r.plddt),
                    "buried_high_conf": bool(
                        r.rsa < BURIED_RSA_MAX and r.plddt >= BURIED_PLDDT_MIN
                    ),
                }
            )
    return pl.DataFrame(records)


def _decision_consequences(cal: dict[str, Any]) -> dict[str, Any]:
    r_dir = Path("ressources/track2")
    config, raw = decision_config.load(r_dir / "it5/decision_config.json")
    rows, _ = expand_aliases(
        read_candidates(
            [
                r_dir / "it5/readthrough_candidates.tsv",
                r_dir / "it5/protein_candidates.tsv",
                r_dir / "it5/literature_candidates.tsv",
            ]
        ),
        raw.get("aliases", {}),
        raw.get("drop_evidence_kinds", []),
    )
    safety: dict[str, str] = {}
    for p in (
        r_dir / "candidate_safety.tsv",
        r_dir / "it4/candidate_safety.tsv",
        r_dir / "it5/candidate_safety.tsv",
    ):
        safety.update(read_safety(p))
    avoid = decision_avoid.build(raw["avoid"]) if raw.get("avoid") else []
    merged_safety = decision_avoid.merge(safety, avoid, config.safety)
    r5_cfg = decision_config.with_param(config, "route:R2", 0.25)

    priors = {
        "pre_calibration_weight_0_55": 0.55,
        "calibrated_point": float(cal["p_low_abundance"]),
        "calibrated_lopo_median": float(cal["lopo_median_p"]),
        "calibrated_ci95_low": float(cal["cluster_bootstrap_ci95"][0]),
        "calibrated_ci95_high": float(cal["cluster_bootstrap_ci95"][1]),
        "random_intercept_iqr_low": float(cal["random_intercept"]["empirical_iqr_p"][0]),
        "random_intercept_median": float(cal["random_intercept"]["empirical_median_p"]),
        "random_intercept_iqr_high": float(cal["random_intercept"]["empirical_iqr_p"][1]),
        "new_protein_pred_low": float(cal["random_intercept"]["new_protein_predictive_ci95"][0]),
        "new_protein_pred_high": float(cal["random_intercept"]["new_protein_predictive_ci95"][1]),
    }

    r5_runs: dict[str, Any] = {}
    r4_runs: dict[str, Any] = {}
    for label, p_val in priors.items():
        res_r5 = evaluate_decision(
            decision_config.with_param(r5_cfg, "prior:missense_class=unstable", p_val),
            rows,
            merged_safety,
        )
        res_r4 = evaluate_decision(
            decision_config.with_param(config, "prior:missense_class=unstable", p_val),
            rows,
            merged_safety,
        )
        for target_dict, res in ((r5_runs, res_r5), (r4_runs, res_r4)):
            target_dict[label] = {
                "p_unstable": round(p_val, 4),
                "best_action": res["best_action"],
                "eu_baseline": round(float(res["eu_baseline"]), 4),
                "evpi": round(float(res["evpi"]), 4),
                "evsi_blot": round(float(res["evsi_blot"]), 4),
                "evsi_share_of_evpi": round(float(res["evsi_share_of_evpi"]), 4),
                "positive_p_unstable": round(float(res["positive_p_unstable"]), 4),
                "negative_p_unstable": round(float(res["negative_p_unstable"]), 4),
                "positive_action": res["positive_action"],
                "negative_action": res["negative_action"],
                "assay_changes_recommendation": bool(res["assay_changes_recommendation"]),
            }
    return {
        "r5_hierarchy_calibrated": r5_runs,
        "r4_uncalibrated": r4_runs,
    }


def cmd_evaluate(_: argparse.Namespace) -> int:
    by_dms = _load_dms_single_mutants()
    scores_df = _build_scores_dataframe(by_dms)
    OUT.mkdir(parents=True, exist_ok=True)
    scores_path = OUT / "scores.parquet"
    scores_df.write_parquet(scores_path)

    atlas = pl.read_parquet(ATLAS)
    labelled_bub1b = labelled_rows(atlas, LABELS, "abundance-lowering", "stable", primary_only=True)
    report = evaluate_calibration(scores_df, labelled_bub1b)
    report["decision_model_consequence"] = _decision_consequences(report["calibration_at_1_55"])

    eval_path = OUT / "evaluation.json"
    eval_path.write_text(json.dumps(report, indent=2) + "\n")

    manifest_data = {
        "protocol": {"path": str(PROTOCOL), "sha256": provenance.digest(PROTOCOL)[0]},
        "thermompnn_version": "370f76ec62bd",
        "thermompnn_gpu": "T4",
        "surviving_proteins": [
            {
                "dms_id": p["dms_id"],
                "uniprot": p["uniprot"],
                "gene": p["gene"],
                "assay_kind": p["assay_kind"],
                "n_all": p["n_all"],
                "n_buried": p["n_buried"],
                "thermompnn_tsv_sha256": provenance.digest(THERMO / f"{p['uniprot']}.tsv")[0],
            }
            for p in report["per_protein"]
        ],
    }
    manifest_path = OUT / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_data, indent=2) + "\n")

    prov = provenance.envelope(
        "abundance_calibration", "tools/abundance_calibration.py evaluate"
    ) | {
        "protocol": {"path": str(PROTOCOL), "sha256": provenance.digest(PROTOCOL)[0]},
        "method": (
            "ThermoMPNN ΔΔG evaluated on 11 sequence-matched, split-disjoint ProteinGym v1 "
            "Expression DMS proteins within buried high-confidence residues (RSA < 0.20, "
            "pLDDT >= 90); protein-equally-weighted logistic calibration at +1.55 kcal/mol "
            "with LOPO cross-validation, cluster bootstrap, and random-intercept intervals."
        ),
        "inputs": [
            {
                "name": "Frozen calibration protocol",
                "path": str(PROTOCOL),
                "sha256": provenance.digest(PROTOCOL)[0],
                "role": "pre-registered selection rules, stratum, and endpoints",
            },
            {
                "name": "BUB1B variant atlas",
                "path": str(ATLAS),
                "sha256": provenance.digest(ATLAS)[0],
                "role": "zero-refit transfer target",
            },
            {
                "name": "BUB1B published allele labels",
                "path": str(LABELS),
                "sha256": provenance.digest(LABELS)[0],
                "role": "8 primary MVA alleles (PMID 20516114)",
            },
        ],
        "outputs": [
            provenance.output(scores_path, scores_df.height),
            provenance.output(eval_path, 1),
            provenance.output(manifest_path, 1),
        ],
        "patient_data": (
            "none: evaluates public DMS assays and the public reference value +1.55 kcal/mol."
        ),
    }
    provenance.write(prov, OUT / "scores.provenance.json")

    render_svg(report, FIG_SVG)
    fig_prov = provenance.envelope(
        "abundance_calibration_figure", "tools/abundance_calibration.py evaluate"
    ) | {
        "inputs": [
            {
                "name": "abundance calibration evaluation",
                "path": str(eval_path),
                "sha256": provenance.digest(eval_path)[0],
                "role": "per-protein buried AUROCs and logistic calibration curve",
            }
        ],
        "outputs": [provenance.output(FIG_SVG, 1)],
    }
    provenance.write(fig_prov, FIG_PROV)

    print(
        json.dumps(
            {
                "n_proteins": report["n_surviving_proteins"],
                "n_buried_variants": report["n_total_buried_variants"],
                "median_auroc_buried": report["summary_all_11_proteins"]["median_auroc_buried"],
                "ci95": report["summary_all_11_proteins"]["median_auroc_buried_ci95"],
                "p_low_at_1_55": report["calibration_at_1_55"]["p_low_abundance"],
                "p_ci95": report["calibration_at_1_55"]["cluster_bootstrap_ci95"],
                "lopo_median": report["calibration_at_1_55"]["lopo_median_p"],
                "new_protein_pred_ci95": report["calibration_at_1_55"]["random_intercept"][
                    "new_protein_predictive_ci95"
                ],
                "gate": report["gate"]["gate"],
            },
            indent=2,
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("evaluate")
    args = parser.parse_args(argv)
    if args.command == "evaluate":
        return cmd_evaluate(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
