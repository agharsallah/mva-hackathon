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
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import polars as pl

from ..kmer.membership import Bait
from ..warehouse.settings import object_store
from ..warehouse.source import client
from . import recover
from .bait import Funnel, Shard, Survivors, manifest, pair_keys, sweep

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
    workers: int = 1
    seconds: float = 0.0
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "stride": self.stride,
            "bait_kmers": self.bait_kmers,
            "shards_swept": self.shards_swept,
            "workers": self.workers,
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


def publish(rows: pl.LazyFrame, key: str, staging: Path) -> tuple[str, int]:
    """Write the recovered reads as one zstd Parquet object and upload it.

    Streamed to disk rather than collected: the whole point of spilling the sweep is that
    the full survivor set never has to exist in memory at once, and materialising it here
    to write it would give that back at the last step.
    """
    store = object_store()
    staging.mkdir(parents=True, exist_ok=True)
    local = staging / Path(key).name
    rows.sink_parquet(local, compression="zstd")
    written = pl.scan_parquet(local).select(pl.len()).collect().item()
    client(store).upload_file(str(local), store.bucket, key)
    local.unlink(missing_ok=True)
    return f"s3://{store.bucket}/{key}", int(written)


def run_bait(
    root: str,
    bait: Bait,
    *,
    stride: int,
    out_key: str | None = None,
    shard_limit: int | None = None,
    collect_mates: bool = True,
    workers: int = 1,
    staging: Path | None = None,
    spill: bool = True,
    progress: Callable[[Shard, int, int], None] | None = None,
) -> tuple[Survivors, BaitResult]:
    """Sweep, fill the orphaned mates, and (when ``out_key`` is given) publish.

    Returns the survivors as well as the result, so a caller on the same machine skips the
    object store entirely — which is what the tests and the laptop route do.
    """
    started = time.perf_counter()
    every = manifest(root)
    shards = every[:shard_limit] if shard_limit is not None else every
    with ExitStack() as stack:
        scratch = staging or Path(stack.enter_context(TemporaryDirectory(prefix=STAGING)))
        scratch.mkdir(parents=True, exist_ok=True)
        spill_dir = scratch / "survivors" if spill else None
        survivors, funnel = sweep(
            root,
            bait,
            stride=stride,
            shards=shards,
            spill_dir=spill_dir,
            workers=workers,
            progress=progress,
        )
        missing = recover.orphans(survivors)
        filled_rows = 0
        if collect_mates and missing.height:
            filled = recover.collect_mates(
                root,
                missing,
                shards,
                spill_dir=spill_dir / "mates" if spill_dir else None,
                workers=workers,
            )
            filled_rows = pair_keys(filled.lazy()).height if filled.parts or filled.frame else 0
            if spill_dir is not None:
                survivors = Survivors(parts=[*survivors.parts, *filled.parts])
            elif filled.frame is not None and filled.frame.height:
                survivors = Survivors(
                    frame=pl.concat([survivors.collect(), filled.frame], how="diagonal")
                )
        result = BaitResult(
            funnel=funnel,
            fragments=pair_keys(survivors.lazy()).height,
            orphans=missing.height,
            orphans_filled=filled_rows,
            stride=stride,
            bait_kmers=len(bait),
            shards_swept=len(shards),
            workers=workers,
        )
        if shard_limit is not None:
            result.notes.append(f"partial pass: {len(shards)} of {len(every)} shards")
        if not collect_mates:
            result.notes.append("mates not collected: orphaned fragments are still half-present")
        if out_key:
            result.published, result.published_rows = publish(survivors.lazy(), out_key, scratch)
        result.seconds = time.perf_counter() - started
        if spill_dir is not None and staging is None:
            # The scratch directory is about to be removed with the parts in it, so the
            # handle we hand back must not still point at them.
            survivors = Survivors(frame=_empty_like(survivors))
        return survivors, result


def _empty_like(survivors: Survivors) -> pl.DataFrame:
    """An empty frame with the survivors' schema — what a caller gets when the parts the
    handle referred to lived in a temporary directory that has now gone."""
    return survivors.lazy().limit(0).collect()


def write_report(result: BaitResult, path: Path) -> Path:
    """The pass's numbers as JSON, so no figure or entry ever retypes one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_bait(path: Path, *, k: int = 31) -> Bait:
    """A bait array from the local filesystem — the laptop route's entry point."""
    return Bait.of(np.load(path), k=k)
