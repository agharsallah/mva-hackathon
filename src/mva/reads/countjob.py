"""Count a probe set across the whole read store — the pass allele balance cannot replace.

:mod:`mva.reads.bait` sweeps the store and returns the reads that *touch* a k-mer set. That
is a membership question and it was the right one for step 2, which was selecting reads. A
dosage measurement asks something the boolean throws away: **how many times** each probe was
seen. A chromosome present in three copies instead of two contributes half again as many
reads, and only a count can say so.

**Why not the bait pass with counting bolted on.** ``hits`` samples every sixteenth window
and still answers membership correctly, because a read overlapping the set by enough bases
hits *some* sampled window. A sampled count is not a count: a probe occurring once in a read
is seen by exactly one window and sampling would miss it fifteen times in sixteen. This pass
reads every window, which is why it is its own verb rather than a flag on the other one.

**Why not ``mva.reads.scan``.** That counts, through a multi-literal string matcher validated
at twenty literals and capped in practice around five hundred. A per-chromosome dosage set is
a quarter of a million probes. Three orders of magnitude apart is a different data structure,
not the same one run longer — :mod:`mva.kmer.count` is that structure.

**Where it runs.** Beside the data. The store, PostgreSQL and the job service resolve to one
host, and a full pass costs minutes there against 4.2 hours streamed to a laptop (measured
2026-09-11: 55.8 s per shard, and parallelism buys nothing because the link saturates). The
result is a vector of counts, one per probe — a few hundred kilobytes — so unlike the bait
pass this one has nothing to publish and hands its answer back in the reply.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import polars as pl

from ..kmer.count import Tally, tally
from ..kmer.membership import Bait
from .access import storage_options
from .bait import BATCH_ROWS, COLUMNS, Shard, _batches, code_matrix, manifest

__all__ = ["CountResult", "count_shard", "load_probes", "run_count"]


@dataclass
class CountResult:
    """What one pass saw: the counts, and the arithmetic that says it was a whole pass."""

    counts: np.ndarray
    reads_scanned: int
    windows_scanned: int
    shards_swept: int
    shards_total: int
    probes: int
    workers: int
    seconds: float = 0.0
    notes: list[str] = field(default_factory=list)

    @property
    def observed(self) -> int:
        """Probes seen at least once. A large silent share is a broken probe set, not a zero."""
        return int(np.count_nonzero(self.counts))

    @property
    def complete(self) -> bool:
        return self.shards_swept == self.shards_total

    def as_dict(self) -> dict[str, object]:
        return {
            "reads_scanned": self.reads_scanned,
            "windows_scanned": self.windows_scanned,
            "shards_swept": self.shards_swept,
            "shards_total": self.shards_total,
            "complete": self.complete,
            "probes": self.probes,
            "observed": self.observed,
            "silent": self.probes - self.observed,
            "mean_count": round(float(self.counts.mean()), 4) if self.counts.size else 0.0,
            "workers": self.workers,
            "seconds": round(self.seconds, 1),
            "notes": list(self.notes),
        }


def count_shard(shard: Shard, root: str, probes: Bait, *, batch_rows: int = BATCH_ROWS) -> Tally:
    """Read one shard and tally every probe occurrence in it."""
    frame = pl.read_parquet(
        shard.url(root), columns=list(COLUMNS), storage_options=storage_options(root)
    )
    total = Tally(counts=np.zeros(len(probes), dtype=np.int64), reads_scanned=0, windows_scanned=0)
    for batch in _batches(frame, batch_rows):
        total = total.merged(tally(code_matrix(batch["sequence"]), probes))
    return total


def run_count(
    root: str,
    probes: Bait,
    *,
    shard_limit: int | None = None,
    workers: int = 1,
    batch_rows: int = BATCH_ROWS,
    progress: Callable[[Shard, int], None] | None = None,
) -> CountResult:
    """One counting pass over the store.

    ``shard_limit`` narrows it, which is what a timing probe and every test use; the full run
    leaves it ``None``. Shards are independent files with no shared state but the accumulator,
    and the per-shard work is NumPy over Arrow that releases the interpreter lock, so
    ``workers`` threads are the right shape here — the same reasoning as the bait sweep, and
    memory scales with it because each worker holds one shard's batches.
    """
    from concurrent.futures import ThreadPoolExecutor
    from threading import Lock

    every = manifest(root)
    shards = every[:shard_limit] if shard_limit is not None else every
    total = Tally(counts=np.zeros(len(probes), dtype=np.int64), reads_scanned=0, windows_scanned=0)
    lock = Lock()
    started = time.perf_counter()

    def one(shard: Shard) -> None:
        nonlocal total
        seen = count_shard(shard, root, probes, batch_rows=batch_rows)
        with lock:
            total = total.merged(seen)
            if progress is not None:
                progress(shard, int(seen.counts.sum()))

    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(one, shards))
    else:
        for shard in shards:
            one(shard)

    result = CountResult(
        counts=total.counts,
        reads_scanned=total.reads_scanned,
        windows_scanned=total.windows_scanned,
        shards_swept=len(shards),
        shards_total=len(every),
        probes=len(probes),
        workers=workers,
        seconds=time.perf_counter() - started,
    )
    if shard_limit is not None:
        result.notes.append(f"partial pass: {len(shards)} of {len(every)} shards")
    return result


def load_probes(path: Path, *, k: int = 31) -> Bait:
    """A probe set from the ``.npy`` the designer wrote — sorted, unique, ready to look up."""
    kmers = np.load(path)
    return Bait(np.sort(np.unique(kmers.astype(np.uint64))), k=k)
