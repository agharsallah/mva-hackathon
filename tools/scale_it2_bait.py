#!/usr/bin/env python3
"""Stage 4 of the step-2 plan: how the k-mer kernel's cost grows with the bait.

The plan pre-registered this before the pass and gave it a numeric gate — *the projected
server-side pass is under an hour*. It measures the production kernel
(:func:`mva.kmer.membership.hits`) over one real, unselected shard of the read store at
five bait sizes spanning four decades, up to the 10⁷ the real bait actually is.

**One shard, taken whole.** The recovered reads on disk are the ones that already matched;
timing against them would measure the expensive branch only. A shard of the store is
whatever the sequencer produced, which is the input a real pass sees.

Usage::

    uv run python tools/scale_it2_bait.py
    uv run python tools/scale_it2_bait.py --shard-index 7 --stride 16
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np
import polars as pl

from mva.kmer import scaling
from mva.kmer.encode import K
from mva.reads.access import resolve_root, storage_options
from mva.reads.bait import code_matrix, manifest

DEFAULT_BAIT = Path("build/it2/step-2/bait.npy")
DEFAULT_OUT = Path("build/it2/step-2/scaling.json")
DEFAULT_CACHE = Path("build/it2/step-2/scaling-shard.parquet")

#: Every read in the store, from ``mva-reads status`` — the denominator of the projection.
STORE_READS = 1_071_835_104


def sample_shard(root: str, index: int, cache: Path, rows: int) -> pl.DataFrame:
    """The sequence column of one shard, cached locally so a re-run costs nothing."""
    if cache.is_file():
        return pl.read_parquet(cache)
    shards = manifest(root)
    shard = shards[index % len(shards)]
    started = time.perf_counter()
    frame = (
        pl.scan_parquet(shard.url(root), storage_options=storage_options(root))
        .select("sequence")
        .head(rows)
        .collect()
    )
    print(f"shard {shard.key}: {frame.height:,} reads in {time.perf_counter() - started:.0f}s")
    cache.parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(cache, compression="zstd")
    return frame


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--bait", type=Path, default=DEFAULT_BAIT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--root", default=None)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--reads", type=int, default=1_000_000, help="reads timed per point")
    parser.add_argument("--stride", type=int, default=16)
    parser.add_argument("--k", type=int, default=K)
    parser.add_argument("--gate-seconds", type=float, default=3600.0)
    args = parser.parse_args(argv)

    pool = np.load(args.bait)
    print(f"bait pool: {pool.size:,} k-mers from {args.bait}")
    frame = sample_shard(resolve_root(args.root), args.shard_index, args.cache, args.reads)
    codes = code_matrix(frame["sequence"])
    print(f"reads timed: {codes.shape[0]:,} x {codes.shape[1]} bp, stride {args.stride}")

    # The decades, then the bait as it actually is: the top of the curve is measured,
    # never extrapolated, because that is the only point a real pass ever runs at.
    sizes = (*scaling.DEFAULT_SIZES, int(pool.size))
    points = scaling.measure(codes, pool, sizes, stride=args.stride, k=args.k)
    print(
        f"\n{'bait k-mers':>12} {'seconds':>9} {'reads/s':>12} {'hit rate':>10} "
        f"{'bait MB':>9} {'peak RSS MB':>12} {'full pass':>12}"
    )
    rows = []
    for point in points:
        projected = scaling.project(point, STORE_READS)
        rows.append({**point.as_dict(), "projected_pass_seconds": round(projected, 1)})
        print(
            f"{point.bait_kmers:>12,} {point.seconds:>9.2f} {point.reads_per_second:>12,.0f} "
            f"{point.hit_rate:>10.5f} {point.bait_bytes / 1e6:>9.1f} "
            f"{point.peak_rss_bytes / 1e6:>12.1f} {projected / 60:>9.1f} min"
        )

    projected_seconds = scaling.project(points[-1], STORE_READS)
    slowdown = points[0].reads_per_second / points[-1].reads_per_second
    passed = projected_seconds <= args.gate_seconds
    report = {
        "bait_pool_kmers": int(pool.size),
        "stride": args.stride,
        "k": args.k,
        "store_reads": STORE_READS,
        "read_length": int(codes.shape[1]),
        "points": rows,
        "slowdown_smallest_to_full_bait": round(slowdown, 3),
        "gate_seconds": args.gate_seconds,
        "gate": "pass" if passed else "fail",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        f"\nthe full bait costs {slowdown:.2f}x per read against 10^3; projected kernel-only pass "
        f"{projected_seconds / 60:.1f} min against a "
        f"{args.gate_seconds / 60:.0f} min gate -> {report['gate']}"
    )
    print(f"report -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
