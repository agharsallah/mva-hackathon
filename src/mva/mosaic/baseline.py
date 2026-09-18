"""The baseline every route divides by — and the failure mode this disease is named after.

Allele balance, read depth and k-mer dosage are all **relative** measurements: a chromosome
is judged against the rest of the genome. That works when the rest of the genome is normal.
Kong 2018's discussion says the model degrades when several chromosomes are abnormal at
once, and *variegated* aneuploidy is exactly that — a different chromosome in different
cells. All three routes therefore share one failure mode, and it is the one this disease
would produce.

Three defences, pre-registered, two of them here:

**(a) Leave one chromosome out.** The baseline is the median of the per-chromosome
estimates with each chromosome held out in turn, not the median of all of them. A
chromosome whose exclusion moves the baseline further than the bootstrap interval is
**flagged** — not corrected, not dropped. A flag says the genome-wide assumption is under
strain on this sample; silently correcting would hide the very thing worth reporting.

**(c) An absolute scale.** :func:`absolute_shift` compares a relative estimate against one
that does not divide by anything — total k-mer mass per base, from the reads route. Where
the two disagree, the median denominator is what moved. The dosage route supplies that
number; this module only knows how to compare the two.

Defence (b), injecting several abnormal chromosomes at once, lives in
:mod:`~mva.mosaic.simulate` because it is a simulation rather than an estimator.

**The interval convention is the project's.** :func:`~mva.pipeline.nulls.separation` fixes
1,000 seeded resamples at 95 %% everywhere in this repository, and the bootstrap here uses
the same two constants so that an interval printed by step 8 means what an interval printed
by step 4 means.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from ..pipeline.nulls import LEVEL, RESAMPLES

__all__ = ["Baseline", "absolute_shift", "leave_one_out"]


@dataclass(frozen=True)
class Baseline:
    """The genome-wide reference value, and whether any one chromosome is holding it up."""

    #: the median over all chromosomes, for reference
    median: float
    #: the median of the leave-one-out medians -- the value to divide by
    robust: float
    low: float
    high: float
    #: chromosome -> the baseline when it alone is held out
    without: dict[str, float]
    #: chromosomes whose exclusion moves the baseline outside the interval
    shifted: tuple[str, ...]
    resamples: int
    level: float

    @property
    def stable(self) -> bool:
        """True when no single chromosome can move the baseline beyond its own noise."""
        return not self.shifted

    @property
    def width(self) -> float:
        return self.high - self.low

    def as_dict(self) -> dict[str, object]:
        return {
            "median": round(self.median, 5),
            "robust": round(self.robust, 5),
            "low": round(self.low, 5),
            "high": round(self.high, 5),
            "width": round(self.width, 5),
            "shifted": list(self.shifted),
            "stable": self.stable,
            "resamples": self.resamples,
            "level": self.level,
            "without": {name: round(value, 5) for name, value in sorted(self.without.items())},
        }


def leave_one_out(
    estimates: Mapping[str, float],
    *,
    seed: int = 0,
    resamples: int = RESAMPLES,
    level: float = LEVEL,
) -> Baseline:
    """The robust baseline, its interval, and every chromosome that can move it.

    ``estimates`` is one number per chromosome — a mean depth, a dosage ratio, a Bdev.
    Nothing here knows which; that is what makes the same function serve all three routes.
    """
    names = [name for name, value in estimates.items() if np.isfinite(value)]
    values = np.array([estimates[name] for name in names], dtype=float)
    if values.size < 3:
        # Two chromosomes cannot say whether one of them is the odd one out.
        median = float(np.median(values)) if values.size else float("nan")
        return Baseline(median, median, median, median, {}, (), resamples, level)

    without = {name: float(np.median(np.delete(values, index))) for index, name in enumerate(names)}
    robust = float(np.median(list(without.values())))

    rng = np.random.default_rng(seed)
    draws = np.array(
        [
            float(np.median(rng.choice(values, size=values.size, replace=True)))
            for _ in range(resamples)
        ]
    )
    tail = (1.0 - level) / 2.0
    low, high = (float(value) for value in np.quantile(draws, [tail, 1.0 - tail]))

    shifted = tuple(name for name, value in without.items() if value < low or value > high)
    return Baseline(
        median=float(np.median(values)),
        robust=robust,
        low=low,
        high=high,
        without=without,
        shifted=shifted,
        resamples=resamples,
        level=level,
    )


def absolute_shift(
    relative: Mapping[str, float], absolute: Mapping[str, float]
) -> dict[str, float]:
    """How far each chromosome's relative estimate sits from its denominator-free one.

    A relative estimate divides by a median over chromosomes; an absolute one divides by
    nothing (total k-mer mass per base). Where a chromosome's two estimates agree the
    denominator was sound for it; where they disagree by more than the others do, the
    median moved — which is defence (c) expressed as a number rather than an argument.
    """
    shared = sorted(set(relative) & set(absolute))
    return {name: float(relative[name] - absolute[name]) for name in shared}
