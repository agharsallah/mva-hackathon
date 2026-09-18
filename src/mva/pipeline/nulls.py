"""How high would this score have come out by chance?

A genome-wide ranking scores tens of thousands of candidates, so a large number at the top
proves nothing on its own — something has to be at the top. Two nulls answer two different
questions, and this module is the machinery both of them share.

**The permutation null** asks whether the *input* mattered: recompute the whole ranking from
inputs drawn at random with the same shape as the real ones, and count how often the random
run reaches the observed score. It tests specificity to this case's evidence.

**The decoy null** asks whether the *scoring* discriminates: score a matched control set
through the identical code path and measure how well the score separates the two. It tests
the filter, which is where discriminating power actually lives — a gene list that separates
nothing tells you the list was the wrong instrument.

Separation is measured as the area under the ROC curve (**AUC**): the probability that a
randomly chosen target outscores a randomly chosen decoy, with ties counted as half. 0.5 is
"no separation at all", and an interval that covers 0.5 means the same thing however large
the point estimate looks.

Nothing here knows what is being scored. Give it numbers.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from statistics import median

#: Bootstrap resamples, matching :meth:`mva.phenotype.benchmark.Result.interval` so every
#: interval in the project is built the same way.
RESAMPLES = 1000

#: Two-sided coverage of a reported interval.
LEVEL = 0.95


@dataclass(frozen=True)
class Separation:
    """How far apart two score distributions are, with the interval that says if it is real."""

    auc: float
    low: float
    high: float
    positives: int
    negatives: int
    resamples: int

    @property
    def separates(self) -> bool:
        """Whether the interval excludes 0.5 — the only reading that survives a reviewer."""
        return self.low > 0.5 or self.high < 0.5

    @property
    def verdict(self) -> str:
        if self.positives == 0 or self.negatives == 0:
            return "not measurable: one side is empty"
        if self.separates:
            return f"separates: AUC {self.auc:.3f} [{self.low:.3f}, {self.high:.3f}]"
        return (
            f"no measured separation: AUC {self.auc:.3f} "
            f"[{self.low:.3f}, {self.high:.3f}] covers 0.5"
        )


@dataclass(frozen=True)
class Permutation:
    """What a null distribution of top scores says about one observed top score."""

    observed: float
    draws: tuple[float, ...]
    #: How many permuted runs reached or exceeded the observed value.
    exceeded: int
    #: Mean count of candidates per run that beat the observed score — the expected number
    #: of false leads, which is the number a reader actually needs.
    expected_false_leads: float

    @property
    def p_value(self) -> float:
        """``(exceeded + 1) / (draws + 1)`` — never zero, because a finite null cannot prove 0."""
        return (self.exceeded + 1) / (len(self.draws) + 1)

    @property
    def null_median(self) -> float | None:
        return median(self.draws) if self.draws else None


def auc(positives: list[float], negatives: list[float]) -> float:
    """Probability a random positive outscores a random negative; ties count as half.

    Computed from ranks (the Mann-Whitney identity) rather than by comparing every pair, so
    it stays linear-ish rather than quadratic on a genome-wide table.
    """
    if not positives or not negatives:
        return 0.5
    combined = sorted(
        (value, side) for side, values in ((1, positives), (0, negatives)) for value in values
    )
    ranks = _midranks([value for value, _ in combined])
    rank_sum = sum(rank for rank, (_, side) in zip(ranks, combined, strict=True) if side == 1)
    n_pos, n_neg = len(positives), len(negatives)
    return (rank_sum - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def separation(
    positives: list[float],
    negatives: list[float],
    *,
    seed: int,
    resamples: int = RESAMPLES,
    level: float = LEVEL,
) -> Separation:
    """AUC with a bootstrap interval, resampled from the observed scores themselves."""
    point = auc(positives, negatives)
    if not positives or not negatives:
        return Separation(point, point, point, len(positives), len(negatives), 0)
    rng = random.Random(seed)
    draws = sorted(
        auc(
            [rng.choice(positives) for _ in range(len(positives))],
            [rng.choice(negatives) for _ in range(len(negatives))],
        )
        for _ in range(resamples)
    )
    tail = (1.0 - level) / 2.0
    return Separation(
        auc=point,
        low=draws[int(tail * resamples)],
        high=draws[min(int((1 - tail) * resamples), resamples - 1)],
        positives=len(positives),
        negatives=len(negatives),
        resamples=resamples,
    )


def permutation(observed: float, tops: list[float], beaten: list[int] | None = None) -> Permutation:
    """Compare ``observed`` against the top score of each permuted run.

    ``beaten`` is how many candidates each permuted run put above ``observed``; its mean is
    the expected number of false leads, which is more useful than a p-value alone when the
    question is "how many of these should I chase".
    """
    counts = beaten or []
    return Permutation(
        observed=observed,
        draws=tuple(tops),
        exceeded=sum(1 for value in tops if value >= observed),
        expected_false_leads=(sum(counts) / len(counts)) if counts else 0.0,
    )


def _midranks(values: list[float]) -> list[float]:
    """1-based ranks with ties averaged, over an already sorted list."""
    ranks: list[float] = [0.0] * len(values)
    start = 0
    while start < len(values):
        stop = start
        while stop + 1 < len(values) and values[stop + 1] == values[start]:
            stop += 1
        shared = (start + stop) / 2 + 1
        for index in range(start, stop + 1):
            ranks[index] = shared
        start = stop + 1
    return ranks
