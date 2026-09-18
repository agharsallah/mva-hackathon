"""Allele balance is over-dispersed, and pretending otherwise manufactures findings.

At a heterozygous call on two intact copies, each read is equally likely to come from
either copy, so the alternate count out of *n* reads looks binomial with p = 0.5. It is
not. Capture bias, local GC content, mapping of one allele slightly better than the other
and PCR duplication all make the spread of the B-allele fraction **wider than binomial**.
A test built on the binomial therefore rejects far too often: every arm looks significant,
and a mosaic finding would be reported where there is only sequencing.

The one-parameter fix is the **beta-binomial**: the per-site success probability is itself
drawn from a Beta distribution centred on *p*, with the spread controlled by ρ, the
intra-class correlation. ρ = 0 recovers the binomial exactly; ρ = 1 makes every read of a
site agree with every other. Its variance is the binomial's inflated by
``1 + (n - 1)·ρ``, which is the "correction 3" the statistical-methods survey asked for.

**One bounded dimension, searched in log space.** :func:`fit_rho` is deliberately the same
shape as :func:`mva.kmer.genotype.fit_dispersion`, for the same reason that one is: with p
fixed at the null there is a single parameter, so a bounded scalar search is sufficient and
auditable — no starting point to get wrong and no convergence story to tell.

**ρ is fitted genome-wide, not per arm.** The over-dispersion is a property of the assay,
and an arm that is genuinely mosaic is *exactly* an arm whose spread is inflated. Fitting ρ
on the arm under test would absorb the signal into the null and guarantee the answer
"nothing here". Every caller passes the pooled autosomal histogram.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import betaln

from .tables import AlleleHistogram

__all__ = [
    "RHO_BOUNDS",
    "fit_rho",
    "log_likelihood",
    "logpmf",
    "mean_and_variance",
    "sample",
]

#: Bounds for the ρ search. Below 1e-6 the beta-binomial is numerically the binomial, and
#: above 0.5 a single site's reads would agree so strongly that depth carried almost no
#: information — neither end is a sequencing assay, so both are refused rather than fitted.
RHO_BOUNDS = (1e-6, 0.5)


def _concentration(rho: float) -> float:
    """The Beta prior's total weight ``a + b``. Larger means tighter; ρ → 0 means infinite."""
    rho = float(np.clip(rho, RHO_BOUNDS[0], RHO_BOUNDS[1]))
    return (1.0 - rho) / rho


def logpmf(k: np.ndarray, n: np.ndarray, p: float, rho: float) -> np.ndarray:
    """log P(k alternate reads of n) under a beta-binomial centred on ``p``.

    Written with :func:`scipy.special.betaln` rather than a Beta-binomial object because
    the arrays here are the histogram's distinct ``(k, n)`` pairs — tens of thousands of
    them, evaluated tens of thousands of times inside the simulation — and this form is
    one vectorised expression with no Python-level loop and no object construction.
    """
    k = np.asarray(k, dtype=float)
    n = np.asarray(n, dtype=float)
    concentration = _concentration(rho)
    alpha = max(p, 1e-12) * concentration
    beta = max(1.0 - p, 1e-12) * concentration
    # The binomial coefficient, as a difference of log-betas: log C(n, k) =
    # -log(n + 1) - betaln(n - k + 1, k + 1). Exact, and it never overflows.
    coefficient = -np.log(n + 1.0) - betaln(n - k + 1.0, k + 1.0)
    return coefficient + betaln(k + alpha, n - k + beta) - betaln(alpha, beta)


def mean_and_variance(n: np.ndarray, p: float, rho: float) -> tuple[np.ndarray, np.ndarray]:
    """Mean and variance of the alternate count — the binomial's, inflated by ρ."""
    n = np.asarray(n, dtype=float)
    mean = n * p
    inflation = 1.0 + (n - 1.0) * float(np.clip(rho, RHO_BOUNDS[0], RHO_BOUNDS[1]))
    return mean, n * p * (1.0 - p) * inflation


def log_likelihood(histogram: AlleleHistogram, p: float, rho: float) -> float:
    """The histogram's total log-likelihood: each pair's logpmf times how often it occurred."""
    if not histogram.n_sites:
        return 0.0
    values = logpmf(histogram.k, histogram.n, p, rho)
    if not np.all(np.isfinite(values)):
        return -np.inf
    return float(np.dot(values, histogram.sites))


def fit_rho(histogram: AlleleHistogram, *, p: float = 0.5) -> float:
    """Maximum-likelihood ρ at a fixed centre.

    Returns the lower bound for an empty histogram — the binomial — because a fitted
    over-dispersion with nothing to fit it on would be an invention, and the binomial is
    the conservative direction for a *null*: it is the one that rejects more readily, so
    the caller cannot accidentally be handed a null that hides its own failure.
    """
    if not histogram.n_sites:
        return RHO_BOUNDS[0]

    def negative_log_likelihood(log_rho: float) -> float:
        value = log_likelihood(histogram, p, float(np.exp(log_rho)))
        return -value if np.isfinite(value) else 1e18

    result = minimize_scalar(
        negative_log_likelihood,
        bounds=(float(np.log(RHO_BOUNDS[0])), float(np.log(RHO_BOUNDS[1]))),
        method="bounded",
    )
    return float(np.exp(result.x))


def sample(n: np.ndarray, p: float, rho: float, rng: np.random.Generator) -> np.ndarray:
    """Draw one alternate count per entry of ``n`` — the forward model, for simulation.

    Two steps, which is the definition rather than an approximation: draw each site's own
    success probability from the Beta, then draw its alternate count from the binomial at
    that probability.
    """
    n = np.asarray(n, dtype=int)
    concentration = _concentration(rho)
    probabilities = rng.beta(
        max(p, 1e-12) * concentration, max(1.0 - p, 1e-12) * concentration, size=n.shape
    )
    return rng.binomial(n, probabilities)
