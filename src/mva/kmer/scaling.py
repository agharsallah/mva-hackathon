"""How the membership kernel's cost grows with the size of the bait.

This is the plan's stage-4 gate, and it asks one question: does testing a read against
**40 million** reference k-mers cost meaningfully more than testing it against a thousand?
The answer decides whether a full pass over a billion reads is an hour or a week.

Three effects pull in different directions, which is why the curve has to be measured
rather than reasoned about:

* the sorted-array probe is ``O(log n)`` per k-mer — 10 comparisons at 10³, 25 at 10⁷,
  so a 2.5x growth in the part of the work that is a binary search;
* the bitmap prefilter's false-positive rate rises with occupancy (a fixed 2³⁰-bit map
  holding 10⁷ keys is ~1 % full, holding 4x10⁷ is ~4 %), so **more** windows survive the
  cheap test and reach the expensive one as the bait grows;
* against that, the per-read work that dominates at every size — decoding bases to 2-bit
  codes, rolling the windows, taking the canonical form — does not depend on the bait at
  all.

If the third effect dominates, the curve is flat and the engine's cost is set by bytes of
sequence, not by bait size. That is the claim stage 4 exists to test.

Reference sequence only: the pool this samples baits from is the reference bait, and the
reads are only ever counted, never returned.
"""

from __future__ import annotations

import resource
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from .encode import K
from .membership import DEFAULT_BITMAP_BITS, Bait, hits

__all__ = ["Point", "measure", "project", "sample_bait"]

#: Bait sizes the gate reports, one per decade. 10⁷ is the size the real bait actually is
#: (~36 M after the uniqueness filter), so the top of the curve is not an extrapolation.
DEFAULT_SIZES = (1_000, 10_000, 100_000, 1_000_000, 10_000_000)


@dataclass(frozen=True)
class Point:
    """One bait size, measured."""

    bait_kmers: int
    reads: int
    seconds: float
    hit_rate: float
    bait_bytes: int
    peak_rss_bytes: int

    @property
    def reads_per_second(self) -> float:
        return self.reads / self.seconds if self.seconds else 0.0

    def as_dict(self) -> dict[str, object]:
        return {
            "bait_kmers": self.bait_kmers,
            "reads": self.reads,
            "seconds": round(self.seconds, 3),
            "reads_per_second": round(self.reads_per_second, 1),
            "hit_rate": round(self.hit_rate, 6),
            "bait_mb": round(self.bait_bytes / 1e6, 1),
            "peak_rss_mb": round(self.peak_rss_bytes / 1e6, 1),
        }


def sample_bait(pool: np.ndarray, size: int, *, seed: int = 0, k: int = K) -> Bait:
    """A bait of ``size`` k-mers drawn without replacement from ``pool``.

    Drawn rather than taken from the front: the bait array is sorted, so its first
    thousand entries all share a leading 2-bit prefix and would make the binary search
    look artificially cheap and the bitmap artificially clustered.
    """
    if size >= pool.size:
        chosen = pool
    else:
        rng = np.random.default_rng(seed)
        chosen = pool[rng.choice(pool.size, size=size, replace=False)]
    return Bait.of(np.unique(chosen), k=k)


def _peak_rss() -> int:
    """Process high-water RSS in bytes.

    ``ru_maxrss`` carries no unit of its own: macOS reports bytes, Linux reports KiB.
    The platform decides it, not the magnitude — inferring from the number gives a
    plausible-looking answer that is wrong by 1024x, which is how this first read 1 TB.

    It is a **high-water mark for the whole process**, so it only ever climbs: read the
    series as the ceiling reached by the time each point finished, not as that point's
    own footprint. ``Point.bait_bytes`` is the exact per-point figure.
    """
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak if sys.platform == "darwin" else peak * 1024


def measure(
    codes: np.ndarray,
    pool: np.ndarray,
    sizes: Sequence[int] = DEFAULT_SIZES,
    *,
    stride: int,
    k: int = K,
    bitmap_bits: int = DEFAULT_BITMAP_BITS,
    seed: int = 0,
) -> list[Point]:
    """Time the kernel over the same reads at each bait size.

    ``codes`` is a ``(reads, length)`` 2-bit code matrix — the same object the sweep hands
    the kernel — so this measures the production path and not a reimplementation of it.
    """
    points: list[Point] = []
    for size in sizes:
        bait = sample_bait(pool, size, seed=seed, k=k)
        bait_bytes = len(bait) * 8 + (bitmap_bits // 8)
        hits(codes[:1], bait, stride)  # warm the code path, not the measurement
        started = time.perf_counter()
        found = hits(codes, bait, stride)
        elapsed = time.perf_counter() - started
        points.append(
            Point(
                bait_kmers=len(bait),
                reads=int(codes.shape[0]),
                seconds=elapsed,
                hit_rate=float(found.mean()) if found.size else 0.0,
                bait_bytes=bait_bytes,
                peak_rss_bytes=_peak_rss(),
            )
        )
    return points


def project(point: Point, total_reads: int) -> float:
    """Seconds the kernel alone would spend on ``total_reads`` at this point's rate.

    Kernel time only. It is a floor on a real pass, never an estimate of one: the pass
    also reads bytes off a disk or a network, and on the laptop that term dominated by an
    order of magnitude (55.8 s per shard of I/O, entry 085).
    """
    rate = point.reads_per_second
    return total_reads / rate if rate else float("inf")
