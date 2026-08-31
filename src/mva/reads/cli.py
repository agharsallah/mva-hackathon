"""``mva-reads`` — build, verify and query the read store.

Thin argparse over the modules that do the work; every verb prints what it measured and
exits non-zero when a check fails, so the same commands are usable interactively and in a
methodology entry's "commands run" block.
"""

import argparse
import sys
import time
from pathlib import Path

from ..warehouse.settings import object_store, setting
from . import bench, scan, store, triage, verify
from .access import connection as _connection
from .access import s3_root as _s3_root
from .engines import ENGINES
from .source import NotADelivery


def _sources(args) -> list:
    """Resolve ``--source``, and explain a bad one instead of raising through it."""
    spec = args.source or setting("MVA_SOURCE_DIR")
    try:
        return store.discover(spec)
    except NotADelivery as error:
        print(f"{error}", file=sys.stderr)
        sys.exit(2)


def do_bench(args) -> int:
    """Race the engines, and — with ``--scale`` — check the winner holds at size."""
    fastqs = _sources(args)
    contenders = tuple(args.engines.split(",")) if args.engines else ()
    budget = dict(contenders=contenders, jobs=args.jobs,
                  memory_limit=args.memory_limit)
    timings = bench.race(fastqs[0], reads=args.reads, **budget)
    if not any(timing.ok for timing in timings):
        return 1
    if args.scale:
        print(f"\nre-running at {args.reads * args.scale:,} reads on the same budget …")
        larger = {timing.engine: timing for timing in
                  bench.race(fastqs[0], reads=args.reads * args.scale, **budget)}
        for small in timings:
            big = larger.get(small.engine)
            if not (small.ok and big):
                continue
            if not big.ok:
                print(f"  {small.engine}: FAILED at {args.scale}× — {big.error}")
                continue
            verdict = ("flat — need does not grow with input" if bench.streams(small, big)
                       else "GROWS with input — check it fits the full file")
            print(f"  {small.engine}: {small.peak_rss / 2**20:.0f} → "
                  f"{big.peak_rss / 2**20:.0f} MiB peak RSS — {verdict}")
        timings = [timing for timing in larger.values() if timing.ok]
        if not timings:
            print("\nno engine completed at scale within the budget")
            return 1
    best = bench.winner(timings)
    print(f"\nwinner: {best.engine} at {best.reads_per_second:,.0f} reads/s")
    return 0


def do_convert(args) -> int:
    fastqs = _sources(args)
    staging = Path(args.staging or setting("MVA_STAGING_DIR")).expanduser()
    source_bytes = sum(fastq.size for fastq in fastqs)
    print(f"converting {len(fastqs)} files ({source_bytes / 2**30:.1f} GiB source) "
          f"with engine={args.engine}, jobs={args.jobs}, staging={staging}")
    try:
        print(f"  disk: {store.check_room(staging, fastqs)}")
    except store.NotEnoughRoom as error:
        print(error, file=sys.stderr)
        return 2
    started = time.perf_counter()
    results = store.convert_all(fastqs, staging, engine=args.engine, jobs=args.jobs,
                                threads=args.threads)
    runs_path, manifest_path = store.write_tables(staging, results)
    total = sum(r.rows for r in results)
    elapsed = time.perf_counter() - started
    print(f"total: {total:,} reads in {elapsed / 60:.1f} min "
          f"({total / elapsed:,.0f} reads/s overall), "
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


def _probes(args) -> tuple[list[str], list[str]]:
    """Probes from ``--kmer`` and/or a file of ``name<TAB>sequence`` (or bare sequences).

    One pass over 1.07 billion reads costs the same whether it carries one probe or
    fifty, so the file form is the one that matters: ask every candidate at once.
    """
    names, probes = [], []
    for index, probe in enumerate(args.kmer or [], start=1):
        names.append(f"kmer{index}")
        probes.append(probe)
    if args.kmers_file:
        for line in Path(args.kmers_file).expanduser().read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.replace("\t", " ").split()
            if len(parts) >= 2:
                names.append(parts[0])
                probes.append(parts[1])
            else:
                names.append(f"line{len(probes) + 1}")
                probes.append(parts[0])
    if not probes:
        print("give at least one --kmer or a --kmers-file", file=sys.stderr)
        sys.exit(2)
    return names, probes


def do_scan(args) -> int:
    root = args.root or _s3_root(object_store())
    names, probes = _probes(args)
    connection = _connection(root)
    started = time.perf_counter()
    hits = scan.kmers(connection, root, probes, limit=args.limit, names=names)
    seconds = time.perf_counter() - started
    for hit in hits:
        label = f"{hit.probe}: " if len(probes) > 1 else "  "
        print(f"{label}lane {hit.lane} read {hit.read_num} tile {hit.tile} "
              f"({hit.x},{hit.y}) strand {hit.strand} at {hit.position}")
    print(f"{len(hits)} hit(s) for {len(probes)} probe(s) in {seconds:.1f}s over {root}")
    return 0


def do_count(args) -> int:
    """How many reads carry each probe — the number that decides if an allele is real."""
    root = args.root or _s3_root(object_store())
    names, probes = _probes(args)
    connection = _connection(root)
    started = time.perf_counter()
    rows = scan.counts(connection, root, probes, names=names)
    seconds = time.perf_counter() - started
    found = {row[0]: row for row in rows}
    print(f"{'probe':>20} {'fwd':>7} {'rev':>7} {'total':>7} {'lanes':>6}  verdict")
    for name in names:
        row = found.get(name)
        if row is None:
            print(f"{name:>20} {0:>7} {0:>7} {0:>7} {0:>6}  absent")
            continue
        _, forward, reverse, total, lanes = row
        print(f"{name:>20} {forward:>7} {reverse:>7} {total:>7} {lanes:>6}  "
              f"{triage.verdict(total, lanes)}")
    print(f"\n{len(probes)} probe(s) in one pass, {seconds:.1f}s over {root}")
    print(triage.EXPECTED_HINT)
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
                   help="re-run at N× the sample and report whether memory grows with it")
    b.add_argument("--jobs", type=int, default=1,
                   help="size the memory budget as one job of a JOBS-way run")
    b.add_argument("--memory-limit",
                   help="DuckDB memory limit per engine (default: the --jobs share)")

    c = add("convert", do_convert, "convert every FASTQ to sharded parquet and upload")
    c.add_argument("--engine", choices=sorted(ENGINES), default="oxbow")
    c.add_argument("--jobs", type=int, default=4,
                   help="files converted concurrently — more is not faster: the engine "
                        "is CPU-bound, and 8x1-thread ran at half the speed of 1x8 "
                        "(methodology/023)")
    c.add_argument("--threads", type=int,
                   help="DuckDB threads per job (default: a fair share, floored at 2)")
    c.add_argument("--staging", help="local shard directory (default: MVA_STAGING_DIR)")
    c.add_argument("--no-upload", action="store_true")

    v = add("verify", do_verify, "prove the store matches the delivery")
    v.add_argument("--expected-total", type=int,
                   help="grand total from ideation/data-findings.md")
    v.add_argument("--shallow", action="store_true",
                   help="skip the full-decompression round-trip checks")

    def add_probes(sub_parser):
        sub_parser.add_argument("--kmer", action="append",
                                help="a probe sequence; repeat for several")
        sub_parser.add_argument("--kmers-file",
                                help="file of probes: 'name<TAB>sequence' or one "
                                     "sequence per line, '#' comments ignored")
        return sub_parser

    s = add_probes(add("scan", do_scan,
                       "k-mer strike: find subsequences on either strand, one pass"))
    s.add_argument("--limit", type=int, default=100,
                   help="reads reported per probe (the scan itself is unlimited)")

    add_probes(add("count", do_count,
                   "count reads carrying each probe — one pass, no read listing"))

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
