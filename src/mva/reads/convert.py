"""Convert one delivered FASTQ into sharded Parquet, and say exactly what was made.

One source file becomes one partition directory of ~250 MB shards
(``lane=<n>/read=<r>/part-*.parquet``). The whole record stream passes through a single
DuckDB ``COPY``, which does the projection, the zstd encoding, the row-group sizing and
the shard roll-over in one pass — there is no intermediate file and no per-record Python
on either engine.

The function returns numbers it *measured* (rows from the COPY, shard sizes from disk)
next to the :class:`~mva.reads.schema.RunFacts` it read from the file's own first record.
Reconciliation against independent expectations is :mod:`mva.reads.verify`'s job, not
this module's.
"""

import gzip
import time
from dataclasses import dataclass
from pathlib import Path

from . import engines, schema


@dataclass(frozen=True)
class Converted:
    """The receipt for one converted source file."""

    facts: schema.RunFacts
    out_dir: Path
    shards: tuple[Path, ...]
    rows: int
    source_bytes: int
    parquet_bytes: int
    engine: str
    seconds: float

    @property
    def reads_per_second(self) -> float:
        return self.rows / self.seconds if self.seconds else 0.0


def peek(fastq: Path) -> schema.RunFacts:
    """Read the first record only — the constants that go to the ``runs`` table."""
    with gzip.open(fastq, "rt") as handle:
        header = handle.readline().rstrip("\n")
        sequence = handle.readline().rstrip("\n")
    return schema.RunFacts.from_header(fastq.name, header, sequence)


def convert_file(fastq: Path, staging: Path, engine: str = "oxbow",
                 threads: int | None = None, memory_limit: str | None = None,
                 row_group_size: int = schema.ROW_GROUP_SIZE,
                 row_groups_per_file: int = schema.ROW_GROUPS_PER_FILE) -> Converted:
    """One FASTQ → one partition directory of shards, on one DuckDB connection.

    ``memory_limit`` matters as soon as more than one file converts at a time: a DuckDB
    instance left to its default claims most of the machine's RAM for its buffer pool,
    and eight of them doing that concurrently is an out-of-memory kill rather than a
    speed-up. :func:`mva.reads.store.convert_all` divides the machine by the job count
    and passes the share.
    """
    import duckdb

    facts = peek(fastq)
    lane, read_num = schema.lane_and_read(fastq.name)
    if (lane, read_num) != (facts.lane, facts.read_num):
        raise ValueError(f"{fastq.name}: filename says lane {lane} read {read_num}, "
                         f"first record says lane {facts.lane} read {facts.read_num}")

    out_dir = staging / schema.PREFIX / schema.shard_dir(lane, read_num)
    out_dir.mkdir(parents=True, exist_ok=True)

    connection = duckdb.connect()
    if threads:
        connection.execute(f"SET threads = {int(threads)}")
    if memory_limit:
        connection.execute(f"SET memory_limit = '{memory_limit}'")
    connection.execute(f"SET temp_directory = '{staging / '.duckdb-spill'}'")
    started = time.perf_counter()
    with engines.ENGINES[engine](connection, fastq) as raw:
        result = connection.execute(f"""
            COPY (SELECT {schema.PROJECTION} FROM {raw.view})
            TO '{out_dir}'
            (FORMAT parquet, COMPRESSION zstd,
             ROW_GROUP_SIZE {int(row_group_size)},
             ROW_GROUPS_PER_FILE {int(row_groups_per_file)},
             FILENAME_PATTERN 'part-{{i}}', OVERWRITE_OR_IGNORE true)
        """).fetchone()
    seconds = time.perf_counter() - started
    connection.close()

    shards = tuple(sorted(out_dir.glob("part-*.parquet")))
    return Converted(
        facts=facts, out_dir=out_dir, shards=shards,
        rows=int(result[0]), source_bytes=fastq.stat().st_size,
        parquet_bytes=sum(shard.stat().st_size for shard in shards),
        engine=engine, seconds=seconds,
    )
