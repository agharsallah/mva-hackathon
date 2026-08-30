"""Convert one delivered FASTQ into sharded Parquet, and say exactly what was made.

One source file becomes one partition directory of ~250 MB shards
(``lane=<n>/read=<r>/part-*.parquet``). The whole record stream passes through a single
DuckDB ``COPY``, which does the projection, the zstd encoding, the row-group sizing and
the shard roll-over in one pass — there is no intermediate file and no per-record Python
on any engine.

The source may be a local file or an object streamed out of the store; everything here
works from :class:`mva.reads.source.Source`, so neither this module nor the engines care
which. The function returns numbers it *measured* (rows from the COPY, shard sizes from
disk) next to the :class:`~mva.reads.schema.RunFacts` it read from the file's own first
record. Reconciliation against independent expectations is :mod:`mva.reads.verify`'s job.
"""

import gzip
import time
from dataclasses import dataclass
from pathlib import Path

from . import engines, schema
from .source import Source, _local_opener


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


def as_source(fastq) -> Source:
    """Accept a path or an already-resolved source; always return a source."""
    if isinstance(fastq, Source):
        return fastq
    path = Path(fastq)
    if not path.is_file():
        raise ValueError(f"{path} is not a readable file")
    return Source(name=path.name, path=path, size=path.stat().st_size,
                  open_stream=_local_opener(path))


def peek(fastq) -> schema.RunFacts:
    """Read the first record only — the constants that go to the ``runs`` table.

    A file that is not gzip, not FASTQ, or empty is diagnosed here, at the cheapest
    possible moment, rather than surfacing as an index error inside a parser later.
    """
    source = as_source(fastq)
    with source.open_stream() as raw:
        try:
            with gzip.open(raw, "rt") as handle:
                header = handle.readline().rstrip("\n")
                sequence = handle.readline().rstrip("\n")
        except (OSError, EOFError) as error:
            raise ValueError(f"{source.name}: not readable as gzip ({error})") from error
    if not header.startswith("@") or not sequence:
        raise ValueError(
            f"{source.name}: does not start with a FASTQ record "
            f"(first line: {header[:60]!r})")
    try:
        return schema.RunFacts.from_header(source.name, header, sequence)
    except (IndexError, ValueError) as error:
        raise ValueError(
            f"{source.name}: first read name is not the Illumina 8-field form this "
            f"pipeline parses — {header[:80]!r}") from error


def convert_file(fastq, staging: Path, engine: str = "oxbow",
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

    source = as_source(fastq)
    facts = peek(source)
    lane, read_num = source.lane_and_read
    if (lane, read_num) != (facts.lane, facts.read_num):
        raise ValueError(f"{source.name}: filename says lane {lane} read {read_num}, "
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
    with engines.ENGINES[engine](connection, source) as raw:
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
        rows=int(result[0]), source_bytes=source.size,
        parquet_bytes=sum(shard.stat().st_size for shard in shards),
        engine=engine, seconds=seconds,
    )
