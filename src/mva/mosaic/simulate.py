"""How small an event could this chromosome have shown? — the half without which "flat" is empty.

A negative result from an allele-balance test is a statement about the *instrument* as much
as about the sample: "no mosaic aneuploidy detected" means nothing until it is finished with
"...above f per cent of cells, at this chromosome's site count and depth". This module
measures that completion, by forward simulation rather than by an asymptotic formula — the
statistic is a folded mean of an over-dispersed mixture and has no clean null distribution,
and the arms differ by two orders of magnitude in site count.

**One procedure, used three times.**

1. Take the arm's own depth margin. Not a nominal coverage — the observed one, so a shallow
   arm is simulated shallow.
2. Write down the statistic's distribution at cell fraction *f*: the sites are split between
   the two bands a mosaic gain makes, each drawn from the fitted beta-binomial, and the
   statistic is their average.
3. Compare that distribution against the 95th percentile of the same statistic at f = 0.

Power is the share of the f > 0 distribution above that threshold; the detection limit
``f80`` is the smallest simulated fraction whose power reaches 80 %.

**Step 2 and 3 are computed, not sampled.** The statistic is an average over tens of
thousands of independent sites, so both distributions are Gaussian with moments available in
closed form (:mod:`~mva.mosaic.moments`). Drawing them instead costs four orders of
magnitude more and carries its own sampling error; the draw-based path is kept for the
cross-check the tests assert.

**The comparison against entry 037 uses this same harness with the statistic swapped.**
That is the only honest way to make the claim that fold-over Bdev has power where a mean
does not: identical sites, identical draws, one line different. :func:`power_curve` takes
the statistic as an argument for exactly that reason.

**Multi-chromosome designs are not a refinement, they are the disease.** *Variegated*
means several chromosomes abnormal at once, and every baseline here is a median over
chromosomes. :func:`multi_chromosome` injects into two or three at once and reports both
arms of the answer: whether the injected chromosomes are recovered, **and** whether the
untouched ones start being flagged. The second is the one that decides whether a
genome-wide bound survives on a genome like this one.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np
from scipy.special import erfc

from . import betabinom, moments
from .tables import AlleleHistogram

__all__ = [
    "GRID",
    "Limit",
    "Statistic",
    "bands_at",
    "bdev_statistic",
    "depth_margin",
    "detection_limit",
    "mean_statistic",
    "power_curve",
    "power_curve_simulated",
]

#: The fractions power is measured at. Coarse on purpose: the answer is reported as "the
#: smallest grid point reaching 80 %%", and a finer grid would suggest a precision the
#: replicate count does not support.
GRID: tuple[float, ...] = (0.01, 0.02, 0.03, 0.05, 0.075, 0.10, 0.15, 0.20, 0.30)

#: A statistic maps (alternate counts, depths, centre) to one number per simulated arm.
Statistic = Callable[[np.ndarray, np.ndarray, float], float]

#: The same two statistics as moment functions, keyed by the name the caller passes. This is
#: the whole of the closed-form path: everything else is arithmetic on the two numbers each
#: one returns.
MOMENTS = {
    "bdev": moments.fold_moments,
    "mean_baf": lambda depths, counts, *, bands, rho, centre: moments.mean_moments(
        depths, counts, bands=bands, rho=rho
    ),
}


def bdev_statistic(alternate: np.ndarray, depths: np.ndarray, centre: float) -> float:
    """Fold, then average. The statistic step 8 uses."""
    return float(np.mean(np.abs(alternate / depths - centre)))


def mean_statistic(alternate: np.ndarray, depths: np.ndarray, centre: float) -> float:
    """Average, then fold — entry 037's statistic, kept so the two can be run head to head."""
    return float(abs(np.mean(alternate / depths) - centre))


def _draw(
    depths: np.ndarray, fraction: float, centre: float, rho: float, rng: np.random.Generator
) -> np.ndarray:
    """One simulated arm's alternate counts at cell fraction ``fraction``.

    A mosaic gain puts half the sites in each band, so each site is assigned a band and then
    drawn from the beta-binomial centred there. At ``fraction`` zero this is the null.
    """
    if fraction <= 0.0:
        return betabinom.sample(depths, centre, rho, rng)
    offset = fraction / (2.0 + fraction)
    upper = rng.random(depths.shape) < 0.5
    drawn = np.empty(depths.shape, dtype=int)
    drawn[upper] = betabinom.sample(depths[upper], centre + offset, rho, rng)
    drawn[~upper] = betabinom.sample(depths[~upper], centre - offset, rho, rng)
    return drawn


@dataclass(frozen=True)
class Limit:
    """One arm's detection limit, and the power curve it was read off."""

    chrom: str
    arm: str
    n_sites: int
    mean_depth: float
    statistic: str
    #: fraction -> power, on :data:`GRID`
    power: dict[float, float]
    #: the smallest grid fraction reaching ``target``; NaN when none does
    f80: float
    target: float
    replicates: int
    threshold: float

    @property
    def detected_anything(self) -> bool:
        return np.isfinite(self.f80)

    def as_dict(self) -> dict[str, object]:
        return {
            "chrom": self.chrom,
            "arm": self.arm,
            "n_sites": self.n_sites,
            "mean_depth": round(self.mean_depth, 2),
            "statistic": self.statistic,
            "f80": None if not self.detected_anything else round(self.f80, 4),
            "target": self.target,
            "replicates": self.replicates,
            "threshold": round(self.threshold, 5),
            "power": {str(round(f, 4)): round(p, 3) for f, p in self.power.items()},
        }


def bands_at(fraction: float, centre: float) -> list[tuple[float, float]]:
    """The two bands a mosaic gain at ``fraction`` puts the heterozygous sites into."""
    if fraction <= 0.0:
        return [(centre, 1.0)]
    offset = fraction / (2.0 + fraction)
    return [(centre - offset, 0.5), (centre + offset, 0.5)]


def depth_margin(histogram: AlleleHistogram) -> tuple[np.ndarray, np.ndarray]:
    """The arm's distinct depths and how many calls sit at each — its own, never nominal."""
    if not histogram.n_sites:
        return np.array([], dtype=int), np.array([], dtype=float)
    unique, index = np.unique(histogram.n, return_inverse=True)
    totals = np.zeros(unique.size, dtype=float)
    np.add.at(totals, index, histogram.sites)
    return unique, totals


def _upper_tail(threshold: float, distribution: moments.Moments, *, folded: bool) -> float:
    """P(statistic > threshold) under a Gaussian with these moments.

    ``folded`` says whether the statistic has already taken an absolute value per site. When
    it has not — entry 037's mean B-allele fraction — the test is two-sided, because a mosaic
    gain could move the mean either way and 037 would have rejected on either. Scoring it
    one-sided would have understated the statistic this step is comparing against.
    """
    if not distribution.usable:
        return float("nan")
    upper = 0.5 * erfc((threshold - distribution.mean) / (distribution.sd * np.sqrt(2.0)))
    if folded:
        return float(upper)
    mirrored = 2.0 * distribution.mean - threshold
    lower = 0.5 * erfc((mirrored - distribution.mean) / (distribution.sd * np.sqrt(2.0)))
    return float(upper + (1.0 - lower))


def power_curve(
    histogram: AlleleHistogram,
    *,
    rho: float,
    centre: float,
    grid: Sequence[float] = GRID,
    target: float = 0.80,
    name: str = "bdev",
) -> Limit:
    """Power against cell fraction for one arm, and the smallest fraction that reaches 80 %.

    Closed form throughout: the statistic's null and alternative distributions are both
    Gaussian over this arm's own depth margin, so power is one normal tail per grid point.
    """
    depths, counts = depth_margin(histogram)
    moment = MOMENTS[name]
    folded = name == "bdev"
    empty = Limit(
        histogram.chrom,
        histogram.arm,
        histogram.n_sites,
        histogram.mean_depth,
        name,
        {},
        float("nan"),
        target,
        0,
        float("nan"),
    )
    if depths.size == 0:
        return empty
    null = moment(depths, counts, bands=bands_at(0.0, centre), rho=rho, centre=centre)
    if not null.usable:
        return empty
    threshold = null.percentile(0.95) if folded else null.percentile(0.975)

    power = {
        fraction: _upper_tail(
            threshold,
            moment(depths, counts, bands=bands_at(fraction, centre), rho=rho, centre=centre),
            folded=folded,
        )
        for fraction in grid
    }
    reached = [fraction for fraction in grid if power[fraction] >= target]
    return Limit(
        chrom=histogram.chrom,
        arm=histogram.arm,
        n_sites=histogram.n_sites,
        mean_depth=histogram.mean_depth,
        statistic=name,
        power=power,
        f80=min(reached) if reached else float("nan"),
        target=target,
        replicates=0,
        threshold=threshold,
    )


def detection_limit(
    histogram: AlleleHistogram,
    *,
    rho: float,
    centre: float,
    **kwargs: object,
) -> Limit:
    """:func:`power_curve` with the fold-over statistic — the step's headline number."""
    return power_curve(histogram, rho=rho, centre=centre, **kwargs)  # type: ignore[arg-type]


def power_curve_simulated(
    histogram: AlleleHistogram,
    *,
    rho: float,
    centre: float,
    statistic: Statistic = bdev_statistic,
    grid: Sequence[float] = GRID,
    replicates: int = 200,
    target: float = 0.80,
    seed: int = 0,
    name: str = "bdev",
) -> Limit:
    """The Monte Carlo version of :func:`power_curve`, kept as its cross-check.

    Four orders of magnitude slower on a whole chromosome and carrying its own sampling
    error, so nothing calls it in a run — but it makes no Gaussian assumption at all, which
    is exactly what a check on the closed form has to avoid.
    """
    depths = np.repeat(histogram.n, histogram.sites.astype(int))
    if depths.size == 0:
        return Limit(
            histogram.chrom,
            histogram.arm,
            0,
            0.0,
            name,
            {},
            float("nan"),
            target,
            replicates,
            float("nan"),
        )
    rng = np.random.default_rng(seed)
    null = np.array(
        [statistic(_draw(depths, 0.0, centre, rho, rng), depths, centre) for _ in range(replicates)]
    )
    threshold = float(np.quantile(null, 0.95))
    power: dict[float, float] = {}
    for fraction in grid:
        values = np.array(
            [
                statistic(_draw(depths, fraction, centre, rho, rng), depths, centre)
                for _ in range(replicates)
            ]
        )
        power[fraction] = float(np.count_nonzero(values > threshold) / replicates)
    reached = [fraction for fraction in grid if power[fraction] >= target]
    return Limit(
        chrom=histogram.chrom,
        arm=histogram.arm,
        n_sites=histogram.n_sites,
        mean_depth=histogram.mean_depth,
        statistic=name,
        power=power,
        f80=min(reached) if reached else float("nan"),
        target=target,
        replicates=replicates,
        threshold=threshold,
    )
