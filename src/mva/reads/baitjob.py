"""One bait pass, end to end — the verb behind both the CLI and ``POST /bait``.

The pass is the only part of step 2 that cannot run where the analysis runs. Measured on
2026-09-11 from the laptop: 55.8 s per shard whether one shard streams or eight in
parallel, so 272 shards is ~4.2 h and the object-store link, not the CPU, is the wall. The
same pass beside the data reads local disk at ~190 MB/s (step-0 entry 027). So the sweep
is packaged as a job that can run either side of that link, with identical code, and the
side it ran on is recorded with its result.

**What crosses the wire is Parquet, not FASTQ.** ~15 million recovered reads are not an
HTTP response and not a good gzip either: the store's quality strings are NovaSeq's
four-level binning, which a columnar format compresses far harder than a text one. The job
publishes one Parquet object; the caller pulls it and runs :func:`mva.reads.recover.to_fastq`
where its aligner lives.

**Nothing here decides anything.** The stride, the bait and the gate thresholds are the
caller's, pre-registered before the run; this module streams, counts and publishes.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import polars as pl

from ..kmer.membership import Bait
from ..warehouse.settings import object_store
from ..warehouse.source import client
from . import recover
from .bait import Funnel, Shard, manifest, sweep

#: Where a job stages bytes it is about to upload, when the caller names nothing.
STAGING = "mva-bait"


@dataclass
class BaitResult:
    """Everything the pass measured, in the shape the QC gate and the entry both read."""

    funnel: Funnel
    fragments: int
    orphans: int
    orphans_filled: int
    published: str = ""
    published_rows: int = 0
    stride: int = 1
    bait_kmers: int = 0
    shards_swept: int = 0
    seconds: float = 0.0
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "stride": self.stride,
            "bait_kmers": self.bait_kmers,
            "shards_swept": self.shards_swept,
            "fragments": self.fragments,
            "orphans": self.orphans,
            "orphans_filled": self.orphans_filled,
            "orphan_fraction": round(self.orphans / self.fragments, 6) if self.fragments else 0.0,
            "published": self.published,
            "published_rows": self.published_rows,
            "seconds": round(self.seconds, 1),
            "notes": list(self.notes),
            **self.funnel.as_dict(),
        }


def fetch_bait(key: str, into: Path, *, k: int = 31) -> Bait:
    """Download the bait array named by object key and index it for lookup."""
    store = object_store()
    into.parent.mkdir(parents=True, exist_ok=True)
    client(store).download_file(store.bucket, key, str(into))
    return Bait.load(into, k=k)


def publish(frame: pl.DataFrame, key: str, staging: Path) -> tuple[str, int]:
    """Write the recovered reads as one zstd Parquet object and upload it."""
    store = object_store()
    staging.mkdir(parents=True, exist_ok=True)
    local = staging / Path(key).name
    frame.write_parquet(local, compression="zstd")
    client(store).upload_file(str(local), store.bucket, key)
    local.unlink(missing_ok=True)
    return f"s3://{store.bucket}/{key}", frame.height


def run_bait(
    root: str,
    bait: Bait,
    *,
    stride: int,
    out_key: str | None = None,
    shard_limit: int | None = None,
    collect_mates: bool = True,
    staging: Path | None = None,
    progress: Callable[[Shard, int, int], None] | None = None,
) -> tuple[pl.DataFrame, BaitResult]:
    """Sweep, fill the orphaned mates, and (when ``out_key`` is given) publish.

    Returns the recovered rows as well as the result, so a caller on the same machine
    skips the object store entirely — which is what the tests and the laptop route do.
    """
    started = time.perf_counter()
    every = manifest(root)
    shards = every[:shard_limit] if shard_limit is not None else every
    survivors, funnel = sweep(root, bait, stride=stride, shards=shards, progress=progress)
    missing = recover.orphans(survivors)
    filled = pl.DataFrame(schema={})
    if collect_mates and missing.height:
        filled = recover.collect_mates(root, missing, shards)
    rows = pl.concat([survivors, filled], how="diagonal") if filled.height else survivors
    result = BaitResult(
        funnel=funnel,
        fragments=_fragments(rows),
        orphans=missing.height,
        orphans_filled=filled.height,
        stride=stride,
        bait_kmers=len(bait),
        shards_swept=len(shards),
    )
    if shard_limit is not None:
        result.notes.append(f"partial pass: {len(shards)} of {len(every)} shards")
    if not collect_mates:
        result.notes.append("mates not collected: orphaned fragments are still half-present")
    if out_key:
        if staging is not None:
            result.published, result.published_rows = publish(rows, out_key, staging)
        else:
            with TemporaryDirectory(prefix=STAGING) as scratch:
                result.published, result.published_rows = publish(rows, out_key, Path(scratch))
    result.seconds = time.perf_counter() - started
    return rows, result


def _fragments(rows: pl.DataFrame) -> int:
    from .bait import pair_keys

    return pair_keys(rows).height


def write_report(result: BaitResult, path: Path) -> Path:
    """The pass's numbers as JSON, so no figure or entry ever retypes one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_bait(path: Path, *, k: int = 31) -> Bait:
    """A bait array from the local filesystem — the laptop route's entry point."""
    return Bait.of(np.load(path), k=k)
