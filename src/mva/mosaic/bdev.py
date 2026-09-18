"""The statistic entry 037 should have used, and the fraction estimate that follows it.

**Why the mean was the wrong statistic.** Add a third copy of a chromosome to a fraction
*f* of cells. A site that was heterozygous now reads as two bands: some cells contribute
one alternate copy of three, others two of three, and across the population the B-allele
fraction splits symmetrically about 0.5 — one band above, one below, in equal numbers.
The **mean is unchanged**. Entry 037 averaged the B-allele fraction inside each megabase
and found every autosome flat, which is what a mosaic gain of any size would have produced.

**Fold-over.** Take ``|BAF − 0.5|`` before averaging. The two bands fold onto each other
instead of cancelling, and the statistic grows with *f* from its first cell. That is the
**B-deviation** (Bdev), and it is the whole difference between a test with power and a
test without one.

**Against what null.** Not zero: even two intact copies give a spread, and folding a
symmetric spread gives a positive mean. The null is the same statistic computed under the
fitted beta-binomial at p = 0.5 with this arm's own depth margin — so an arm with fewer
reads is judged against a wider null rather than flagged for being shallow.

**Reference bias is subtracted, not ignored.** Reads carrying the reference allele map
slightly more readily, so the BAF sits a little below 0.5 genome-wide; entry 037 measured
0.4954–0.4984 per autosome. Folding around 0.5 would turn that constant offset into a
constant Bdev on every chromosome. The centre is therefore the pooled autosomal median,
measured once and reported, and never assumed to be 0.5.

**The fraction estimate is a trisomy mapping, applied to the upper band only.** Markello
2012's DANFIP relation ``f = (2·BAF − 1) / (1 − BAF)`` is undefined below 0.5 and assumes
a gain, so it is evaluated on the upper band after the split and inherits every error the
split makes.

**And that error is large here, which is measured rather than assumed.** DANFIP was
designed for dense SNP arrays, where a site's B-allele fraction is precise. At this
sample's depth the spread of a *balanced* site is already wider than the band separation a
10 % mosaic would create, so "the sites above the centre" is mostly the upper half of the
noise, and the raw estimate is biased upward — at f = 0 it returns something far from
zero. :func:`danfip` therefore runs the identical estimator on null draws from the same
depths and ρ, reports that as ``f_null``, and reports ``f_corrected`` beside the raw
number. The corrected value is the one to quote, the raw one is what the published method
gives, and the gap between them is a result about the instrument.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import betabinom
from .tables import AlleleHistogram

__all__ = [
    "MIN_SITES",
    "Bdev",
    "Danfip",
    "bdev",
    "centre",
    "danfip",
    "null_draws",
    "statistic",
]

#: Sites below this are not tested. Entry 037 used the same floor for a megabase bin, and
#: the reason is unchanged: below it the statistic is noise, and a row that says
#: "not measurable" is information while a row that says "flat" would be a claim.
MIN_SITES = 20


def centre(histogram: AlleleHistogram) -> float:
    """The BAF the fold is taken around — the site-weighted mean, not 0.5.

    Called on the *pooled autosomal* histogram, once per sample. Using each arm's own value
    would fold a genuine mosaic shift away along with the bias.

    The mean and not the median, for two reasons that agree. A site's BAF lives on a grid
    of 1/n — about 0.023 steps at this depth — so the median is one of ~44 grid points and
    reports 0.5 exactly whenever the true centre is anywhere near it, which is precisely the
    bias this function exists to measure. And the mean is unbiased for the centre even when
    a mosaic *is* present: a gain splits the sites into two bands symmetric about it, which
    is the same fact that makes the mean useless as a detector and ideal as a centre.
    """
    return histogram.weighted(histogram.baf)


def statistic(histogram: AlleleHistogram, *, around: float) -> float:
    """Mean ``|BAF − around|``, site-weighted. The Bdev itself."""
    if not histogram.n_sites:
        return float("nan")
    return histogram.weighted(np.abs(histogram.baf - around))


@dataclass(frozen=True)
class Bdev:
    """One arm's fold-over deviation, and what the null says about it."""

    chrom: str
    arm: str
    n_sites: int
    mean_depth: float
    observed: float
    #: mean and standard deviation of the statistic under the fitted null
    null_mean: float
    null_sd: float
    #: the null's upper 95th percentile — the rejection threshold the power curve uses
    null_p95: float
    #: how many null standard deviations above the null mean the observation sits
    z: float
    #: share of null draws at or above the observation, with the +1/+1 floor so it is
    #: never reported as zero
    p_value: float
    rho: float
    centre: float

    @property
    def measurable(self) -> bool:
        return self.n_sites >= MIN_SITES

    @property
    def exceeds_null(self) -> bool:
        return self.measurable and self.observed > self.null_p95

    def as_dict(self) -> dict[str, object]:
        return {
            "chrom": self.chrom,
            "arm": self.arm,
            "n_sites": self.n_sites,
            "mean_depth": round(self.mean_depth, 2),
            "bdev": round(self.observed, 5),
            "null_mean": round(self.null_mean, 5),
            "null_sd": round(self.null_sd, 5),
            "null_p95": round(self.null_p95, 5),
            "z": round(self.z, 3),
            "p_value": round(self.p_value, 5),
            "rho": round(self.rho, 5),
            "centre": round(self.centre, 5),
            "measurable": self.measurable,
            "exceeds_null": self.exceeds_null,
        }


def null_draws(
    histogram: AlleleHistogram,
    *,
    rho: float,
    around: float,
    draws: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """The statistic's distribution when nothing is wrong with this arm.

    The arm's own depths are resampled and its alternate counts redrawn from the fitted
    beta-binomial, so the null carries this arm's site count and depth profile. A shallow
    arm gets a wider null rather than a false positive.
    """
    if not histogram.n_sites:
        return np.array([])
    depths = np.repeat(histogram.n, histogram.sites.astype(int))
    values = np.empty(draws, dtype=float)
    for index in range(draws):
        drawn = betabinom.sample(depths, around, rho, rng)
        values[index] = float(np.mean(np.abs(drawn / depths - around)))
    return values


def bdev(
    histogram: AlleleHistogram,
    *,
    rho: float,
    around: float,
    draws: int = 200,
    seed: int = 0,
) -> Bdev:
    """One arm's Bdev against its own simulated null."""
    observed = statistic(histogram, around=around)
    draws_array = null_draws(
        histogram, rho=rho, around=around, draws=draws, rng=np.random.default_rng(seed)
    )
    if draws_array.size == 0:
        mean = sd = p95 = float("nan")
        z = float("nan")
        p_value = float("nan")
    else:
        mean = float(draws_array.mean())
        sd = float(draws_array.std(ddof=1))
        p95 = float(np.quantile(draws_array, 0.95))
        z = (observed - mean) / sd if sd > 0 else float("inf")
        p_value = float((np.count_nonzero(draws_array >= observed) + 1) / (draws_array.size + 1))
    return Bdev(
        chrom=histogram.chrom,
        arm=histogram.arm,
        n_sites=histogram.n_sites,
        mean_depth=histogram.mean_depth,
        observed=observed,
        null_mean=mean,
        null_sd=sd,
        null_p95=p95,
        z=z,
        p_value=p_value,
        rho=rho,
        centre=around,
    )


@dataclass(frozen=True)
class Danfip:
    """The cell-fraction estimate, its null bias, and the band split both rest on."""

    chrom: str
    arm: str
    #: the published estimator, applied as written
    f_raw: float
    #: the same estimator on null draws at this arm's depths and rho -- its bias at f = 0
    f_null: float
    #: f_raw - f_null, floored at zero. The number to quote
    f_hat: float
    low: float
    high: float
    #: how many of the arm's sites fell in the upper band
    upper_sites: int
    centre: float

    def as_dict(self) -> dict[str, object]:
        return {
            "chrom": self.chrom,
            "arm": self.arm,
            "f_raw": round(self.f_raw, 5),
            "f_null": round(self.f_null, 5),
            "f_hat": round(self.f_hat, 5),
            "f_low": round(self.low, 5),
            "f_high": round(self.high, 5),
            "upper_sites": self.upper_sites,
            "centre": round(self.centre, 5),
        }


def _fraction(baf: float) -> float:
    """Markello 2012's trisomy relation, guarded against its singularity at BAF = 1."""
    return (2.0 * baf - 1.0) / max(1.0 - baf, 1e-6)


def _upper_mean(baf: np.ndarray, weights: np.ndarray, around: float) -> float:
    """The mean B-allele fraction of the sites above ``around``. NaN when there are none.

    The mean and not the median, although the median is the more robust summary of a band.
    At this depth a site's BAF lives on a grid of 1/n -- about 0.023 steps at 44 reads --
    and the median of a gridded variable is one of its grid points, so it moves in jumps of
    0.13 in estimated fraction and its bootstrap interval collapses onto a single value. The
    mean of the same sites is continuous. Robustness is bought back by the null-bias
    subtraction, which is the larger error here by an order of magnitude.
    """
    upper = baf > around
    if not upper.any():
        return float("nan")
    return float(np.average(baf[upper], weights=weights[upper]))


def danfip(
    histogram: AlleleHistogram,
    *,
    around: float,
    rho: float,
    draws: int = 200,
    seed: int = 0,
) -> Danfip:
    """Estimate the mosaic fraction from the upper band, and measure the estimator's bias.

    The interval is the 2.5th-97.5th percentile of the *corrected* estimate across null
    draws -- which is what a reader needs: it says how far from zero this arm's estimate
    could have landed with nothing wrong with it.
    """
    depths = np.repeat(histogram.n, histogram.sites.astype(int))
    if depths.size == 0:
        nan = float("nan")
        return Danfip(histogram.chrom, histogram.arm, nan, nan, nan, nan, nan, 0, around)

    raw = _fraction(_upper_mean(histogram.baf, histogram.sites, around))

    rng = np.random.default_rng(seed)
    ones = np.ones_like(depths, dtype=float)
    null = np.empty(draws, dtype=float)
    for index in range(draws):
        drawn = betabinom.sample(depths, around, rho, rng)
        null[index] = _fraction(_upper_mean(drawn / depths, ones, around))

    bias = float(np.median(null))
    spread = np.quantile(null - bias, [0.025, 0.975])
    return Danfip(
        chrom=histogram.chrom,
        arm=histogram.arm,
        f_raw=raw,
        f_null=bias,
        f_hat=max(raw - bias, 0.0),
        low=max(raw - bias + float(spread[0]), 0.0),
        high=max(raw - bias + float(spread[1]), 0.0),
        upper_sites=int(histogram.sites[histogram.baf > around].sum()),
        centre=around,
    )
