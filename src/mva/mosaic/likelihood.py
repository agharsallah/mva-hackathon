"""What each of the five models says about the data — the likelihoods, and nothing else.

Split from :mod:`mva.mosaic.madseq` so that module is about *choosing* between models and
this one is about *scoring* them. Three functions, and the reason each is shaped the way it
is matters more than its arithmetic:

:func:`allele_log_likelihood`  the beta-binomial mixture over a model's bands **plus a
                               shared noise component**. Without that component the richest
                               model wins on every chromosome, because a few per cent of
                               real heterozygous calls have an allele balance no single
                               beta-binomial produces and 200,000 calls turn that mismatch
                               into thousands of BIC units.
:func:`depth_log_likelihood`   **one** Gaussian on the chromosome's mean depth ratio. The
                               obvious negative binomial over every call's depth measures
                               site-to-site variation *within* the chromosome, which says
                               nothing about whether the chromosome as a whole is deeper —
                               and at 350,000 calls it decides every comparison on 0.5 % of
                               ordinary GC variation.
:func:`site_depth_log_likelihood`  that negative binomial, kept because it is the right
                               description of depth at a site and because the dispersion fit
                               needs a likelihood to maximise. It does not select models.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import logsumexp

from ..kmer.genotype import nb_logpmf
from . import betabinom, models
from .tables import AlleleHistogram, DepthHistogram

__all__ = [
    "DEFAULT_DEPTH_SD",
    "DISPERSION_BOUNDS",
    "allele_log_likelihood",
    "depth_log_likelihood",
    "fit_depth_dispersion",
    "site_depth_log_likelihood",
]

#: Bounds for the negative-binomial depth dispersion, matching mva.kmer.genotype's.
DISPERSION_BOUNDS = (1e-2, 1e4)

#: Fallback spread of the per-chromosome depth ratio when the caller has not measured one.
#: 2 % is deliberately generous: it is roughly what GC and mappability produce between
#: chromosomes on a normal genome, and a too-narrow default would manufacture calls.
DEFAULT_DEPTH_SD = 0.02


def allele_log_likelihood(
    histogram: AlleleHistogram,
    bands: list[models.Band],
    rho: float,
    *,
    noise: float = 0.0,
    centre: float = 0.5,
) -> float:
    """A mixture of beta-binomials over the model's bands, plus the shared noise component.

    ``noise`` is the share of calls the bands do not claim to explain — collapsed repeats,
    unflagged copy-number change, one allele mapping badly. Every model carries it with the
    same fixed width, so the comparison is about band structure rather than about which
    model has a spare parameter to spend on the tails.
    """
    if not histogram.n_sites or not bands:
        return 0.0
    share = float(np.clip(noise, 0.0, 0.5))
    stacked = [
        np.log(max(band.weight, 1e-12) * (1.0 - share))
        + betabinom.logpmf(histogram.k, histogram.n, band.centre, rho)
        for band in bands
    ]
    if share > 0.0:
        stacked.append(
            np.log(share) + betabinom.logpmf(histogram.k, histogram.n, centre, models.NOISE_RHO)
        )
    per_pair = logsumexp(np.vstack(stacked), axis=0)
    if not np.all(np.isfinite(per_pair)):
        return -np.inf
    return float(np.dot(per_pair, histogram.sites))


def site_depth_log_likelihood(histogram: DepthHistogram, mean: float, dispersion: float) -> float:
    """A negative binomial over every call's depth. **Not** used for model selection.

    Kept because it is the correct description of depth at a site and because
    :func:`fit_depth_dispersion` needs a likelihood to maximise. Using it to compare models
    would weight one chromosome-level fact by the number of sites that happen to lie on the
    chromosome; see the module docstring.
    """
    if not histogram.n_sites:
        return 0.0
    values = nb_logpmf(histogram.depth.astype(float), mean, dispersion)
    if not np.all(np.isfinite(values)):
        return -np.inf
    return float(np.dot(values, histogram.sites))


def depth_log_likelihood(
    histogram: DepthHistogram, mean: float, *, spread: float = DEFAULT_DEPTH_SD
) -> float:
    """One Gaussian on the chromosome's mean depth, against the between-chromosome spread.

    ``spread`` is in units of the baseline, so a 2 %% spread at a 42x baseline is 0.84x.
    """
    if not histogram.n_sites or mean <= 0:
        return 0.0
    sigma = max(spread * mean, 1e-9)
    residual = (histogram.mean - mean) / sigma
    return float(-0.5 * residual**2 - np.log(sigma * np.sqrt(2.0 * np.pi)))


def fit_depth_dispersion(histogram: DepthHistogram, mean: float) -> float:
    """Maximum-likelihood dispersion at a fixed mean, over the histogram rather than the calls.

    :func:`mva.kmer.genotype.fit_dispersion` does the same search over an array of counts.
    Here the counts arrive already tallied -- hundreds of thousands of calls in a few
    hundred distinct depths -- so the likelihood is a weighted sum and the search is three
    orders of magnitude cheaper. The search itself is identical: one bounded dimension in
    log space.
    """
    if not histogram.n_sites or mean <= 0:
        return DISPERSION_BOUNDS[1]

    def negative_log_likelihood(log_dispersion: float) -> float:
        value = site_depth_log_likelihood(histogram, mean, float(np.exp(log_dispersion)))
        return -value if np.isfinite(value) else 1e18

    result = minimize_scalar(
        negative_log_likelihood,
        bounds=(float(np.log(DISPERSION_BOUNDS[0])), float(np.log(DISPERSION_BOUNDS[1]))),
        method="bounded",
    )
    return float(np.exp(result.x))
