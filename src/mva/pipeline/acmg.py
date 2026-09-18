"""The ACMG/AMP evidence ladder, as a Bayesian classifier.

The ACMG/AMP guidelines classify a variant by counting criteria of four strengths —
*supporting*, *moderate*, *strong*, *very strong*. Tavtigian 2018 (PMID 29300386) showed the
counting rules are reproduced almost exactly by a Bayesian model in which each strength is a
fixed **likelihood ratio** (how many times more likely the observation is if the variant is
pathogenic than if it is not), applied to a **prior** of 0.10 that a variant reaching a
clinical laboratory is pathogenic.

In software terms: a strength label is not a score, it is a multiplier on the odds. Four
labels, four multipliers, and the ladder is geometric — each rung is the square root of the
one above it, which is why the numbers look arbitrary and are not:

    very strong = 350
    strong      = 350 ** (1/2)  = 18.7
    moderate    = 350 ** (1/4)  =  4.33
    supporting  = 350 ** (1/8)  =  2.08

Benign evidence is the same ladder inverted — a *supporting benign* observation divides the
odds by 2.08 rather than multiplying by it. Nothing here knows about any disease, gene or
case: it is the published ladder and no more.
"""

from __future__ import annotations

from enum import Enum
from math import log

#: Tavtigian 2018's prior probability of pathogenicity for a variant reaching a clinical lab.
#: Used as the prior odds of the genotype half of the likelihood ratio, never of the pair
#: posterior, which carries its own prior.
PRIOR = 0.10

#: The top rung, from which the whole ladder is derived.
VERY_STRONG = 350.0


class Strength(Enum):
    """One rung of the ACMG ladder, with its sign.

    ``NONE`` is a real state, not a missing value: it is what a lane returns when it looked
    and found nothing to say, and it multiplies the odds by exactly 1.
    """

    VERY_STRONG = "very_strong"
    STRONG = "strong"
    MODERATE = "moderate"
    SUPPORTING = "supporting"
    NONE = "none"
    SUPPORTING_BENIGN = "supporting_benign"
    MODERATE_BENIGN = "moderate_benign"
    STRONG_BENIGN = "strong_benign"
    VERY_STRONG_BENIGN = "very_strong_benign"

    @property
    def is_benign(self) -> bool:
        return self.name.endswith("_BENIGN")


#: The pathogenic side of the ladder. The benign side is derived, never tabulated twice.
_PATHOGENIC: dict[Strength, float] = {
    Strength.VERY_STRONG: VERY_STRONG,
    Strength.STRONG: VERY_STRONG ** (1 / 2),
    Strength.MODERATE: VERY_STRONG ** (1 / 4),
    Strength.SUPPORTING: VERY_STRONG ** (1 / 8),
    Strength.NONE: 1.0,
}


def likelihood_ratio(strength: Strength) -> float:
    """The odds multiplier for one rung — benign rungs are the reciprocal of their twin."""
    if not strength.is_benign:
        return _PATHOGENIC[strength]
    twin = Strength[strength.name.removesuffix("_BENIGN")]
    return 1.0 / _PATHOGENIC[twin]


def cap(strength: Strength, ceiling: Strength) -> Strength:
    """Lower ``strength`` to ``ceiling`` when it would otherwise exceed it.

    A lane whose calibration could not be read from its own paper is capped rather than
    dropped: it still contributes a direction, but never more than the ceiling the step
    pre-registered for it. Benign and pathogenic sides are capped independently — a ceiling
    on pathogenic evidence says nothing about how far benign evidence may go.
    """
    if strength.is_benign != ceiling.is_benign:
        return strength
    if abs(_log_rungs(strength)) <= abs(_log_rungs(ceiling)):
        return strength
    return ceiling


def _log_rungs(strength: Strength) -> float:
    """Signed position on the ladder, in powers of the supporting rung."""
    lr = likelihood_ratio(strength)
    if lr == 1.0:
        return 0.0
    return log(lr) / log(_PATHOGENIC[Strength.SUPPORTING])
