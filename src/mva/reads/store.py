"""Build the whole read store: every FASTQ, in parallel, then publish it.

Orchestration only — the real work is :func:`mva.reads.convert.convert_file`. Files
convert concurrently (gzip is one stream, so parallelism across the eight files is the
only parallel decompression available), each on its own DuckDB connection with a fair
slice of the machine's threads.

Publishing means three things, in order: shards uploaded to the object store with boto3
multipart (they are opaque bytes at this point — re-encoding them through DuckDB would
cost another full pass), then two small tables written beside them: ``runs`` (one row per
source file: the constants, the counts, the engine, the duration) and ``manifest`` (one
row per shard: key, rows, bytes). The store is self-describing — verification reads the
manifest, never this process's memory.
"""

import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..warehouse.source import client
from . import schema
from .convert import Converted, convert_file
from .source import resolve

#: Object keys for the two describing tables.
RUNS_KEY = f"{schema.PREFIX}/runs.parquet"
MANIFEST_KEY = f"{schema.PREFIX}/manifest.parquet"


def discover(spec) -> list:
    """Every FASTQ at ``spec`` — a local directory, or ``s3``/``s3://bucket/prefix``.

    Thin pass-through to :func:`mva.reads.source.resolve`, kept because "discover the
    delivery" is the verb the rest of the pipeline thinks in.
    """
    return resolve(str(spec))


#: Parquet written per byte of source gzip, measured on the delivery: a 6,000,000-read
#: sample of ``L001_R1`` produced 339 MiB from source bytes in the same proportion
#: (``methodology/022``). Slightly above the whole-set figure, so it errs toward asking
#: for more room rather than less.
OUTPUT_RATIO = 0.75


class NotEnoughRoom(RuntimeError):
    """Staging cannot hold the Parquet this conversion would write."""


def check_room(staging: Path, sources: list, ratio: float = OUTPUT_RATIO) -> str:
    """Refuse before converting if the staging filesystem cannot hold the output.

    A conversion writes every shard locally before uploading, so it needs roughly
    three quarters of the delivery's compressed size in free space. Finding that out
    after four hours and 90% of the reads is the worst possible time.
    """
    needed = int(sum(source.size for source in sources) * ratio)
    staging.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(staging).free
    summary = (f"{needed / 2**30:.1f} GiB needed, {free / 2**30:.1f} GiB free "
               f"on {staging}")
    if free < needed:
        raise NotEnoughRoom(
            f"not enough room to stage the conversion: {summary}.\n"
            f"  Free space, point --staging at a bigger filesystem, or convert a subset.")
    return summary


#: Measured non-DuckDB cost of one job: the reader's Arrow batches, the Rust side and
#: the interpreter. A 6M-read conversion held ~2 GB resident against a 1 GB DuckDB
#: limit, so the budget hands DuckDB a gigabyte less than the arithmetic suggests.
READER_OVERHEAD_GIB = 1


def machine_share(jobs: int) -> tuple[int, str]:
    """Threads and DuckDB memory limit for one job, given how many run at once.

    Half the machine's RAM is divided between the jobs; the other half is left to the
    page cache and everything else on the box. Without this a parallel run is an
    out-of-memory kill: each DuckDB defaults to claiming ~80% of RAM.

    The limit governs DuckDB's buffer pool *only*, and the dominant part of that pool is
    the Parquet writer holding one row group per thread — which is why
    :data:`~mva.reads.schema.ROW_GROUP_SIZE` is as much a memory setting as a layout one.

    Threads are floored at two per job rather than divided exactly. The full conversion
    measured why (``methodology/023``): eight one-thread jobs ran at half the speed of
    one eight-thread job, because the engine is CPU-bound in DuckDB's projection and
    Parquet encoding, not in the gzip decompression that file-level parallelism overlaps.
    Mild oversubscription costs little; starving the writer costs half the machine.
    """
    threads = max(2, (os.cpu_count() or 4) // max(1, jobs))
    try:
        total = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError):  # not exposed on every platform
        return threads, "2GB"
    share = total / 2**30 / 2 / max(1, jobs)
    return threads, f"{max(1, int(share) - READER_OVERHEAD_GIB)}GB"


def convert_all(fastqs: list, staging: Path, engine: str = "oxbow",
                jobs: int = 2, threads: int | None = None,
                report=print) -> list[Converted]:
    """Convert every file, ``jobs`` at a time, splitting the machine fairly between them."""
    per_job, memory_limit = machine_share(jobs)
    per_job = threads or per_job
    report(f"  each job: {per_job} threads, {memory_limit} DuckDB memory limit")

    def one(fastq) -> Converted:
        done = convert_file(fastq, staging, engine=engine, threads=per_job,
                            memory_limit=memory_limit)
        report(f"  {done.facts.source}: {done.rows:,} reads in {done.seconds:,.0f}s "
               f"({done.reads_per_second:,.0f}/s), {len(done.shards)} shards, "
               f"{done.parquet_bytes / 2**30:.2f} GiB")
        return done

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        return list(pool.map(one, fastqs))


def write_tables(staging: Path, results: list[Converted]) -> tuple[Path, Path]:
    """Write ``runs.parquet`` and ``manifest.parquet`` into the staging root."""
    import duckdb

    runs = [(c.facts.source, c.facts.instrument, c.facts.run, c.facts.flowcell,
             c.facts.lane, c.facts.read_num, c.facts.control, c.facts.read_length,
             c.rows, c.source_bytes, c.parquet_bytes, c.engine, round(c.seconds, 1))
            for c in results]
    manifest = [(shard_key(c, shard), shard.stat().st_size, c.facts.lane,
                 c.facts.read_num, c.facts.source)
                for c in results for shard in c.shards]

    root = staging / schema.PREFIX
    runs_path, manifest_path = root / "runs.parquet", root / "manifest.parquet"
    connection = duckdb.connect()
    connection.execute("""
        CREATE TABLE runs (source VARCHAR, instrument VARCHAR, run VARCHAR,
            flowcell VARCHAR, lane UTINYINT, read_num UTINYINT, control VARCHAR,
            read_length USMALLINT, reads UBIGINT, source_bytes UBIGINT,
            parquet_bytes UBIGINT, engine VARCHAR, seconds DOUBLE)""")
    connection.executemany("INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", runs)
    connection.execute("""
        CREATE TABLE manifest (key VARCHAR, bytes UBIGINT, lane UTINYINT,
            read_num UTINYINT, source VARCHAR)""")
    connection.executemany("INSERT INTO manifest VALUES (?,?,?,?,?)", manifest)
    # Shard row counts come from the files themselves, not from this process.
    connection.execute(f"""
        CREATE TABLE shard_rows AS
        SELECT filename, count(*) AS rows
        FROM read_parquet('{root}/lane=*/read=*/part-*.parquet',
                          filename=true, hive_partitioning=false)
        GROUP BY filename""")
    connection.execute(f"""
        COPY (SELECT m.key, s.rows, m.bytes, m.lane, m.read_num, m.source
              FROM manifest m JOIN shard_rows s
              ON s.filename LIKE '%/' || m.key
              ORDER BY m.key)
        TO '{manifest_path}' (FORMAT parquet)""")
    connection.execute(f"COPY (SELECT * FROM runs ORDER BY lane, read_num) "
                       f"TO '{runs_path}' (FORMAT parquet)")
    connection.close()
    return runs_path, manifest_path


def shard_key(converted: Converted, shard: Path) -> str:
    """The object key one staged shard will be uploaded under (its own name, kept)."""
    lane, read_num = converted.facts.lane, converted.facts.read_num
    return f"{schema.PREFIX}/{schema.shard_dir(lane, read_num)}/{shard.name}"


def upload(store, staging: Path, results: list[Converted], report=print) -> int:
    """Ship every shard plus the two tables. Returns the number of objects sent."""
    s3 = client(store)
    sent = 0
    for converted in results:
        for shard in converted.shards:
            s3.upload_file(str(shard), store.bucket, shard_key(converted, shard))
            sent += 1
        report(f"  uploaded {len(converted.shards)} shards for {converted.facts.source}")
    root = staging / schema.PREFIX
    for path, key in ((root / "runs.parquet", RUNS_KEY),
                      (root / "manifest.parquet", MANIFEST_KEY)):
        s3.upload_file(str(path), store.bucket, key)
        sent += 1
    return sent
