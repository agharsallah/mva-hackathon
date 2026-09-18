"""Turning a ranker's *measured* recall curve into a likelihood ratio per rank.

LIRICAL asks: how many times more likely is this observation if the gene is causal than if
it is not? For a phenotype ranking the observation is **the rank the gene came out at**, so
the two distributions needed are:

* ``P(rank = r | causal)`` — measured, by running the ranker on held-out diseases whose
  causal gene is known and recording where it landed. That is exactly what a recall-at-N
  curve is: ``recall(n)`` is the probability the causal gene ranked at or above ``n``.
* ``P(rank = r | not causal)`` — a gene drawn at random from the candidate universe is
  equally likely to occupy any position, so the density is flat at ``1 / universe``.

The ratio of the two is the likelihood ratio, and because both distributions are
probabilities over the *same* partition (every gene is either ranked somewhere or has no
rank at all), the arithmetic closes: an unranked gene gets the leftover causal mass over the
leftover null mass — a number below 1, never zero. A gene nobody has curated is
down-weighted, not deleted, which is the whole reason a likelihood ratio is used here.

Nothing in this module knows what is being ranked. Give it a curve and two population sizes
and it will convert a rank into a ratio — for a phenotype ranker, a network ranker, or
anything else that has been benchmarked.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass

#: No bin may contribute a ratio outside this range. A measured curve with a tiny sample can
#: produce an empty bin, and an empty bin means "not measured", never "impossible".
MIN_LR = 1e-3
MAX_LR = 1e3


@dataclass(frozen=True)
class RecallPoint:
    """One point of a recall-at-N curve: of the known causal genes, this fraction ranked <= n."""

    n: int
    recall: float


@dataclass(frozen=True)
class RankBin:
    """One interval of ranks, and what a gene landing in it is worth."""

    low: int
    high: int
    causal_mass: float
    null_mass: float
    likelihood_ratio: float

    @property
    def width(self) -> int:
        return self.high - self.low


@dataclass(frozen=True)
class RankLikelihood:
    """A measured recall curve, read as a likelihood ratio per rank.

    ``ranked`` is how many candidates the ranker could place at all; ``universe`` is how many
    candidates exist. ``unrankable`` is the measured fraction of causal genes the ranker
    could not place — the curve's own miss rate at infinity, not one minus its last point.
    """

    curve: tuple[RecallPoint, ...]
    ranked: int
    universe: int
    unrankable: float
    source: str

    def __post_init__(self) -> None:
        if self.ranked <= 0 or self.universe < self.ranked:
            raise ValueError("universe must be at least as large as the ranked population")
        if not 0.0 <= self.unrankable < 1.0:
            raise ValueError("unrankable is a fraction of causal genes")
        if not self.curve:
            raise ValueError("a likelihood needs a measured curve")
        ns = [point.n for point in self.curve]
        if ns != sorted(ns) or len(set(ns)) != len(ns):
            raise ValueError("curve points must be strictly increasing in n")

    def bins(self) -> tuple[RankBin, ...]:
        """The curve as disjoint rank intervals, plus the tail out to ``ranked``."""
        out: list[RankBin] = []
        low = 0
        previous = 0.0
        for point in self.curve:
            out.append(self._bin(low, point.n, point.recall - previous))
            low, previous = point.n, point.recall
        if self.ranked > low:
            tail = max((1.0 - self.unrankable) - previous, 0.0)
            out.append(self._bin(low, self.ranked, tail))
        return tuple(out)

    def unranked_lr(self) -> float:
        """What a gene the ranker could not place at all is worth."""
        null = (self.universe - self.ranked) / self.universe
        if null <= 0:
            return 1.0
        return _clamp(self.unrankable / null)

    def lr(self, rank: int | None) -> float:
        """The likelihood ratio for a gene at ``rank``; ``None`` means the ranker had no rank."""
        if rank is None:
            return self.unranked_lr()
        if rank < 1:
            raise ValueError(f"rank is 1-based; got {rank}")
        bins = self.bins()
        edges = [b.high for b in bins]
        index = bisect_right(edges, rank - 1)
        if index >= len(bins):
            return self.unranked_lr()
        return bins[index].likelihood_ratio

    def _bin(self, low: int, high: int, causal: float) -> RankBin:
        null = (high - low) / self.universe
        ratio = _clamp(causal / null) if null > 0 else 1.0
        return RankBin(
            low=low,
            high=high,
            causal_mass=causal,
            null_mass=null,
            likelihood_ratio=ratio,
        )


def from_benchmark(
    curve: list[dict[str, float]],
    *,
    ranked: int,
    universe: int,
    unrankable: float,
    source: str,
) -> RankLikelihood:
    """Build from the JSON a benchmark run writes — ``[{"n": 300, "recall": 0.33}, ...]``."""
    points = tuple(RecallPoint(n=int(row["n"]), recall=float(row["recall"])) for row in curve)
    return RankLikelihood(
        curve=points,
        ranked=ranked,
        universe=universe,
        unrankable=unrankable,
        source=source,
    )


def _clamp(value: float) -> float:
    return min(max(value, MIN_LR), MAX_LR)
