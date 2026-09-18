"""Does the literature order anything a hit count does not?

A knowledge route is the easiest route in this whole iteration to fool yourself with. The
gene at the top of any literature search is the gene most has been written about, and the
most-written-about gene in a symptom-derived candidate set is very often the one somebody
already solved. A ranking that merely reproduces citation volume has learned nothing about
*this* child, however convincing its top row looks.

So the route is measured twice, against two baselines fixed before the run:

**Citation volume.** Rank the same genes by PubMed hit count alone. If the knowledge
ranking agrees with that ordering, the route *is* citation volume and is reported as a
negative result rather than fused into step 6.

**The decoy set.** Score the 396 matched control genes through the identical code path and
measure the separation as an AUC with a bootstrap interval — the same instrument step 4
used, reused rather than re-derived, so the two routes' weights are comparable numbers.

Agreement is reported as a **Spearman rank correlation** (how well one ordering predicts
the other, ties handled by mid-ranks) *and* as **top-k overlap**, because they fail
differently: a route can reshuffle the long tail while leaving the leaders untouched, and
only the second notices.

Nothing here knows what a gene is. Give it names and scores.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ..pipeline.nulls import Separation, separation

__all__ = [
    "Agreement",
    "RouteWeight",
    "agreement",
    "ranks",
    "spearman",
    "tied_at",
    "top_k_overlap",
    "weigh",
]

#: The leader set the overlap is measured on. Five is what the plan pre-registered.
TOP_K = 5

#: Seed for the decoy bootstrap. Fixed so the interval is reproducible from the entry.
SEED = 20260918


@dataclass(frozen=True)
class Agreement:
    """How closely two orderings of the same genes agree."""

    rho: float
    overlap: int
    k: int
    genes: int
    #: The leaders of each ordering, so a reader can see *which* gene moved.
    left_top: tuple[str, ...] = ()
    right_top: tuple[str, ...] = ()
    #: How many genes sit on the score that decides entry to the left ordering's top k.
    #:
    #: A coarse score ties heavily, and a top-k set cut out of a tie is decided by whatever
    #: the sort falls back on — here the gene symbol, which carries nothing. When this
    #: number is larger than the number of slots the tie is filling, the overlap statistic
    #: is partly alphabetical and must be read with that said out loud.
    tied_at_k: int = 0

    @property
    def reorders(self) -> bool:
        """Pre-registered condition: rho below 0.9, or the top-k sets are not identical."""
        return self.rho < 0.9 or self.overlap < self.k

    @property
    def verdict(self) -> str:
        if self.reorders:
            return f"reorders: rho {self.rho:.3f}, top-{self.k} overlap {self.overlap}/{self.k}"
        return (
            f"does not reorder: rho {self.rho:.3f} and the top {self.k} are identical - "
            "the ordering is citation volume under another name"
        )


@dataclass(frozen=True)
class RouteWeight:
    """What step 6 is entitled to do with this route, derived from its own measurement."""

    separation: Separation
    agreement: Agreement

    @property
    def ranking_route(self) -> bool:
        """A route may rank only if it both separates and adds something to the count."""
        return self.separation.separates and self.agreement.reorders

    @property
    def verdict(self) -> str:
        if self.ranking_route:
            return "ranking route: separates targets from decoys and reorders the citation baseline"
        reasons = []
        if not self.separation.separates:
            reasons.append("no measured separation from matched decoys")
        if not self.agreement.reorders:
            reasons.append("adds nothing to the citation count")
        return "confirmation route at weight 0: " + "; ".join(reasons)


def ranks(scores: Sequence[tuple[str, float]]) -> dict[str, float]:
    """Mid-rank per name, highest score first, ties sharing the average of their ranks.

    Mid-ranks rather than arbitrary tie-breaking because a knowledge score is coarse — a
    matched-term count takes eight values — and breaking those ties on an alphabetical
    order would manufacture a disagreement that the data does not contain.
    """
    ordered = sorted(scores, key=lambda row: -row[1])
    out: dict[str, float] = {}
    index = 0
    while index < len(ordered):
        stop = index
        while stop + 1 < len(ordered) and ordered[stop + 1][1] == ordered[index][1]:
            stop += 1
        mid = (index + stop) / 2.0 + 1.0
        for position in range(index, stop + 1):
            out[ordered[position][0]] = mid
        index = stop + 1
    return out


def spearman(left: Sequence[tuple[str, float]], right: Sequence[tuple[str, float]]) -> float:
    """Spearman's rho over the names both orderings contain.

    Returns 0.0 when fewer than three names are shared or when either ordering is
    constant: a correlation over two points, or over a column with no variance, is not a
    measurement and printing one would invite it to be read as one.
    """
    left_ranks, right_ranks = ranks(left), ranks(right)
    shared = sorted(set(left_ranks) & set(right_ranks))
    if len(shared) < 3:
        return 0.0
    n = len(shared)
    xs = [left_ranks[name] for name in shared]
    ys = [right_ranks[name] for name in shared]
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    dx = [x - mean_x for x in xs]
    dy = [y - mean_y for y in ys]
    numerator = sum(a * b for a, b in zip(dx, dy, strict=True))
    denominator = (sum(a * a for a in dx) * sum(b * b for b in dy)) ** 0.5
    return numerator / denominator if denominator else 0.0


def top_k_overlap(
    left: Sequence[tuple[str, float]], right: Sequence[tuple[str, float]], k: int = TOP_K
) -> tuple[int, tuple[str, ...], tuple[str, ...]]:
    """How many names the two orderings' top ``k`` share, and what each top ``k`` is."""
    left_top = tuple(name for name, _ in sorted(left, key=lambda row: (-row[1], row[0]))[:k])
    right_top = tuple(name for name, _ in sorted(right, key=lambda row: (-row[1], row[0]))[:k])
    return len(set(left_top) & set(right_top)), left_top, right_top


def tied_at(scores: Sequence[tuple[str, float]], k: int = TOP_K) -> int:
    """How many genes share the score that decides entry to the top ``k``.

    Reported rather than resolved. A knowledge score built on a matched-term count takes a
    handful of values, so the k-th place is often a tie of dozens, and which of them the
    sort admits is decided by the gene symbol. That does not make the overlap statistic
    wrong; it makes it partly alphabetical, and a reader has to be told which.
    """
    ordered = sorted(scores, key=lambda row: -row[1])
    if len(ordered) < k:
        return len(ordered)
    boundary = ordered[k - 1][1]
    return sum(1 for _, score in ordered if score == boundary)


def agreement(
    knowledge: Sequence[tuple[str, float]],
    citations: Sequence[tuple[str, float]],
    k: int = TOP_K,
) -> Agreement:
    """The two agreement statistics between the knowledge ordering and its baseline."""
    overlap, left_top, right_top = top_k_overlap(knowledge, citations, k)
    shared = {name for name, _ in knowledge} & {name for name, _ in citations}
    return Agreement(
        rho=spearman(knowledge, citations),
        overlap=overlap,
        k=k,
        genes=len(shared),
        left_top=left_top,
        right_top=right_top,
        tied_at_k=tied_at(knowledge, k),
    )


def weigh(
    target_scores: Sequence[float],
    decoy_scores: Sequence[float],
    knowledge: Sequence[tuple[str, float]],
    citations: Sequence[tuple[str, float]],
    *,
    seed: int = SEED,
) -> RouteWeight:
    """Both measurements at once: what step 6 needs to know about this route, and why.

    The two conditions are conjunctive on purpose. A route that separates targets from
    decoys but only because famous genes are both better studied and more likely to be
    nominated has not demonstrated knowledge; a route that reorders the citation count but
    cannot tell a candidate from a matched control has demonstrated noise.
    """
    return RouteWeight(
        separation=separation(list(target_scores), list(decoy_scores), seed=seed),
        agreement=agreement(knowledge, citations),
    )
