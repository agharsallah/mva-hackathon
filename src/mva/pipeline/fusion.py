"""Merging several rankings of the same candidates into one, and saying what that is worth.

Four instruments looked at this case and each produced its own ordering: symptoms alone, a
likelihood ratio over the callset, published knowledge, and the raw reads. **Reciprocal rank
fusion** (Cormack 2009) merges orderings without needing their scores to be on the same
scale — each list contributes ``w / (k + rank)`` and the sums are added up. It needs no
training data, which is exactly the situation here.

Three things this module refuses to let a caller gloss over:

* **A route that ranks nothing may not vote.** ``Route.admitted`` is set by whoever measured
  the route, not here; a route that failed its own admission test is kept in the input with
  ``weight = 0`` so it still appears in every exhibit, contributing zero. Deleting it would
  hide the measurement that disqualified it.
* **Absent is not last.** A candidate missing from a route's top ``TOP_N`` gets
  :data:`MISSING_RANK`, never a score of zero and never rank infinity. The route said
  "not in my top 50", which is a weaker statement than "worst".
* **Correlated lists are not separate witnesses.** Each route declares which *raw inputs* it
  read. The independent-evidence count is the size of the **union** of those inputs over the
  routes that ranked the candidate — so two routes that both read the symptom terms count
  once, not twice.

Nothing here knows about genes, alleles or this case. Give it ordered keys.

The ``ranx`` library was considered as a reference implementation and not adopted: it pulls a
compiled dependency tree for forty lines of arithmetic. The tests check every sum against the
published formula computed by hand instead, which is the property an external library would
have been used to check.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

__all__ = [
    "MISSING_RANK",
    "TOP_N",
    "UNITS",
    "Confirmation",
    "Edge",
    "Frozen",
    "FusedPair",
    "K",
    "Pair",
    "Route",
    "RouteRank",
    "freeze",
    "fuse",
    "inherit",
    "leave_one_out",
]

#: Cormack 2009's constant. It damps the top of each list so that one route's rank 1 cannot
#: by itself outweigh agreement further down; 60 is the published default and is fixed here
#: rather than tuned, because tuning it after seeing the answer is how a fusion lies.
K = 60

#: How many candidates each route contributes. Beyond this a route is saying "I did not
#: look", not "these are bad".
TOP_N = 50

#: The rank given to a candidate a route did not list. One worse than the last listed rank,
#: so every absent candidate is treated identically and none is scored zero.
MISSING_RANK = TOP_N + 1

#: What a route ranks. A route that orders genes or alleles has its ranks *inherited* by the
#: pairs those belong to; a route that already orders pairs is used as it stands.
UNITS = ("pair", "gene", "allele")


@dataclass(frozen=True, order=True)
class Pair:
    """One biallelic candidate: a gene and the one or two alleles proposed for it.

    ``allele_b`` is empty for the single-allele shape — one damaging allele with no partner,
    which a funnel deletes and a ranking keeps.
    """

    gene: str
    allele_a: str
    allele_b: str = ""

    @property
    def id(self) -> str:
        """The stable identifier used in exports, tables and the frozen hash."""
        return f"{self.gene}|{self.allele_a}|{self.allele_b}"

    def keys(self, unit: str) -> tuple[str, ...]:
        """The keys a route of ``unit`` would have ranked, for this pair."""
        if unit == "pair":
            return (self.id,)
        if unit == "gene":
            return (self.gene,)
        if unit == "allele":
            return tuple(a for a in (self.allele_a, self.allele_b) if a)
        raise ValueError(f"unit must be one of {UNITS}, not {unit!r}")


@dataclass(frozen=True)
class Route:
    """One instrument's ordering, and what it is entitled to do.

    ``admitted`` and ``weight`` are decisions made by whoever measured the route — its
    separation, its recall, its error rate — and are recorded here, not derived here.
    """

    name: str
    unit: str
    admitted: bool = True
    weight: float = 1.0
    #: The raw inputs this route read: the vocabulary is the caller's, but it must name
    #: *sources*, not steps, or the independent-evidence count degenerates into a route count.
    inputs: tuple[str, ...] = ()
    #: One sentence: the measurement that admitted or disqualified it.
    reason: str = ""

    def __post_init__(self) -> None:
        if self.unit not in UNITS:
            raise ValueError(f"{self.name}: unit must be one of {UNITS}, not {self.unit!r}")
        if self.weight < 0:
            raise ValueError(f"{self.name}: a negative weight is not a vote, it is a veto")

    @property
    def votes(self) -> bool:
        """Whether this route contributes to the sum at all."""
        return self.admitted and self.weight > 0


@dataclass(frozen=True)
class Edge:
    """One dependency in the route-dependency graph: who consumed whose output.

    The graph is an exhibit and an audit trail. It does **not** enter the arithmetic — the
    collapse that matters is done by :class:`Route.inputs`, because two routes are correlated
    exactly when they read the same source, whether or not one called the other.
    """

    source: str
    target: str
    consumed: str
    shared_input: bool = False


@dataclass(frozen=True)
class RouteRank:
    """Where one route placed one pair, and whether it said so directly."""

    route: str
    pair: Pair
    rank: int
    #: True when the rank was inherited from a gene or an allele rather than stated for the
    #: pair itself. A reader needs this: three pairs in one gene share one opinion.
    inherited: bool = False


@dataclass(frozen=True)
class Confirmation:
    """What the confirmation route says about a pair. No rank, three booleans.

    A route measured to order nothing is not made into a ranker by being given a weight; it
    is asked the questions it can answer.
    """

    read_confirmed: bool = False
    single_copy: bool = False
    no_cn_loss: bool = False

    @property
    def complete(self) -> bool:
        """All three answered in the affirmative."""
        return self.read_confirmed and self.single_copy and self.no_cn_loss

    @property
    def inputs(self) -> tuple[str, ...]:
        """The raw input this contributes to the independent-evidence count, if any."""
        return ("reads",) if self.read_confirmed else ()


@dataclass(frozen=True)
class FusedPair:
    """One candidate after fusion: its score, its rank, and what stands behind it."""

    pair: Pair
    score: float
    rank: int
    per_route: Mapping[str, int] = field(default_factory=dict)
    confirmation: Confirmation = Confirmation()
    #: The union of the raw inputs of every route that listed this pair, plus the reads when
    #: the confirmation route saw it. Sorted, so the row is stable.
    inputs: tuple[str, ...] = ()

    @property
    def independent_evidence(self) -> int:
        """How many disjoint sources speak for this pair. One means four routes, one witness."""
        return len(self.inputs)


@dataclass(frozen=True)
class Frozen:
    """A fused ranking, exported and hashed before anybody compares it to anything."""

    text: str
    sha256: str
    rows: int


def inherit(
    route: Route,
    order: Sequence[str],
    pairs: Iterable[Pair],
    *,
    top: int = TOP_N,
) -> list[RouteRank]:
    """Turn one route's ordered keys into per-pair ranks.

    ``order`` is the route's own ranking, best first, in whatever unit the route works in:
    pair ids, gene symbols or allele identifiers. Only the first ``top`` entries are read —
    past that the route is not expressing an opinion.

    A pair whose key is absent gets no row at all; :func:`fuse` supplies
    :data:`MISSING_RANK` for it, so "absent" is stated in exactly one place.

    An allele-unit route gives a pair the **best** rank among its alleles: the route's claim
    is about one allele, and the pair inherits the strongest such claim rather than an
    average that no instrument ever produced.
    """
    position = {key: index + 1 for index, key in enumerate(order[:top])}
    inherited = route.unit != "pair"
    ranks: list[RouteRank] = []
    for pair in pairs:
        found = [position[key] for key in pair.keys(route.unit) if key in position]
        if found:
            ranks.append(
                RouteRank(route=route.name, pair=pair, rank=min(found), inherited=inherited)
            )
    return ranks


def _rank_of(ranks: Iterable[RouteRank]) -> dict[tuple[str, str], int]:
    """``(route, pair id) -> rank``, keeping the best rank if a caller passes duplicates."""
    best: dict[tuple[str, str], int] = {}
    for row in ranks:
        key = (row.route, row.pair.id)
        if key not in best or row.rank < best[key]:
            best[key] = row.rank
    return best


def _competition_ranks(scores: Sequence[float]) -> list[int]:
    """1, 2, 2, 4 — ties share a rank and the next rank skips. ``scores`` is descending."""
    ranks: list[int] = []
    for index, score in enumerate(scores):
        if index and score == scores[index - 1]:
            ranks.append(ranks[-1])
        else:
            ranks.append(index + 1)
    return ranks


def fuse(
    routes: Sequence[Route],
    ranks: Iterable[RouteRank],
    *,
    confirmations: Mapping[str, Confirmation] | None = None,
    k: int = K,
    missing: int = MISSING_RANK,
) -> list[FusedPair]:
    """Reciprocal rank fusion over the routes that vote.

    ``score(pair) = Σ w_r / (k + rank_r)`` over every voting route, with ``missing`` standing
    in for a route that did not list the pair. Routes that do not vote still appear in
    ``per_route`` — a reader sees where the weight-0 route would have put it — but contribute
    nothing to the sum.

    The result is sorted by score descending, ties broken by pair id so two runs of the same
    inputs produce byte-identical output; that is what makes the frozen hash mean something.
    """
    rows = list(ranks)
    by_key = _rank_of(rows)
    pairs = {row.pair.id: row.pair for row in rows}
    confirmed = dict(confirmations or {})
    for pair_id in confirmed:
        if pair_id not in pairs:
            raise ValueError(f"confirmation for {pair_id!r}, which no route ranked")

    scored: list[tuple[float, str, Pair, dict[str, int], tuple[str, ...]]] = []
    for pair_id, pair in pairs.items():
        per_route = {r.name: by_key.get((r.name, pair_id), missing) for r in routes}
        score = sum(
            r.weight / (k + per_route[r.name]) for r in routes if r.votes and r.name in per_route
        )
        sources = {
            source for r in routes if r.votes and per_route[r.name] < missing for source in r.inputs
        }
        sources.update(confirmed.get(pair_id, Confirmation()).inputs)
        scored.append((score, pair_id, pair, per_route, tuple(sorted(sources))))

    scored.sort(key=lambda row: (-row[0], row[1]))
    positions = _competition_ranks([row[0] for row in scored])
    return [
        FusedPair(
            pair=pair,
            score=score,
            rank=position,
            per_route=per_route,
            confirmation=confirmed.get(pair_id, Confirmation()),
            inputs=sources,
        )
        for (score, pair_id, pair, per_route, sources), position in zip(
            scored, positions, strict=True
        )
    ]


def leave_one_out(
    routes: Sequence[Route],
    ranks: Iterable[RouteRank],
    *,
    confirmations: Mapping[str, Confirmation] | None = None,
    k: int = K,
    missing: int = MISSING_RANK,
) -> dict[str, list[FusedPair]]:
    """Re-fuse once per voting route, with that route removed.

    The question it answers is "does any single instrument carry the result". With fewer than
    two voting routes there is nothing to leave out and the answer is an empty mapping —
    which is itself the finding, and must be reported as one rather than as a passing test.
    """
    voting = [route for route in routes if route.votes]
    if len(voting) < 2:
        return {}
    rows = list(ranks)
    out: dict[str, list[FusedPair]] = {}
    for dropped in voting:
        kept = [route if route.name != dropped.name else _silenced(route) for route in routes]
        out[dropped.name] = fuse(kept, rows, confirmations=confirmations, k=k, missing=missing)
    return out


def _silenced(route: Route) -> Route:
    """The same route, contributing nothing — kept so ``per_route`` still shows its opinion."""
    return Route(
        name=route.name,
        unit=route.unit,
        admitted=False,
        weight=0.0,
        inputs=route.inputs,
        reason=f"left out: {route.reason}" if route.reason else "left out",
    )


#: The frozen export's columns. Written out rather than derived from the dataclass, because
#: the hash of this file is quoted in a methodology entry and a silent column change would
#: invalidate it without anybody noticing.
COLUMNS = ("rank", "pair_id", "gene", "score", "independent_evidence", "inputs", "confirmation")


def freeze(fused: Sequence[FusedPair], *, routes: Sequence[Route] = ()) -> Frozen:
    """Serialise a fused ranking to canonical TSV and hash it.

    The text is the artifact: same rows, same order, same formatting, therefore same digest.
    Scores are printed at 12 significant digits — enough that two orderings which differ
    cannot hash the same, few enough that platform float formatting cannot make an identical
    run differ from itself.
    """
    header = list(COLUMNS) + [route.name for route in routes]
    lines = ["\t".join(header)]
    for row in fused:
        confirmation = "".join(
            flag
            for flag, on in (
                ("R", row.confirmation.read_confirmed),
                ("1", row.confirmation.single_copy),
                ("C", row.confirmation.no_cn_loss),
            )
            if on
        )
        cells = [
            str(row.rank),
            row.pair.id,
            row.pair.gene,
            f"{row.score:.12g}",
            str(row.independent_evidence),
            ",".join(row.inputs),
            confirmation or "-",
        ]
        cells.extend(str(row.per_route.get(route.name, MISSING_RANK)) for route in routes)
        lines.append("\t".join(cells))
    text = "\n".join(lines) + "\n"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return Frozen(text=text, sha256=digest, rows=len(fused))
