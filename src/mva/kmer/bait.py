"""Cut the bait: which stretches of the reference we want reads from, and their k-mers.

**Bait** is this step's name for the reference sequence of the regions we care about,
chopped into k-mers. A read from one of those regions shares k-mers with it even when the
read carries a variant: one substitution kills the ``k`` windows that span it and leaves
every other window of the read intact, so a variant-carrying read is still recovered. That
is the property the whole step rests on, and it is why the bait is cut from the
**reference** and carries no patient information.

**Padding is a decision, not a default.** A gene's coding exons are a few thousand bases;
a structural variant that removes one has its breakpoints in the introns around it, and a
splice-disrupting allele sits just outside the exon. So intervals are padded, and by how
much is per tier: the plan fixes core ±50 kb (structural reach) and net ±2 kb (splice and
near-intronic). Both numbers are inputs here, never hard-coded.

**Merging matters for the arithmetic, not the result.** Overlapping padded exons of the
same gene would otherwise be encoded several times; the k-mer set is a set either way, but
the reported "bait bp" — the number the expected-recovery gate is computed from — would be
wrong. So intervals are merged per contig before anything is counted.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import fasta
from .encode import K, codes_of, window_kmers
from .membership import DEFAULT_BITMAP_BITS, Bait


@dataclass(frozen=True)
class Interval:
    """A half-open reference range, bare contig spelling, 0-based."""

    contig: str
    start: int
    end: int

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError(f"empty interval {self.contig}:{self.start}-{self.end}")

    def padded(self, padding: int, limit: int | None = None) -> Interval:
        end = self.end + padding
        return Interval(
            contig=self.contig,
            start=max(0, self.start - padding),
            end=end if limit is None else min(end, limit),
        )


@dataclass(frozen=True)
class BaitPlan:
    """What will be cut, and how much of it there is — printed before any pass runs."""

    intervals: tuple[Interval, ...]
    bases: int
    by_contig: dict[str, int]

    @property
    def contigs(self) -> set[str]:
        return {interval.contig for interval in self.intervals}


def merge(intervals: Iterable[Interval]) -> tuple[Interval, ...]:
    """Sorted, non-overlapping intervals — so ``bases`` counts every base once."""
    ordered = sorted(intervals, key=lambda i: (i.contig, i.start, i.end))
    merged: list[Interval] = []
    for interval in ordered:
        if merged and merged[-1].contig == interval.contig and interval.start <= merged[-1].end:
            last = merged[-1]
            if interval.end > last.end:
                merged[-1] = Interval(last.contig, last.start, interval.end)
            continue
        merged.append(interval)
    return tuple(merged)


def plan(intervals: Iterable[Interval]) -> BaitPlan:
    """Merge the intervals and count what the pass will cost."""
    merged = merge(intervals)
    by_contig: dict[str, int] = {}
    for interval in merged:
        by_contig[interval.contig] = by_contig.get(interval.contig, 0) + (
            interval.end - interval.start
        )
    return BaitPlan(intervals=merged, bases=sum(by_contig.values()), by_contig=by_contig)


def expected_reads(bases: int, depth: float, read_length: int) -> float:
    """How many reads a region of ``bases`` should contribute at this depth.

    Depth is bases sequenced per reference base, so a region of *b* bases was covered by
    ``b * depth`` sequenced bases, which is ``b * depth / read_length`` reads. The gate
    around this number is 0.5-2x: below it the bait or the scan lost reads, above it the
    bait is catching something it should not (a repeat that survived the uniqueness
    filter). Both are findings, not warnings.
    """
    if read_length <= 0:
        raise ValueError("read length must be positive")
    return bases * depth / read_length


def cut(
    reference: Path,
    intervals: Iterable[Interval],
    *,
    k: int = K,
    bits: int | None = DEFAULT_BITMAP_BITS,
) -> tuple[Bait, BaitPlan]:
    """Read the reference once and return the canonical k-mer set of these intervals.

    Windows containing a base that is not A/C/G/T (an assembly gap, a masked region) are
    dropped: they have no k-mer to match against.
    """
    laid_out = plan(intervals)
    per_contig: dict[str, list[Interval]] = {}
    for interval in laid_out.intervals:
        per_contig.setdefault(interval.contig, []).append(interval)
    collected: list[np.ndarray] = []
    for contig in fasta.contigs(reference, wanted=set(per_contig)):
        codes = codes_of(contig.bases)
        for interval in per_contig[contig.name]:
            window = codes[interval.start : min(interval.end, codes.size)]
            if window.size < k:
                continue
            kmers, valid = window_kmers(window, k)
            collected.append(kmers[valid])
    joined = np.concatenate(collected) if collected else np.empty(0, dtype=np.uint64)
    return Bait.of(joined, k=k, bits=bits), laid_out


@dataclass(frozen=True)
class Coverage:
    """How much usable bait one labelled set of intervals actually has.

    The headline off-target percentage is a genome-wide average and can hide the thing it
    is a proxy for: a region whose k-mers are *all* repetitive contributes no bait at all,
    and reads from it are then missing for a reason that has nothing to do with the
    sample. This is that number per label — per gene, per tier, per exon — so a later
    absence can be read against the bait density where it was observed.
    """

    label: str
    bases: int
    windows: int
    surviving: int

    @property
    def density(self) -> float:
        """Surviving k-mers per base. ~1.0 where every window is unique, 0 where none is."""
        return self.surviving / self.bases if self.bases else 0.0

    @property
    def lost(self) -> float:
        return 1.0 - (self.surviving / self.windows) if self.windows else 0.0


def profile(
    reference: Path,
    kept: Bait,
    by_label: dict[str, list[Interval]],
    *,
    k: int = K,
) -> dict[str, Coverage]:
    """Per-label bait density after the uniqueness filter, in one reference pass.

    ``by_label`` maps any label — a gene symbol, a tier, an exon id — to its intervals.
    Windows are counted with their multiplicity within the label, because what matters
    downstream is how much of the region is *reachable*, not how many distinct integers it
    contributed to the global set.
    """
    per_contig: dict[str, list[tuple[str, Interval]]] = {}
    tally: dict[str, list[int]] = {label: [0, 0, 0] for label in by_label}
    for label, intervals in by_label.items():
        for interval in merge(intervals):
            per_contig.setdefault(interval.contig, []).append((label, interval))
    for contig in fasta.contigs(reference, wanted=set(per_contig)):
        codes = codes_of(contig.bases)
        for label, interval in per_contig[contig.name]:
            window = codes[interval.start : min(interval.end, codes.size)]
            counts = tally[label]
            counts[0] += int(window.size)
            if window.size < k:
                continue
            kmers, valid = window_kmers(window, k)
            usable = kmers[valid]
            counts[1] += int(usable.size)
            counts[2] += int(kept.contains(usable).sum())
    return {
        label: Coverage(label=label, bases=counts[0], windows=counts[1], surviving=counts[2])
        for label, counts in tally.items()
    }


def from_regions(
    rows: Sequence[tuple[str, int, int, str]],
    padding_by_tier: dict[str, int],
    default_padding: int,
) -> tuple[Interval, ...]:
    """Turn ``(contig, start, end, tier)`` rows into padded intervals.

    The tier is the target set's own column (``core`` / ``net`` / ``mechanism-term`` /
    ``decoy``), so the padding decision travels with the gene rather than being applied by
    a caller that has to remember which list it is holding.
    """
    return tuple(
        Interval(contig, int(start), int(end)).padded(padding_by_tier.get(tier, default_padding))
        for contig, start, end, tier in rows
    )
