"""The ``mva-reads bait`` verb — sweep the store against a whole baited region.

Its own module for the reason :mod:`mva.warehouse.cli` splits its verbs out: the bait pass
has more options than any other read-store verb (a bait file, a stride, a shard limit, two
output destinations, a report) and ``cli.py`` was already near the 400-line ceiling. The
verb registers itself through the same ``add`` helper the others use, so the command line
is unchanged.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from . import access, baitjob


def do_bait(args) -> int:
    """Sweep the whole store against a baited region and write what it recovered.

    The counterpart of ``count``: that verb asks whether a handful of designed k-mers are
    present, this one asks which reads came from tens of megabases of reference. Run it
    beside the data — from a remote client the pass is bound by the link, measured at
    55.8 s per shard on 2026-09-11, which is hours rather than minutes.
    """
    root = args.root or access.s3_root()
    bait = baitjob.load_bait(Path(args.bait), k=args.k)
    print(f"bait: {len(bait):,} canonical {args.k}-mers, stride {args.stride}")
    shown = {"count": 0}

    def progress(shard, rows, kept) -> None:
        shown["count"] += 1
        print(f"  [{shown['count']:>3}] {shard.key.split('/')[-1]:>16} {rows:>9,} -> {kept:>8,}")

    rows, result = baitjob.run_bait(
        root,
        bait,
        stride=args.stride,
        out_key=args.out_key,
        shard_limit=args.shards,
        collect_mates=not args.no_mates,
        workers=args.workers,
        staging=Path(args.staging) if args.staging else None,
        progress=progress if args.verbose else None,
    )
    summary = result.as_dict()
    for field_name in ("shards", "reads_scanned", "reads_matched", "fragments", "orphans"):
        print(f"{field_name:>16}: {summary[field_name]:,}")
    print(f"{'matched':>16}: {result.funnel.matched_fraction * 100:.4f}% of reads scanned")
    print(f"{'seconds':>16}: {summary['seconds']}")
    if args.report:
        print(f"report -> {baitjob.write_report(result, Path(args.report))}")
    if args.out:
        rows.lazy().sink_parquet(Path(args.out), compression="zstd")
        print(f"reads  -> {args.out}")
    if result.published:
        print(f"published -> {result.published} ({result.published_rows:,} rows)")
    for note in result.notes:
        print(f"note: {note}")
    return 0


def register(add: Callable) -> None:
    """Attach the verb to ``mva-reads``'s sub-parser."""
    b = add("bait", do_bait, "recover every read that came from a baited region")
    b.add_argument("--bait", required=True, help="path to the bait array (.npy of uint64)")
    b.add_argument("--k", type=int, default=31, help="k the bait was cut at")
    b.add_argument(
        "--stride",
        type=int,
        default=16,
        help="test every stride-th k-mer of a read; 1 is exhaustive and ~15x the work",
    )
    b.add_argument("--shards", type=int, help="stop after N shards — the scaling test")
    b.add_argument("--no-mates", action="store_true", help="skip the orphaned-mate pass")
    b.add_argument("--out", help="write the recovered reads here as Parquet")
    b.add_argument("--out-key", help="also publish them to the object store under this key")
    b.add_argument("--report", help="write the funnel as JSON here")
    b.add_argument(
        "--workers",
        type=int,
        default=1,
        help="shards swept at once; memory scales with it, so it is bounded by RAM",
    )
    b.add_argument(
        "--staging",
        help="keep the spilled survivor parts here instead of a temporary directory",
    )
    b.add_argument("--verbose", action="store_true", help="one line per shard")
