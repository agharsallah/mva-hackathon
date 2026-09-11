#!/usr/bin/env python3
"""Off-target bait load as a function of k and padding — the failed gate, characterised.

The pre-registered gate is "bait k-mers also present elsewhere in GRCh38 are dropped and
counted; off-target < 5 % of bait". It failed at 8.79 % (entry 085). The wrong response is
to try parameters until it passes: a gate that moves after seeing its own result stops
being a gate, and the same discipline is what makes step 1's refuted H012 worth reading.

The right response is to measure the surface the single number sits on. Two questions,
both answerable and neither of them "how do we pass":

**Does k fix it?** Longer k-mers are more unique, monotonically — a 51-mer has far fewer
exact copies elsewhere in the genome than a 31-mer. So the curve says how much of the
8.79 % is a property of the regions and how much is a property of the choice of k. If the
curve is flat, the regions are repetitive and no k would have helped; if it is steep, k=31
was the binding constraint and the report should say so.

**Where does the loss live?** The bait is not uniform: core and mechanism-term genes carry
±50 kb of flank, which is intron and intergenic sequence, while the exon-proximal zone is
±2 kb. Splitting the off-target load by zone says whether the repetitive bait is in the
part step 2 actually reasons about.

What this tool does **not** do is change anything. k stays at 31 — it is shared with step
3's genotyping, where FastGT's retention band and the probe design depend on it, and
changing it here to satisfy a gate would silently move a parameter another step depends on.

Usage::

    uv run python tools/sweep_it2_bait_uniqueness.py --k 31 41 51
    uv run python tools/sweep_it2_bait_uniqueness.py --zones-only
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mva.kmer import regions as regions_module
from mva.kmer import uniqueness
from mva.kmer.bait import Interval, cut, plan

DEFAULT_STEP1 = Path("build/it2/step-1")
DEFAULT_OUT = Path("build/it2/step-2")
DEFAULT_CODING = Path("ressources/reference/coding_regions.tsv")
DEFAULT_REFERENCE = Path("build/reference/GRCh38.fa")
WIDE_TIERS = ("core", "mechanism-term")


def intervals_for(
    step1: Path, coding: Path, wide_pad: int, narrow_pad: int
) -> tuple[list[Interval], dict[str, list[Interval]]]:
    """The padded intervals, and the same set labelled by zone.

    ``exon-proximal`` is every gene's coding intervals at the narrow padding — the zone
    every tier shares. ``wide-flank`` is what the wide tiers add on top of it, which is
    where intronic and intergenic sequence enters the bait.
    """
    tier_of = regions_module.read_tiers(
        [(step1 / "targets.tsv", None), (step1 / "decoys.tsv", "decoy")]
    )
    by_gene = regions_module.read_gene_model(coding)
    padded, _, _ = regions_module.pad_by_tier(
        tier_of, by_gene, wide_tiers=WIDE_TIERS, wide_pad=wide_pad, narrow_pad=narrow_pad
    )
    narrow = regions_module.padded_by_gene(
        tier_of, by_gene, wide_tiers=(), wide_pad=narrow_pad, narrow_pad=narrow_pad
    )
    wide_only = regions_module.padded_by_gene(
        {gene: tier for gene, tier in tier_of.items() if tier in WIDE_TIERS},
        by_gene,
        wide_tiers=WIDE_TIERS,
        wide_pad=wide_pad,
        narrow_pad=narrow_pad,
    )
    zones = {
        "exon-proximal": [i for group in narrow.values() for i in group],
        "wide-tier-total": [i for group in wide_only.values() for i in group],
    }
    return padded, zones


def measure(reference: Path, intervals: list[Interval], k: int) -> dict[str, float]:
    """Cut at this k and count how much of it occurs more than once in the genome."""
    started = time.perf_counter()
    bait, laid = cut(reference, intervals, k=k)
    occurrence = uniqueness.count_in_genome(reference, bait)
    _, report = uniqueness.drop_repeats(bait, occurrence)
    return {
        "k": k,
        "bases": laid.bases,
        "kmers": report["bait_kmers"],
        "repeated": report["repeated"],
        "unseen": report["unseen"],
        "off_target": report["repeated"] / max(report["bait_kmers"], 1),
        "seconds": round(time.perf_counter() - started, 1),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step1", type=Path, default=DEFAULT_STEP1)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--coding", type=Path, default=DEFAULT_CODING)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--k", type=int, nargs="+", default=[31, 41, 51])
    parser.add_argument("--wide-pad", type=int, default=50_000)
    parser.add_argument("--narrow-pad", type=int, default=2_000)
    parser.add_argument("--zones-only", action="store_true", help="skip the k sweep")
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    padded, zones = intervals_for(args.step1, args.coding, args.wide_pad, args.narrow_pad)
    print(f"full bait: {plan(padded).bases:,} bases")

    by_zone = {}
    for name, group in zones.items():
        laid = plan(group)
        print(f"\nzone {name}: {laid.bases:,} bases — measuring at k={args.k[0]}")
        by_zone[name] = measure(args.reference, list(laid.intervals), args.k[0])
        result = by_zone[name]
        print(
            f"  {result['repeated']:,} of {result['kmers']:,} repeated "
            f"({result['off_target'] * 100:.2f}%) in {result['seconds']:.0f}s"
        )

    by_k = []
    if not args.zones_only:
        for k in args.k:
            print(f"\nfull bait at k={k} …")
            result = measure(args.reference, padded, k)
            by_k.append(result)
            print(
                f"  {result['repeated']:,} of {result['kmers']:,} repeated "
                f"({result['off_target'] * 100:.2f}%) in {result['seconds']:.0f}s"
            )

    if by_k:
        print(f"\n{'k':>4} {'bait k-mers':>14} {'repeated':>12} {'off-target':>11}  gate")
        for result in by_k:
            verdict = "PASS" if result["off_target"] < 0.05 else "FAIL"
            print(
                f"{result['k']:>4} {result['kmers']:>14,} {result['repeated']:>12,} "
                f"{result['off_target'] * 100:>10.2f}%  {verdict}"
            )

    payload = {
        "question": "how much of the 8.79% off-target load is k, and how much is the regions",
        "gate": {"rule": "off_target < 0.05", "observed_at_k31": 0.0879, "verdict": "fail"},
        "parameters_unchanged": (
            "k stays 31: it is shared with step 3's k-mer genotyping, where the probe "
            "design and FastGT's retention band depend on it. This sweep characterises "
            "the instrument; it does not retune it to pass a gate it already failed."
        ),
        "by_zone": by_zone,
        "by_k": by_k,
        "wide_pad": args.wide_pad,
        "narrow_pad": args.narrow_pad,
    }
    path = args.out / "uniqueness-sweep.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nwrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
