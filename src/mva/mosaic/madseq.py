"""Fit all five models to one chromosome, and say which one — if any — earned the call.

Kong 2018's MAD-seq (PMID 29773658) is a hierarchical Bayesian model fitted by MCMC in a
package that has since been removed from Bioconductor, with a repository that no longer
builds. The model itself is a paragraph of equations, so it is re-implemented here from
the paper rather than resurrected: a beta-binomial mixture on allele fraction times a
negative binomial on depth, five parameterisations compared by **BIC**.

**Maximum likelihood, not MCMC — a stated simplification.** Every model has at most four
free parameters, all bounded, so a multi-start simplex finds the mode without a sampler, a
prior or a convergence diagnostic. What is given up is the posterior width on *f*, and that
is bought back where it matters: the interval quoted for a fraction comes from
:mod:`~mva.mosaic.simulate`'s forward simulation, which is a stronger statement than a
posterior anyway because it also carries the detection limit.

**ρ is fitted per chromosome here, and genome-wide in the Bdev test — deliberately.** They
answer different questions. Bdev asks "is this contig more spread out than the genome", so
its null must come from elsewhere or there is nothing to exceed. Model selection asks "is
the excess spread *bimodal*", and there a ρ imported from other chromosomes is simply a
misfit that the richest model absorbs: on this sample the per-chromosome ρ ranges twelvefold
(0.0057 on chr5 to 0.067 on chr21), so a shared value describes almost no contig. The two
instruments have opposite blind spots, which is why the step reports both.

**ΔBIC < 10 is low-confidence, and is Kong's own threshold.** Adopted as written. A
chromosome whose best and second-best models sit inside it is reported as
*not distinguishable*, never as the better-scoring one — the number, not the ranking, is
what gets printed.

**The depth evidence for a whole chromosome is one number, not three hundred thousand.**
The obvious implementation sums a negative binomial over every PASS call's depth, and it is
wrong in a way that quietly decides every call: with 350,000 sites, a chromosome sitting
0.5 %% off the genome-wide mean — ordinary GC and mappability variation, present on a
perfectly normal genome — produces a likelihood difference of thousands, and every
chromosome is called monosomic or trisomic. What that sum measures is *site-to-site* depth
variation within the chromosome, which says nothing about whether the chromosome **as a
whole** is deeper than the rest of the genome.

So the depth term here is a single Gaussian on the chromosome's mean depth ratio, whose
width is the **measured spread of that ratio across chromosomes**. One observation, one
comparison, against the variation a normal genome actually shows. The within-chromosome
negative binomial is still fitted and reported — it is the right description of depth at a
site, and its variance-to-mean ratio is a QC number — but it does not choose between models.
This is a departure from Kong 2018's formulation and it is recorded as one.

**The baseline must not assume any chromosome is normal.** That is the whole difficulty of
a *variegated* disease and it is not solved here: this module takes the baseline and the
spread it is given. :mod:`~mva.mosaic.baseline` computes them, by leaving each chromosome
out in turn and flagging any whose exclusion moves the result.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize, minimize_scalar
from scipy.special import expit, logit

from . import betabinom, models
from .likelihood import (
    DEFAULT_DEPTH_SD,
    allele_log_likelihood,
    depth_log_likelihood,
    fit_depth_dispersion,
)
from .models import Model
from .tables import AlleleHistogram, DepthHistogram

__all__ = [
    "DELTA_BIC",
    "FRACTION_BOUNDS",
    "ModelFit",
    "Verdict",
    "best",
    "fit_model",
    "fit_models",
]

#: Kong 2018's own low-confidence threshold, adopted as written.
DELTA_BIC = 10.0

#: A mosaic fraction below 0.5 %% is not distinguishable from noise at any realistic depth,
#: and above 0.9 the sample is not mosaic but constitutional -- which is a different claim
#: and a different test.
FRACTION_BOUNDS = (0.005, 0.90)


@dataclass(frozen=True)
class ModelFit:
    """One model fitted to one chromosome."""

    chrom: str
    model: str
    fraction: float
    tract: float
    #: fitted per chromosome, not the genome-wide value the Bdev null uses
    rho: float
    #: the share of calls no band claims to explain -- repeats, unflagged copy number,
    #: one allele mapping badly. Every model carries it, so it cannot decide the comparison
    noise_share: float
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
            "rho": round(self.rho, 6),
            "noise_share": round(self.noise_share, 5),
            "depth_dispersion": round(self.depth_dispersion, 3),
            "log_likelihood": round(self.log_likelihood, 2),
            "parameters": self.parameters,
            "observations": self.observations,
            "bic": round(self.bic, 2),
        }


#: Starting noise share for the shape fit. Two per cent: what the clean autosomes here
#: actually show, so the simplex begins inside the answer rather than at a boundary.
START_NOISE = 0.02


def _fit_shape(
    alleles: AlleleHistogram,
    bands: list[models.Band],
    *,
    centre: float,
    rho: float,
) -> tuple[float, float, float]:
    """Best (log-likelihood, ρ, ε) for a *fixed* band layout — the inner fit.

    Two parameters, both nuisance, both about shape rather than about mechanism. Keeping
    them in their own simplex is what makes the outer search over the cell fraction
    meaningful: in a four-dimensional simplex the allele term's pull on ρ is five orders of
    magnitude larger than the depth term's pull on *f*, and the fraction coordinate simply
    drifts to wherever it started.
    """

    def negative(theta: np.ndarray) -> float:
        fitted = float(np.clip(np.exp(theta[0]), *betabinom.RHO_BOUNDS))
        noise = float(np.clip(expit(theta[1]), 1e-6, 0.5))
        value = allele_log_likelihood(alleles, bands, fitted, noise=noise, centre=centre)
        return -value if np.isfinite(value) else 1e18

    found = minimize(
        negative,
        np.array([np.log(rho), logit(START_NOISE)]),
        method="Nelder-Mead",
        options={"maxiter": 400, "xatol": 1e-4, "fatol": 1e-3},
    )
    return (
        float(-found.fun),
        float(np.clip(np.exp(found.x[0]), *betabinom.RHO_BOUNDS)),
        float(np.clip(expit(found.x[1]), 1e-6, 0.5)),
    )


def fit_model(
    model: Model,
    alleles: AlleleHistogram,
    depth: DepthHistogram,
    *,
    rho: float,
    centre: float,
    baseline_depth: float,
    depth_spread: float = DEFAULT_DEPTH_SD,
) -> ModelFit:
    """Fit one model to one chromosome: the cell fraction outside, the shape inside.

    ``rho`` is the genome-wide value and is only a starting point; the fitted one is per
    chromosome, for the reason in the module docstring.

    **The depth term is inside the objective, not added to the result.** A monosomy's bands
    are a normal chromosome's bands, so its allele likelihood is flat in the cell fraction
    and depth is the only thing that identifies *f* at all. Fitting the allele term first
    and adding depth afterwards sent it to the bound.
    """

    def score(fraction: float, tract: float) -> tuple[float, float, float, float]:
        bands = models.bands_for(model, fraction, centre, tract)
        allele, fitted_rho, noise = _fit_shape(alleles, bands, centre=centre, rho=rho)
        depths = depth_log_likelihood(
            depth, baseline_depth * models.depth_ratio(model, fraction), spread=depth_spread
        )
        return allele + depths, fitted_rho, noise, allele

    def best_tract(fraction: float) -> float:
        if not model.has_tract:
            return 0.0
        return float(
            minimize_scalar(
                lambda share: -score(fraction, share)[0], bounds=(0.0, 0.9), method="bounded"
            ).x
        )

    if model.has_fraction:
        fraction = float(
            minimize_scalar(
                lambda value: -score(value, best_tract(value))[0],
                bounds=FRACTION_BOUNDS,
                method="bounded",
            ).x
        )
    else:
        fraction = 0.0
    tract = best_tract(fraction)
    _, fitted_rho, noise, allele = score(fraction, tract)

    mean = baseline_depth * models.depth_ratio(model, fraction)
    return ModelFit(
        chrom=alleles.chrom or depth.chrom,
        model=model.name,
        fraction=fraction,
        tract=tract,
        rho=fitted_rho,
        noise_share=noise,
        depth_dispersion=fit_depth_dispersion(depth, mean),
        allele_log_likelihood=allele,
        depth_log_likelihood=depth_log_likelihood(depth, mean, spread=depth_spread),
        parameters=model.parameters,
        # The heterozygous calls, plus the one chromosome-level depth observation. Counting
        # every PASS call here would make log N -- and so the BIC penalty -- depend on how
        # many sites happen to lie on the chromosome rather than on how much was measured.
        observations=max(alleles.n_sites + 1, 2),
    )


def fit_models(
    alleles: AlleleHistogram,
    depth: DepthHistogram,
    *,
    rho: float,
    centre: float,
    baseline_depth: float,
    depth_spread: float = DEFAULT_DEPTH_SD,
) -> tuple[ModelFit, ...]:
    """All five, in declaration order."""
    return tuple(
        fit_model(
            model,
            alleles,
            depth,
            rho=rho,
            centre=centre,
            baseline_depth=baseline_depth,
            depth_spread=depth_spread,
        )
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
    #: the noise share the ``normal`` model needed -- this contig's honest tail burden
    noise_share: float = 0.0

    @property
    def measurable(self) -> bool:
        """False when the tails swallow the contig: no band structure survives underneath."""
        return self.noise_share <= models.NOISE_CEILING

    @property
    def call(self) -> str:
        """The model name, or the honest refusal. Never the ranking on its own."""
        if not self.measurable:
            return "not measurable"
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
            "noise_share": round(self.noise_share, 5),
            "measurable": self.measurable,
        }


def best(fits: tuple[ModelFit, ...], *, delta: float = DELTA_BIC) -> Verdict:
    """Rank five fits by BIC and apply Kong's low-confidence rule."""
    ranked = sorted(fits, key=lambda fit: fit.bic)
    leader, second = ranked[0], ranked[1]
    by_name = {fit.model: fit for fit in fits}
    pair = by_name["cnloh"].bic - by_name["mitotic_trisomy"].bic
    # The gate reads ``normal``'s noise share, not the leader's: a degenerate fit can hide
    # the tails inside its extra bands and report almost none, which is exactly the failure
    # the gate exists to catch.
    tails = by_name["normal"].noise_share
    return Verdict(
        chrom=leader.chrom,
        best=leader.model,
        runner_up=second.model,
        delta_bic=second.bic - leader.bic,
        fraction=leader.fraction,
        trisomy_vs_cnloh=pair,
        confident=(second.bic - leader.bic) >= delta,
        noise_share=tails,
    )
