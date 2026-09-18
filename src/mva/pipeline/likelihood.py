"""Combining independent-ish evidence into a posterior, without ever dropping a candidate.

A **hard filter** answers "is this gene in or out". A **likelihood ratio** (LR) answers "how
many times more likely is what I observed if this gene is causal than if it is not", and a
product of LRs applied to a prior gives a posterior. Nothing is ever excluded; a bad
observation multiplies by a number below 1 and the candidate sinks.

Two properties this module exists to guarantee:

* **The arithmetic is printable.** Every term keeps its name, its number, its source and its
  correlation group, so "why is this pair at rank 1" is answered by reading a table rather
  than by re-reading the code.
* **Correlated evidence is not counted twice.** Two lanes that were trained on overlapping
  data (a missense predictor tuned on ClinVar, and ClinVar itself) are not independent, and
  multiplying both at full strength inflates the posterior. Lanes carry a *correlation
  group*; within a group only the single strongest lane contributes and the others are kept
  in the record with a contribution of exactly 1. The rule is deliberately blunt — a
  measured correlation matrix does not exist for these tools on this case, and a blunt rule
  that is stated beats a tuned one that is not.

Nothing here knows about a disease, a gene or a coordinate: callers build :class:`Lane`
values from whatever evidence they have and hand them over.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from math import log10

from .acmg import Strength, likelihood_ratio

#: Odds this large are reported as-is but never allowed to overflow the log; a lane may not
#: exceed it in either direction. 1e12 is far above any product these lanes can justify and
#: exists only so a degenerate input cannot produce ``inf`` and poison a whole ranking.
LR_CEILING = 1e12


@dataclass(frozen=True)
class Lane:
    """One named strand of evidence, and the odds multiplier it contributes.

    ``group`` is the correlation group: lanes sharing a non-empty group are treated as one
    piece of evidence. ``source`` is the receipt — a PMID, a table name, a methodology entry
    — and is required by every consumer that writes an evidence row.
    """

    name: str
    likelihood_ratio: float
    source: str
    group: str = ""
    strength: Strength | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if self.likelihood_ratio <= 0:
            raise ValueError(f"lane {self.name!r}: likelihood ratio must be positive")
        if not self.source:
            raise ValueError(f"lane {self.name!r}: every lane names its source")

    @classmethod
    def from_strength(
        cls, name: str, strength: Strength, source: str, *, group: str = "", note: str = ""
    ) -> Lane:
        """Build a lane from an ACMG rung, so the ladder is the only place the numbers live."""
        return cls(
            name=name,
            likelihood_ratio=likelihood_ratio(strength),
            source=source,
            group=group,
            strength=strength,
            note=note,
        )

    @property
    def log10_lr(self) -> float:
        return log10(self.likelihood_ratio)

    @property
    def is_silent(self) -> bool:
        """Whether the lane says nothing — it looked, and had no evidence either way."""
        return self.likelihood_ratio == 1.0


@dataclass(frozen=True)
class Posterior:
    """A prior, the lanes that moved it, and where they left it."""

    prior: float
    lanes: tuple[Lane, ...]
    #: The lanes as they were actually applied: a damped member of a correlation group keeps
    #: its name and its note but carries a likelihood ratio of 1.
    applied: tuple[Lane, ...]

    @property
    def prior_odds(self) -> float:
        return self.prior / (1.0 - self.prior)

    @property
    def combined_lr(self) -> float:
        total = 1.0
        for lane in self.applied:
            total *= lane.likelihood_ratio
        return min(max(total, 1.0 / LR_CEILING), LR_CEILING)

    @property
    def posterior_odds(self) -> float:
        return self.prior_odds * self.combined_lr

    @property
    def probability(self) -> float:
        odds = self.posterior_odds
        return odds / (1.0 + odds)

    @property
    def log10_lr(self) -> float:
        return log10(self.combined_lr)

    @property
    def terms(self) -> tuple[tuple[str, float], ...]:
        """The arithmetic, labelled, in the order it was applied — including the damped ones.

        Same shape as :attr:`mva.pipeline.ranking.PairEvidence.terms`, so a consumer that
        already renders one renders the other.
        """
        return tuple((lane.name, lane.likelihood_ratio) for lane in self.applied)

    @property
    def damped(self) -> tuple[str, ...]:
        """The lanes a correlation group suppressed — named, so the suppression is visible."""
        applied = {lane.name: lane for lane in self.applied}
        return tuple(
            lane.name
            for lane in self.lanes
            if lane.likelihood_ratio != applied[lane.name].likelihood_ratio
        )


def combine(lanes: Iterable[Lane], *, prior: float) -> Posterior:
    """Apply ``lanes`` to ``prior``, damping every correlation group to its strongest member.

    ``prior`` is a probability strictly between 0 and 1. Nothing is filtered: a lane whose
    ratio is below 1 lowers the posterior and stays in the record.
    """
    if not 0.0 < prior < 1.0:
        raise ValueError(f"prior must lie strictly between 0 and 1; got {prior}")
    ordered = tuple(lanes)
    _reject_duplicate_names(ordered)
    return Posterior(prior=prior, lanes=ordered, applied=_damp(ordered))


def strongest(lanes: Sequence[Lane]) -> Lane | None:
    """The lane furthest from 1 in either direction, or ``None`` for an empty sequence.

    Ties are broken by the order given, so a caller that lists its best-calibrated lane first
    gets a deterministic answer.
    """
    if not lanes:
        return None
    return max(lanes, key=lambda lane: abs(lane.log10_lr))


def _damp(lanes: Sequence[Lane]) -> tuple[Lane, ...]:
    keep: dict[str, str] = {}
    for lane in lanes:
        if not lane.group:
            continue
        members = [other for other in lanes if other.group == lane.group]
        winner = strongest(members)
        if winner is not None:
            keep[lane.group] = winner.name
    return tuple(
        lane
        if not lane.group or keep.get(lane.group) == lane.name
        else replace(
            lane,
            likelihood_ratio=1.0,
            note=(f"{lane.note} " if lane.note else "").strip()
            + f" [damped: correlated with {keep.get(lane.group, '?')}]",
        )
        for lane in lanes
    )


def _reject_duplicate_names(lanes: Sequence[Lane]) -> None:
    seen: set[str] = set()
    for lane in lanes:
        if lane.name in seen:
            raise ValueError(f"duplicate lane name {lane.name!r}: a term is applied once")
        seen.add(lane.name)
