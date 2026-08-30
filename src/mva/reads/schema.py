"""The one place that knows what a read row looks like and where a shard lives.

A FASTQ record is four lines; the first is a composite key with eight fields packed into
it (``methodology/012`` decodes it). Everything constant per source file — instrument,
run, flowcell, lane, read number, control — is *not* stored per row: it goes to the
eight-row ``runs`` dimension table, and the read name is reconstructed from columns when
needed. What survives per read is what varies: flowcell coordinates, the filter flag, the
barcode, and the two payload strings that are 97% of the bytes.

Both conversion engines normalise to the same raw contract — three columns
``header`` (the name line without its ``@``), ``sequence``, ``quality`` — and
:data:`PROJECTION` is the single SQL that turns that contract into the stored schema, so
the engines cannot drift apart.
"""

import re
from dataclasses import dataclass

#: Stored per read. Types chosen from measured ranges (tile ≤ 9999, x/y ≤ ~5e5).
COLUMNS = {
    "tile": "USMALLINT",
    "x": "UINTEGER",
    "y": "UINTEGER",
    "is_filtered": "BOOLEAN",
    "index_pair": "VARCHAR",
    "sequence": "VARCHAR",
    "quality": "VARCHAR",
}

#: The shared projection from the raw engine contract to the stored columns.
#: ``header`` is ``instrument:run:flowcell:lane:tile:x:y read:filtered:control:index``;
#: the space splits the positional head from the descriptive tail.
PROJECTION = """
    CAST(split_part(split_part(header, ' ', 1), ':', 5) AS USMALLINT) AS tile,
    CAST(split_part(split_part(header, ' ', 1), ':', 6) AS UINTEGER)  AS x,
    CAST(split_part(split_part(header, ' ', 1), ':', 7) AS UINTEGER)  AS y,
    split_part(split_part(header, ' ', 2), ':', 2) = 'Y'              AS is_filtered,
    split_part(split_part(header, ' ', 2), ':', 4)                    AS index_pair,
    sequence,
    quality
"""

#: One row group per this many reads.
#:
#: **This number is a memory budget, not just a layout choice.** DuckDB's Parquet writer
#: holds a whole row group in memory before flushing it, once per writer thread, and a
#: read is ~300 uncompressed bytes — so 1,000,000 rows is ~300 MB per group and ran a
#: conversion out of memory under a 1 GB limit (``methodology/021``). At 200,000 rows the
#: same conversion peaks around 2 GB and runs at full speed.
ROW_GROUP_SIZE = 200_000

#: Shards roll over after this many row groups: ~4M reads ≈ 250 MB per shard, unchanged
#: from the larger row group — the shard size is set by the product, so shrinking the
#: group and raising this count keeps the file size while cutting the writer's buffer.
ROW_GROUPS_PER_FILE = 20

#: Where the read store lives inside the bucket.
PREFIX = "reads"

#: Recognises ``..._L001_R1_001.fastq.gz`` and captures (lane, read number).
FASTQ_NAME = re.compile(r"_L(\d{3})_R([12])_\d+\.(?:fastq|fq)\.gz$")


def shard_dir(lane: int, read_num: int) -> str:
    """Hive-style partition path for one (lane, read) pair, relative to the store root."""
    return f"lane={lane}/read={read_num}"


def shard_key(lane: int, read_num: int, index: int) -> str:
    """The object key for one shard."""
    return f"{PREFIX}/{shard_dir(lane, read_num)}/part-{index:04d}.parquet"


def lane_and_read(filename: str) -> tuple[int, int]:
    """Lane and read number encoded in a delivered FASTQ filename."""
    match = FASTQ_NAME.search(filename)
    if not match:
        raise ValueError(f"not a recognised paired FASTQ name: {filename!r}")
    return int(match.group(1)), int(match.group(2))


@dataclass(frozen=True)
class RunFacts:
    """What is constant across one source file — the ``runs`` dimension row.

    Read from the file's first record before conversion; :mod:`mva.reads.verify` checks
    the last record against it afterwards, so "constant" is verified at both ends rather
    than assumed.
    """

    source: str
    instrument: str
    run: str
    flowcell: str
    lane: int
    read_num: int
    control: str
    read_length: int

    @classmethod
    def from_header(cls, source: str, header: str, sequence: str) -> "RunFacts":
        head, _, tail = header.lstrip("@").partition(" ")
        h, t = head.split(":"), tail.split(":")
        return cls(source=source, instrument=h[0], run=h[1], flowcell=h[2],
                   lane=int(h[3]), read_num=int(t[0]), control=t[2],
                   read_length=len(sequence))

    def rebuild_name(self, tile: int, x: int, y: int,
                     is_filtered: bool, index_pair: str) -> str:
        """The exact FASTQ name line for one stored row — the round-trip check."""
        flag = "Y" if is_filtered else "N"
        return (f"@{self.instrument}:{self.run}:{self.flowcell}:{self.lane}:"
                f"{tile}:{x}:{y} {self.read_num}:{flag}:{self.control}:{index_pair}")
