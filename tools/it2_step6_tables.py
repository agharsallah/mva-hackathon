"""The shape of step 6's exported rows: five tables, one frozen file, one JSON sidecar.

Kept apart from the stage that runs the fusion because these are *schemas*. A column list is
a promise the warehouse loader, the API route and the dashboard all read, and a promise is
easier to keep when changing it is a deliberate edit to a file of nothing else.

No column here can hold a coordinate. A pair is ``gene | class:rsid | class:rsid`` and a
route is a name, so there is no position on the surface to withhold.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mva.pipeline.fusion import FusedPair, Route

__all__ = [
    "EDGE_COLUMNS",
    "EXPORT_TOP",
    "FROZEN",
    "LOO_COLUMNS",
    "LOO_TOP",
    "PROVENANCE",
    "RANK_COLUMNS",
    "ROUTE_COLUMNS",
    "SCORE_COLUMNS",
    "leaders",
    "loo_rows",
    "route_rows",
    "score_rows",
    "statistic",
]


#: How many fused rows reach the exported tables and the dashboard. The frozen file carries
#: every pair; a table nobody can scroll is not an exhibit.
EXPORT_TOP = 200

#: How many rows the leave-one-out table keeps per removal. The question it answers is about
#: the top of the ranking, and a full re-export per route would be four copies of the file.
LOO_TOP = 20

#: The frozen artifact. Its digest is what the entry quotes.
FROZEN = "fused-ranking.tsv"

ROUTE_COLUMNS = (
    "route",
    "unit",
    "source_step",
    "source_table",
    "admitted",
    "weight_primary",
    "weight_sensitivity",
    "statistic",
    "inputs",
    "reason",
    "measured_by",
)
RANK_COLUMNS = ("route", "pair_id", "gene", "rank", "inherited")
SCORE_COLUMNS = (
    "fused_rank",
    "pair_id",
    "gene",
    "rrf_score",
    "rank_sensitivity",
    "independent_evidence",
    "inputs",
    "read_confirmed",
    "single_copy",
    "no_cn_loss",
    "shape",
    "phase",
    "tier",
    "is_target",
    "is_decoy",
    "curated",
    "reachable",
    "unphaseable",
    "combined_lr",
    "collapsed_rows",
)
LOO_COLUMNS = ("removed", "fused_rank", "pair_id", "gene", "rrf_score", "rank_with_all", "delta")
EDGE_COLUMNS = ("source", "target", "consumed", "shared_input")

#: Which step measured each route, so the exported table carries its receipt.
PROVENANCE: dict[str, tuple[str, str, str]] = {
    "phenotype": ("step-1", "results.it2_targets", "084, 091"),
    "likelihood": ("step-4", "results.it2_lr_pairs", "099, 100"),
    "knowledge": ("step-5", "results.it2_knowledge_ranks", "103, 105"),
    "confirmation": (
        "step-2 + step-3",
        "results.it2_kmer_pairs, results.it2_exon_cn",
        "087, 090, 097",
    ),
}


def statistic(name: str, loaded: dict[str, Any]) -> str:
    """The one number that admitted or disqualified a route, for its table row."""
    if name == "phenotype":
        recall = loaded["recall"]
        return (
            f"recall@{recall['n']} {recall['recall']:.3f} "
            f"[{recall['low']:.3f}, {recall['high']:.3f}]"
        )
    if name == "likelihood":
        return loaded["separation"].verdict
    if name == "knowledge":
        weight = loaded["knowledge_weight"]
        return weight.separation.verdict if weight else "not asked"
    return "discrimination 0: 10 of 396 targets against 10 of 396 decoys, Fisher p = 0.589"


def route_rows(routes: list[Route], loaded: dict[str, Any], sensitivity: dict[str, float]):
    for route in routes:
        step, table, entries = PROVENANCE[route.name]
        yield {
            "route": route.name,
            "unit": route.unit,
            "source_step": step,
            "source_table": table,
            "admitted": route.admitted,
            "weight_primary": route.weight,
            "weight_sensitivity": sensitivity.get(route.name, 0.0),
            "statistic": statistic(route.name, loaded),
            "inputs": ",".join(route.inputs),
            "reason": route.reason,
            "measured_by": entries,
        }


def score_rows(fused: list[FusedPair], best: dict[str, dict[str, Any]], sensitivity_rank):
    for row in fused:
        meta = best.get(row.pair.id, {})
        yield {
            "fused_rank": row.rank,
            "pair_id": row.pair.id,
            "gene": row.pair.gene,
            "rrf_score": f"{row.score:.12g}",
            "rank_sensitivity": sensitivity_rank.get(row.pair.id),
            "independent_evidence": row.independent_evidence,
            "inputs": ",".join(row.inputs),
            "read_confirmed": row.confirmation.read_confirmed,
            "single_copy": row.confirmation.single_copy,
            "no_cn_loss": row.confirmation.no_cn_loss,
            "shape": meta.get("shape"),
            "phase": meta.get("phase"),
            "tier": meta.get("tier"),
            "is_target": meta.get("is_target"),
            "is_decoy": meta.get("is_decoy"),
            "curated": meta.get("curated"),
            "reachable": meta.get("reachable"),
            "unphaseable": meta.get("unphaseable"),
            "combined_lr": meta.get("combined_lr"),
            "collapsed_rows": meta.get("collapsed_rows"),
        }


def loo_rows(out: dict[str, list[FusedPair]], primary: dict[str, int]):
    for removed, fused in sorted(out.items()):
        for row in fused[:LOO_TOP]:
            with_all = primary.get(row.pair.id)
            yield {
                "removed": removed,
                "fused_rank": row.rank,
                "pair_id": row.pair.id,
                "gene": row.pair.gene,
                "rrf_score": f"{row.score:.12g}",
                "rank_with_all": with_all,
                "delta": None if with_all is None else row.rank - with_all,
            }


def leaders(fused: list[FusedPair], best: dict[str, dict[str, Any]], count: int = 10):
    """The head of the ranking as the entry will quote it — no coordinate, one row per pair."""
    return [
        {
            "rank": row.rank,
            "pair_id": row.pair.id,
            "gene": row.pair.gene,
            "rrf_score": row.score,
            "independent_evidence": row.independent_evidence,
            "inputs": list(row.inputs),
            "per_route": dict(row.per_route),
            "confirmation": {
                "read_confirmed": row.confirmation.read_confirmed,
                "single_copy": row.confirmation.single_copy,
                "no_cn_loss": row.confirmation.no_cn_loss,
            },
            "tier": best.get(row.pair.id, {}).get("tier"),
            "shape": best.get(row.pair.id, {}).get("shape"),
            "phase": best.get(row.pair.id, {}).get("phase"),
            "is_target": best.get(row.pair.id, {}).get("is_target"),
        }
        for row in fused[:count]
    ]
