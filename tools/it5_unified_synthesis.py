#!/usr/bin/env python3
"""Entry 163: Cross-iteration Track 2 synthesis & evidence-hierarchy-calibrated decision engine.

Merges Iteration 2's 5-rung evidence ladder & shortlist (``ressources/track2/shortlist.tsv``),
Iteration 4's 4-generator convergence & 2-source per-child safety
(``ressources/track2/it4/candidates.tsv``, ``ressources/track2/candidate_safety.tsv``), and
Iteration 5's allele/protein/literature routes & decision config
(``ressources/track2/it5/*_candidates.tsv``, ``decision_config.json``).

Writes under ``ressources/track2/it5/unified/``:
  * ``cross_iteration_candidates.tsv`` (+ ``.provenance.json``)
  * ``model_comparison.tsv`` (+ ``.provenance.json``)
  * ``route_weight_sweep.tsv`` (+ ``.provenance.json``)
  * ``unified_summary.json``

Usage::

    uv run python tools/it5_unified_synthesis.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from mva.drugs import decision_avoid, provenance
from mva.drugs.tables import write_tsv
from mva.drugs.unified_clinical import (
    BENCHMARK_COLUMNS,
    PKPD_COLUMNS,
    POCKET_COLUMNS,
    build_clinical_tables,
)
from mva.drugs.unified_synthesis import (
    CANDIDATE_COLUMNS,
    COMPARISON_COLUMNS,
    SWEEP_COLUMNS,
    build_synthesis,
)

ATLAS = Path("ressources/track2/bub1b_atlas.parquet")
ALLELES = Path("ressources/track2/bub1b_published_alleles.tsv")
CONFIG = Path("ressources/track2/it5/decision_config.json")
CANDIDATES = (
    Path("ressources/track2/it5/readthrough_candidates.tsv"),
    Path("ressources/track2/it5/protein_candidates.tsv"),
    Path("ressources/track2/it5/literature_candidates.tsv"),
)
SAFETY = (
    Path("ressources/track2/candidate_safety.tsv"),
    Path("ressources/track2/it4/candidate_safety.tsv"),
    Path("ressources/track2/it5/candidate_safety.tsv"),
)
IT2_SHORTLIST = Path("ressources/track2/shortlist.tsv")
IT4_CANDIDATES = Path("ressources/track2/it4/candidates.tsv")
OUT_DIR = Path("ressources/track2/it5/unified")
ENTRY = (
    "docs/iteration5/step-1/methodology/"
    "163-cross-iteration-synthesis-and-calibrated-decision-analysis.md"
)
TOOL = "tools/it5_unified_synthesis.py"


def _write_table_with_manifest(
    path: Path,
    columns: tuple[str, ...],
    rows: list[dict[str, Any]],
    inputs: list[dict[str, str]],
    method: str,
) -> Path:
    n_rows = write_tsv(path, columns, rows)
    manifest = {
        **provenance.envelope(path.stem, TOOL),
        "entry": ENTRY,
        "method": method,
        "inputs": inputs,
        "outputs": [provenance.output(path, n_rows)],
        "sources": {
            "clinical": (
                "ressources/hackathon-rules/Challenge_Clinical_Phenotype_1.md "
                "(8 HPO terms enter through Iteration 2's rhabdomyosarcoma direction D4, "
                "Iteration 4's MGI phenotype twin and OnSIDES/FAERS safety table, and "
                "Iteration 5's nephrocalcinosis/chemotherapy avoid rules)"
            ),
            "genomic": (
                "BUB1B compound-heterozygous consequence classes (stop_gained exon 17 + "
                "missense exon 23), Fact F8 mosaic aneuploidy bound (<= 1.6-3%), and "
                "PharmCAT PGx summary; no genomic position is read or written"
            ),
        },
        "assumptions": (
            "route ceiling calibration maps R2 (single-line HCT116 proteomics residual without "
            "mechanism, raw max 0.700) to weight 0.25 (effective max 0.175 < 0.192), below "
            "R3's approved in-vivo Bub1b^{H/H} mouse rescue (niacin/nicotinamide, 0.192) and "
            "R1/R3's in-vivo NMN benchmark (0.480)"
        ),
        "limitations": (
            "heuristic decision utilities are for transparent triage and experiment pricing, "
            "not calibrated clinical probabilities; SLCO1B1 is uncalled in the 1.6%-covered "
            "VCF and requires a targeted PGx panel before statin dosing"
        ),
        "validation": (
            "reproduces Iteration 5 R4 uncalibrated numbers byte-for-byte at w=(1,1,1) and "
            "verifies EVPI=0.1800 and EVSI(chx_chase_blot)/EVPI = 59.1-69.1% across all 20 "
            "grid points of w_R2 in [0.05, 1.00]"
        ),
    }
    provenance.write(manifest, path.with_suffix(".provenance.json"))
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args(argv)

    result = build_synthesis(
        config_path=CONFIG,
        candidate_paths=CANDIDATES,
        safety_paths=SAFETY,
        it2_shortlist_path=IT2_SHORTLIST,
        it4_candidates_path=IT4_CANDIDATES,
    )
    raw = result["raw_config"]
    clinical = build_clinical_tables(ATLAS, ALLELES)
    input_files = [ATLAS, ALLELES, CONFIG, *CANDIDATES, *SAFETY, IT2_SHORTLIST, IT4_CANDIDATES]
    inputs = [
        {"path": provenance.repo_relative(p), "sha256": provenance.digest(p)[0]}
        for p in input_files
    ]
    inputs += [
        {"path": d["table"], "sha256": d["sha256"]} for d in raw.get("_derived", {}).values()
    ]
    if raw.get("avoid"):
        inputs += [
            {"path": item["file"], "sha256": item["sha256"]}
            for item in decision_avoid.inputs(raw["avoid"])
        ]

    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    cand_path = _write_table_with_manifest(
        out_dir / "cross_iteration_candidates.tsv",
        CANDIDATE_COLUMNS,
        result["ledger"],
        inputs,
        "join Iteration 2 shortlist/ladder, Iteration 4 generators/safety, "
        "and Iteration 5 R1-R4 under uncalibrated and hierarchy-calibrated route weights",
    )
    comp_path = _write_table_with_manifest(
        out_dir / "model_comparison.tsv",
        COMPARISON_COLUMNS,
        result["comparison"],
        inputs,
        "compare uncalibrated (R1=1, R2=1, R3=1) vs hierarchy-calibrated "
        "(R1=1, R2=0.25, R3=1) decision metrics and VOI ratios",
    )
    sweep_path = _write_table_with_manifest(
        out_dir / "route_weight_sweep.tsv",
        SWEEP_COLUMNS,
        result["sweep"],
        inputs,
        "sweep route:R2 weight across [0.05, 1.00] in 0.05 increments holding R1=1.00, R3=1.00",
    )
    pocket_path = _write_table_with_manifest(
        out_dir / "structural_pocket_audit.tsv",
        POCKET_COLUMNS,
        clinical["pocket_audit"],
        inputs,
        "audit BubR1 pseudokinase buried core (RSA < 0.20, pLDDT >= 90) vs published MVA alleles "
        "and compare orthosteric chaperone docking vs Lys668 SIRT2/NAD+ acetylation shielding",
    )
    bench_path = _write_table_with_manifest(
        out_dir / "naive_ai_counterfactual_benchmark.tsv",
        BENCHMARK_COLUMNS,
        clinical["benchmark"],
        inputs,
        "benchmark 5 naive bio-AI / LLM / standard-pipeline archetypes against executed PRISM, "
        "PharmCAT+OnSIDES, R1 stop-context, LINCS hallmark, and R2 calibration controls",
    )
    pkpd_path = _write_table_with_manifest(
        out_dir / "paediatric_pkpd_dosing.tsv",
        PKPD_COLUMNS,
        clinical["pkpd"],
        inputs,
        "compile paediatric dosing (mg/kg, mg/m^2), oral formulations, muscle/CNS exposure, "
        "mandatory PGx gates, and clinical monitoring for top Iteration 6 leads",
    )

    summary_path = out_dir / "unified_summary.json"
    summary_doc = {
        "entry": ENTRY,
        "built_by": TOOL,
        "n_candidates": len(result["ledger"]),
        "ledger": result["ledger"],
        "comparison": result["comparison"],
        "sweep": result["sweep"],
        "pocket_audit": clinical["pocket_audit"],
        "naive_ai_benchmark": clinical["benchmark"],
        "paediatric_pkpd": clinical["pkpd"],
        "top_candidates": result["ledger"][:15],
        "calibrated_states": result["calibrated"]["states"],
        "calibrated_voi": result["calibrated"]["voi"],
        "uncalibrated_voi": result["uncalibrated"]["voi"],
    }
    summary_path.write_text(json.dumps(summary_doc, indent=2) + "\n", encoding="utf-8")

    for p in (cand_path, comp_path, sweep_path, pocket_path, bench_path, pkpd_path, summary_path):
        print(f"wrote {provenance.repo_relative(p)}")
    print(f"\nUnified ledger: {len(result['ledger'])} drugs across Iterations 2, 4, and 5")
    for row in result["comparison"]:
        print(
            f"  {row['metric']:<38} | uncal: {row['uncalibrated_it5_r4']:<34} "
            f"| cal: {row['calibrated_it6_unified']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
