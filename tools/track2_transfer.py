#!/usr/bin/env python3
"""Run the whole Track 2 pipeline, unchanged, on a **second case** — the scalability proof.

    uv run python tools/track2_transfer.py                 # cold pass: build, snapshot, enrich
    uv run python tools/track2_transfer.py --warm          # and a second, cache-warm pass
    uv run python tools/track2_transfer.py --card-only     # write the card, run nothing

``tools/track2_decoys.py`` swaps the *gene* and keeps the child: that measures specificity.
This swaps the *case* — a different disease with its own OMIM/MONDO identifiers, its own
phenotype annotation read out of ``phenotype.hpoa``, its own tumour and its own standard of
care — and measures **portability**: does the same code, with no edit and no hand-written
query, produce the same tables for a case it was never written for?

What the script does, in order:

1. read the committed spec (``ressources/track2/transfer/<SYMBOL>/transfer_spec.json``);
2. read that disease's HPO terms out of ``phenotype.hpoa``, skipping ``NOT``-qualified rows,
   and record the file's own ``#version`` line — the terms are **read, never typed**;
3. build the transfer card (:func:`mva.drugs.transfer.transfer_card`) beside the spec;
4. ``write_snapshot`` and then ``enrich.run`` into that folder, timed, exactly as for the
   real card — the enrichment finds no ``evidence.tsv`` and grades on the automated rungs;
5. write ``ressources/track2/transfer_comparison.tsv`` with a provenance manifest: one row
   per case, the real card's numbers read from its own committed ``snapshot.json`` and its
   ``analysis.json``, the transfer case's from the run that just happened.

**Only the automated rungs are comparable.** A transfer card has no curated literature, so
rungs 2 and 3 cannot appear for it at all; the table prints ``curated_rows`` beside every
count so that boundary is visible rather than implied. No genomic position exists in any
input or output: cards, gene symbols, drug names, trial ids, counts.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mva.drugs import enrich, provenance, tables, transfer
from mva.drugs.mechanism import DEFAULT_CARD, load
from mva.drugs.snapshot import DEFAULT_OUT_DIR, write_snapshot

DEFAULT_SPEC = Path("ressources/track2/transfer/TRIP13/transfer_spec.json")
DEFAULT_HPOA = Path("build/reference-scratch/phenotype.hpoa")
DEFAULT_COMPARISON = Path("ressources/track2/transfer_comparison.tsv")
DEFAULT_REAL_ANALYSIS = Path("build/track2/analysis.json")
BUILT_BY = "tools/track2_transfer.py"

#: The manifest's ``method``. Formatted with the annotation release actually read, so the
#: sentence can never claim a version the run did not use.
METHOD = (
    "One row per case. The transfer case's card is built by mva.drugs.transfer.transfer_card "
    "from the committed spec plus the HPO terms for its OMIM id read out of phenotype.hpoa "
    "(release {version}; rows whose qualifier column is NOT are skipped). The same "
    "mva-drugs snapshot and mva.drugs.enrich.run then execute on it with no code change and "
    "no hand-written query. Counts are read back from each case's snapshot.json (targets, "
    "candidate rows, distinct approved drugs, per-source request counts) and its enrichment "
    "analysis (drugs at each best rung, shortlist and do-not row counts, per-source request "
    "counts); cached_replies is replies minus live, summed over both stages. wall_seconds is "
    "the measured snapshot+enrichment wall clock of the pass this table was written from, and "
    "is empty for a case this run did not execute. Only the automated rungs (1, 4, 5) are "
    "comparable: rungs 2 and 3 come from a hand-curated evidence.tsv that a transfer card "
    "does not have, which is what curated_rows records."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--hpoa", type=Path, default=DEFAULT_HPOA)
    parser.add_argument("--template", type=Path, default=DEFAULT_CARD)
    parser.add_argument("--out-dir", type=Path, default=None, help="default: the spec's folder")
    parser.add_argument("--real-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--real-analysis", type=Path, default=DEFAULT_REAL_ANALYSIS)
    parser.add_argument("--comparison", type=Path, default=DEFAULT_COMPARISON)
    parser.add_argument("--analysis", type=Path, default=None, help="default: under build/track2")
    parser.add_argument("--refresh", action="store_true", help="bypass the HTTP cache")
    parser.add_argument(
        "--warm",
        action="store_true",
        help="run the whole pipeline a second time on the warm cache and report both costs",
    )
    parser.add_argument("--card-only", action="store_true", help="write the card, run nothing")
    return parser.parse_args()


def build_card(args: argparse.Namespace) -> tuple[Path, transfer.HpoAnnotation, Path]:
    """Write the transfer card from the spec and the public annotation. Returns its path."""
    template = load(args.template)
    spec = transfer.load_spec(args.spec)
    annotation = transfer.hpo_annotation(args.hpoa, spec.disease_id)
    print(f"phenotype  {annotation.provenance}")
    card = transfer.transfer_card(template, spec.with_phenotype(annotation))
    out_dir = args.out_dir or Path(args.spec).parent
    out_dir.mkdir(parents=True, exist_ok=True)
    card_path = out_dir / "mechanism.json"
    card_path.write_text(json.dumps(card, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {card_path}  ({len(card['case']['hpo_terms'])} HPO terms, 0 alleles)")
    return card_path, annotation, out_dir


def one_pass(card_path: Path, out_dir: Path, analysis_path: Path, *, refresh: bool, label: str):
    """Snapshot then enrich, each timed. Returns ``(snapshot index, analysis, seconds)``."""
    print(f"\n=== {label} pass: snapshot ===")
    started = time.monotonic()
    snapshot = write_snapshot(card_path, out_dir, refresh=refresh, progress=print)
    snapshot_s = time.monotonic() - started
    print(f"\n=== {label} pass: enrichment ===")
    mark = time.monotonic()
    result = enrich.run(
        card_path, out_dir, analysis_path=analysis_path, refresh=refresh, progress=print
    )
    enrich_s = time.monotonic() - mark
    live, cached = transfer.request_totals(
        snapshot.counts.get("requests"), result.analysis.get("requests")
    )
    print(
        f"\n{label:<5} snapshot {snapshot_s:7.1f}s · enrichment {enrich_s:7.1f}s · "
        f"total {snapshot_s + enrich_s:7.1f}s · live requests {live:,} · cached replies {cached:,}"
    )
    return snapshot.counts, result.analysis, snapshot_s + enrich_s


def _read_json(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _curated_rows(folder: Path) -> int:
    return len(enrich.read_optional_tsv(folder / "evidence.tsv"))


def _manifest_inputs(paths: list[Path]) -> list[dict[str, Any]]:
    """One input row per **committed** file the table rests on, with its digest."""
    rows = []
    for path in paths:
        if not path.is_file():
            continue
        sha, size = provenance.digest(path)
        rows.append(
            {
                "name": provenance.repo_relative(path),
                "path": provenance.repo_relative(path),
                "sha256": sha,
                "bytes": size,
            }
        )
    return rows


def write_comparison(
    args: argparse.Namespace,
    out_dir: Path,
    annotation: transfer.HpoAnnotation,
    runs: list[transfer.CaseRun],
) -> None:
    """The comparison table and its manifest. Inputs are committed files only."""
    rows = transfer.comparison_rows(runs)
    written = tables.write_tsv(args.comparison, tables.TRANSFER_COMPARISON_COLUMNS, rows)
    inputs = _manifest_inputs(
        [
            Path(args.spec),
            out_dir / "mechanism.json",
            out_dir / "snapshot.json",
            out_dir / "evidence_ladder.tsv",
            out_dir / "shortlist.tsv",
            out_dir / "do_not.tsv",
            Path(args.template),
            args.real_dir / "snapshot.json",
            args.real_dir / "evidence_ladder.tsv",
            args.real_dir / "shortlist.tsv",
            args.real_dir / "do_not.tsv",
        ]
    )
    manifest = provenance.envelope("transfer_comparison", BUILT_BY) | {
        "method": METHOD.format(version=annotation.version),
        "cases": [{"case": row["case"], "role": row["role"], "gene": row["gene"]} for row in rows],
        "inputs": inputs,
        "outputs": [provenance.output(args.comparison, written)],
        "known_gap": (
            "the two enrichment analyses this table reads its rung counts, request counts and "
            "wall clock from live under build/ and are not committed: "
            f"{provenance.repo_relative(args.real_analysis)} and "
            f"{provenance.repo_relative(Path(args.analysis))}. Every count in them is "
            "reproducible from the committed tables named above by re-running "
            "`uv run python tools/track2_enrich.py --skip-live` per folder; the wall clock is "
            "a measurement of one machine on one day and is not reproducible by construction. "
            "The HPO annotation the transfer card's clinical terms were read from "
            f"({annotation.source}, release {annotation.version}) is a downloaded public "
            "reference under build/ as well; the card records the release it was read at."
        ),
        "patient_data": (
            "none, on either row. The transfer case is public annotation (OMIM, MONDO, HPO, "
            "PubMed) and asserts no allele in any person; the real case's row carries counts "
            "only. No genomic position appears in any column by construction."
        ),
    }
    provenance.write(manifest, args.comparison.with_suffix(".provenance.json"))
    print(f"\nwrote {args.comparison}  {written} row(s)")
    header = tables.TRANSFER_COMPARISON_COLUMNS
    print("\t".join(header))
    for row in rows:
        print("\t".join(tables.cell(row.get(name)) for name in header))


def main() -> int:
    args = parse_args()
    card_path, annotation, out_dir = build_card(args)
    if args.card_only:
        return 0
    args.analysis = args.analysis or Path(f"build/track2/transfer-{out_dir.name}-analysis.json")

    snapshot, analysis, cold_s = one_pass(
        card_path, out_dir, args.analysis, refresh=args.refresh, label="cold"
    )
    wall = cold_s
    if args.warm:
        snapshot, analysis, warm_s = one_pass(
            card_path, out_dir, args.analysis, refresh=False, label="warm"
        )
        print(f"\ncold {cold_s:.1f}s → warm {warm_s:.1f}s")
        wall = warm_s

    real = transfer.CaseRun(
        label="BUB1B / MVA1 (the proband)",
        role="real case",
        snapshot=_read_json(args.real_dir / "snapshot.json"),
        analysis=_read_json(args.real_analysis),
        curated_rows=_curated_rows(args.real_dir),
    )
    moved = transfer.CaseRun(
        label=f"{out_dir.name} / {annotation.disease_name}",
        role="transfer case",
        snapshot=snapshot,
        analysis=analysis,
        curated_rows=_curated_rows(out_dir),
        wall_seconds=wall,
    )
    write_comparison(args, out_dir, annotation, [real, moved])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
