"""Merging the lanes: do the models agree, and what do they say together?

Four deterministic outputs, all of them computed without a single tuned parameter — the plan
calls this the *deterministic layer*, and it is the one part of iteration 4 that is never cut:

1. **Agreement matrix** — Spearman ρ (rank correlation: do two lanes order the same alleles
   the same way, ignoring the scale each one uses) between every pair of lanes, over the
   alleles both scored, with ``n`` printed beside every cell. A ρ computed on nine shared
   alleles is not the same claim as one computed on thirty thousand.
2. **Reciprocal rank fusion (RRF)** — merge N ranked lists by summing ``1 / (k + rank)``.
   Cormack, Clarke & Buettcher, *Reciprocal rank fusion outperforms Condorcet and individual
   rank learning methods*, SIGIR 2009, pp. 758-759, DOI ``10.1145/1571941.1572114``
   (**verified against Crossref 2026-09-19** — title, authors, venue, year and pages all
   matched; methodology entry 130). The point of
   RRF is that it has no weights to fit: a lane contributes by *where* it puts a pair, not by
   how confident its scores look, so two lanes on different scales merge honestly.
3. **Consensus with and without catalogue-adjacent lanes** — a *catalogue-adjacent* score is
   one whose training data included ClinVar (the public catalogue of variants already called
   pathogenic), so it may simply be recalling the answer. The consensus rank is printed both
   ways and the catalogue-free number is the one the claim is filed on.
4. **Disagreement table** — alleles in the top 1 % of one lane and the bottom half of another.
   Models disagreeing is a finding to explain, not a bug to hide.

Everything here is pure: it takes the ranking objects of :mod:`mva.zoo.rank` and returns
dictionaries and strings. Nothing reads a database, so every number in the merged report can
be recomputed from the JSON it emits.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .rank import ModelRank, Pair, RankTable

__all__ = [
    "RRF_CITATION",
    "AgreementMatrix",
    "ConsensusRank",
    "Disagreement",
    "agreement_matrix",
    "consensus",
    "disagreements",
    "merged_report",
    "render_merged",
    "rrf",
]

#: The citation for reciprocal rank fusion. The DOI is deliberately not asserted: the repo's
#: rule is that a citation is checked before it is printed as fact.
RRF_CITATION = (
    "Cormack GV, Clarke CLA, Buettcher S. Reciprocal rank fusion outperforms Condorcet and "
    "individual rank learning methods. SIGIR 2009, pp. 758-759. "
    "doi:10.1145/1571941.1572114 (verified against Crossref 2026-09-19)"
)

#: Minimum shared alleles before a Spearman ρ is reported at all. Below this the correlation
#: is noise with a decimal point on it.
MIN_SHARED = 3


# ---------------------------------------------------------------------------------------
# 1. Agreement
# ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class AgreementMatrix:
    """Spearman ρ per lane pair, with the shared-allele count behind every cell."""

    models: tuple[str, ...]
    rho: dict[tuple[str, str], float | None]
    n: dict[tuple[str, str], int]

    def cell(self, a: str, b: str) -> tuple[float | None, int]:
        return (self.rho.get((a, b)), self.n.get((a, b), 0))

    def rows(self) -> list[dict[str, Any]]:
        """The matrix as flat rows — the shape the JSON and the heat map both read."""
        return [
            {"a": a, "b": b, "rho": self.rho.get((a, b)), "n": self.n.get((a, b), 0)}
            for a in self.models
            for b in self.models
        ]


def agreement_matrix(scores_by_model: Mapping[str, Mapping[str, float]]) -> AgreementMatrix:
    """Spearman ρ between every ordered pair of lanes over the alleles both scored.

    The matrix is symmetric by construction (ρ(a,b) = ρ(b,a)) and the diagonal is 1.0 for any
    lane with at least :data:`MIN_SHARED` scores. A cell with too few shared alleles, or with
    no variance on one side, is ``None`` — an absent number, not a zero.
    """
    from scipy.stats import spearmanr

    models = tuple(sorted(scores_by_model))
    rho: dict[tuple[str, str], float | None] = {}
    n: dict[tuple[str, str], int] = {}
    for i, a in enumerate(models):
        for b in models[i:]:
            shared = sorted(set(scores_by_model[a]) & set(scores_by_model[b]))
            left = [scores_by_model[a][k] for k in shared]
            right = [scores_by_model[b][k] for k in shared]
            value: float | None = None
            if len(shared) >= MIN_SHARED and len(set(left)) > 1 and len(set(right)) > 1:
                computed = float(spearmanr(left, right).statistic)
                value = None if math.isnan(computed) else round(computed, 4)
            rho[(a, b)] = rho[(b, a)] = value
            n[(a, b)] = n[(b, a)] = len(shared)
    return AgreementMatrix(models=models, rho=rho, n=n)


# ---------------------------------------------------------------------------------------
# 2 and 3. Fusion and consensus
# ---------------------------------------------------------------------------------------


def rrf(rank_tables: Mapping[str, RankTable], k: int = 60) -> list[tuple[Pair, float]]:
    """Reciprocal rank fusion over the lanes' pair rankings.

    Each lane contributes ``1 / (k + rank)`` for every pair it ranked; a pair a lane could
    not score contributes nothing from that lane (it is not penalised with a last place it
    never earned). ``k = 60`` is the constant the original paper used; it damps the influence
    of the very top of any single list.

    Returns ``(pair, fused_score)`` sorted by fused score descending, ties broken by the
    pair's key so the order is reproducible.
    """
    totals: dict[tuple[str, str, str], float] = {}
    seen: dict[tuple[str, str, str], Pair] = {}
    for table in rank_tables.values():
        for row in table.ranked:
            key = row.pair.key
            totals[key] = totals.get(key, 0.0) + 1.0 / (k + row.rank)
            seen.setdefault(key, row.pair)
    ordered = sorted(totals.items(), key=lambda item: (-item[1], item[0]))
    return [(seen[key], round(score, 10)) for key, score in ordered]


@dataclass(frozen=True)
class ConsensusRank:
    """Where RRF puts the confirmed pair, and which lanes were allowed to vote."""

    rank: int | None
    n_pairs: int
    fused_score: float | None
    lanes: tuple[str, ...]
    excluded_lanes: tuple[str, ...]
    k: int
    percentile: float | None = None


def consensus(
    rank_per_model: Mapping[str, ModelRank],
    cards: Mapping[str, Mapping[str, Any]],
    *,
    exclude_adjacent: bool,
    k: int = 60,
) -> ConsensusRank:
    """The confirmed pair's RRF rank, optionally with catalogue-adjacent lanes silenced.

    ``cards`` is the registry's card per lane; only its ``catalogue_adjacent`` flag is read
    here. A lane missing from ``cards`` is treated as *not* adjacent and the caller is
    expected to have checked the registry — the flag is a licence-and-provenance fact, not
    something this module may guess.
    """
    excluded = tuple(
        model
        for model in sorted(rank_per_model)
        if exclude_adjacent and bool(cards.get(model, {}).get("catalogue_adjacent", False))
    )
    tables = {model: rank.table for model, rank in rank_per_model.items() if model not in excluded}
    fused = rrf(tables, k=k)
    confirmed = next(
        (r.table.confirmed for r in rank_per_model.values() if r.table.confirmed is not None), None
    )
    lanes = tuple(sorted(tables))
    if confirmed is None:
        return ConsensusRank(None, len(fused), None, lanes, excluded, k)
    wanted = confirmed.key
    for index, (pair, score) in enumerate(fused, start=1):
        if pair.key == wanted:
            return ConsensusRank(
                rank=index,
                n_pairs=len(fused),
                fused_score=score,
                lanes=lanes,
                excluded_lanes=excluded,
                k=k,
                percentile=round(100.0 * index / len(fused), 4) if fused else None,
            )
    return ConsensusRank(None, len(fused), None, lanes, excluded, k)


# ---------------------------------------------------------------------------------------
# 4. Disagreement
# ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Disagreement:
    """One allele two lanes read in opposite ways."""

    allele_id: str
    high_model: str
    high_score: float
    high_percentile: float
    low_model: str
    low_score: float
    low_percentile: float


def disagreements(
    scores_by_model: Mapping[str, Mapping[str, float]],
    top: float = 0.01,
    bottom: float = 0.5,
    *,
    limit: int = 200,
) -> list[Disagreement]:
    """Alleles in the top ``top`` fraction of one lane and the bottom ``bottom`` of another.

    Both cut-offs are on *positions*, not raw scores, because the lanes are on unrelated
    scales. With the defaults: the allele is in a lane's most-damaging 1 % and in another
    lane's worse-scoring half. Ordered pairs, so (A high, B low) and (B high, A low) are two
    different findings and both are listed.

    Edge cases are deliberate: a lane with fewer than ``1/top`` alleles still contributes its
    single best allele (the top set is never empty), and ``top = 1.0`` with ``bottom = 1.0``
    lists every shared allele, which is what a caller asking for that should get.
    """
    positions = {model: _positions(scores) for model, scores in scores_by_model.items()}
    out: list[Disagreement] = []
    for high_model, high_pos in sorted(positions.items()):
        n_high = len(high_pos)
        if not n_high:
            continue
        cut = max(1, math.ceil(n_high * top))
        leaders = {allele for allele, rank in high_pos.items() if rank <= cut}
        for low_model, low_pos in sorted(positions.items()):
            if low_model == high_model or not low_pos:
                continue
            floor = len(low_pos) * (1.0 - bottom)
            for allele in sorted(leaders & set(low_pos)):
                if low_pos[allele] <= floor:
                    continue
                out.append(
                    Disagreement(
                        allele_id=allele,
                        high_model=high_model,
                        high_score=scores_by_model[high_model][allele],
                        high_percentile=round(100.0 * high_pos[allele] / n_high, 4),
                        low_model=low_model,
                        low_score=scores_by_model[low_model][allele],
                        low_percentile=round(100.0 * low_pos[allele] / len(low_pos), 4),
                    )
                )
    out.sort(key=lambda d: (d.high_percentile, -d.low_percentile, d.allele_id))
    return out[:limit]


def _positions(scores: Mapping[str, float]) -> dict[str, int]:
    """Allele → position from the top (1 = highest score); ties share the better position."""
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    out: dict[str, int] = {}
    previous: float | None = None
    rank = 0
    for index, (allele, value) in enumerate(ordered, start=1):
        if previous is None or value != previous:
            rank, previous = index, value
        out[allele] = rank
    return out


# ---------------------------------------------------------------------------------------
# The merged report
# ---------------------------------------------------------------------------------------

#: Bumped whenever the JSON below changes shape, so a stored report says which reader it needs.
SCHEMA_VERSION = 1


def merged_report(
    ranks: Mapping[str, ModelRank],
    cards: Mapping[str, Mapping[str, Any]],
    scores_by_model: Mapping[str, Mapping[str, float]],
    *,
    run_id: str,
    method: str = "fusion",
    rrf_k: int = 60,
    sources: Sequence[str] = (),
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Everything step 6 needs, as one JSON-serialisable dictionary.

    The renderer below prints this and computes nothing of its own, so a number in the merged
    report is always a key in this structure — which is what makes the report auditable.
    """
    matrix = agreement_matrix(scores_by_model)
    free = consensus(ranks, cards, exclude_adjacent=True, k=rrf_k)
    aware = consensus(ranks, cards, exclude_adjacent=False, k=rrf_k)
    return {
        "schema_version": SCHEMA_VERSION,
        "method": method,
        "run_id": run_id,
        "generated_at": generated_at or datetime.now(UTC).isoformat(timespec="seconds"),
        "rrf_k": rrf_k,
        "citation": RRF_CITATION,
        "lanes": [_lane_json(ranks[model], cards.get(model, {})) for model in sorted(ranks)],
        "agreement": {"models": list(matrix.models), "cells": matrix.rows()},
        "consensus": {
            "catalogue_free": _consensus_json(free),
            "all_lanes": _consensus_json(aware),
        },
        "disagreements": [vars(d) for d in disagreements(scores_by_model)],
        "lineage": {
            "sources": list(sources),
            "run_id": run_id,
            "tool": "mva.zoo.merge.merged_report",
        },
    }


def _lane_json(rank: ModelRank, card: Mapping[str, Any]) -> dict[str, Any]:
    confirmed = rank.confirmed
    return {
        "model": rank.model,
        "version": card.get("version", ""),
        "tier": card.get("tier"),
        "catalogue_adjacent": bool(card.get("catalogue_adjacent", False)),
        "licence": card.get("licence", ""),
        "n_ranked": rank.table.n_ranked,
        "unscored_pairs": rank.table.unscored_pairs,
        "scored_alleles": rank.table.scored_alleles,
        "confirmed": None if confirmed is None else vars(confirmed),
    }


def _consensus_json(value: ConsensusRank) -> dict[str, Any]:
    return {
        "rank": value.rank,
        "n_pairs": value.n_pairs,
        "fused_score": value.fused_score,
        "percentile": value.percentile,
        "lanes": list(value.lanes),
        "excluded_lanes": list(value.excluded_lanes),
        "k": value.k,
    }


def render_merged(report: Mapping[str, Any], narrative: str, *, dated: str = "") -> str:
    """The merged report as Markdown (see :mod:`mva.zoo.merge_render`)."""
    from .merge_render import render_merged as _render

    return _render(report, narrative, dated=dated)
