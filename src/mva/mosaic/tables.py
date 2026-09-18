"""The two histograms every mosaic model reads — and why they are histograms.

A whole-genome callset has millions of heterozygous calls. Every model in this package
treats the calls on one arm as **exchangeable** — it asks how the alternate-read fraction
is distributed, not which position showed what — and for such a model the counts

    how many calls showed *k* alternate reads out of *n*

carry the entire likelihood. Going from 2.8 million rows to ~20,000 distinct ``(k, n)``
pairs loses nothing a likelihood can see, makes every fit vectorised arithmetic over a
small array, and leaves no genomic position anywhere in the pipeline: there is nothing to
redact because nothing positional was ever loaded.

What it *does* cost is stated once, here, and repeated wherever a result is quoted:
**position is gone, so segmentation is gone.** A mosaic event confined to part of an arm
cannot be found by anything downstream of this module. Whole-arm and whole-chromosome
events can.

Two histograms, because they answer different questions:

* :class:`AlleleHistogram` — heterozygous calls only, keyed ``(k, n)``. Allele balance.
* :class:`DepthHistogram` — **every** PASS call, keyed by depth. Dosage. It cannot be
  derived from the first: depth at a heterozygous call is conditioned on that call
  existing, and the event most in need of a depth signal — a monosomy — is the one that
  removes heterozygous calls.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

import numpy as np

__all__ = [
    "AlleleHistogram",
    "DepthHistogram",
    "allele_histograms",
    "depth_histograms",
    "pool",
    "pool_depth",
]

#: A key is ``(chrom, arm)``. ``arm`` is ``p``, ``q``, ``cen`` or ``unplaced`` as
#: ``results.it2_mosaic_*`` spells it.
Key = tuple[str, str]


@dataclass(frozen=True)
class AlleleHistogram:
    """Heterozygous calls on one arm, as ``(k alternate of n total) -> how many``."""

    chrom: str
    arm: str
    #: alternate-read counts, one entry per distinct ``(k, n)`` pair
    k: np.ndarray
    #: total reads at the same pairs
    n: np.ndarray
    #: how many calls showed that pair
    sites: np.ndarray

    def __post_init__(self) -> None:
        if not (self.k.shape == self.n.shape == self.sites.shape):
            raise ValueError("k, n and sites must be the same length")
        if self.n.size and int(self.n.min()) <= 0:
            raise ValueError("a call with no reads has no allele balance")

    @property
    def label(self) -> str:
        return f"{self.chrom}{self.arm}"

    @property
    def n_sites(self) -> int:
        """Heterozygous calls represented, not distinct pairs."""
        return int(self.sites.sum())

    @property
    def baf(self) -> np.ndarray:
        """The B-allele fraction of each pair. Weight by :attr:`sites`, never by row."""
        return self.k / self.n

    @property
    def mean_depth(self) -> float:
        """Site-weighted mean of ``n``. Zero when the arm has no heterozygous call."""
        return float(np.average(self.n, weights=self.sites)) if self.n_sites else 0.0

    def weighted(self, values: np.ndarray) -> float:
        """The site-weighted mean of a per-pair quantity — the only correct average here."""
        return float(np.average(values, weights=self.sites)) if self.n_sites else 0.0

    def quantile(self, q: float) -> float:
        """A site-weighted quantile of the BAF, for the band split the DANFIP fit needs."""
        if not self.n_sites:
            return float("nan")
        order = np.argsort(self.baf)
        share = np.cumsum(self.sites[order]) / self.n_sites
        return float(self.baf[order][int(np.searchsorted(share, q, side="left"))])


@dataclass(frozen=True)
class DepthHistogram:
    """Every PASS call on one arm, as ``depth -> how many``."""

    chrom: str
    arm: str
    depth: np.ndarray
    sites: np.ndarray

    def __post_init__(self) -> None:
        if self.depth.shape != self.sites.shape:
            raise ValueError("depth and sites must be the same length")

    @property
    def label(self) -> str:
        return f"{self.chrom}{self.arm}"

    @property
    def n_sites(self) -> int:
        return int(self.sites.sum())

    @property
    def mean(self) -> float:
        return float(np.average(self.depth, weights=self.sites)) if self.n_sites else 0.0

    @property
    def variance(self) -> float:
        """Site-weighted variance. Compared against the mean it is the over-dispersion."""
        if not self.n_sites:
            return 0.0
        centred = self.depth - self.mean
        return float(np.average(centred**2, weights=self.sites))

    @property
    def variance_to_mean(self) -> float:
        """1.0 for a Poisson process. Real sequencing depth is always above it."""
        return self.variance / self.mean if self.mean else 0.0

    def expand(self) -> np.ndarray:
        """One entry per call. For a median or a bootstrap; large, so used deliberately."""
        return np.repeat(self.depth, self.sites)


def _column(rows: Sequence[Mapping[str, object]], name: str, dtype: type) -> np.ndarray:
    return np.array([row[name] for row in rows], dtype=dtype)


def allele_histograms(rows: Iterable[Mapping[str, object]]) -> dict[Key, AlleleHistogram]:
    """Group ``results.it2_mosaic_sites`` rows into one histogram per ``(chrom, arm)``."""
    grouped: dict[Key, list[Mapping[str, object]]] = {}
    for row in rows:
        grouped.setdefault((str(row["chrom"]), str(row["arm"])), []).append(row)
    return {
        key: AlleleHistogram(
            chrom=key[0],
            arm=key[1],
            k=_column(group, "k", int),
            n=_column(group, "n", int),
            sites=_column(group, "sites", float),
        )
        for key, group in grouped.items()
    }


def depth_histograms(rows: Iterable[Mapping[str, object]]) -> dict[Key, DepthHistogram]:
    """Group ``results.it2_mosaic_depth`` rows into one histogram per ``(chrom, arm)``."""
    grouped: dict[Key, list[Mapping[str, object]]] = {}
    for row in rows:
        grouped.setdefault((str(row["chrom"]), str(row["arm"])), []).append(row)
    return {
        key: DepthHistogram(
            chrom=key[0],
            arm=key[1],
            depth=_column(group, "depth", int),
            sites=_column(group, "sites", float),
        )
        for key, group in grouped.items()
    }


def pool(histograms: Sequence[AlleleHistogram], *, chrom: str, arm: str) -> AlleleHistogram:
    """Add histograms together — arms into a chromosome, or autosomes into a null.

    Summing counts is exact: the pooled histogram is the histogram of the pooled calls,
    which is not true of any summary statistic they might have been reduced to first.
    """
    if not histograms:
        return AlleleHistogram(chrom, arm, np.array([]), np.array([]), np.array([]))
    totals: dict[tuple[int, int], float] = {}
    for histogram in histograms:
        for key_k, key_n, count in zip(histogram.k, histogram.n, histogram.sites, strict=True):
            pair = (int(key_k), int(key_n))
            totals[pair] = totals.get(pair, 0.0) + float(count)
    pairs = sorted(totals)
    return AlleleHistogram(
        chrom=chrom,
        arm=arm,
        k=np.array([pair[0] for pair in pairs], dtype=int),
        n=np.array([pair[1] for pair in pairs], dtype=int),
        sites=np.array([totals[pair] for pair in pairs], dtype=float),
    )


def pool_depth(histograms: Sequence[DepthHistogram], *, chrom: str, arm: str) -> DepthHistogram:
    """The same addition for depth histograms."""
    totals: dict[int, float] = {}
    for histogram in histograms:
        for value, count in zip(histogram.depth, histogram.sites, strict=True):
            totals[int(value)] = totals.get(int(value), 0.0) + float(count)
    depths = sorted(totals)
    return DepthHistogram(
        chrom=chrom,
        arm=arm,
        depth=np.array(depths, dtype=int),
        sites=np.array([totals[value] for value in depths], dtype=float),
    )
