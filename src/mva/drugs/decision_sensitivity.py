"""Where does the decision flip? Prior sweeps, exact flip points and a tornado.

* **Flip points.** With every other weight held, the expected utility of each action is a
  straight line in one prior ``p = P(variable=value)`` (the other values share ``1 - p`` in
  their stated ratio, so every state's weight is linear in ``p``). The best action over
  ``p in [0, 1]`` is therefore the *upper envelope* of those lines, and the prior values at
  which it changes are computed exactly - no grid, no interpolation.
* **Sweep.** EVPI and each test's EVSI on a grid of ``p``, for the value-of-information curve.
* **Tornado.** Each addressed parameter (see :mod:`mva.drugs.decision_config`) is set to its
  low and high end in turn, the rest held; the swing of the chosen metric, and whether the
  best action changes, are recorded. Rows sort by swing, largest first.

Every function takes ``build``: a callable from a config to a decision table, so this module
knows nothing about where candidates or safety flags come from.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from mva.drugs.decision_config import with_param, with_prior
from mva.drugs.decision_model import DecisionConfig, DecisionTable
from mva.drugs.decision_voi import best_index, evpi, evsi, expected, test_likelihoods

__all__ = [
    "Segment",
    "TornadoRow",
    "envelope",
    "flip_points",
    "metrics",
    "sweep",
    "tornado",
]

Build = Callable[[DecisionConfig], DecisionTable]
EPS = 1e-12


@dataclass(frozen=True)
class Segment:
    """``[start, end]`` of ``p`` over which ``action`` is best."""

    start: float
    end: float
    action: str


@dataclass(frozen=True)
class TornadoRow:
    param: str
    low: float
    high: float
    metric_low: float
    metric_high: float
    best_low: str
    best_high: str
    base_best: str

    @property
    def swing(self) -> float:
        return abs(self.metric_high - self.metric_low)

    @property
    def flips(self) -> bool:
        """True when either end of the range changes the best action."""
        return self.best_low != self.base_best or self.best_high != self.base_best


def envelope(lines: Sequence[tuple[float, float]]) -> list[tuple[float, float, int]]:
    """Upper envelope of ``y = a + b p`` on [0, 1] as ``(start, end, line index)`` pieces.

    Ties at a point go to the line that dominates just after it (larger slope), then to the
    lower index - the same baseline-first rule as :func:`best_index`.
    """

    def pick(candidates: Sequence[int], at: float) -> int:
        top = max(lines[i][0] + lines[i][1] * at for i in candidates)
        tied = [i for i in candidates if lines[i][0] + lines[i][1] * at >= top - EPS]
        slope = max(lines[i][1] for i in tied)
        return next(i for i in tied if lines[i][1] >= slope - EPS)

    pieces: list[tuple[float, float, int]] = []
    start, current = 0.0, pick(range(len(lines)), 0.0)
    while True:
        a0, b0 = lines[current]
        crossings = [
            ((a0 - a) / (b - b0), j)
            for j, (a, b) in enumerate(lines)
            if b > b0 + EPS and start + EPS < (a0 - a) / (b - b0) < 1.0 - EPS
        ]
        if not crossings:
            pieces.append((start, 1.0, current))
            return pieces
        at = min(x for x, _ in crossings)
        nxt = pick([j for x, j in crossings if x <= at + EPS], at)
        pieces.append((start, at, current))
        start, current = at, nxt


def flip_points(config: DecisionConfig, build: Build, variable: str, value: str) -> list[Segment]:
    """The best action as a function of ``P(variable=value)``, one segment per action run."""
    zero, one = (
        build(with_prior(config, variable, value, 0.0)),
        build(with_prior(config, variable, value, 1.0)),
    )
    if zero.actions != one.actions:
        raise ValueError("the action set changed across the sweep")
    e0, e1 = expected(zero.utility, zero.probs), expected(one.utility, one.probs)
    pieces = envelope([(a, b - a) for a, b in zip(e0, e1, strict=True)])
    return [Segment(s, e, zero.actions[i]) for s, e, i in pieces]


def metrics(config: DecisionConfig, table: DecisionTable) -> dict[str, float | str]:
    """Best action, its EU, EVPI and ``evsi:<test>`` for every configured test."""
    eus = expected(table.utility, table.probs)
    best = best_index(eus)
    out: dict[str, float | str] = {
        "best": table.actions[best],
        "eu_best": eus[best],
        "evpi": evpi(table.utility, table.probs),
    }
    for test in config.tests:
        likelihoods = test_likelihoods(table.states, test)
        out[f"evsi:{test.name}"] = evsi(table.utility, table.probs, likelihoods)[0]
    return out


def sweep(
    config: DecisionConfig, build: Build, variable: str, value: str, steps: int = 101
) -> list[dict[str, float | str]]:
    """:func:`metrics` at ``steps`` evenly spaced priors ``P(variable=value)`` in [0, 1]."""
    rows = []
    for i in range(steps):
        p = i / (steps - 1)
        swept = with_prior(config, variable, value, p)
        rows.append({"p": p, **metrics(swept, build(swept))})
    return rows


def tornado(config: DecisionConfig, build: Build, metric: str) -> list[TornadoRow]:
    """One row per configured :class:`~mva.drugs.decision_model.TornadoParam`."""
    base = metrics(config, build(config))
    rows = []
    for spec in config.tornado:
        ends = []
        for value in (spec.low, spec.high):
            varied = with_param(config, spec.param, value)
            ends.append(metrics(varied, build(varied)))
        rows.append(
            TornadoRow(
                param=spec.param,
                low=spec.low,
                high=spec.high,
                metric_low=float(ends[0][metric]),
                metric_high=float(ends[1][metric]),
                best_low=str(ends[0]["best"]),
                best_high=str(ends[1]["best"]),
                base_best=str(base["best"]),
            )
        )
    return sorted(rows, key=lambda row: -row.swing)
