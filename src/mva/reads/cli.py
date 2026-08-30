"""``mva-reads`` — build, verify and query the read store.

Thin argparse over the modules that do the work; every verb prints what it measured and
exits non-zero when a check fails, so the same commands are usable interactively and in a
methodology entry's "commands run" block.
"""

import argparse
import sys
from pathlib import Path

from ..warehouse.settings import object_store, setting
from . import bench, scan, schema, store, verify
from .engines import ENGINES
from .source import NotADelivery


def _s3_root(cfg) -> str:
    return f"s3://{cfg.bucket}/{schema.PREFIX}"


def _connection(root: str):
    """A DuckDB connection able to read ``root`` — with the store secret when remote."""
    if root.startswith("s3://"):
        from ..warehouse.objects import connect
        return connect(object_store())
    import duckdb
    return duckdb.connect()


def _sources(args) -> list:
    """Resolve ``--source``, and explain a bad one instead of raising through it."""
    spec = args.source or setting("MVA_SOURCE_DIR")
    try:
        return store.discover(spec)
    except NotADelivery as error:
        print(f"{error}", file=sys.stderr)
        sys.exit(2)


def do_bench(args) -> int:
    """Race the engines, and — with ``--scale`` — prove the winner actually streams."""
    fastqs = _sources(args)
    contenders = tuple(args.engines.split(",")) if args.engines else ()
    timings = bench.race(fastqs[0], reads=args.reads, contenders=contenders)
    if not any(timing.ok for timing in timings):
        return 1
    if args.scale:
        print(f"\nre-running at {args.reads * args.scale:,} reads to test memory growth …")
        larger = {timing.engine: timing for timing in
                  bench.race(fastqs[0], reads=args.reads * args.scale,
                             contenders=contenders)}
        for small in timings:
            big = larger.get(small.engine)
            if small.ok and big and big.ok:
                verdict = "streams" if bench.streams(small, big) else "BUFFERS — unusable at full scale"
                print(f"  {small.engine}: {small.peak_rss / 2**20:.0f} → "
                      f"{big.peak_rss / 2**20:.0f} MiB peak RSS — {verdict}")
        timings = [t for t in larger.values()
                   if bench.streams(next(s for s in timings if s.engine == t.engine), t)]
        if not timings:
            print("\nno engine streamed at scale")
            return 1
    best = bench.winner(timings)
    print(f"\nwinner: {best.engine} at {best.reads_per_second:,.0f} reads/s")
    return 0


def do_convert(args) -> int:
    fastqs = _sources(args)
    staging = Path(args.staging or setting("MVA_STAGING_DIR")).expanduser()
    staging.mkdir(parents=True, exist_ok=True)
    print(f"converting {len(fastqs)} files with engine={args.engine}, "
          f"jobs={args.jobs}, staging={staging}")
    results = store.convert_all(fastqs, staging, engine=args.engine, jobs=args.jobs)
    runs_path, manifest_path = store.write_tables(staging, results)
    total = sum(r.rows for r in results)
    print(f"total: {total:,} reads, "
          f"{sum(r.parquet_bytes for r in results) / 2**30:.2f} GiB parquet")
    print(f"wrote {runs_path} and {manifest_path}")
    if args.no_upload:
        print("upload skipped (--no-upload)")
        return 0
    cfg = object_store()
    sent = store.upload(cfg, staging, results)
    print(f"uploaded {sent} objects to {_s3_root(cfg)}")
    return 0


def do_verify(args) -> int:
    root = args.root or _s3_root(object_store())
    sources: list[Path] = [] if args.shallow else _sources(args)
    report = verify.run(root, sources, expected_total=args.expected_total,
                        deep=not args.shallow, connection=_connection(root))
    for line in report.notes + report.failures:
        print(line)
    print(f"\n{'PASS' if report.ok else 'FAIL'} — {report.shards} shards, "
          f"{report.total_rows:,} rows")
    return 0 if report.ok else 1


def do_scan(args) -> int:
    root = args.root or _s3_root(object_store())
    connection = _connection(root)
    import time
    started = time.perf_counter()
    hits = scan.kmer(connection, root, args.kmer, limit=args.limit)
    seconds = time.perf_counter() - started
    for hit in hits:
        print(f"  lane {hit.lane} read {hit.read_num} tile {hit.tile} "
              f"({hit.x},{hit.y}) strand {hit.strand} at {hit.position}")
    print(f"{len(hits)} hit(s) in {seconds:.1f}s over {root}")
    return 0


def do_qc(args) -> int:
    root = args.root or _s3_root(object_store())
    rows = scan.qc(_connection(root), root)
    print(f"{'lane':>4} {'read':>4} {'reads':>14} {'filtered%':>10} {'<Q37%':>7}")
    for lane, read, reads, filtered, below in rows:
        print(f"{lane:>4} {read:>4} {reads:>14,} {filtered:>10} {below:>7}")
    return 0


def do_sql(args) -> int:
    root = args.root or _s3_root(object_store())
    for row in scan.sql(_connection(root), root, args.query):
        print("\t".join(str(value) for value in row))
    return 0


def do_status(args) -> int:
    cfg = object_store()
    root = _s3_root(cfg)
    connection = _connection(root)
    try:
        rows = connection.execute(f"""
            SELECT lane, read_num, count(*) AS shards, sum(rows) AS reads,
                   round(sum(bytes) / 2.0**30, 2) AS gib
            FROM '{root}/manifest.parquet' GROUP BY lane, read_num
            ORDER BY lane, read_num""").fetchall()
    except Exception as error:
        print(f"no manifest at {root}/manifest.parquet — store not built? ({error})")
        return 1
    print(f"{'lane':>4} {'read':>4} {'shards':>7} {'reads':>14} {'GiB':>7}")
    for lane, read, shards, reads, gib in rows:
        print(f"{lane:>4} {read:>4} {shards:>7} {reads:>14,} {gib:>7}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mva-reads",
                                     description="the queryable read store")
    sub = parser.add_subparsers(dest="verb", required=True)

    def add(name, handler, help_text):
        p = sub.add_parser(name, help=help_text)
        p.set_defaults(handler=handler)
        p.add_argument("--source", help="delivery directory, or 's3' / "
                                        "'s3://bucket/prefix' to stream from the object "
                                        "store (default: MVA_SOURCE_DIR)")
        p.add_argument("--root", help="store root: staging path or s3:// prefix "
                                      "(default: the object store)")
        return p

    b = add("bench", do_bench, "race the conversion engines on a sample")
    b.add_argument("--reads", type=int, default=1_000_000)
    b.add_argument("--engines", default="", help="comma-separated subset to race")
    b.add_argument("--scale", type=int, default=0, metavar="N",
                   help="re-run at N× the sample and disqualify engines whose "
                        "memory grows with it")

    c = add("convert", do_convert, "convert every FASTQ to sharded parquet and upload")
    c.add_argument("--engine", choices=sorted(ENGINES), default="oxbow")
    c.add_argument("--jobs", type=int, default=2, help="files converted concurrently")
    c.add_argument("--staging", help="local shard directory (default: MVA_STAGING_DIR)")
    c.add_argument("--no-upload", action="store_true")

    v = add("verify", do_verify, "prove the store matches the delivery")
    v.add_argument("--expected-total", type=int,
                   help="grand total from ideation/data-findings.md")
    v.add_argument("--shallow", action="store_true",
                   help="skip the full-decompression round-trip checks")

    s = add("scan", do_scan, "k-mer strike: find a subsequence on either strand")
    s.add_argument("--kmer", required=True)
    s.add_argument("--limit", type=int, default=100)

    add("qc", do_qc, "per-lane read counts, filter rate, quality profile")

    q = add("sql", do_sql, "arbitrary SQL with the store bound as `reads`")
    q.add_argument("query")

    add("status", do_status, "what the object store currently holds")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
