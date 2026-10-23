#!/usr/bin/env python3
"""ESM-2 model-generation check: assemble the Modal scan, evaluate it, place the child locally.

Frozen protocol: ``ressources/track2/it6/esm2_check/protocol.md``. The scan itself runs on
Modal (``src/mva/zoo/modal_apps/esm2.py``) through ``tools/modal_trace.py run esm2 full`` and
leaves ``build/it6/esm2/chunk-*.json``.

    uv run python tools/esm2_check.py evaluate      # public table + evaluation.json
    uv run python tools/esm2_check.py place         # build/it6/esm2/child.json only

``evaluate`` reads only public inputs. ``place`` is the one step that reads the case, and it
writes under ``build/`` alone.
"""

from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path
from typing import Any

import polars as pl

from mva.drugs import provenance
from mva.drugs.esm2_check import (
    CONTEXT,
    DOMAIN,
    HIGH_DAMAGE_PERCENTILE,
    evaluate,
    jobs,
    score_table,
    window_shift,
)
from mva.drugs.variant_atlas import labelled_rows, parse_change
from mva.drugs.variant_atlas_model import percentile_rank

RAW = Path("build/it6/esm2")
FASTA = RAW / "O60566.fasta"
OUT = Path("ressources/track2/it6/esm2_check")
ATLAS = Path("ressources/track2/bub1b_atlas.parquet")
LABELS = Path("ressources/track2/bub1b_published_alleles.tsv")
PROTOCOL = OUT / "protocol.md"
POSITIVE, NEGATIVE = "abundance-lowering", "stable"
STEP = 1 / 15


def _sequence() -> str:
    lines = FASTA.read_text().splitlines()
    return "".join(line.strip() for line in lines if not line.startswith(">"))


def _scan() -> tuple[dict[tuple[int, int], list[float]], dict[str, Any]]:
    chunks = sorted(RAW.glob("chunk-*.json"))
    if not chunks:
        raise SystemExit("no chunks: run tools/modal_trace.py run esm2 full first")
    probs: dict[tuple[int, int], list[float]] = {}
    meta: dict[str, Any] = {"seconds": 0.0, "chunks": len(chunks)}
    for path in chunks:
        reply = json.loads(path.read_text())
        meta |= {k: reply[k] for k in ("version", "digest", "gpu", "context")}
        meta["seconds"] += reply["seconds"]
        for start, site, vec in reply["rows"]:
            probs[(start, site)] = vec
    return probs, meta


def _gate(primary: dict[str, Any]) -> dict[str, Any]:
    esm2 = primary["predictors"]["esm2_damage"]
    strong = esm2["auroc"] >= 14 * STEP - 1e-9 and esm2["exact_tail"] <= 0.05
    shifts = [abs(v - esm2["auroc"]) for v in primary["window_auroc"].values()]
    stable = all(s <= STEP + 1e-9 for s in shifts)
    if strong and stable:
        verdict = "strong reference discrimination (exploratory; class floor still unmet)"
    elif strong:
        verdict = "strong but context-dependent: fragile, backup only"
    elif esm2["auroc"] > 0.6:
        verdict = "partial discrimination below the inclusion gate: report, not pitch"
    else:
        verdict = "weak/null discrimination: transparent negative result, report only"
    rule = "strong = AUROC >= 14/15 and exact one-sided tail <= 0.05 (protocol)"
    return {"strong": strong, "window_stable": stable, "verdict": verdict, "rule": rule}


def cmd_evaluate(_: argparse.Namespace) -> int:
    seq = _sequence()
    atlas = pl.read_parquet(ATLAS)
    reference = "".join(atlas.unique("position").sort("position")["wt"].to_list())
    if reference != seq:
        raise SystemExit("UniProt sequence differs from the atlas reference")
    probs, meta = _scan()
    missing = set(jobs(len(seq), CONTEXT)) - set(probs)
    if missing:
        raise SystemExit(f"{len(missing)} planned jobs missing: the scan is incomplete")
    table = score_table(seq, probs)
    table = table.join(atlas.select("change", "region"), on="change", how="left")
    OUT.mkdir(parents=True, exist_ok=True)
    scores = OUT / "esm2_scores.parquet"
    table.write_parquet(scores)
    report: dict[str, Any] = {"protocol": str(PROTOCOL), "model": meta, "sets": {}}
    for name, primary_only in (("primary", True), ("extended", False)):
        labelled = labelled_rows(atlas, LABELS, POSITIVE, NEGATIVE, primary_only)
        report["sets"][name] = evaluate(labelled, table)
    domain = table.filter(pl.col("position").is_between(*DOMAIN))
    labelled_changes = [a["change"] for a in report["sets"]["extended"]["alleles"]]
    report["window_sensitivity"] = {
        "labelled": window_shift(table, labelled_changes),
        "pseudokinase_domain": window_shift(domain),
        "all": window_shift(table),
    }
    report["correlation_with_comparators"] = {
        name: float(
            table.join(atlas.select("change", col), on="change")
            .select(pl.corr("damage", col, method="spearman") * sign)
            .item()
        )
        for name, col, sign in (
            ("thermompnn_ddg", "ddg", 1),
            ("esm1b_llr_negated", "esm1b_llr", -1),
        )
    }
    report["gate"] = _gate(report["sets"]["primary"])
    evaluation = OUT / "evaluation.json"
    evaluation.write_text(json.dumps(report, indent=2) + "\n")
    protocol_sha = provenance.digest(PROTOCOL)[0]
    manifest = provenance.envelope("esm2_scores", "tools/esm2_check.py evaluate") | {
        "protocol": {"path": str(PROTOCOL), "sha256": protocol_sha},
        "method": (
            "ESM-2 650M masked marginals: llr = log P(alt) - log P(wt) at the masked site, "
            "damage = -llr. Primary window: 1,022 residues, site-centred, terminal-clamped; "
            "damage_n / damage_c: fixed windows 1-1022 and 29-1050."
        ),
        "inputs": [
            {
                "name": "UniProtKB O60566 canonical FASTA",
                "url": "https://rest.uniprot.org/uniprotkb/O60566.fasta",
                "path": str(FASTA),
                "sha256": provenance.digest(FASTA)[0],
                "role": "sequence (checked equal to the atlas reference)",
            },
            {
                "name": "ESM-2 650M",
                "url": "https://huggingface.co/facebook/esm2_t33_650M_UR50D",
                "version": meta["version"],
                "weights_digest": meta["digest"],
                "gpu": meta["gpu"],
                "gpu_seconds": round(meta["seconds"], 1),
                "role": "masked-marginal log-probs",
            },
            {
                "name": "published allele labels",
                "path": str(LABELS),
                "sha256": provenance.digest(LABELS)[0],
                "role": "evaluation labels (PMID 20516114)",
            },
            {
                "name": "variant atlas",
                "path": str(ATLAS),
                "sha256": provenance.digest(ATLAS)[0],
                "role": "ThermoMPNN ddg and ESM1b comparators; region",
            },
        ],
        "outputs": [provenance.output(scores, table.height), provenance.output(evaluation, 1)],
        "patient_data": "none: every row is a possible substitution of the public protein.",
    }
    provenance.write(manifest, OUT / "esm2_scores.provenance.json")
    for name, result in report["sets"].items():
        line = {"set": name, "n": [result["n_positive"], result["n_negative"]]}
        line |= {k: round(v["auroc"], 3) for k, v in result["predictors"].items()}
        line["esm2_tail"] = round(result["predictors"]["esm2_damage"]["exact_tail"], 4)
        print(json.dumps(line))
    print(json.dumps(report["gate"]))
    return 0


def cmd_place(args: argparse.Namespace) -> int:
    out = RAW / "child.json"
    case = tomllib.loads(args.case.read_text())["case"]
    records = pl.read_parquet(args.records, columns=["gene", "consequence", "hgvs_p"])
    hits = records.filter(
        (pl.col("gene") == case["confirmed_gene"])
        & pl.col("consequence").str.contains("missense_variant")
    )
    if hits.height != 1:
        raise SystemExit(f"expected one missense record, found {hits.height}")
    change = parse_change(str(hits["hgvs_p"][0]))
    if change is None:
        raise SystemExit("unparseable hgvs_p")
    table = pl.read_parquet(OUT / "esm2_scores.parquet")
    key = f"{change.wt}{change.position}{change.alt}"
    row = table.filter(pl.col("change") == key)
    if row.height != 1:
        raise SystemExit(f"{key}: not a single row (reference mismatch?)")
    r = row.row(0, named=True)
    domain = table.filter(pl.col("position").is_between(*DOMAIN))
    pct = percentile_rank(table["damage"].to_list(), r["damage"])
    placed = {
        "change": key,
        "damage": r["damage"], "damage_n": r["damage_n"], "damage_c": r["damage_c"],
        "percentile_all": pct,
        "percentile_domain": percentile_rank(domain["damage"].to_list(), r["damage"]),
        "percentile_all_n": percentile_rank(table["damage_n"].drop_nulls().to_list(), r["damage_n"])
        if r["damage_n"] is not None else None,
        "percentile_all_c": percentile_rank(table["damage_c"].drop_nulls().to_list(), r["damage_c"])
        if r["damage_c"] is not None else None,
        "high_damage": pct >= HIGH_DAMAGE_PERCENTILE,
    }  # fmt: skip
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(placed, indent=2) + "\n")
    print(json.dumps({k: v for k, v in placed.items() if k != "change"}, indent=1))
    print(f"wrote {out} (build/ only: names the substitution)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("evaluate")
    place = sub.add_parser("place")
    place.add_argument("--case", type=Path, default=Path("src/mva/zoo/zoo.example.toml"))
    place.add_argument("--records", type=Path, default=Path("build/it4/records.parquet"))
    args = parser.parse_args(argv)
    return {"evaluate": cmd_evaluate, "place": cmd_place}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
