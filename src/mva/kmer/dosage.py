"""How many copies of a chromosome are in this sample — counted, not aligned.

A chromosome present in extra copies contributes more reads, so a fixed set of reference
k-mers taken from it is seen more often. That is the whole idea, and it is the only route in
this package that can see a chromosome with **no heterozygous sites at all**: the male X, or
a gain that is present in every cell. Allele balance is blind to both.

**Two denominators, and their disagreement is a reported column.**

*Relative.* Each chromosome's mean probe count divided by the median across autosomes. Easy
to read and easy to trust wrongly: it assumes most chromosomes are normal, which is exactly
what *variegated* aneuploidy is not.

*Absolute.* The same counts divided by the genome-wide calibration set's own mean — k-mer
mass per probe, which no single chromosome can move. Noisier, and it does not care how many
chromosomes are abnormal.

Where the two agree the denominator was sound for that chromosome. Where they disagree by
more than the others do, the median moved — which is defence (c) of the iteration-2 plan
expressed as a number rather than as an argument.

**The interval is a bootstrap over probes, not over reads.** Resampling the probe set says
how much of a chromosome's estimate is the particular k-mers that survived the uniqueness
filter, which is the error a caller can actually do something about. Read-level sampling
noise is inside each probe's count already.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from .chromosome import CALIBRATION_NAME, ChromosomeProbes

__all__ = [
    "LEVEL",
    "RESAMPLES",
    "Composition",
    "Dosage",
    "absolute_scale",
    "composition",
    "dosage",
    "gc_fraction",
]

#: The project's interval convention, restated rather than imported. ``mva.kmer`` is a leaf
#: package -- pure NumPy over reference sequence, importing no sibling -- and
#: :mod:`mva.pipeline.nulls` sits on the same row, so the two cannot import each other.
#: ``tests/test_kmer_dosage.py`` asserts these equal that module's, which turns a copied
#: constant from a drift risk into a checked one.
RESAMPLES = 1_000
LEVEL = 0.95


@dataclass(frozen=True)
class Dosage:
    """One chromosome's copy signal, against both denominators."""

    chrom: str
    probes: int
    #: probes that were never seen at all -- a set of silent probes is a warning, not a zero
    silent: int
    mean_count: float
    #: mean count ÷ the autosomal median. 1.0 is two copies, 1.5 is three, 0.5 is one
    relative: float
    low: float
    high: float
    #: mean count ÷ the calibration set's mean. Same units, no assumption about chromosomes
    absolute: float

    @property
    def disagreement(self) -> float:
        """How far the two denominators are apart for this chromosome."""
        return self.relative - self.absolute

    @property
    def silent_share(self) -> float:
        return self.silent / self.probes if self.probes else 0.0

    def as_dict(self) -> dict[str, object]:
        return {
            "chrom": self.chrom,
            "probes": self.probes,
            "silent": self.silent,
            "silent_share": round(self.silent_share, 4),
            "mean_count": round(self.mean_count, 3),
            "relative": round(self.relative, 4),
            "low": round(self.low, 4),
            "high": round(self.high, 4),
            "absolute": round(self.absolute, 4),
            "disagreement": round(self.disagreement, 4),
        }


def _per_contig(
    counts: np.ndarray, probes: ChromosomeProbes, kmers: np.ndarray | None = None
) -> dict[str, np.ndarray]:
    """Split a count vector into one array per contig.

    ``kmers`` is the **sorted unique** array the counts are indexed by -- which is what a
    counting pass actually returns, because a lookup structure holds each k-mer once. The
    design is deliberately not deduplicated: the calibration set is drawn from the
    per-chromosome pool, so a probe can belong to two groups and its single count is read by
    both. Without the mapping the two vectors are different lengths, and the mismatch fails
    in the worst possible way -- an off-by-one that still produces plausible dosages.

    Omitting ``kmers`` means the counts are already in the design's own order, which is what
    a caller that tallied the design directly has.
    """
    if kmers is None:
        if counts.size != len(probes):
            raise ValueError(
                f"counts has {counts.size} entries for {len(probes)} probes: "
                "the tally and the probe set are not from the same design"
            )
        slots = np.arange(len(probes))
    else:
        if counts.size != kmers.size:
            raise ValueError(
                f"counts has {counts.size} entries for {kmers.size} counted k-mers: "
                "the tally and the k-mer array are not from the same pass"
            )
        slots = np.searchsorted(kmers, probes.kmers)
        if slots.size and (
            int(slots.max()) >= kmers.size or not np.array_equal(kmers[slots], probes.kmers)
        ):
            raise ValueError(
                "a probe in the design is absent from the counted k-mers: "
                "the probe set and the pass are not from the same build"
            )
    return {name: counts[slots[probes.owner == index]] for index, name in enumerate(probes.contigs)}


def absolute_scale(
    counts: np.ndarray, probes: ChromosomeProbes, kmers: np.ndarray | None = None
) -> float:
    """The calibration set's mean count — the denominator that assumes nothing.

    Returns ``nan`` when the design carried no calibration set, which is a statement the
    caller must handle rather than a zero it can divide by.
    """
    blocks = _per_contig(counts, probes, kmers)
    calibration = blocks.get(CALIBRATION_NAME)
    if calibration is None or not calibration.size:
        return float("nan")
    return float(calibration.mean())


def dosage(
    counts: np.ndarray,
    probes: ChromosomeProbes,
    *,
    kmers: np.ndarray | None = None,
    autosomes: Mapping[str, bool] | None = None,
    seed: int = 0,
    resamples: int = RESAMPLES,
    level: float = LEVEL,
) -> tuple[Dosage, ...]:
    """Per-chromosome dosage against both denominators, with a probe bootstrap.

    ``autosomes`` names which contigs may enter the relative denominator; by default every
    contig whose name is a number. X and Y must not: one copy of each is the expectation in
    a male proband, and including them would drag the median every autosome is judged by.
    """
    blocks = _per_contig(counts, probes, kmers)
    blocks.pop(CALIBRATION_NAME, None)
    is_autosome = autosomes or {name: name.isdigit() for name in blocks}

    means = {
        name: float(values.mean()) if values.size else float("nan")
        for name, values in blocks.items()
    }
    pool = [means[name] for name in means if is_autosome.get(name) and np.isfinite(means[name])]
    denominator = float(np.median(pool)) if pool else float("nan")
    scale = absolute_scale(counts, probes, kmers)

    rng = np.random.default_rng(seed)
    tail = (1.0 - level) / 2.0
    results: list[Dosage] = []
    for name, values in blocks.items():
        if not values.size:
            continue
        draws = np.array(
            [
                float(rng.choice(values, size=values.size, replace=True).mean())
                for _ in range(resamples)
            ]
        )
        low, high = (float(value / denominator) for value in np.quantile(draws, [tail, 1.0 - tail]))
        results.append(
            Dosage(
                chrom=name,
                probes=int(values.size),
                silent=int(np.count_nonzero(values == 0)),
                mean_count=means[name],
                relative=means[name] / denominator if denominator else float("nan"),
                low=low,
                high=high,
                absolute=means[name] / scale if scale and np.isfinite(scale) else float("nan"),
            )
        )
    return tuple(results)


@dataclass(frozen=True)
class Composition:
    """What a chromosome's *sequence* predicts about its dosage, before biology is invoked.

    A dosage is a count, and counts in short-read sequencing depend on GC content: library
    preparation and amplification favour some compositions over others, by a few per cent
    across a whole chromosome. That is the same size as a low-fraction mosaic gain, so the
    two are confusable and the bootstrap interval cannot tell them apart -- it resamples
    probes, which measures counting noise and says nothing about a bias shared by every
    probe on the chromosome.

    This is the correction: regress each chromosome's dosage on its GC, and report the
    residual. A spread that the composition explains is an instrument property; what
    survives is what a copy-number claim may be made from.

    **Which GC matters, and it is not the probes'.** Pass ``gc`` to regress on the
    chromosome's own composition, measured from the reference. Two reasons, both settled
    before any residual was looked at. Mechanically, GC bias acts on *fragments* of a few
    hundred bases, so a 31-mer's own GC is the wrong scale. Practically, the surviving
    probes are a filtered sample: the uniqueness filter removes repetitive sequence, which
    is not composed like the chromosome around it, so probe GC can understate a chromosome's
    by two points or more -- and a chromosome whose probes understate its GC gets a positive
    residual manufactured for it by the fit. Omitting ``gc`` falls back to probe GC, which
    needs no reference at hand and carries exactly that risk.
    """

    #: The GC fraction each contig was regressed on, and where it came from.
    gc: Mapping[str, float]
    source: str
    #: Dosage with the fitted composition trend removed, recentred on one.
    residual: Mapping[str, float]
    #: Pearson correlation of dosage against probe GC, across the contigs fitted.
    correlation: float
    #: Dosage per unit GC fraction, and the intercept, as fitted.
    slope: float
    intercept: float
    #: Standard deviation across the fitted contigs, before and after the trend is removed.
    spread: float
    residual_spread: float
    fitted: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "correlation": round(self.correlation, 4),
            "slope": round(self.slope, 4),
            "intercept": round(self.intercept, 4),
            "spread": round(self.spread, 5),
            "residual_spread": round(self.residual_spread, 5),
            "fitted": list(self.fitted),
            "gc": {name: round(value, 5) for name, value in self.gc.items()},
            "residual": {name: round(value, 5) for name, value in self.residual.items()},
        }


def gc_fraction(codes: np.ndarray, k: int) -> np.ndarray:
    """The GC share of each 2-bit packed k-mer, without decoding it to letters.

    The encoding is ``A=00 C=01 G=10 T=11``, so a base is G or C exactly when its two bits
    differ. Taking the even and odd bit planes and XOR-ing them turns "is this base G or C"
    into one bit per base, and the popcount of that is the answer -- which keeps a million
    k-mers in integer arrays instead of in strings.
    """
    packed = codes.astype(np.uint64)
    low = packed & np.uint64(0x5555555555555555)  # the 1s bit of every base
    high = (packed >> np.uint64(1)) & np.uint64(0x5555555555555555)  # the 2s bit
    # One surviving bit per G or C, then count them. Bases above the k-th are zero in both
    # planes, so they XOR to zero and cannot be miscounted as an A.
    return np.bitwise_count(low ^ high).astype(np.float64) / k


def composition(
    rows: tuple[Dosage, ...],
    probes: ChromosomeProbes,
    *,
    exclude: frozenset[str] = frozenset(),
    gc: Mapping[str, float] | None = None,
) -> Composition:
    """Fit each contig's dosage against its GC content and report the residual.

    ``gc`` is the composition to regress on, per contig, and should be the chromosome's own
    from the reference; without it the probes' mean GC is used and the docstring above says
    what that costs. ``exclude`` names contigs that must not enter the fit because their
    dosage is not a copy-number-one measurement -- the sex chromosomes in a male proband,
    whose true ratio is a half and would dominate any regression through them.
    """
    source = "reference chromosome GC" if gc is not None else "probe GC"
    if gc is None:
        per_contig = _per_contig(probes.kmers, probes)
        gc = {
            name: float(gc_fraction(codes, probes.k).mean())
            for name, codes in per_contig.items()
            if codes.size
        }
    fitted = tuple(row.chrom for row in rows if row.chrom not in exclude and row.chrom in gc)
    x = np.array([gc[name] for name in fitted])
    y = np.array([row.relative for row in rows if row.chrom in fitted])
    slope, intercept = np.polyfit(x, y, 1) if x.size > 2 else (0.0, float(y.mean()))
    predicted = slope * x + intercept
    residual = y - predicted + 1.0
    correlation = float(np.corrcoef(x, y)[0, 1]) if x.size > 2 else 0.0
    return Composition(
        gc=dict(gc),
        source=source,
        residual=dict(zip(fitted, (float(value) for value in residual), strict=True)),
        correlation=correlation,
        slope=float(slope),
        intercept=float(intercept),
        spread=float(y.std(ddof=1)),
        residual_spread=float(residual.std(ddof=1)),
        fitted=fitted,
    )
