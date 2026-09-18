#!/usr/bin/env python3
"""Fuse the routes into one iteration-2 ranking, freeze it, and hash it before anyone looks.

This is the stage the blind protocol is built around. It reads three orderings and one
confirmation instrument, combines them by reciprocal rank fusion with the constants the plan
fixed before any of it ran (k = 60, top 50 per route, absent = rank 51, equal weights), and
writes the result to a file whose **sha256 is printed and recorded in the methodology entry
before the comparison against iteration 1 exists**. A ranking that is hashed first cannot be
quietly re-run until it agrees with the answer.

Nothing here reads an iteration-1 table. The unblinding is a separate stage, filed as its own
entry, and ``mva-science check --blind iteration2`` is what enforces the order.

Two sensitivity analyses are written beside the primary result and never instead of it:

* **leave-one-route-out** — re-fuse once per voting route with that route silenced, so
  "does any single instrument carry this" has a table rather than an opinion;
* **measured-error-rate weights** — the symptom route weighted by its held-out recall, the
  likelihood route by ``1 - p`` of its permutation null, the knowledge route by its own
  target-versus-decoy AUC. Measured, never a band chosen now.

Usage::

    uv run python tools/fuse_it2_routes.py
    uv run python tools/fuse_it2_routes.py --out build/it2/step-6 --export-top 200
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import it2_step6_common as common
import it2_step6_routes as route_rules
import it2_step6_tables as tables_module
from mva.pipeline import fusion, fusion_freeze
from mva.pipeline.fusion import Route


def build_ranks(routes: list[Route], loaded: dict[str, Any]) -> list[fusion.RouteRank]:
    """Every route's ordering mapped onto pairs, with the inheritance rule applied once."""
    pairs = loaded["pairs"]
    orders: dict[str, list[str]] = {
        "phenotype": loaded["phenotype"],
        "likelihood": [pair.id for pair in pairs],
        "knowledge": loaded["knowledge"] or [],
        "confirmation": [],
    }
    ranks: list[fusion.RouteRank] = []
    for route in routes:
        order = orders.get(route.name, [])
        if order:
            ranks.extend(fusion.inherit(route, order, pairs, top=loaded["top"]))
    return ranks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=common.DEFAULT_OUT)
    parser.add_argument("--export-top", type=int, default=tables_module.EXPORT_TOP)
    args = parser.parse_args(argv)

    loaded = common.load()
    weights = route_rules.sensitivity_weights(
        recall=loaded["recall"],
        null=loaded["null"],
        knowledge_auc=(
            loaded["knowledge_weight"].separation.auc if loaded["knowledge_weight"] else None
        ),
    )
    routes = route_rules.routes(
        recall=loaded["recall"],
        lr=loaded["separation"],
        null=loaded["null"],
        knowledge=loaded["knowledge"],
        knowledge_weight=loaded["knowledge_weight"],
    )
    ranks = build_ranks(routes, loaded)
    # Only pairs some route listed are fused at all — everything else is absent from every
    # route, which is a score of nothing rather than a row. The confirmation instrument has
    # an opinion about far more genes than that, so it is narrowed to the ranked universe
    # here rather than being allowed to introduce candidates no ranking route nominated.
    listed = {row.pair.id for row in ranks}
    confirmations = {
        pair_id: value for pair_id, value in loaded["confirmations"].items() if pair_id in listed
    }

    fused = fusion.fuse(routes, ranks, confirmations=confirmations)
    weighted = fusion.fuse(
        [
            Route(
                name=r.name,
                unit=r.unit,
                admitted=r.admitted,
                weight=weights.get(r.name, 0.0),
                inputs=r.inputs,
                reason=r.reason,
            )
            for r in routes
        ],
        ranks,
        confirmations=confirmations,
    )
    dropped = fusion.leave_one_out(routes, ranks, confirmations=confirmations)

    frozen = fusion_freeze.freeze(fused, routes=routes)
    (args.out).mkdir(parents=True, exist_ok=True)
    (args.out / tables_module.FROZEN).write_text(frozen.text, encoding="utf-8")

    primary_rank = {row.pair.id: row.rank for row in fused}
    sensitivity_rank = {row.pair.id: row.rank for row in weighted}
    tables = args.out / "tables"
    written = {
        "it2_fusion_routes": common.write_tsv(
            tables / "it2_fusion_routes.tsv",
            tables_module.route_rows(routes, loaded, weights),
            tables_module.ROUTE_COLUMNS,
        ),
        "it2_fusion_scores": common.write_tsv(
            tables / "it2_fusion_scores.tsv",
            tables_module.score_rows(fused[: args.export_top], loaded["best"], sensitivity_rank),
            tables_module.SCORE_COLUMNS,
        ),
        "it2_fusion_ranks": common.write_tsv(
            tables / "it2_fusion_ranks.tsv",
            (
                {
                    "route": row.route,
                    "pair_id": row.pair.id,
                    "gene": row.pair.gene,
                    "rank": row.rank,
                    "inherited": row.inherited,
                }
                for row in ranks
                if primary_rank.get(row.pair.id, 10**9) <= args.export_top
            ),
            tables_module.RANK_COLUMNS,
        ),
        "it2_fusion_loo": common.write_tsv(
            tables / "it2_fusion_loo.tsv",
            tables_module.loo_rows(dropped, primary_rank, fused[0].pair.id if fused else ""),
            tables_module.LOO_COLUMNS,
        ),
        "it2_route_edges": common.write_tsv(
            tables / "it2_route_edges.tsv", route_rules.EDGES, tables_module.EDGE_COLUMNS
        ),
    }

    summary: dict[str, Any] = {
        "frozen": {
            "file": str(args.out / tables_module.FROZEN),
            "sha256": frozen.sha256,
            "rows": frozen.rows,
            "frozen_at": datetime.now(UTC).isoformat(timespec="seconds"),
        },
        "constants": {
            "k": fusion.K,
            "top_per_route": loaded["top"],
            "missing_rank": fusion.MISSING_RANK,
            "seed": common.SEED,
        },
        "pairs": {
            "keys": len(loaded["pairs"]),
            "scored_rows": sum(r["collapsed_rows"] for r in loaded["best"].values()),
        },
        "routes": [
            {
                "name": r.name,
                "unit": r.unit,
                "admitted": r.admitted,
                "weight_primary": r.weight,
                "weight_sensitivity": weights.get(r.name, 0.0),
                "inputs": list(r.inputs),
                "statistic": tables_module.statistic(r.name, loaded),
                "reason": r.reason,
                "listed": sum(1 for row in ranks if row.route == r.name),
            }
            for r in routes
        ],
        "measurements": {
            "phenotype_recall": loaded["recall"],
            "likelihood_separation": {
                "auc": loaded["separation"].auc,
                "low": loaded["separation"].low,
                "high": loaded["separation"].high,
                "positives": loaded["separation"].positives,
                "negatives": loaded["separation"].negatives,
            },
            "permutation_null": loaded["null"],
            "knowledge": (
                {
                    "auc": loaded["knowledge_weight"].separation.auc,
                    "low": loaded["knowledge_weight"].separation.low,
                    "high": loaded["knowledge_weight"].separation.high,
                    "rho": loaded["knowledge_weight"].agreement.rho,
                    "top_k_overlap": loaded["knowledge_weight"].agreement.overlap,
                    "top_k": loaded["knowledge_weight"].agreement.k,
                    "tied_at_k": loaded["knowledge_weight"].agreement.tied_at_k,
                    "verdict": loaded["knowledge_weight"].verdict,
                }
                if loaded["knowledge_weight"]
                else None
            ),
        },
        "leaders": tables_module.leaders(fused, loaded["best"]),
        "sensitivity_leaders": tables_module.leaders(weighted, loaded["best"], count=5),
        "leave_one_out": {
            removed: {
                "top": [
                    {"rank": row.rank, "pair_id": row.pair.id, "gene": row.pair.gene}
                    for row in rows[:3]
                ],
                # Where the all-routes leader lands once this route is silenced. Without it
                # the table says who won, not what was lost, and H042 is a claim about the
                # second.
                "leader_rank": next(
                    (row.rank for row in rows if row.pair.id == fused[0].pair.id), None
                ),
                "leader_kept_rank_one": next(
                    (row.rank == 1 for row in rows if row.pair.id == fused[0].pair.id), False
                ),
                "rows": len(rows),
            }
            for removed, rows in sorted(dropped.items())
        },
        "confirmation": {
            "genes_measured": len({pair_id.split("|")[0] for pair_id in confirmations}),
            "pairs_measured": len(confirmations),
            "pairs_complete": sum(1 for c in confirmations.values() if c.complete),
        },
        "tables": written,
    }
    common.write_json(args.out / "fusion.json", summary)

    print(f"frozen  {args.out / tables_module.FROZEN}")
    print(f"sha256  {frozen.sha256}")
    print(f"rows    {frozen.rows}")
    for row in summary["routes"]:
        mark = "rank" if row["admitted"] else "confirm"
        print(f"  {row['name']:<13} {mark:<8} w={row['weight_primary']:<4} {row['statistic']}")
    for row in summary["leaders"][:5]:
        print(
            f"  #{row['rank']:<3} {row['pair_id']:<48} "
            f"score {row['rrf_score']:.6f}  evidence {row['independent_evidence']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
