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

__all__ = ["LEVEL", "RESAMPLES", "Dosage", "absolute_scale", "dosage"]

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


def _per_contig(counts: np.ndarray, probes: ChromosomeProbes) -> dict[str, np.ndarray]:
    """Split a flat count vector into one array per contig, in the probe set's own order."""
    if counts.size != len(probes):
        raise ValueError(
            f"counts has {counts.size} entries for {len(probes)} probes: "
            "the tally and the probe set are not from the same design"
        )
    return {name: counts[probes.owner == index] for index, name in enumerate(probes.contigs)}


def absolute_scale(counts: np.ndarray, probes: ChromosomeProbes) -> float:
    """The calibration set's mean count — the denominator that assumes nothing.

    Returns ``nan`` when the design carried no calibration set, which is a statement the
    caller must handle rather than a zero it can divide by.
    """
    blocks = _per_contig(counts, probes)
    calibration = blocks.get(CALIBRATION_NAME)
    if calibration is None or not calibration.size:
        return float("nan")
    return float(calibration.mean())


def dosage(
    counts: np.ndarray,
    probes: ChromosomeProbes,
    *,
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
    blocks = _per_contig(counts, probes)
    blocks.pop(CALIBRATION_NAME, None)
    is_autosome = autosomes or {name: name.isdigit() for name in blocks}

    means = {
        name: float(values.mean()) if values.size else float("nan")
        for name, values in blocks.items()
    }
    pool = [means[name] for name in means if is_autosome.get(name) and np.isfinite(means[name])]
    denominator = float(np.median(pool)) if pool else float("nan")
    scale = absolute_scale(counts, probes)

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
