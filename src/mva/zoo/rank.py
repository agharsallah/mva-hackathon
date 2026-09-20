"""Turning per-allele scores into a ranking of pairs, one lane at a time.

Every model in the zoo emits one number per allele (a *variant-effect score*: higher = more
damaging, as that model defines it). The pairs themselves are built in :mod:`mva.zoo.pairs`;
this module is only about ordering them.

The pair score is deliberately the dullest thing that could work::

    pair_score(pair) = (min(left, right), max(left, right))

sorted by ``min`` first. In software terms it is the *bottleneck rule*: a pair is only as
damaging as its weaker half, because a gene with one intact copy is usually fine. ``max`` is
only the tie-break. Nothing is fitted and nothing is weighted, so the ranking carries no free
parameter a reviewer has to trust.

One rule the rest of the package depends on: **a pair with an unscored half is excluded from
that lane** — not scored zero. A model that cannot see splice variants must not be credited
with an opinion it never had. The count of such pairs (``unscored_pairs``) is reported beside
every rank.

Percentile convention, used everywhere in this package: a percentile is a **position from the
top**, in percent. Rank 1 of 20 is ``5.0`` ("the top 5 %"), rank 20 of 20 is ``100.0``.
Smaller is better. "Top decile" therefore means ``percentile <= 10``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .pairs import Pair, PairBuild, pairs_from_alleles, pairs_from_fixture

__all__ = [
    "MODEL_RANKS_COLUMNS",
    "MODEL_RANKS_TABLE",
    "ConfirmedRank",
    "ModelRank",
    "Pair",
    "PairBuild",
    "RankTable",
    "RankedPair",
    "confirmed_rank",
    "pair_score",
    "pairs_from_alleles",
    "pairs_from_fixture",
    "rank_pairs",
    "rank_per_model",
    "read_only_percentiles",
    "to_rows",
    "write_ranks",
]


@dataclass(frozen=True)
class RankedPair:
    """One pair with its lane score and its position in that lane."""

    pair: Pair
    min_score: float
    max_score: float
    rank: int


@dataclass(frozen=True)
class RankTable:
    """One lane's ranking of the callset's pairs, plus what it could not score.

    ``confirmed`` is kept beside the ranking rather than inside it, so that a lane which
    could not score the confirmed pair still knows which pair it failed to score.
    """

    model: str
    ranked: list[RankedPair] = field(default_factory=list)
    unscored_pairs: int = 0
    scored_alleles: int = 0
    confirmed: Pair | None = None

    @property
    def n_ranked(self) -> int:
        return len(self.ranked)

    def find(self, pair: Pair) -> RankedPair | None:
        """The ranked row for ``pair``, or ``None`` when this lane could not score it."""
        wanted = pair.key
        return next((row for row in self.ranked if row.pair.key == wanted), None)


@dataclass(frozen=True)
class ConfirmedRank:
    """Where the confirmed pair landed in one lane. ``None`` fields mean *not scored here*."""

    gene: str
    rank: int | None
    n_ranked: int
    percentile: float | None
    left_percentile: float | None
    right_percentile: float | None
    min_score: float | None = None
    max_score: float | None = None

    @property
    def scored(self) -> bool:
        return self.rank is not None


@dataclass(frozen=True)
class ModelRank:
    """One lane's whole ranking result: the table and the confirmed pair's place in it."""

    model: str
    table: RankTable
    confirmed: ConfirmedRank | None


# ---------------------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------------------


#: Where the append-only lineage edge lands. Not the schema the *result* lands in:
#: ``results`` holds the tables this module writes, ``warehouse`` holds
#: ``data_lineage``. Passing one schema for both is the bug entry 128 caught on the
#: first real run of the DAG.
LINEAGE_SCHEMA = "warehouse"


def pair_score(scores: Mapping[str, float], pair: Pair) -> tuple[float, float] | None:
    """``(min, max)`` of the pair's two allele scores, or ``None`` if either is unscored."""
    left = scores.get(pair.left_id)
    right = scores.get(pair.right_id)
    if left is None or right is None:
        return None
    return (min(left, right), max(left, right))


def rank_pairs(pairs: Sequence[Pair], scores: Mapping[str, float], *, model: str = "") -> RankTable:
    """Rank one lane's pairs by ``(min desc, max desc)``.

    Ties share a rank (competition ranking: 1, 2, 2, 4), so two pairs a model cannot tell
    apart are never separated by an accident of sort order. Pairs with an unscored half are
    excluded and counted.
    """
    scored: list[tuple[float, float, Pair]] = []
    unscored = 0
    for pair in pairs:
        value = pair_score(scores, pair)
        if value is None:
            unscored += 1
            continue
        scored.append((value[0], value[1], pair))
    scored.sort(key=lambda row: (-row[0], -row[1], row[2].key))

    ranked: list[RankedPair] = []
    previous: tuple[float, float] | None = None
    rank = 0
    for index, (low, high, pair) in enumerate(scored, start=1):
        if previous != (low, high):
            rank = index
            previous = (low, high)
        ranked.append(RankedPair(pair=pair, min_score=low, max_score=high, rank=rank))
    return RankTable(
        model=model,
        ranked=ranked,
        unscored_pairs=unscored,
        scored_alleles=len(scores),
        confirmed=next((p for p in pairs if p.is_confirmed), None),
    )


def confirmed_rank(
    table: RankTable, scores: Mapping[str, float] | None = None
) -> ConfirmedRank | None:
    """The confirmed pair's rank and percentile in one lane.

    Returns ``None`` when no pair in the table is flagged confirmed (the flag is set by the
    pair builder, from the gene symbol). When the pair exists but this lane scored neither or
    only one of its alleles, a row is still returned with ``rank=None`` — "this lane has no
    opinion" is a result, and the report prints it as one.
    """
    confirmed = table.confirmed
    if confirmed is None:
        return None
    lane_scores = scores if scores is not None else {}
    row = table.find(confirmed)
    n = table.n_ranked
    if row is None:
        return ConfirmedRank(
            gene=confirmed.gene,
            rank=None,
            n_ranked=n,
            percentile=None,
            left_percentile=_allele_percentile(lane_scores, confirmed.left_id),
            right_percentile=_allele_percentile(lane_scores, confirmed.right_id),
        )
    return ConfirmedRank(
        gene=confirmed.gene,
        rank=row.rank,
        n_ranked=n,
        percentile=round(100.0 * row.rank / n, 4) if n else None,
        left_percentile=_allele_percentile(lane_scores, confirmed.left_id),
        right_percentile=_allele_percentile(lane_scores, confirmed.right_id),
        min_score=row.min_score,
        max_score=row.max_score,
    )


def _allele_percentile(scores: Mapping[str, float], allele: str) -> float | None:
    """Position of one allele among all scored alleles of the lane, from the top, in percent."""
    value = scores.get(allele)
    if value is None or not scores:
        return None
    higher = sum(1 for other in scores.values() if other > value)
    return round(100.0 * (higher + 1) / len(scores), 4)


def rank_per_model(
    pairs: Sequence[Pair], scores_by_model: Mapping[str, Mapping[str, float]]
) -> dict[str, ModelRank]:
    """Run :func:`rank_pairs` once per lane and keep each lane's confirmed-pair row."""
    out: dict[str, ModelRank] = {}
    for model in sorted(scores_by_model):
        scores = scores_by_model[model]
        table = rank_pairs(pairs, scores, model=model)
        out[model] = ModelRank(model=model, table=table, confirmed=confirmed_rank(table, scores))
    return out


def read_only_percentiles(
    scores_by_model: Mapping[str, Mapping[str, float]],
    records: Iterable[Mapping[str, Any] | Any],
) -> list[dict[str, Any]]:
    """Per-model percentiles for the alleles only the raw reads saw.

    Those alleles have no VCF partner, so they are **scored but never paired** (plan §5,
    step 1). Their percentile among each lane's scored alleles is the only number the MVP
    reports for them, and this builds that table.
    """
    read_only = [r for r in records if _field(r, "is_read_only")]
    out: list[dict[str, Any]] = []
    for model in sorted(scores_by_model):
        scores = scores_by_model[model]
        for record in read_only:
            key = str(_field(record, "allele_id"))
            if key not in scores:
                continue
            out.append(
                {
                    "model": model,
                    "allele_id": key,
                    "gene": _field(record, "gene"),
                    "consequence": _field(record, "consequence"),
                    "score": scores[key],
                    "percentile": _allele_percentile(scores, key),
                    "n_scored": len(scores),
                }
            )
    return out


def _field(record: Mapping[str, Any] | Any, name: str) -> Any:
    if isinstance(record, Mapping):
        return record.get(name)
    return getattr(record, name, None)


# ---------------------------------------------------------------------------------------
# The warehouse table
# ---------------------------------------------------------------------------------------

#: ``results.it4_model_ranks`` — the top of each lane's pair ranking plus its confirmed row.
#: Append-only like every other iteration-4 table: a re-run is a new ``run_id``, never an edit.
MODEL_RANKS_TABLE = "it4_model_ranks"
MODEL_RANKS_COLUMNS: tuple[tuple[str, str], ...] = (
    ("run_id", "VARCHAR"),
    ("model", "VARCHAR"),
    ("gene", "VARCHAR"),
    ("left_allele_id", "VARCHAR"),
    ("right_allele_id", "VARCHAR"),
    ("phase", "VARCHAR"),
    ("min_score", "DOUBLE"),
    ("max_score", "DOUBLE"),
    ("rank", "BIGINT"),
    ("n_ranked", "BIGINT"),
    ("percentile", "DOUBLE"),
    ("unscored_pairs", "BIGINT"),
    ("is_confirmed", "BOOLEAN"),
    ("ts", "TIMESTAMP"),
)

#: How many top pairs per lane reach the table. The confirmed pair is always written, even
#: when it falls below the cut — the whole point of the table is that one row.
DEFAULT_TOP = 100


def to_rows(
    ranks: Mapping[str, ModelRank], *, run_id: str, top: int = DEFAULT_TOP
) -> list[tuple[Any, ...]]:
    """Flatten the per-lane rankings into ``results.it4_model_ranks`` rows."""
    now = datetime.now(UTC)
    rows: list[tuple[Any, ...]] = []
    for model in sorted(ranks):
        table = ranks[model].table
        n = table.n_ranked
        keep = [row for row in table.ranked if row.rank <= top or row.pair.is_confirmed]
        rows.extend(
            (
                run_id,
                model,
                row.pair.gene,
                row.pair.left_id,
                row.pair.right_id,
                row.pair.phase,
                row.min_score,
                row.max_score,
                row.rank,
                n,
                round(100.0 * row.rank / n, 4) if n else None,
                table.unscored_pairs,
                row.pair.is_confirmed,
                now,
            )
            for row in keep
        )
    return rows


def write_ranks(
    connection: Any,
    schema: str,
    ranks: Mapping[str, ModelRank],
    *,
    run_id: str,
    top: int = DEFAULT_TOP,
    source_ref: str = "results.coding_alleles + warehouse.allele_scores",
    lineage_schema: str = LINEAGE_SCHEMA,
) -> int:
    """Create the table if absent, append this run's rows, and record one lineage edge.

    ``schema`` is where the *result* lands (``results``); ``lineage_schema`` is where the
    edge lands (``warehouse``). They are different schemas and were the same argument until
    a real run said ``Table with name data_lineage does not exist`` (entry 128).
    """
    from ..warehouse.lineage import ensure_tables, record
    from ..warehouse.postgres import ALIAS, safe_identifier

    safe = safe_identifier(schema)
    columns = ", ".join(f"{name} {sql}" for name, sql in MODEL_RANKS_COLUMNS)
    connection.execute(f"CREATE TABLE IF NOT EXISTS {ALIAS}.{safe}.{MODEL_RANKS_TABLE} ({columns})")
    rows = to_rows(ranks, run_id=run_id, top=top)
    placeholders = ", ".join("?" for _ in MODEL_RANKS_COLUMNS)
    if rows:
        # One `executemany`, not 402 `execute`s. Against the *hosted* warehouse every
        # statement is a network round trip, and the row-at-a-time loop this replaced cost
        # 336.7 s of a 541 s run — 62 % of a whole DAG pass spent on 402 small inserts
        # (measured by agent G2, wave 4). :mod:`mva.zoo.cache` batches for the same reason.
        connection.executemany(
            f"INSERT INTO {ALIAS}.{safe}.{MODEL_RANKS_TABLE} VALUES ({placeholders})",
            [list(row) for row in rows],
        )
    ensure_tables(connection, lineage_schema)
    record(
        connection,
        lineage_schema,
        target_schema=schema,
        target_table=MODEL_RANKS_TABLE,
        target_rows=len(rows),
        source_kind="table",
        source_ref=source_ref,
        source_version=run_id,
        transform=f"mva.zoo.rank.rank_per_model (top={top}, pair score = (min, max))",
        tool="mva-zoo",
        notes=f"{len(ranks)} lanes; confirmed pair always kept",
    )
    return len(rows)
