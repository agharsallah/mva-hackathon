#!/usr/bin/env python3
"""Per-gene bait density after the uniqueness filter — what the off-target gate proxies for.

The gate in ``plan.md`` §4b is "off-target k-mers < 5 % of bait". That number is a
genome-wide average, and an average is the wrong instrument for the risk it stands in for:
the risk is not that 9 % of k-mers are repetitive, it is that **some particular gene** is
so repetitive that the bait cannot reach it, and a later "no second allele here" would
then be a statement about the reference rather than about the child.

So this asks the question the gate was asking, per gene and per tier: how many bait k-mers
survive, how dense are they per base, and which genes fall so far below the rest that step
2 must not claim coverage of them.

Reads ``bait.npy`` (already filtered) and re-cuts each gene's intervals to see which of its
windows are in it. One reference pass.

Usage::

    uv run python tools/profile_it2_bait.py
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mva.kmer import regions
from mva.kmer.bait import profile
from mva.kmer.membership import Bait

DEFAULT_STEP1 = Path("build/it2/step-1")
DEFAULT_OUT = Path("build/it2/step-2")
DEFAULT_CODING = Path("ressources/reference/coding_regions.tsv")
DEFAULT_REFERENCE = Path("build/reference/GRCh38.fa")

#: Tiers that carry the wide padding — kept in step with tools/build_it2_bait.py.
WIDE_TIERS = ("core", "mechanism-term")

#: Genes below this share of the median density are reported as unreachable-by-bait.
SPARSE_FRACTION = 0.5


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step1", type=Path, default=DEFAULT_STEP1)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--coding", type=Path, default=DEFAULT_CODING)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--k", type=int, default=31)
    parser.add_argument("--core-pad", type=int, default=50_000)
    parser.add_argument("--net-pad", type=int, default=2_000)
    args = parser.parse_args(argv)

    tier_of = regions.read_tiers(
        [(args.step1 / "targets.tsv", None), (args.step1 / "decoys.tsv", "decoy")]
    )
    by_gene = regions.read_gene_model(args.coding)
    labelled = regions.padded_by_gene(
        tier_of,
        by_gene,
        wide_tiers=WIDE_TIERS,
        wide_pad=args.core_pad,
        narrow_pad=args.net_pad,
    )

    bait = Bait.load(args.out / "bait.npy", k=args.k)
    print(f"{len(bait):,} surviving bait k-mers; profiling {len(labelled)} genes")
    coverage = profile(args.reference, bait, labelled, k=args.k)

    rows = sorted(coverage.values(), key=lambda c: c.density)
    densities = [c.density for c in rows if c.windows]
    median = densities[len(densities) // 2] if densities else 0.0
    sparse = [c for c in rows if c.windows and c.density < median * SPARSE_FRACTION]

    per_tier: dict[str, list[int]] = {}
    for symbol, cover in coverage.items():
        bucket = per_tier.setdefault(tier_of[symbol], [0, 0, 0])
        bucket[0] += cover.bases
        bucket[1] += cover.windows
        bucket[2] += cover.surviving

    print(f"\n{'tier':>16} {'bases':>14} {'windows':>14} {'surviving':>14} {'lost':>7}")
    for tier, (bases, windows, surviving) in sorted(per_tier.items()):
        lost = 1 - surviving / windows if windows else 0
        print(f"{tier:>16} {bases:>14,} {windows:>14,} {surviving:>14,} {lost * 100:>6.2f}%")

    print(f"\nmedian per-gene density {median:.3f} surviving k-mers per base")
    print(f"{len(sparse)} gene(s) below {SPARSE_FRACTION:.0%} of it — bait cannot reach them well:")
    for cover in sparse[:15]:
        print(f"  {cover.label:>14} {tier_of[cover.label]:>15} density {cover.density:.3f}")
    if len(sparse) > 15:
        print(f"  … and {len(sparse) - 15} more, all listed in the TSV")

    table = args.out / "bait-profile.tsv"
    with table.open("w", encoding="utf-8", newline="\n") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["symbol", "tier", "bases", "windows", "surviving", "density", "lost"])
        for cover in sorted(coverage.values(), key=lambda c: c.label):
            writer.writerow(
                [
                    cover.label,
                    tier_of[cover.label],
                    cover.bases,
                    cover.windows,
                    cover.surviving,
                    f"{cover.density:.6f}",
                    f"{cover.lost:.6f}",
                ]
            )
    summary = {
        "genes_profiled": len(coverage),
        "median_density": round(median, 6),
        "sparse_fraction_threshold": SPARSE_FRACTION,
        "sparse_genes": [c.label for c in sparse],
        "per_tier": {
            tier: {
                "bases": bases,
                "windows": windows,
                "surviving": surviving,
                "lost": round(1 - surviving / windows, 6) if windows else 0.0,
            }
            for tier, (bases, windows, surviving) in sorted(per_tier.items())
        },
    }
    (args.out / "bait-profile.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nwrote {table} and bait-profile.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
