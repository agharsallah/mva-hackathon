"""How a ranked set of fits is read — the three refusals, and what licenses each.

Split from :mod:`mva.mosaic.madseq` so that module fits the five models and this one decides
what their ranking is allowed to say. The split is also what keeps both under the size gate,
and the concerns really are separate: the fitting is arithmetic, and every line here is a
rule about when a number may be called a result.

Three ways the ranking is refused, in the order they are checked:

``not measurable``            the contig's tail burden under ``normal`` is past
                              :data:`mva.mosaic.models.NOISE_CEILING`. No band structure
                              survives underneath it, so there is nothing for a mechanism to
                              be a mechanism *of*.
``model family not usable``   a parameter of the winning fit is pinned against its own
                              bound. A boundary solution is not an estimate: it says the
                              shape the data wants is outside the family rather than inside
                              it at that value.
``not distinguishable``       Kong 2018's own rule — the margin over the runner-up is under
                              ten, so the ranking is not a call.

Only when all three pass does the model's name appear. On this sample that happens once, on
the single contig whose fit is entirely in the interior, and the model it names is ``normal``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import betabinom, models
from .madseq import DELTA_BIC, FRACTION_BOUNDS, TRACT_BOUND, ModelFit

__all__ = [
    "BOUND_MARGIN",
    "DEGENERATE_RHO_FACTOR",
    "Verdict",
    "best",
]

#: How close to its lower bound the over-dispersion must sit to count as collapsed. Ten
#: times the bound: a real fit never approaches it, because real allele balance is
#: over-dispersed and rho is what says so.
DEGENERATE_RHO_FACTOR = 10.0

#: How close to a bound counts as being at it. One per cent: tight enough that a genuine
#: estimate near the edge is not condemned, loose enough that the optimiser stopping a
#: rounding error short of the bound is still caught.
BOUND_MARGIN = 0.01


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
    #: the leading fit's own parameters, so a reader can see whether any of them is pinned
    #: against a bound -- which is what separates a mechanism from a density estimator
    #: wearing one's name
    leader_rho: float = float("nan")
    leader_tract: float = 0.0
    leader_noise: float = 0.0

    @property
    def measurable(self) -> bool:
        """False when the tails swallow the contig: no band structure survives underneath."""
        return self.noise_share <= models.NOISE_CEILING

    @property
    def degenerate(self) -> bool:
        """True when a parameter of the winning fit is pinned against its own bound.

        A boundary solution is not an estimate: the optimiser was pushed as far as the
        parameterisation allows and stopped there, which says the shape the data wants is
        outside the family rather than inside it at that value. Only parameters the winning
        model actually fits are checked — ``normal`` has no tract and no fraction to pin.
        """
        model = models.by_name(self.best)
        if not np.isfinite(self.leader_rho):
            return False
        if self.leader_rho <= betabinom.RHO_BOUNDS[0] * DEGENERATE_RHO_FACTOR:
            return True
        # The noise share is checked at its *upper* end only. Zero is the right answer for
        # data with no tails -- every simulated arm in the test suite fits it -- and
        # condemning that would flag a correct fit on clean data. A large share is caught by
        # NOISE_CEILING instead, one property up.
        if self.leader_noise >= 0.5 * (1.0 - BOUND_MARGIN):
            return True
        if model.has_tract and self.leader_tract >= TRACT_BOUND * (1.0 - BOUND_MARGIN):
            return True
        return bool(
            model.has_fraction
            and (
                self.fraction <= FRACTION_BOUNDS[0] * (1.0 + BOUND_MARGIN)
                or self.fraction >= FRACTION_BOUNDS[1] * (1.0 - BOUND_MARGIN)
            )
        )

    @property
    def call(self) -> str:
        """The model name, or the honest refusal. Never the ranking on its own."""
        if not self.measurable:
            return "not measurable"
        if self.degenerate:
            return "model family not usable"
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
            "degenerate": self.degenerate,
            "leader_rho": round(self.leader_rho, 6),
            "leader_tract": round(self.leader_tract, 4),
            "leader_noise": round(self.leader_noise, 5),
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
        leader_rho=leader.rho,
        leader_tract=leader.tract,
        leader_noise=leader.noise_share,
    )
