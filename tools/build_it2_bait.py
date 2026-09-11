#!/usr/bin/env python3
"""Cut the step-2 bait from the reference, and measure how much of it is honest.

Step 1 chose *which genes* with the DNA never opened. This turns that gene list into the
only thing the read store can be asked about — a set of reference k-mers — and reports the
three numbers the plan's gate is written against, **before** any read is scanned:

``bait bases``      how much reference the pass will look for
``expected reads``  bases x depth / read length; the pass is judged against 0.5-2x of it
``off-target %``    bait k-mers that also occur elsewhere in the genome, dropped and counted

**Padding is per tier, and the tiers come from step 1.** ``core`` and ``mechanism-term``
genes get the wide padding, because a structural variant that removes an exon has its
breakpoints deep in the introns around it; ``net`` and the decoys get the narrow one,
which reaches splice sites and near-intronic alleles. Both numbers are flags.

**The decoys are baited identically.** They are the read route's null (H020): if the same
rules yield as many biallelic candidates in 396 shape-matched genes nobody's symptoms
nominated, the route has no discriminating power. A null that went through a different
pipeline would measure the pipeline, not the route — so they ride the same pass.

Writes, under ``--out`` (gitignored — the bait is reference sequence, but it is 300+ MB):

``bait.npy``         sorted unique canonical k-mers, after the uniqueness filter
``bait-raw.npy``     the same before it, so the filter can be re-run without re-cutting
``summary.json``     the gate numbers, per tier and in total
``provenance.json``  inputs with their sha256, the parameters, and the code version

Usage::

    uv run python tools/build_it2_bait.py
    uv run python tools/build_it2_bait.py --core-pad 50000 --net-pad 2000 --skip-uniqueness
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mva.kmer import regions, uniqueness
from mva.kmer.bait import cut, expected_reads, plan
from mva.kmer.membership import Bait

DEFAULT_STEP1 = Path("build/it2/step-1")
DEFAULT_OUT = Path("build/it2/step-2")
DEFAULT_CODING = Path("ressources/reference/coding_regions.tsv")
DEFAULT_REFERENCE = Path("build/reference/GRCh38.fa")

#: Tiers that get the wide padding. `core` is step 1's top-50-by-score; `mechanism-term`
#: is the rule-admitted chromosome-instability set. Both are the tier the plan calls
#: "core" and gives structural-variant reach.
WIDE_TIERS = ("core", "mechanism-term")

#: Depth and read length of this delivery, owned by ideation/data-findings.md. Flags, so
#: the tool is not about this case.
DEFAULT_DEPTH = 44.0
DEFAULT_READ_LENGTH = 150


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 22), b""):
            digest.update(chunk)
    return digest.hexdigest()


def code_version() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):  # pragma: no cover
        return "unknown"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step1", type=Path, default=DEFAULT_STEP1)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--coding", type=Path, default=DEFAULT_CODING)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--k", type=int, default=31)
    parser.add_argument("--core-pad", type=int, default=50_000, help="core / mechanism-term")
    parser.add_argument("--net-pad", type=int, default=2_000, help="net / decoy")
    parser.add_argument("--depth", type=float, default=DEFAULT_DEPTH)
    parser.add_argument("--read-length", type=int, default=DEFAULT_READ_LENGTH)
    parser.add_argument(
        "--skip-uniqueness", action="store_true", help="cut only; leave the off-target gate unrun"
    )
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    tier_of = regions.read_tiers(
        [(args.step1 / "targets.tsv", None), (args.step1 / "decoys.tsv", "decoy")]
    )
    by_gene = regions.read_gene_model(args.coding)
    padded, per_tier, missing = regions.pad_by_tier(
        tier_of,
        by_gene,
        wide_tiers=WIDE_TIERS,
        wide_pad=args.core_pad,
        narrow_pad=args.net_pad,
    )
    laid = plan(padded)

    print(f"{len(tier_of):,} genes ({len(missing)} absent from the gene model)")
    print(f"{'tier':>16} {'genes':>7} {'padded bases':>15}")
    for tier, counts in sorted(per_tier.items()):
        print(f"{tier:>16} {counts['genes']:>7,} {counts['bases']:>15,}")
    print(f"{'merged total':>16} {'':>7} {laid.bases:>15,}")
    expected = expected_reads(laid.bases, args.depth, args.read_length)
    fraction = laid.bases / 3_099_922_541
    print(
        f"\nbait is {fraction * 100:.2f}% of the genome; at {args.depth}x and "
        f"{args.read_length} bp that is ~{expected:,.0f} reads "
        f"(gate: 0.5-2x => {expected * 0.5:,.0f}-{expected * 2:,.0f})"
    )

    started = time.perf_counter()
    raw, _ = cut(args.reference, laid.intervals, k=args.k)
    print(f"\ncut {len(raw):,} canonical {args.k}-mers in {time.perf_counter() - started:.0f}s")
    np.save(args.out / "bait-raw.npy", raw.kmers)

    report: dict[str, int] = {}
    kept: Bait = raw
    if args.skip_uniqueness:
        # bait.npy is the *filtered* bait and nothing else. Writing the unfiltered set
        # there would leave a file whose name promises a gate that never ran — the kind
        # of quiet substitution a later pass has no way to notice.
        print(
            "\n--skip-uniqueness: wrote bait-raw.npy only; bait.npy left as it was.\n"
            "  Re-run without the flag to produce the filtered bait."
        )
    else:
        started = time.perf_counter()
        occurrence = uniqueness.count_in_genome(args.reference, raw)
        kept, report = uniqueness.drop_repeats(raw, occurrence)
        seconds = time.perf_counter() - started
        off_target = report["repeated"] / max(report["bait_kmers"], 1)
        print(
            f"uniqueness pass: {report['windows_scanned']:,} genome windows in {seconds:.0f}s\n"
            f"  {report['repeated']:,} of {report['bait_kmers']:,} bait k-mers occur more "
            f"than once ({off_target * 100:.2f}%) -> dropped"
        )
        print(f"  {report['unseen']:,} never found (must be 0)")
        print(f"  gate: off-target < 5% -> {'PASS' if off_target < 0.05 else 'FAIL'}")
        np.save(args.out / "bait.npy", kept.kmers)

    summary = {
        "k": args.k,
        "padding": {"wide": args.core_pad, "narrow": args.net_pad, "wide_tiers": WIDE_TIERS},
        "genes": len(tier_of),
        "genes_absent_from_gene_model": missing,
        "per_tier": per_tier,
        "intervals_merged": len(laid.intervals),
        "bait_bases": laid.bases,
        "genome_fraction": round(fraction, 6),
        "expected_reads": round(expected),
        "expected_reads_gate": [round(expected * 0.5), round(expected * 2)],
        "kmers_cut": len(raw),
        "kmers_kept": len(kept),
        "uniqueness": report,
        "bases_by_contig": laid.by_contig,
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    reference_manifest = args.reference.parent / f"{args.reference.stem}.provenance.json"
    provenance = {
        "generated_at": datetime.now(UTC).isoformat(),
        "tool": "tools/build_it2_bait.py",
        "code_version": code_version(),
        "inputs": {
            "targets": {
                "file": str(args.step1 / "targets.tsv"),
                "sha256": sha256(args.step1 / "targets.tsv"),
                "produced_by": "tools/build_it2_targets.py (step 1, entry 084)",
            },
            "decoys": {
                "file": str(args.step1 / "decoys.tsv"),
                "sha256": sha256(args.step1 / "decoys.tsv"),
            },
            "gene_model": {"file": str(args.coding), "sha256": sha256(args.coding)},
            "reference": {
                "file": str(args.reference),
                "sha256": sha256(args.reference),
                "manifest": str(reference_manifest),
            },
        },
        "parameters": {
            "k": args.k,
            "core_pad": args.core_pad,
            "net_pad": args.net_pad,
            "depth": args.depth,
            "read_length": args.read_length,
            "uniqueness_filter": not args.skip_uniqueness,
        },
        "outputs": {
            "bait": "bait.npy",
            "bait_before_uniqueness_filter": "bait-raw.npy",
            "summary": "summary.json",
        },
        "notes": [
            "Reference sequence only: the bait carries no patient information.",
            "Decoys are cut with identical rules so H020 measures the route, not the pipeline.",
        ],
    }
    (args.out / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    print(f"\nwrote {args.out}/bait.npy, summary.json, provenance.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
