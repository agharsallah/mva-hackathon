"""Expected utility and the value of information over a decision table.

Plain arithmetic over an ``actions x states`` utility matrix and a prior over states:

* **expected utility** ``EU(a) = sum_s P(s) u(a, s)``; the best action maximises it. Ties go
  to the lower action index, and action 0 is the baseline, so a drug must *strictly* beat
  deferring.
* **EVPI** (expected value of perfect information): how much better the decision would be,
  on average, if the state were known before choosing -
  ``sum_s P(s) max_a u(a, s) - max_a EU(a)``. An upper bound on what any test is worth.
* **EVPPI** (partial perfect information): the same with only one variable revealed.
* **EVSI** (expected value of sample information) for a real, imperfect test: for each
  result ``r`` the prior is updated by Bayes' rule (``P(s | r)``, the **posterior**), the
  best action is chosen again, and the gains are averaged over ``P(r)``:
  ``sum_r P(r) max_a EU(a | r) - max_a EU(a)``. Always ``0 <= EVSI <= EVPI``.

The numbers inherit the heuristic status of the utilities (see
:data:`mva.drugs.decision_model.HEURISTIC_NOTE`): they rank which uncertainty matters most
for the triage, in utility units; they are not money, QALYs or probabilities of benefit.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from mva.drugs.decision_model import NamedTest, State

__all__ = [
    "Outcome",
    "best_index",
    "evpi",
    "evppi",
    "evsi",
    "expected",
    "posterior",
    "test_likelihoods",
]

Matrix = Sequence[Sequence[float]]
TIE = 1e-12


@dataclass(frozen=True)
class Outcome:
    """One test result: its marginal probability, the posterior and the action it picks."""

    result: str
    probability: float
    posterior: tuple[float, ...]
    best: int
    value: float


def expected(utility: Matrix, probs: Sequence[float]) -> list[float]:
    """``EU(a)`` for every action row."""
    return [sum(u * p for u, p in zip(row, probs, strict=True)) for row in utility]


def best_index(values: Sequence[float]) -> int:
    """The first index within :data:`TIE` of the maximum."""
    top = max(values)
    return next(i for i, v in enumerate(values) if v >= top - TIE)


def evpi(utility: Matrix, probs: Sequence[float]) -> float:
    """Expected value of perfect information on the whole state."""
    informed = sum(p * max(row[s] for row in utility) for s, p in enumerate(probs))
    return max(0.0, informed - max(expected(utility, probs)))


def evppi(utility: Matrix, probs: Sequence[float], groups: Sequence[str]) -> float:
    """Perfect information on one variable: ``groups[s]`` is that variable's value in ``s``."""
    informed = 0.0
    for group in dict.fromkeys(groups):
        mask = [p if g == group else 0.0 for p, g in zip(probs, groups, strict=True)]
        informed += max(expected(utility, mask))
    return max(0.0, informed - max(expected(utility, probs)))


def posterior(probs: Sequence[float], likelihood: Sequence[float]) -> tuple[float, list[float]]:
    """``(P(r), P(s | r))`` by Bayes' rule; a zero-probability result keeps the prior."""
    joint = [p * lik for p, lik in zip(probs, likelihood, strict=True)]
    marginal = sum(joint)
    if marginal <= 0.0:
        return 0.0, list(probs)
    return marginal, [j / marginal for j in joint]


def test_likelihoods(states: Sequence[State], test: NamedTest) -> dict[str, list[float]]:
    """``{"positive": P(+|s), "negative": P(-|s)}`` per state for a binary test."""
    pos = [
        test.sensitivity if dict(state)[test.variable] == test.positive else 1 - test.specificity
        for state in states
    ]
    return {"positive": pos, "negative": [1.0 - p for p in pos]}


def evsi(
    utility: Matrix, probs: Sequence[float], likelihoods: dict[str, list[float]]
) -> tuple[float, list[Outcome]]:
    """Expected value of sample information and the per-result decision."""
    outcomes: list[Outcome] = []
    total = 0.0
    for result, likelihood in likelihoods.items():
        marginal, post = posterior(probs, likelihood)
        values = expected(utility, post)
        best = best_index(values)
        outcomes.append(Outcome(result, marginal, tuple(post), best, values[best]))
        total += marginal * values[best]
    return max(0.0, total - max(expected(utility, probs))), outcomes
