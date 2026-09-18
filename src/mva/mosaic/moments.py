"""The null distribution of a folded mean, computed rather than simulated.

Every statistic in this package is an average of a per-site quantity over an arm's
heterozygous calls — ``|BAF − centre|`` for the fold-over deviation, ``BAF`` for entry
037's. The obvious way to get its null distribution is to redraw the arm a few hundred
times, and that is what the first implementation did. On the real callset it cost hours:
each draw samples a Beta and a binomial for every one of up to 200,000 sites, and the run
needs tens of thousands of draws.

It is also unnecessary. A per-site quantity has an **exact** mean and variance under the
beta-binomial, obtained by enumerating ``k = 0…n`` for each distinct depth — a few thousand
evaluations for a whole chromosome, once. The average of 200,000 independent such
quantities is Gaussian by the central limit theorem to far better precision than 200 draws
could measure, so the null mean, its standard deviation and any percentile follow in closed
form.

**Faster and more accurate, not a trade.** A 200-draw Monte Carlo estimate of a 95th
percentile carries its own sampling error of a few per cent; the analytic value has none.
``tests/test_mosaic_moments.py`` asserts the two agree, which is the property that makes
replacing one with the other safe.

**Where the approximation is and is not valid.** The CLT needs many independent sites, and
:data:`MIN_SITES_FOR_CLT` is the floor below which this module refuses rather than
approximates. Sites on one arm are not perfectly independent — a run of reads spanning two
nearby heterozygous calls correlates them — which inflates the true variance a little. That
direction is the anticonservative one, so the fitted over-dispersion ρ is doing that work
and it is stated here rather than assumed away.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from . import betabinom

__all__ = ["MIN_SITES_FOR_CLT", "Moments", "fold_moments", "mean_moments", "percentile"]

#: Below this many calls the central limit theorem is not a safe approximation and the
#: caller is told so rather than handed a number.
MIN_SITES_FOR_CLT = 30


class Moments:
    """The mean and standard deviation of an arm's statistic under a stated model."""

    __slots__ = ("mean", "sd", "sites")

    def __init__(self, mean: float, sd: float, sites: int) -> None:
        self.mean = mean
        self.sd = sd
        self.sites = sites

    @property
    def usable(self) -> bool:
        return self.sites >= MIN_SITES_FOR_CLT and np.isfinite(self.sd) and self.sd > 0

    def percentile(self, quantile: float) -> float:
        """A Gaussian percentile of the statistic. ``quantile`` is a share, e.g. 0.95."""
        return percentile(self.mean, self.sd, quantile)

    def as_dict(self) -> dict[str, float | int]:
        return {"mean": self.mean, "sd": self.sd, "sites": self.sites}


def percentile(mean: float, sd: float, quantile: float) -> float:
    """The Gaussian quantile, written with an inverse error function to avoid a scipy call.

    ``scipy.stats.norm.ppf`` would do the same; this is one line, has no import cost inside
    a loop that runs per arm per fraction, and is exact to machine precision.
    """
    from scipy.special import erfinv

    return float(mean + sd * np.sqrt(2.0) * float(erfinv(2.0 * quantile - 1.0)))


def _per_depth(
    depth: int, bands: Sequence[tuple[float, float]], rho: float, transform
) -> tuple[float, float]:
    """Exact mean and second moment of ``transform(k / depth)`` at one depth.

    ``bands`` is ``[(centre, weight), …]``: the mixture the model predicts. Enumerating
    every ``k`` is what makes this exact — the support is finite and small.
    """
    k = np.arange(depth + 1, dtype=float)
    n = np.full(depth + 1, float(depth))
    probability = np.zeros(depth + 1, dtype=float)
    for centre, weight in bands:
        probability += weight * np.exp(betabinom.logpmf(k, n, centre, rho))
    total = probability.sum()
    if total <= 0:
        return 0.0, 0.0
    probability /= total
    values = transform(k / depth)
    return float(np.dot(probability, values)), float(np.dot(probability, values**2))


def _combine(
    depths: np.ndarray,
    counts: np.ndarray,
    bands: Sequence[tuple[float, float]],
    rho: float,
    transform,
) -> Moments:
    """Mean and standard deviation of the site-average, over a histogram of depths."""
    sites = float(counts.sum())
    if sites <= 0:
        return Moments(float("nan"), float("nan"), 0)
    first = np.empty(depths.size, dtype=float)
    second = np.empty(depths.size, dtype=float)
    for index, depth in enumerate(depths):
        first[index], second[index] = _per_depth(int(depth), bands, rho, transform)
    mean = float(np.dot(counts, first) / sites)
    # Var(mean) = sum_i Var_i / N^2, and the sites on an arm are treated as independent.
    variance = float(np.dot(counts, second - first**2) / sites**2)
    return Moments(mean, float(np.sqrt(max(variance, 0.0))), int(sites))


def fold_moments(
    depths: np.ndarray,
    counts: np.ndarray,
    *,
    bands: Sequence[tuple[float, float]],
    rho: float,
    centre: float,
) -> Moments:
    """The fold-over statistic's moments: the mean of ``|BAF − centre|``."""
    return _combine(depths, counts, bands, rho, lambda baf: np.abs(baf - centre))


def mean_moments(
    depths: np.ndarray,
    counts: np.ndarray,
    *,
    bands: Sequence[tuple[float, float]],
    rho: float,
) -> Moments:
    """Entry 037's statistic: the mean B-allele fraction, before any folding.

    Its moments are computed the same way, which is the point — the two statistics can then
    be compared on identical assumptions rather than on identical random draws.
    """
    return _combine(depths, counts, bands, rho, lambda baf: baf)
