"""Fit all five models to one chromosome, and say which one — if any — earned the call.

Kong 2018's MAD-seq (PMID 29773658) is a hierarchical Bayesian model fitted by MCMC in a
package that has since been removed from Bioconductor, with a repository that no longer
builds. The model itself is a paragraph of equations, so it is re-implemented here from
the paper rather than resurrected: a beta-binomial mixture on allele fraction times a
negative binomial on depth, five parameterisations compared by **BIC**.

**Maximum likelihood, not MCMC — a stated simplification.** Every model has at most two
free parameters beyond a nuisance dispersion, both bounded, so a bounded search finds the
mode without a sampler, a prior or a convergence diagnostic. What is given up is the
posterior width on *f*, and that is bought back where it matters: the interval quoted for a
fraction comes from :mod:`~mva.mosaic.simulate`'s forward simulation, which is a stronger
statement than a posterior anyway because it also carries the detection limit.

**ΔBIC < 10 is low-confidence, and is Kong's own threshold.** Adopted as written. A
chromosome whose best and second-best models sit inside it is reported as
*not distinguishable*, never as the better-scoring one — the number, not the ranking, is
what gets printed.

**The depth term needs a baseline that does not assume any chromosome is normal.** That is
the whole difficulty of a *variegated* disease and it is not solved here: this module takes
the baseline it is given. :mod:`~mva.mosaic.baseline` is what computes it, by leaving each
chromosome out in turn and flagging any whose exclusion moves it.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import logsumexp

from ..kmer.genotype import nb_logpmf
from . import betabinom, models
from .models import Model
from .tables import AlleleHistogram, DepthHistogram

__all__ = [
    "DELTA_BIC",
    "FRACTION_BOUNDS",
    "ModelFit",
    "Verdict",
    "allele_log_likelihood",
    "best",
    "depth_log_likelihood",
    "fit_depth_dispersion",
    "fit_model",
    "fit_models",
]

#: Kong 2018's own low-confidence threshold, adopted as written.
DELTA_BIC = 10.0

#: A mosaic fraction below 0.5 %% is not distinguishable from noise at any realistic depth,
#: and above 0.9 the sample is not mosaic but constitutional -- which is a different claim
#: and a different test.
FRACTION_BOUNDS = (0.005, 0.90)

#: Bounds for the negative-binomial depth dispersion, matching mva.kmer.genotype's.
DISPERSION_BOUNDS = (1e-2, 1e4)


@dataclass(frozen=True)
class ModelFit:
    """One model fitted to one chromosome."""

    chrom: str
    model: str
    fraction: float
    tract: float
    depth_dispersion: float
    allele_log_likelihood: float
    depth_log_likelihood: float
    parameters: int
    observations: int

    @property
    def log_likelihood(self) -> float:
        return self.allele_log_likelihood + self.depth_log_likelihood

    @property
    def bic(self) -> float:
        """``-2 logL + k log N``. Lower is better."""
        return -2.0 * self.log_likelihood + self.parameters * float(np.log(self.observations))

    def as_dict(self) -> dict[str, object]:
        return {
            "chrom": self.chrom,
            "model": self.model,
            "fraction": round(self.fraction, 5),
            "tract": round(self.tract, 4),
            "depth_dispersion": round(self.depth_dispersion, 3),
            "log_likelihood": round(self.log_likelihood, 2),
            "parameters": self.parameters,
            "observations": self.observations,
            "bic": round(self.bic, 2),
        }


def allele_log_likelihood(
    histogram: AlleleHistogram, bands: list[models.Band], rho: float
) -> float:
    """A mixture of beta-binomials over the model's bands, weighted by the histogram."""
    if not histogram.n_sites or not bands:
        return 0.0
    stacked = np.vstack(
        [
            np.log(max(band.weight, 1e-12))
            + betabinom.logpmf(histogram.k, histogram.n, band.centre, rho)
            for band in bands
        ]
    )
    per_pair = logsumexp(stacked, axis=0)
    if not np.all(np.isfinite(per_pair)):
        return -np.inf
    return float(np.dot(per_pair, histogram.sites))


def depth_log_likelihood(histogram: DepthHistogram, mean: float, dispersion: float) -> float:
    """A negative binomial on read depth, weighted by how often each depth occurred."""
    if not histogram.n_sites:
        return 0.0
    values = nb_logpmf(histogram.depth.astype(float), mean, dispersion)
    if not np.all(np.isfinite(values)):
        return -np.inf
    return float(np.dot(values, histogram.sites))


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
        value = depth_log_likelihood(histogram, mean, float(np.exp(log_dispersion)))
        return -value if np.isfinite(value) else 1e18

    result = minimize_scalar(
        negative_log_likelihood,
        bounds=(float(np.log(DISPERSION_BOUNDS[0])), float(np.log(DISPERSION_BOUNDS[1]))),
        method="bounded",
    )
    return float(np.exp(result.x))


def _tract_weight(
    model: Model, fraction: float, alleles: AlleleHistogram, *, rho: float, centre: float
) -> float:
    """The balanced-tract share, fitted only for the model that has one."""
    if not model.has_tract:
        return 0.0

    def negative(share: float) -> float:
        bands = models.bands_for(model, fraction, centre, share)
        value = allele_log_likelihood(alleles, bands, rho)
        return -value if np.isfinite(value) else 1e18

    return float(minimize_scalar(negative, bounds=(0.0, 0.9), method="bounded").x)


def fit_model(
    model: Model,
    alleles: AlleleHistogram,
    depth: DepthHistogram,
    *,
    rho: float,
    centre: float,
    baseline_depth: float,
) -> ModelFit:
    """Fit one model's free parameters to one chromosome, by bounded search."""

    def total(fraction: float) -> tuple[float, float, float, float]:
        tract = _tract_weight(model, fraction, alleles, rho=rho, centre=centre)
        bands = models.bands_for(model, fraction, centre, tract)
        allele = allele_log_likelihood(alleles, bands, rho)
        mean = baseline_depth * models.depth_ratio(model, fraction)
        dispersion = fit_depth_dispersion(depth, mean)
        return allele, depth_log_likelihood(depth, mean, dispersion), tract, dispersion

    if model.has_fraction:

        def negative(fraction: float) -> float:
            allele, depths, _, _ = total(fraction)
            value = allele + depths
            return -value if np.isfinite(value) else 1e18

        fraction = float(minimize_scalar(negative, bounds=FRACTION_BOUNDS, method="bounded").x)
    else:
        fraction = 0.0

    allele, depths, tract, dispersion = total(fraction)
    return ModelFit(
        chrom=alleles.chrom or depth.chrom,
        model=model.name,
        fraction=fraction,
        tract=tract,
        depth_dispersion=dispersion,
        allele_log_likelihood=allele,
        depth_log_likelihood=depths,
        parameters=model.parameters,
        observations=max(alleles.n_sites + depth.n_sites, 2),
    )


def fit_models(
    alleles: AlleleHistogram,
    depth: DepthHistogram,
    *,
    rho: float,
    centre: float,
    baseline_depth: float,
) -> tuple[ModelFit, ...]:
    """All five, in declaration order."""
    return tuple(
        fit_model(model, alleles, depth, rho=rho, centre=centre, baseline_depth=baseline_depth)
        for model in models.MODELS
    )


@dataclass(frozen=True)
class Verdict:
    """Which model won, by how much, and whether that margin means anything."""

    chrom: str
    best: str
    runner_up: str
    delta_bic: float
    fraction: float
    #: mitotic trisomy against copy-neutral LOH specifically -- the pair that differs only
    #: by depth, and the one a reader must be able to check on its own
    trisomy_vs_cnloh: float
    confident: bool

    @property
    def call(self) -> str:
        """The model name, or the honest refusal. Never the ranking on its own."""
        return self.best if self.confident else "not distinguishable"

    def as_dict(self) -> dict[str, object]:
        return {
            "chrom": self.chrom,
            "call": self.call,
            "best": self.best,
            "runner_up": self.runner_up,
            "delta_bic": round(self.delta_bic, 2),
            "fraction": round(self.fraction, 5),
            "trisomy_vs_cnloh": round(self.trisomy_vs_cnloh, 2),
            "confident": self.confident,
        }


def best(fits: tuple[ModelFit, ...], *, delta: float = DELTA_BIC) -> Verdict:
    """Rank five fits by BIC and apply Kong's low-confidence rule."""
    ranked = sorted(fits, key=lambda fit: fit.bic)
    leader, second = ranked[0], ranked[1]
    by_name = {fit.model: fit for fit in fits}
    pair = by_name["cnloh"].bic - by_name["mitotic_trisomy"].bic
    return Verdict(
        chrom=leader.chrom,
        best=leader.model,
        runner_up=second.model,
        delta_bic=second.bic - leader.bic,
        fraction=leader.fraction,
        trisomy_vs_cnloh=pair,
        confident=(second.bic - leader.bic) >= delta,
    )
