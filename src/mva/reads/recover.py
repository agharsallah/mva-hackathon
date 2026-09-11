"""Turn the sweep's survivors back into paired FASTQ an aligner will accept.

The store is not a FASTQ file: the read name was never stored, because every part of it
that is constant across a source file lives in the eight-row ``runs`` table instead
(:mod:`mva.reads.schema`). Rebuilding a record therefore means joining a row back to its
run — which is exactly what :meth:`mva.reads.schema.RunFacts.rebuild_name` does, and what
:func:`mva.reads.verify.round_trip` already proves is byte-exact.

**Why mates need a second pass.** An aligner reads R1 and R2 as parallel files, record for
record: line *n* of one must be the mate of line *n* of the other. The sweep finds reads,
not fragments, so a fragment whose R1 overlapped the bait and whose R2 fell outside it
arrives half-present. :func:`orphans` names those fragments and :func:`collect_mates`
fetches the missing halves, filtered to the key set rather than re-tested against the
bait.

**The orphan count is a measurement, not an inconvenience.** Every orphan is a fragment
that straddles the edge of a baited region. Their share is the empirical size of the
bait-edge zone, and step 2 needs that number anyway: it is the same edge that makes a
read-pair SV caller see a deletion where the bait simply stopped.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polars as pl

from .access import storage_options
from .bait import COLUMNS, PAIR_KEY, Shard, Survivors
from .schema import RunFacts

#: Both mates of a fragment, in the order an aligner expects them.
MATES = (1, 2)


@dataclass(frozen=True)
class Recovered:
    """What was written, and the counts that prove the two files line up."""

    files: dict[int, Path]
    fragments: int
    orphans_filled: int
    dropped: int

    def as_dict(self) -> dict[str, object]:
        return {
            "files": {str(read): str(path) for read, path in self.files.items()},
            "fragments": self.fragments,
            "orphans_filled": self.orphans_filled,
            "dropped": self.dropped,
        }


def orphans(survivors: Survivors | pl.DataFrame) -> pl.DataFrame:
    """Fragments the sweep matched on one mate only, with the mate that is missing.

    Returns the pair key plus a ``read`` column naming the mate still to fetch, which is
    what :func:`collect_mates` filters on. Reads the sweep lazily, so a spilled pass never
    materialises its survivors to answer this — only the orphan keys, which are small.
    """
    lazy = _lazy(survivors)
    if not lazy.collect_schema().names():
        return pl.DataFrame(schema=dict.fromkeys((*PAIR_KEY, "read"), pl.Int64))
    seen = sum(MATES)
    return (
        lazy.select([pl.col(name).cast(pl.Int64) for name in (*PAIR_KEY, "read")])
        .unique()
        .group_by(list(PAIR_KEY))
        .agg(pl.col("read").sum().alias("seen"))
        .filter(pl.col("seen") < seen)
        .with_columns((pl.lit(seen) - pl.col("seen")).alias("read"))
        .select([*PAIR_KEY, "read"])
        .collect(engine="streaming")
    )


def _lazy(survivors: Survivors | pl.DataFrame | pl.LazyFrame) -> pl.LazyFrame:
    if isinstance(survivors, Survivors):
        return survivors.lazy()
    if isinstance(survivors, pl.DataFrame):
        return survivors.lazy()
    return survivors


def collect_mates(
    root: str,
    wanted: pl.DataFrame,
    shards: list[Shard],
    *,
    batch_rows: int = 1_000_000,
) -> pl.DataFrame:
    """Read the missing mates out of the store by key, without re-testing the bait.

    Only the shards of the partitions the orphans are in are opened, and each is filtered
    by a semi-join against the key set, so the cost is a read of those partitions and no
    k-mer work at all.
    """
    if wanted.height == 0:
        return pl.DataFrame(schema={})
    needed = {(int(lane), int(read)) for lane, read in wanted.select("lane", "read").rows()}
    frames: list[pl.DataFrame] = []
    for shard in shards:
        if (shard.lane, shard.read_num) not in needed:
            continue
        keys = wanted.filter(
            (pl.col("lane") == shard.lane) & (pl.col("read") == shard.read_num)
        ).select("tile", "x", "y")
        frame = pl.read_parquet(
            shard.url(root), columns=list(COLUMNS), storage_options=storage_options(root)
        ).with_columns(
            pl.lit(shard.lane, dtype=pl.Int64).alias("lane"),
            pl.lit(shard.read_num, dtype=pl.Int64).alias("read"),
        )
        found = frame.join(
            keys.with_columns(
                pl.col("tile").cast(frame.schema["tile"]),
                pl.col("x").cast(frame.schema["x"]),
                pl.col("y").cast(frame.schema["y"]),
            ),
            on=["tile", "x", "y"],
            how="semi",
        )
        if found.height:
            frames.append(found)
        del frame
    return pl.concat(frames) if frames else pl.DataFrame(schema={})


def runs(root: str) -> dict[tuple[int, int], RunFacts]:
    """The store's ``runs`` dimension, keyed by ``(lane, read)`` — the name rebuilder."""
    frame = pl.read_parquet(
        f"{root.rstrip('/')}/runs.parquet", storage_options=storage_options(root)
    )
    facts: dict[tuple[int, int], RunFacts] = {}
    for row in frame.iter_rows(named=True):
        facts[(int(row["lane"]), int(row["read_num"]))] = RunFacts(
            source=str(row["source"]),
            instrument=str(row["instrument"]),
            run=str(row["run"]),
            flowcell=str(row["flowcell"]),
            lane=int(row["lane"]),
            read_num=int(row["read_num"]),
            control=str(row["control"]),
            read_length=int(row["read_length"]),
        )
    return facts


def write_fastq(rows: pl.DataFrame, facts: dict[tuple[int, int], RunFacts], path: Path) -> int:
    """Write one mate's records, in pair-key order so both files stay aligned."""
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = rows.sort(list(PAIR_KEY))
    written = 0
    with path.open("w", encoding="ascii", newline="\n") as handle:
        for row in ordered.iter_rows(named=True):
            run = facts[(int(row["lane"]), int(row["read"]))]
            name = run.rebuild_name(
                tile=int(row["tile"]),
                x=int(row["x"]),
                y=int(row["y"]),
                is_filtered=bool(row["is_filtered"]),
                index_pair=str(row["index_pair"]),
            )
            handle.write(f"{name}\n{row['sequence']}\n+\n{row['quality']}\n")
            written += 1
    return written


def to_fastq(
    survivors: Survivors | pl.DataFrame,
    facts: dict[tuple[int, int], RunFacts],
    out_dir: Path,
    *,
    stem: str = "baited",
) -> Recovered:
    """Write complete pairs as ``<stem>_R1.fastq`` / ``<stem>_R2.fastq``.

    A fragment still missing a mate after :func:`collect_mates` is **dropped, not padded**
    — an aligner given an unpaired record in a paired run mis-assigns the insert size for
    every read after it. The dropped count is reported so the loss is visible rather than
    silent.
    """
    lazy = _lazy(survivors)
    if not lazy.collect_schema().names():
        return Recovered(files={}, fragments=0, orphans_filled=0, dropped=0)
    keyed = lazy.with_columns([pl.col(name).cast(pl.Int64) for name in (*PAIR_KEY, "read")])
    counts = (
        keyed.group_by(list(PAIR_KEY))
        .agg(pl.col("read").n_unique().alias("mates"))
        .collect(engine="streaming")
    )
    complete = counts.filter(pl.col("mates") == len(MATES)).select(list(PAIR_KEY))
    dropped = counts.height - complete.height
    if complete.height == 0:
        return Recovered(files={}, fragments=0, orphans_filled=0, dropped=dropped)
    files: dict[int, Path] = {}
    for mate in MATES:
        path = out_dir / f"{stem}_R{mate}.fastq"
        mine = (
            keyed.filter(pl.col("read") == mate)
            .join(complete.lazy(), on=list(PAIR_KEY), how="semi")
            .collect(engine="streaming")
        )
        write_fastq(mine, facts, path)
        files[mate] = path
    return Recovered(files=files, fragments=complete.height, orphans_filled=0, dropped=dropped)
