"""Read-level aggregates, straight out of the object store.

The store is 272 hive-partitioned Parquet shards holding 1.07 billion reads. Nothing here
downloads a shard: DuckDB's ``httpfs`` asks for byte ranges, and Parquet's column layout
means a query that touches only ``tile``, ``x`` and ``y`` transfers a small fraction of
the file. That is the whole reason these endpoints exist at all.

The cost model is measured, not guessed, and it decides the shape of every function below:

* the two dimension tables (``runs``, ``manifest``) are tiny and instant;
* a **column-pruned** aggregate over one shard is ~2.5 s — cheap enough to serve, once,
  behind the cache;
* anything that touches ``quality`` reads the fat column and costs ~21 s per shard, so
  those functions **sample** a bounded number of rows instead of scanning a partition.

Shard object keys come from the manifest, never from string formatting. The stored keys
are ``part-0.parquet`` … ``part-33.parquet`` — unpadded — and guessing a padded name
produces a "file not found" that looks like a missing shard rather than a naming bug.
"""

from ..reads import access, schema
from ..warehouse.settings import object_store
from .queries.access import rows

#: Rows sampled per partition by the quality endpoints. 100k reads × 149 cycles is 14.9M
#: quality values — a stable mean per cycle, from one row group, in seconds.
SAMPLE_ROWS = 100_000

#: Flowcell coordinates are binned to this many units per side before counting, which
#: turns ~4M reads into ~31k heat-map cells.
TILE_BIN = 1000


def root() -> str:
    """The store's prefix, e.g. ``s3://mva/reads``."""
    return access.s3_root()


def url(key: str) -> str:
    """The ``s3://`` URL for one object key as the manifest spells it."""
    return object_store().url(key)


def opened():
    """A DuckDB connection carrying the object-store secret."""
    return access.connection(root())


def _table(name: str) -> str:
    return f"read_parquet('{root()}/{name}.parquet')"


def runs() -> list[dict]:
    """The eight-row ``runs`` dimension: one row per delivered FASTQ."""
    with _Connected() as connection:
        return rows(
            connection,
            f"""
            SELECT source, instrument, run, flowcell, lane, read_num, read_length,
                   reads, source_bytes, parquet_bytes, engine, seconds
            FROM {_table("runs")} ORDER BY lane, read_num
        """,
        )


def totals() -> dict:
    """Total reads and the read length, for the overview object."""
    with _Connected() as connection:
        found = rows(
            connection,
            f"""
            SELECT sum(reads) AS total_reads, max(read_length) AS read_length
            FROM {_table("runs")}
        """,
        )
    row = found[0] if found else {}
    return {
        "total_reads": _int(row.get("total_reads")),
        "read_length": _int(row.get("read_length")),
    }


def partitions() -> list[dict]:
    """Shards, reads and gibibytes per ``(lane, read)`` partition."""
    with _Connected() as connection:
        return rows(
            connection,
            f"""
            SELECT lane, read_num, count(*) AS shards, sum(rows) AS reads,
                   round(sum(bytes) / 1024.0 / 1024 / 1024, 2) AS gib
            FROM {_table("manifest")}
            GROUP BY lane, read_num ORDER BY lane, read_num
        """,
        )


def shard_keys(connection, lane: int, read_num: int) -> list[str]:
    """Every shard key for one partition, in numeric ``part-N`` order.

    Ordered by the *number* in the name, not the name: lexical order puts ``part-10``
    before ``part-2``, which would silently reshuffle which shard index means what.
    """
    found = rows(
        connection,
        f"""
        SELECT key FROM {_table("manifest")}
        WHERE lane = ? AND read_num = ?
        ORDER BY CAST(regexp_extract(key, 'part-(\\d+)', 1) AS INTEGER)
    """,
        [lane, read_num],
    )
    return [row["key"] for row in found]


def flowcell(lane: int, read_num: int, shard: int = 0) -> list[dict]:
    """Read density across one shard's flowcell surface, binned to :data:`TILE_BIN`.

    Reads three narrow integer columns out of a ~240 MB shard, which is why this costs
    seconds rather than minutes.
    """
    with _Connected() as connection:
        keys = shard_keys(connection, lane, read_num)
        if not keys:
            raise LookupError(f"no shards for lane {lane} read {read_num}")
        if not 0 <= shard < len(keys):
            raise LookupError(
                f"shard {shard} out of range: lane {lane} read {read_num} has {len(keys)}"
            )
        return rows(
            connection,
            f"""
            SELECT tile, x // {TILE_BIN} AS xb, y // {TILE_BIN} AS yb, count(*) AS n
            FROM read_parquet('{url(keys[shard])}')
            GROUP BY ALL ORDER BY tile, xb, yb
        """,
        )


def cycle_quality(sample_rows: int = SAMPLE_ROWS) -> list[dict]:
    """Mean Phred score per sequencing cycle, per partition — the read-quality decay curve.

    Sampled, not scanned: one partition is 34 shards of the fattest column in the store.
    ``LIMIT`` stops DuckDB after the first row group, so the sample is the store's first
    ``sample_rows`` reads in that partition rather than a random draw — acceptable because
    the question is "does quality fall off along the read", which is a per-cycle mean that
    is stable at this sample size, not a per-read statistic.

    The per-character decode is a lambda over ``range(1, length+1)`` rather than a string
    split: it indexes the string directly, so there is no dependency on how a particular
    DuckDB version splits on an empty delimiter.
    """
    return _per_partition(
        """
        SELECT cycle, round(avg(q), 2) AS mean_q FROM (
            SELECT unnest(range(1, length(quality) + 1)) AS cycle,
                   unnest(list_transform(range(1, length(quality) + 1),
                                         i -> ascii(quality[i]) - 33)) AS q
            FROM sample)
        GROUP BY cycle ORDER BY cycle
    """,
        sample_rows,
    )


def quality_levels(sample_rows: int = SAMPLE_ROWS) -> list[dict]:
    """How many bases sit at each Phred value, per partition.

    On a NovaSeq the answer is a handful of levels, not a smooth curve: the instrument
    quantises quality into four bins (about 2, 11, 25 and 37). Plotting it as a histogram
    of four bars is honest; plotting it as a continuous distribution is not.
    """
    return _per_partition(
        """
        SELECT q AS phred, count(*) AS count FROM (
            SELECT unnest(list_transform(range(1, length(quality) + 1),
                                         i -> ascii(quality[i]) - 33)) AS q
            FROM sample)
        GROUP BY q ORDER BY q
    """,
        sample_rows,
    )


def _per_partition(body: str, sample_rows: int) -> list[dict]:
    """Run ``body`` against a ``sample`` CTE for every partition, tagging lane and read.

    Lane and read number are attached in Python from the manifest rather than read from
    the hive path, because each query names one shard file directly — the partition
    columns are not in the file, only in its key.
    """
    limit = int(sample_rows)
    out: list[dict] = []
    with _Connected() as connection:
        found = rows(
            connection,
            f"SELECT DISTINCT lane, read_num FROM {_table('manifest')} ORDER BY lane, read_num",
        )
        for partition in found:
            lane, read_num = int(partition["lane"]), int(partition["read_num"])
            keys = shard_keys(connection, lane, read_num)
            if not keys:
                continue
            aggregated = rows(
                connection,
                f"""
                WITH sample AS (
                    SELECT quality FROM read_parquet('{url(keys[0])}') LIMIT {limit})
                {body}
            """,
            )
            out.extend({"lane": lane, "read_num": read_num, **row} for row in aggregated)
    return out


class _Connected:
    """Context manager around :func:`opened` — DuckDB connections are not one."""

    def __enter__(self):
        self.connection = opened()
        return self.connection

    def __exit__(self, *_) -> None:
        self.connection.close()


def _int(value) -> int | None:
    return None if value is None else int(value)


#: Re-exported so callers can name the store layout without importing the reads package.
PREFIX = schema.PREFIX
