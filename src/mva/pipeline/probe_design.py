"""Design a submission as a measurement: what would every possible reply tell us?

The challenge scorer returns five numbers per upload. Read naively they are a score. Read
against a **hypothesis space** — the set of answer keys we still consider possible — they
are a measurement: each possible truth produces one reply, and the reply we actually get
rules out every truth that would have produced a different one.

This module makes that reading mechanical and case-agnostic. Give it the rows of a
candidate submission and a list of hypothesised truths (each a set of one or two alleles,
optionally weighted by prior belief), and it:

* simulates the reply for every truth with :func:`mva.pipeline.scorer.score`, the local
  replica of the published scorer;
* groups truths by the reply they would produce — the **decode table**: one line per
  distinguishable outcome, listing which truths survive it;
* measures how much a submission would teach us: the expected information gain (in bits)
  over the prior, so two candidate layouts can be compared before one is spent.

Nothing here touches the network or the database. It is the "information-gain probe
designer" step 6 names, in its simplest honest form: exhaustive simulation over an
explicit hypothesis space, no closed-form decode rule to get wrong.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field

from .scorer import ScoreResult, score
from .submission import Row
from .variant import Variant

__all__ = ["Design", "Hypothesis", "Outcome", "design", "entropy", "reply_key"]


@dataclass(frozen=True)
class Hypothesis:
    """One possible answer key with the belief we hold in it before the upload."""

    truth: frozenset[Variant]
    label: str
    prior: float = 1.0

    def __post_init__(self) -> None:
        if not 1 <= len(self.truth) <= 2:
            raise ValueError(f"{self.label}: an answer key holds one or two alleles")
        if self.prior < 0:
            raise ValueError(f"{self.label}: prior must be non-negative")


@dataclass(frozen=True)
class Outcome:
    """One distinguishable reply and the hypotheses that would produce it."""

    key: tuple
    reply: ScoreResult
    hypotheses: tuple[Hypothesis, ...]
    mass: float  # summed normalised prior of the surviving hypotheses

    @property
    def decisive(self) -> bool:
        """A reply that leaves exactly one hypothesis standing."""
        return len(self.hypotheses) == 1


@dataclass
class Design:
    """A candidate submission evaluated against a hypothesis space."""

    rows: list[Row]
    outcomes: list[Outcome] = field(default_factory=list)
    prior_entropy: float = 0.0
    expected_posterior_entropy: float = 0.0

    @property
    def expected_information_gain(self) -> float:
        """Bits of uncertainty the upload is expected to remove."""
        return self.prior_entropy - self.expected_posterior_entropy

    @property
    def max_ambiguity(self) -> int:
        """The largest number of hypotheses any single reply leaves indistinguishable."""
        return max((len(o.hypotheses) for o in self.outcomes), default=0)


def reply_key(result: ScoreResult) -> tuple:
    """The part of a reply the oracle actually exposes, hashable.

    ``rank_points`` is a function of the two ranks, and ``n_predictions_at_f_max`` is not
    returned by the real endpoint, so neither adds information; both are left out.
    """
    return (
        result.full_match_rank,
        result.partial_match_rank,
        round(result.f_max, 6),
        None if result.f_max_threshold is None else round(result.f_max_threshold, 6),
    )


def entropy(weights: list[float]) -> float:
    """Shannon entropy in bits of a normalised distribution; zero weights contribute 0."""
    total = sum(weights)
    if total <= 0:
        return 0.0
    return -sum((w / total) * math.log2(w / total) for w in weights if w > 0)


def design(rows: list[Row], hypotheses: list[Hypothesis]) -> Design:
    """Simulate every hypothesis against ``rows`` and group by the reply it would produce."""
    if not hypotheses:
        raise ValueError("a design needs at least one hypothesis to measure against")
    total = sum(h.prior for h in hypotheses)
    if total <= 0:
        raise ValueError("every prior is zero; nothing to weigh")

    groups: dict[tuple, list[tuple[Hypothesis, ScoreResult]]] = defaultdict(list)
    for hypothesis in hypotheses:
        result = score(rows, hypothesis.truth)
        groups[reply_key(result)].append((hypothesis, result))

    outcomes: list[Outcome] = []
    expected_posterior = 0.0
    for key, members in groups.items():
        members_h = tuple(h for h, _ in members)
        mass = sum(h.prior for h in members_h) / total
        posterior_h = entropy([h.prior for h in members_h])
        expected_posterior += mass * posterior_h
        outcomes.append(Outcome(key=key, reply=members[0][1], hypotheses=members_h, mass=mass))

    # Most likely reply first; a full match before a partial before nothing; then by rank.
    outcomes.sort(key=lambda o: (-o.mass, *(-1 if v is None else v for v in o.key[:2]), -o.key[2]))
    return Design(
        rows=rows,
        outcomes=outcomes,
        prior_entropy=entropy([h.prior for h in hypotheses]),
        expected_posterior_entropy=expected_posterior,
    )
