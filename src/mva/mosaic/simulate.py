"""How small an event could this chromosome have shown? — the half without which "flat" is empty.

A negative result from an allele-balance test is a statement about the *instrument* as much
as about the sample: "no mosaic aneuploidy detected" means nothing until it is finished with
"...above f per cent of cells, at this chromosome's site count and depth". This module
measures that completion, by forward simulation rather than by an asymptotic formula — the
statistic is a folded mean of an over-dispersed mixture and has no clean null distribution,
and the arms differ by two orders of magnitude in site count.

**One procedure, used three times.**

1. Draw the arm's own depths. Not a nominal coverage — the observed depth margin, so a
   shallow arm is simulated shallow.
2. Redraw the alternate counts from the fitted beta-binomial: at f = 0 centred on the
   sample's own centre, and at f > 0 split half and half between the two bands a mosaic gain
   makes.
3. Recompute the same statistic the real data was scored with, and compare against the 95th
   percentile of the f = 0 draws.

Power is the share of draws above that threshold; the detection limit ``f80`` is the
smallest simulated fraction whose power reaches 80 %.

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

from . import betabinom
from .tables import AlleleHistogram

__all__ = [
    "GRID",
    "Limit",
    "MultiResult",
    "Statistic",
    "bdev_statistic",
    "detection_limit",
    "mean_statistic",
    "multi_chromosome",
    "power_curve",
]

#: The fractions power is measured at. Coarse on purpose: the answer is reported as "the
#: smallest grid point reaching 80 %%", and a finer grid would suggest a precision the
#: replicate count does not support.
GRID: tuple[float, ...] = (0.01, 0.02, 0.03, 0.05, 0.075, 0.10, 0.15, 0.20, 0.30)

#: A statistic maps (alternate counts, depths, centre) to one number per simulated arm.
Statistic = Callable[[np.ndarray, np.ndarray, float], float]


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


def power_curve(
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
    """Power against cell fraction for one arm, and the smallest fraction that reaches 80 %."""
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


def detection_limit(
    histogram: AlleleHistogram,
    *,
    rho: float,
    centre: float,
    **kwargs: object,
) -> Limit:
    """:func:`power_curve` with the fold-over statistic — the step's headline number."""
    return power_curve(histogram, rho=rho, centre=centre, **kwargs)  # type: ignore[arg-type]


@dataclass(frozen=True)
class MultiResult:
    """One multi-chromosome design: what was injected, what was found, what was invented."""

    fraction: float
    affected: tuple[str, ...]
    #: injected chromosomes whose statistic crossed their own null threshold
    recovered: tuple[str, ...]
    #: untouched chromosomes that crossed theirs — the arm that matters for a bound
    false_positives: tuple[str, ...]
    tested: int
    replicate: int

    @property
    def recall(self) -> float:
        return len(self.recovered) / len(self.affected) if self.affected else float("nan")

    @property
    def false_positive_rate(self) -> float:
        clean = self.tested - len(self.affected)
        return len(self.false_positives) / clean if clean else float("nan")


def multi_chromosome(
    histograms: dict[str, AlleleHistogram],
    *,
    affected: Sequence[str],
    fraction: float,
    rho: float,
    centre: float,
    replicates: int = 200,
    statistic: Statistic = bdev_statistic,
    seed: int = 0,
) -> list[MultiResult]:
    """Inject into several chromosomes at once and score every chromosome, injected or not.

    Each replicate redraws *every* chromosome — the untouched ones from the null — so the
    false-positive arm is measured on the same draws that produced the recoveries, rather
    than assumed from a nominal 5 %.
    """
    rng = np.random.default_rng(seed)
    depths = {
        name: np.repeat(histogram.n, histogram.sites.astype(int))
        for name, histogram in histograms.items()
    }
    thresholds = {
        name: float(
            np.quantile(
                [statistic(_draw(depth, 0.0, centre, rho, rng), depth, centre) for _ in range(50)],
                0.95,
            )
        )
        for name, depth in depths.items()
        if depth.size
    }

    results: list[MultiResult] = []
    for replicate in range(replicates):
        recovered: list[str] = []
        invented: list[str] = []
        for name, depth in depths.items():
            if not depth.size:
                continue
            injected = name in affected
            value = statistic(
                _draw(depth, fraction if injected else 0.0, centre, rho, rng), depth, centre
            )
            if value > thresholds[name]:
                (recovered if injected else invented).append(name)
        results.append(
            MultiResult(
                fraction=fraction,
                affected=tuple(affected),
                recovered=tuple(recovered),
                false_positives=tuple(invented),
                tested=len(thresholds),
                replicate=replicate,
            )
        )
    return results
