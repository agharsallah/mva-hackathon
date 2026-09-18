#!/usr/bin/env python3
"""Ask gnomAD whether the leading pairs travel on the same chromosome copy or on opposite ones.

The step's goal has two halves. The first — which biallelic pair has the highest posterior —
is answered by ``tools/rank_it2_pairs.py``. This is the second: **what is its P(trans)?**

Phase cannot be measured for this case. No fragment spans the lead pair (step 2, entry 088:
10,911 bases against ~266-base fragments) and no parental DNA exists. What remains is the
population statistic Guo 2024 derived and gnomAD serves: over everyone in the reference
cohort who carries both variants, how the genotype combinations fall tells you how often
the two travel together.

Three honest outcomes, all pre-registered:

``observed``       gnomAD returned a probability for this exact pair
``undetermined``   at least one allele is not in gnomAD v2 — the expected state for an
                   ultra-rare disease allele — so the uninformative prior is reported and
                   labelled, never zero and never silently 1
``same-site``      two ALT alleles of one position, which is trans by construction

Every reply is cached under ``--out/ptrans/`` with the query that produced it, so the run
reproduces without a network.

Usage::

    uv run python tools/lookup_it2_ptrans.py --top 25
    uv run python tools/lookup_it2_ptrans.py --offline     # prior only, no requests
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mva.pipeline.ptrans import (
    DATASET,
    UNINFORMATIVE_PRIOR,
    GnomadCooccurrence,
    TransEstimate,
    base_rate,
    estimate,
)

DEFAULT_OUT = Path("build/it2/step-4")

COLUMNS = [
    "gene",
    "shape",
    "phase",
    "rank",
    "combined_lr",
    "p_trans",
    "state",
    "left_rsid",
    "right_rsid",
    "left_id",
    "right_id",
    "source",
    "note",
]


def leading_pairs(path: Path, limit: int) -> list[dict]:
    """The top compound hypotheses by likelihood ratio, best gene first, one per gene."""
    rows = []
    seen: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        header = handle.readline().rstrip("\n").split("\t")
        for line in handle:
            row = dict(zip(header, line.rstrip("\n").split("\t"), strict=False))
            if row.get("shape") != "compound" or row["gene"] in seen:
                continue
            seen.add(row["gene"])
            rows.append(row)
            if len(rows) >= limit:
                break
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--top", type=int, default=25, help="how many leading genes to ask about")
    parser.add_argument("--offline", action="store_true", help="report the prior, make no request")
    args = parser.parse_args(argv)

    pairs_table = args.out / "tables" / "it2_lr_pairs.tsv"
    if not pairs_table.is_file():
        print(f"no ranking to read: {pairs_table} is absent — run tools/rank_it2_pairs.py first")
        return 1

    rows = leading_pairs(pairs_table, args.top)
    cache = args.out / "ptrans"
    cache.mkdir(parents=True, exist_ok=True)

    lookup = None if args.offline else GnomadCooccurrence()
    estimates: list[TransEstimate] = []
    out: list[dict] = []
    try:
        for index, row in enumerate(rows, start=1):
            found = estimate(
                lookup,
                left_rsid=row.get("left_rsid", ""),
                right_rsid=row.get("right_rsid", ""),
                same_site=False,
            )
            estimates.append(found)
            out.append(
                {
                    "gene": row["gene"],
                    "shape": row["shape"],
                    "phase": row["phase"],
                    "rank": index,
                    "combined_lr": row["combined_lr"],
                    "p_trans": f"{found.p_trans:.6g}",
                    "state": found.state.value,
                    "left_rsid": row.get("left_rsid", ""),
                    "right_rsid": row.get("right_rsid", ""),
                    "left_id": found.left_id,
                    "right_id": found.right_id,
                    "source": found.source,
                    "note": found.note,
                }
            )
            (cache / f"{index:03d}-{row['gene']}.json").write_text(
                json.dumps(
                    {
                        "gene": row["gene"],
                        "dataset": DATASET,
                        "left_rsid": row.get("left_rsid", ""),
                        "right_rsid": row.get("right_rsid", ""),
                        "state": found.state.value,
                        "p_trans": found.p_trans,
                        "left_id": found.left_id,
                        "right_id": found.right_id,
                        "note": found.note,
                        "caveat": found.caveat,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
    finally:
        if lookup is not None:
            lookup.close()

    table = args.out / "tables" / "it2_ptrans.tsv"
    table.parent.mkdir(parents=True, exist_ok=True)
    with table.open("w", encoding="utf-8") as handle:
        handle.write("\t".join(COLUMNS) + "\n")
        for row in out:
            handle.write("\t".join(str(row[column]) for column in COLUMNS) + "\n")

    states: dict[str, int] = {}
    for item in estimates:
        states[item.state.value] = states.get(item.state.value, 0) + 1
    with_rsid = sum(1 for row in out for key in ("left_rsid", "right_rsid") if row[key])
    resolved = sum(1 for row in out for key in ("left_id", "right_id") if row[key])
    summary = {
        "dataset": DATASET,
        "offline": args.offline,
        "pairs": len(out),
        "states": states,
        # The only bridge from a GRCh38 allele to gnomAD v2 (GRCh37) is the dbSNP
        # identifier, so an allele with no rsID is undetermined before any request is made.
        # Reported as a coverage number rather than described as a caveat.
        "alleles": 2 * len(out),
        "alleles_with_rsid": with_rsid,
        "alleles_resolved_in_dataset": resolved,
        "prior": UNINFORMATIVE_PRIOR,
        "empirical_base_rate": base_rate(estimates),
        "requests": getattr(lookup, "requests", 0),
        "lead": out[0] if out else None,
    }
    (args.out / "ptrans.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, default=str))
    print(f"wrote {table}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
