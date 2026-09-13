"""From two counts to a genotype, with a posterior instead of a threshold.

Each allele has a reference probe and an alternate probe. Counting both in the reads gives
two numbers, and the genotype is which of three stories explains them:

======================  ==========================================================
**hom-ref** (0 copies)  the reference probe is covered, the alternate is near zero
**het** (1 copy)        both are covered at about half the depth
**hom-alt** (2 copies)  the alternate is covered, the reference is near zero
======================  ==========================================================

"Near zero" is not zero, and "about half" is not exactly half, which is why this is a
fitted model and not a pair of cutoffs.

**Negative binomial, not Poisson.** Sequencing coverage is not a Poisson process. GC
content, amplification and mappability make some places systematically deeper than others,
so the variance of a count exceeds its mean — **over-dispersion**. A Poisson model has no
parameter for that and answers the question "is 12 surprising when I expected 22" far too
confidently. The negative binomial adds exactly one parameter, the dispersion, and the
variance-to-mean ratio of the calibration counts is reported beside every fit so a reader
can see how far from Poisson this sample actually is. FastGT (Pajuste 2017) uses the same
family for the same reason, and this is a port of its classifier onto ``scipy.stats.nbinom``.

**Fitted on this sample, from markers whose answer is already known.** The delivered callset
names tens of thousands of confident heterozygous and homozygous-alternate SNVs. Counting
*their* probes gives a set of counts whose class is not in question, and the model's four
quantities are read off them:

* **λ, the per-copy coverage** — the mean alternate count of the heterozygous markers. The
  same number computed from their *reference* counts is reported beside it: the two are the
  same quantity measured on opposite sides of the same markers, and a gap between them is a
  strand or mapping asymmetry, not a genotype.
* **the dispersion** — by maximum likelihood at that mean.
* **the error rate** — the reference probe of a homozygous-alternate marker should never be
  seen; how often it is, is the rate at which a sequencing error manufactures a k-mer that
  is not there. It is what stops an absent allele being called present.
* **the class priors** — a stated parameter, defaulting to **uniform**. A population prior
  would be right for a genome scan and is wrong here: every allele typed has already been
  nominated by an aligner and a caller, so the question is not "what is a random site" but
  "is this particular claim true".

**Calibration markers must come from the same baited recovery as the probes.** The bait
recovered 0.905 of the reads carrying a known allele (entry 087). Drawing calibration and
probe counts from the same recovery makes that factor common to both sides of the ratio the
model fits, so it cancels. A genome-wide calibration set against baited probe counts would
read every allele as about 10 % under-covered.

**No-call is an answer.** An allele whose best posterior does not clear the floor, or whose
probes disagree, is *not* quietly assigned its most likely class. The model returns the
state and the caller reports it, because "the instrument could not say" and "the allele is
absent" are different findings and only one of them is about the child.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.stats import nbinom

#: Posterior a call must reach to be a call. H024 is written about this number.
DEFAULT_FLOOR = 0.95

#: Bounds for the dispersion search. Below 0.01 the distribution is almost all mass at zero;
#: above 10,000 it is Poisson to any precision a count of this size can distinguish.
DISPERSION_BOUNDS = (1e-2, 1e4)


class Genotype(IntEnum):
    """Copies of the alternate allele, plus the state that is not a count."""

    HOM_REF = 0
    HET = 1
    HOM_ALT = 2
    NO_CALL = -1


#: The three classes a posterior is computed over, in column order.
CLASSES = (Genotype.HOM_REF, Genotype.HET, Genotype.HOM_ALT)


@dataclass(frozen=True)
class Fit:
    """The model, and the numbers that say whether to believe it."""

    lambda_per_copy: float
    dispersion: float
    error_rate: float
    priors: tuple[float, float, float]
    variance_to_mean: float
    lambda_from_reference: float
    het_markers: int
    hom_alt_markers: int

    @property
    def expected_depth(self) -> float:
        """Total expected coverage of a diploid site — the number to read against the
        measured median depth of the baited alignment."""
        return 2.0 * self.lambda_per_copy

    @property
    def side_disagreement(self) -> float:
        """Relative gap between λ measured on the alternate and on the reference side.

        Both are the per-copy coverage of the *same* heterozygous markers. A large gap means
        the two probes of a pair are not sampling the reads equally — a reference-bias or
        strand effect — and the fit should be retired rather than explained."""
        if self.lambda_per_copy <= 0:
            return float("inf")
        return abs(self.lambda_from_reference - self.lambda_per_copy) / self.lambda_per_copy

    def as_dict(self) -> dict[str, float | int]:
        return {
            "lambda_per_copy": round(self.lambda_per_copy, 4),
            "lambda_from_reference": round(self.lambda_from_reference, 4),
            "side_disagreement": round(self.side_disagreement, 4),
            "expected_depth": round(self.expected_depth, 4),
            "dispersion": round(self.dispersion, 4),
            "variance_to_mean": round(self.variance_to_mean, 4),
            "error_rate": round(self.error_rate, 6),
            "prior_hom_ref": self.priors[0],
            "prior_het": self.priors[1],
            "prior_hom_alt": self.priors[2],
            "het_markers": self.het_markers,
            "hom_alt_markers": self.hom_alt_markers,
        }


def _nb_logpmf(counts: np.ndarray, mean: float, dispersion: float) -> np.ndarray:
    """``nbinom`` parameterised by its mean, which is how the model thinks about it."""
    mean = max(mean, 1e-9)
    probability = dispersion / (dispersion + mean)
    return np.asarray(nbinom.logpmf(counts, dispersion, probability), dtype=float)


def _fit_dispersion(counts: np.ndarray, mean: float) -> float:
    """Maximum-likelihood dispersion at a fixed mean.

    One dimension, bounded, so a scalar search is both sufficient and auditable — there is
    no starting point to get wrong and no convergence story to tell.
    """
    if counts.size == 0:
        return DISPERSION_BOUNDS[1]

    def negative_log_likelihood(log_dispersion: float) -> float:
        value = _nb_logpmf(counts, mean, float(np.exp(log_dispersion))).sum()
        return float(-value) if np.isfinite(value) else 1e18

    result = minimize_scalar(
        negative_log_likelihood,
        bounds=(float(np.log(DISPERSION_BOUNDS[0])), float(np.log(DISPERSION_BOUNDS[1]))),
        method="bounded",
    )
    return float(np.exp(result.x))


def fit(
    het_reference: np.ndarray,
    het_alternate: np.ndarray,
    hom_alt_reference: np.ndarray,
    hom_alt_alternate: np.ndarray,
    *,
    priors: tuple[float, float, float] = (1 / 3, 1 / 3, 1 / 3),
) -> Fit:
    """Read the model off markers whose genotype the delivered callset already settled.

    The four arrays are probe counts, not genotypes: ``het_alternate`` is the alternate
    probe's count at each confidently heterozygous marker, and so on.
    """
    het_alternate = np.asarray(het_alternate, dtype=float)
    het_reference = np.asarray(het_reference, dtype=float)
    hom_alt_reference = np.asarray(hom_alt_reference, dtype=float)
    hom_alt_alternate = np.asarray(hom_alt_alternate, dtype=float)
    if het_alternate.size == 0:
        raise ValueError("no heterozygous calibration markers: nothing to fit λ on")

    per_copy = float(het_alternate.mean())
    dispersion = _fit_dispersion(het_alternate, per_copy)
    variance_to_mean = float(het_alternate.var(ddof=1) / per_copy) if per_copy > 0 else 0.0

    # A homozygous-alternate marker has no reference copy, so every reference-probe count it
    # shows was manufactured — by a sequencing error, or by a read from somewhere the
    # uniqueness filter did not catch. Expressed per expected-copy so it scales with depth.
    if hom_alt_alternate.size and hom_alt_alternate.mean() > 0:
        error_rate = float(hom_alt_reference.mean() / hom_alt_alternate.mean())
    else:
        error_rate = 0.0

    return Fit(
        lambda_per_copy=per_copy,
        dispersion=dispersion,
        error_rate=error_rate,
        priors=priors,
        variance_to_mean=variance_to_mean,
        lambda_from_reference=float(het_reference.mean()) if het_reference.size else 0.0,
        het_markers=int(het_alternate.size),
        hom_alt_markers=int(hom_alt_alternate.size),
    )


def expected(fit_: Fit, copies: int) -> tuple[float, float]:
    """Mean reference and alternate probe counts for a genotype with ``copies`` alternates.

    A copy contributes λ to its own probe and ``error_rate × λ`` to the other one — the rate
    at which a read of one allele is miscounted as the other.
    """
    alt_copies, ref_copies = float(copies), float(2 - copies)
    alternate = (
        alt_copies * fit_.lambda_per_copy + fit_.error_rate * ref_copies * fit_.lambda_per_copy
    )
    reference = (
        ref_copies * fit_.lambda_per_copy + fit_.error_rate * alt_copies * fit_.lambda_per_copy
    )
    return reference, alternate


def posteriors(reference: np.ndarray, alternate: np.ndarray, fit_: Fit) -> np.ndarray:
    """Posterior over the three classes, one row per observation.

    Computed in log space and normalised with the usual max-subtraction, because at 44× the
    likelihood of the wrong class underflows a float long before it stops mattering.
    """
    reference = np.asarray(reference, dtype=float)
    alternate = np.asarray(alternate, dtype=float)
    columns = []
    for index, genotype in enumerate(CLASSES):
        mean_reference, mean_alternate = expected(fit_, int(genotype))
        prior = max(fit_.priors[index], 1e-12)
        columns.append(
            _nb_logpmf(reference, mean_reference, fit_.dispersion)
            + _nb_logpmf(alternate, mean_alternate, fit_.dispersion)
            + np.log(prior)
        )
    stacked = np.stack(columns, axis=-1)
    # A row where every class is impossible has no posterior to normalise, and the usual
    # max-subtraction would turn it into NaN — which argmax then reads as class 0, quietly
    # calling the allele homozygous reference. It happens for real: a count that is not a
    # whole number (the median of an even number of probes) has zero probability under
    # every negative binomial, because the distribution is over counts. Such a row is
    # returned flat, which fails any posterior floor and is reported as a no-call — the
    # honest answer, and the one an unexplained hom-ref would have hidden.
    impossible = ~np.isfinite(stacked).any(axis=-1)
    stacked = np.where(impossible[..., None], 0.0, stacked)
    stacked -= stacked.max(axis=-1, keepdims=True)
    weights = np.exp(stacked)
    return weights / weights.sum(axis=-1, keepdims=True)


@dataclass(frozen=True)
class Call:
    """One allele's verdict, with everything needed to argue with it."""

    genotype: Genotype
    posterior: float
    reference_count: int
    alternate_count: int
    probes: int
    agreeing: int

    @property
    def confident(self) -> bool:
        return self.genotype is not Genotype.NO_CALL


def call_alleles(
    reference: np.ndarray,
    alternate: np.ndarray,
    probes: np.ndarray,
    fit_: Fit,
    *,
    floor: float = DEFAULT_FLOOR,
    minimum_probes: int = 1,
) -> list[Call]:
    """Per-allele calls from per-allele summed counts.

    ``probes`` is how many probe pairs survived for each allele. An allele below
    ``minimum_probes`` is a ``NO_CALL`` whatever its counts say: one probe cannot disagree
    with itself, so its agreement carries no information.
    """
    weights = posteriors(reference, alternate, fit_)
    best = weights.argmax(axis=-1)
    strength = weights.max(axis=-1)
    calls: list[Call] = []
    for index in range(len(best)):
        enough = probes[index] >= minimum_probes
        clears = strength[index] >= floor
        genotype = CLASSES[best[index]] if (enough and clears) else Genotype.NO_CALL
        calls.append(
            Call(
                genotype=genotype,
                posterior=float(strength[index]),
                reference_count=int(reference[index]),
                alternate_count=int(alternate[index]),
                probes=int(probes[index]),
                agreeing=0,
            )
        )
    return calls


def per_probe_agreement(
    reference: np.ndarray, alternate: np.ndarray, fit_: Fit
) -> tuple[np.ndarray, np.ndarray]:
    """The class each individual probe pair votes for, and its posterior.

    H024 asks that all of an allele's probes agree. Agreement is only evidence when it was
    computed probe by probe — summing the counts first would hide exactly the disagreement
    a private neighbouring variant produces.
    """
    weights = posteriors(reference, alternate, fit_)
    return weights.argmax(axis=-1), weights.max(axis=-1)


def dropout(fit_: Fit, copies: int = 1) -> float:
    """P(count = 0 | the allele is present at ``copies``), from the fitted model.

    The quantity behind "absent". Computed from the negative binomial rather than from the
    Poisson tail the method survey quoted: over-dispersion puts far more mass at zero than
    Poisson does, and the optimistic figure would make every absence look decisive.
    """
    _, mean_alternate = expected(fit_, copies)
    return float(np.exp(_nb_logpmf(np.array([0.0]), mean_alternate, fit_.dispersion))[0])


def minimum_count(fit_: Fit, *, false_positive: float = 1e-3) -> int:
    """The smallest alternate count an absent allele is unlikely to reach by error alone.

    H025 rests on this: "present" means a count this model would not expect a
    homozygous-reference site to manufacture more often than ``false_positive``.
    """
    _, mean_alternate = expected(fit_, 0)
    for threshold in range(1000):
        tail = float(
            nbinom.sf(
                threshold - 1,
                fit_.dispersion,
                fit_.dispersion / (fit_.dispersion + max(mean_alternate, 1e-9)),
            )
        )
        if tail <= false_positive:
            return threshold
    return 1000


__all__ = [
    "CLASSES",
    "DEFAULT_FLOOR",
    "Call",
    "Fit",
    "Genotype",
    "call_alleles",
    "dropout",
    "expected",
    "fit",
    "minimum_count",
    "per_probe_agreement",
    "posteriors",
]
