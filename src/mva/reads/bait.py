"""Sweep the whole read store once and keep the reads that touch a bait.

This is the step-2 counterpart of :mod:`mva.reads.scan`. Same store, same one-pass
discipline, opposite shape of question:

=========================  ==============================  ==============================
                           ``scan`` (step 0, entry 027)     ``bait`` (this module)
=========================  ==============================  ==============================
patterns                   up to 500 designed k-mers        ~40 million reference k-mers
survivors expected         dozens to thousands of reads     ~15 million reads
engine                     Polars ``contains_any``          :mod:`mva.kmer` uint64 lookup
what a hit means           "this exact allele is present"   "this read came from here"
=========================  ==============================  ==============================

**The pass is columnar and batched, not row-by-row.** Each shard is read once with only
the four columns this needs, then handed to the k-mer kernel in slices: the sequence
column arrives as one contiguous Arrow buffer, is reshaped into a ``(rows, read_length)``
matrix with no copying, and every read in the slice is tested in the same vectorised
operations. The cost is therefore set by bytes moved, not by read count.

**Both mates are kept, and that takes two passes.** R1 and R2 of one fragment share the
flowcell coordinate ``(lane, tile, x, y)``, which is the store's natural pair key
(:mod:`mva.reads.schema`). A fragment lying inside the baited region matches on both mates
and costs nothing extra; a fragment straddling the edge of the region matches on one. The
second pass (:mod:`mva.reads.recover`) collects those orphaned mates, and how many there
were is a reported number — it is the direct measure of how much the bait's edges cost.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock

import numpy as np
import polars as pl

from ..kmer import encode
from ..kmer.membership import Bait, hits
from .access import storage_options
from .schema import PREFIX

#: Reads handed to the k-mer kernel at once. The kernel allocates a handful of arrays of
#: ``batch x offsets`` uint64, so 200,000 rows is a few hundred MB of working set — the
#: same order as :data:`mva.reads.schema.ROW_GROUP_SIZE`, and for the same reason.
BATCH_ROWS = 200_000

#: Columns the sweep reads. The store's other columns are never touched, which is the
#: whole point of having converted FASTQ to Parquet.
COLUMNS = ("tile", "x", "y", "sequence", "quality", "is_filtered", "index_pair")

#: What the pair key is, stated once. R1 and R2 of one fragment share it.
PAIR_KEY = ("lane", "tile", "x", "y")


@dataclass(frozen=True)
class Survivors:
    """The reads a sweep kept — in memory, or spilled to Parquet parts on disk.

    One type for both so nothing downstream has to ask which mode the pass ran in. The
    lazy view is the only access every consumer needs; :meth:`collect` exists for tests
    and for the small frames (orphan keys) where materialising is the point.
    """

    frame: pl.DataFrame | None = None
    parts: tuple[Path, ...] | list[Path] = ()

    def lazy(self) -> pl.LazyFrame:
        if self.frame is not None:
            return self.frame.lazy()
        if not self.parts:
            return _empty().lazy()
        return pl.scan_parquet([str(part) for part in self.parts])

    def collect(self) -> pl.DataFrame:
        return self.frame if self.frame is not None else self.lazy().collect(engine="streaming")

    @property
    def spilled(self) -> bool:
        return self.frame is None


@dataclass(frozen=True)
class Shard:
    """One Parquet file of the store, and the partition it belongs to."""

    key: str
    lane: int
    read_num: int
    rows: int
    size: int

    def url(self, root: str) -> str:
        return f"{root.rstrip('/')}/{self.key.split(PREFIX + '/', 1)[-1]}"


@dataclass
class Funnel:
    """What the pass did, counted — the step's QC gate, not a log line."""

    shards: int = 0
    reads_scanned: int = 0
    reads_matched: int = 0
    seconds: float = 0.0
    by_partition: dict[str, int] = field(default_factory=dict)

    @property
    def matched_fraction(self) -> float:
        return self.reads_matched / self.reads_scanned if self.reads_scanned else 0.0

    def as_dict(self) -> dict[str, object]:
        return {
            "shards": self.shards,
            "reads_scanned": self.reads_scanned,
            "reads_matched": self.reads_matched,
            "matched_fraction": round(self.matched_fraction, 8),
            "seconds": round(self.seconds, 1),
            "by_partition": dict(self.by_partition),
        }


def manifest(root: str) -> list[Shard]:
    """Every shard of the store, from the companion table it publishes about itself.

    Reading the manifest rather than listing objects means the pass and
    :func:`mva.reads.verify.against_manifest` agree on what "the whole store" is.
    """
    frame = pl.read_parquet(
        f"{root.rstrip('/')}/manifest.parquet", storage_options=storage_options(root)
    )
    return [
        Shard(
            key=str(row["key"]),
            lane=int(row["lane"]),
            read_num=int(row["read_num"]),
            rows=int(row["rows"]),
            size=int(row["bytes"]),
        )
        for row in frame.iter_rows(named=True)
    ]


def code_matrix(sequences: pl.Series) -> np.ndarray:
    """A ``(rows, length)`` matrix of 2-bit codes from a Polars string column.

    Reads off one sequencer run are the same length, and Arrow stores a string column as
    one contiguous byte buffer plus offsets — so when every row has the same width the
    matrix is a reshape of that buffer with no copy and no Python loop. Ragged input (a
    trimmed store, a test fixture) falls back to padding with ``N``, which the encoder
    already treats as "no k-mer here".
    """
    rows = sequences.len()
    if rows == 0:
        return np.empty((0, 0), dtype=np.uint8)
    lengths = sequences.str.len_bytes().to_numpy()
    width = int(lengths.max())
    if int(lengths.min()) == width:
        flat = _contiguous_bytes(sequences, rows, width)
        if flat is not None:
            return encode.CODES[flat.reshape(rows, width)]
    padded = np.full((rows, width), ord("N"), dtype=np.uint8)
    for index, text in enumerate(sequences.to_list()):
        raw = (text or "").encode("ascii", errors="replace")
        padded[index, : len(raw)] = np.frombuffer(raw, dtype=np.uint8)
    return encode.CODES[padded]


def _contiguous_bytes(sequences: pl.Series, rows: int, width: int) -> np.ndarray | None:
    """The column's raw bytes as one flat array, or ``None`` if that is not possible.

    Arrow keeps a string column as an offsets buffer plus one values buffer, so when every
    row is the same width the bytes we want are already contiguous and the matrix is a
    view, not a copy. Anything unexpected — nulls, a chunked array, an offset layout this
    does not recognise — returns ``None`` and the caller falls back to the slow path
    rather than reading the wrong bytes confidently.
    """
    array = sequences.to_arrow()
    if hasattr(array, "combine_chunks"):
        array = array.combine_chunks()
    if array.null_count:
        return None
    buffers = array.buffers()
    if len(buffers) < 3 or buffers[1] is None or buffers[2] is None:
        return None
    index_type = np.int64 if "large" in str(array.type) else np.int32
    offsets = np.frombuffer(buffers[1], dtype=index_type)
    base = int(array.offset)
    if offsets.size < base + rows + 1:
        return None
    start, end = int(offsets[base]), int(offsets[base + rows])
    if end - start != rows * width:
        return None
    return np.frombuffer(buffers[2], dtype=np.uint8)[start:end]


def _batches(frame: pl.DataFrame, rows: int) -> Iterator[pl.DataFrame]:
    for start in range(0, frame.height, rows):
        yield frame.slice(start, rows)


def sweep_shard(
    shard: Shard, root: str, bait: Bait, *, stride: int, batch_rows: int = BATCH_ROWS
) -> pl.DataFrame:
    """Read one shard and return the rows whose read shares a k-mer with the bait."""
    frame = pl.read_parquet(
        shard.url(root), columns=list(COLUMNS), storage_options=storage_options(root)
    )
    kept: list[pl.DataFrame] = []
    for batch in _batches(frame, batch_rows):
        matched = hits(code_matrix(batch["sequence"]), bait, stride=stride)
        if matched.any():
            kept.append(batch.filter(pl.Series(matched)))
    if not kept:
        return frame.clear().with_columns(
            pl.lit(shard.lane, dtype=pl.Int64).alias("lane"),
            pl.lit(shard.read_num, dtype=pl.Int64).alias("read"),
        )
    return pl.concat(kept).with_columns(
        pl.lit(shard.lane, dtype=pl.Int64).alias("lane"),
        pl.lit(shard.read_num, dtype=pl.Int64).alias("read"),
    )


def sweep(
    root: str,
    bait: Bait,
    *,
    stride: int,
    shards: list[Shard] | None = None,
    batch_rows: int = BATCH_ROWS,
    spill_dir: Path | None = None,
    workers: int = 1,
    progress: Callable[[Shard, int, int], None] | None = None,
) -> tuple[Survivors, Funnel]:
    """One pass over the store; returns the matching reads and the funnel that counts it.

    ``shards`` narrows the pass — the scaling test and every unit test use it, and the
    full run leaves it ``None``. ``progress`` is called after each shard with the shard,
    the rows it held and the rows it kept, so a long pass can report without this module
    owning an opinion about logging.

    ``spill_dir`` is what makes the full pass safe on a machine whose memory we do not
    control. ~15 million recovered reads carrying their sequence and quality strings is
    several gigabytes, and holding them until the last of 272 shards is the shape of
    failure that wastes three hours and produces nothing. With a spill directory each
    shard's survivors are written as they are found and everything after reads them
    lazily; without one they are kept in memory, which is what the tests want.

    ``workers`` sweeps that many shards at once. Shards are independent — separate files,
    separate output parts, no shared state but the counters — and the per-shard cost is
    NumPy and Arrow work that releases the interpreter lock, so threads are the right
    shape here rather than processes that would each need their own copy of the bait.
    Memory scales with it: each worker holds one shard's batches, so ``workers`` is
    bounded by RAM, not by cores.
    """
    every = shards if shards is not None else manifest(root)
    funnel = Funnel()
    lock = Lock()
    kept: dict[int, pl.DataFrame] = {}
    parts: dict[int, Path] = {}
    if spill_dir is not None:
        spill_dir.mkdir(parents=True, exist_ok=True)

    def one(item: tuple[int, Shard]) -> None:
        index, shard = item
        matched = sweep_shard(shard, root, bait, stride=stride, batch_rows=batch_rows)
        height = matched.height
        if height and spill_dir is not None:
            part = spill_dir / f"survivors-{index:04d}.parquet"
            matched.write_parquet(part, compression="zstd")
            matched = matched.clear()
        with lock:
            partition = f"lane={shard.lane}/read={shard.read_num}"
            funnel.shards += 1
            funnel.reads_scanned += shard.rows
            funnel.reads_matched += height
            funnel.by_partition[partition] = funnel.by_partition.get(partition, 0) + height
            if height:
                if spill_dir is None:
                    kept[index] = matched
                else:
                    parts[index] = spill_dir / f"survivors-{index:04d}.parquet"
            if progress is not None:
                progress(shard, shard.rows, height)

    started = time.perf_counter()
    work = list(enumerate(every))
    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(one, work))
    else:
        for item in work:
            one(item)
    funnel.seconds = time.perf_counter() - started

    if spill_dir is not None:
        return Survivors(parts=[parts[key] for key in sorted(parts)]), funnel
    ordered = [kept[key] for key in sorted(kept)]
    return Survivors(frame=pl.concat(ordered) if ordered else _empty()), funnel


def _empty() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "tile": pl.UInt16,
            "x": pl.UInt32,
            "y": pl.UInt32,
            "sequence": pl.String,
            "quality": pl.String,
            "is_filtered": pl.Boolean,
            "index_pair": pl.String,
            "lane": pl.Int64,
            "read": pl.Int64,
        }
    )


def pair_keys(survivors: pl.LazyFrame | pl.DataFrame) -> pl.DataFrame:
    """The distinct fragments the sweep found, whichever mate matched."""
    lazy = survivors.lazy() if isinstance(survivors, pl.DataFrame) else survivors
    if not lazy.collect_schema().names():
        return pl.DataFrame(schema=dict.fromkeys(PAIR_KEY, pl.Int64))
    return (
        lazy.select([pl.col(name).cast(pl.Int64) for name in PAIR_KEY])
        .unique(maintain_order=False)
        .collect(engine="streaming")
    )
