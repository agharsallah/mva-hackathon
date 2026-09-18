"""Iteration 2, step 6 as JSON: four instruments, one ranking, and what carries it.

``/api/steps`` shows every step's goal, claims and blind-gate rows. This route shows step 6's
*tables*, because a fusion that only reported its winner would be hiding the two things that
make it readable: **where each route actually put each candidate**, and **what happens when a
route is taken away**.

**Nothing here can carry a coordinate.** A pair is ``gene | consequence class:rsid | class:rsid``
and a route is a name, so the surface has no position on it to withhold — the same design the
step-5 route uses, for the same reason.

**The decision block is served only once it exists.** The freeze receipt (file, digest,
timestamp) is available from the moment the ranking is frozen; the comparison against
iteration 1 lands in ``decision.json`` when the unblinding entry is filed, and until then the
key is simply absent. The page reads the absence and renders nothing about iteration 1, which
is the blind protocol expressed as a payload rather than as a promise.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from ..warehouse.postgres import ALIAS
from ..warehouse.settings import Postgres
from .queries.access import fetch
from .response import Envelope, live

SOURCE = "pg.results.it2_fusion_*"

#: Where the stage writes the numbers no table holds.
ANALYSIS = Path("build/it2/step-6")

#: Each block is ``name -> SQL``, one per exhibit, so adding a column to a result table does
#: not silently widen what the browser receives.
BLOCKS: dict[str, str] = {
    # The four instruments with the measurement that admitted or disqualified each one.
    "routes": f"""
        SELECT route, unit, source_step, source_table, admitted,
               weight_primary, weight_sensitivity, statistic, inputs, reason, measured_by
        FROM {ALIAS}.results.it2_fusion_routes
        ORDER BY admitted DESC, weight_primary DESC, route
    """,
    # The declared dependency graph: who read whose output, and which inputs are shared.
    "edges": f"""
        SELECT source, target, consumed, shared_input
        FROM {ALIAS}.results.it2_route_edges
        ORDER BY shared_input DESC, source, target
    """,
    # Routes x leading pairs. ``defaulted`` says a cell is the rank-51 "never listed"
    # default rather than an opinion — without it the heatmap reads agreement into silence.
    "matrix": f"""
        SELECT pair_id, gene, fused_rank, route, unit, admitted,
               route_rank, defaulted, inherited, independent_evidence,
               is_target, is_decoy, tier
        FROM {ALIAS}.results.it2_fusion_matrix
        ORDER BY fused_rank, pair_id, route
    """,
    # The fused leaderboard itself, with the confirmation triple and both rankings.
    "leaders": f"""
        SELECT fused_rank, pair_id, gene, rrf_score, rank_sensitivity,
               independent_evidence, inputs, read_confirmed, single_copy, no_cn_loss,
               shape, phase, tier, is_target, is_decoy, curated, reachable, unphaseable,
               combined_lr, collapsed_rows
        FROM {ALIAS}.results.it2_fusion_scores
        WHERE fused_rank <= 40
        ORDER BY fused_rank, pair_id
    """,
    # Does any single instrument carry the result?
    "stability": f"""
        SELECT removed, unit, statistic, leader_rank, leader_kept_rank_one,
               pairs_at_rank_one, genes_at_rank_one, a_new_leader_gene
        FROM {ALIAS}.results.it2_fusion_stability
        ORDER BY coalesce(leader_rank, 999) DESC, removed
    """,
    # The top 20 with each of the four disjoint inputs named one by one.
    "evidence": f"""
        SELECT fused_rank, pair_id, gene, independent_evidence, inputs,
               has_hpo, has_vcf, has_reads, has_literature,
               read_confirmed, single_copy, no_cn_loss, confirmation_complete,
               is_target, is_decoy, tier, unphaseable
        FROM {ALIAS}.results.it2_fusion_evidence
        ORDER BY fused_rank, pair_id
    """,
    # The fusion's own decoy null: how far down do the matched controls sit?
    "reach": f"""
        SELECT class, pairs, genes, best_rank, median_rank,
               pairs_in_top, genes_in_top, pairs_in_top_sensitivity
        FROM {ALIAS}.results.it2_fusion_reach
        ORDER BY best_rank
    """,
    # Every route's own ordering of the exported pairs, for the rank-movement exhibit.
    "movement": f"""
        SELECT route, pair_id, gene, rank, inherited
        FROM {ALIAS}.results.it2_fusion_ranks
        ORDER BY route, rank, pair_id
    """,
}

#: Keys of ``fusion.json`` held back from the payload: the SQL blocks already serve the same
#: rows, and shipping both invites the page and the database to disagree.
BULKY = frozenset({"leaders", "sensitivity_leaders", "tables"})


def _read(path: Path) -> dict:
    """One analysis file, or an empty object — an absent stage renders as an absent block."""
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(loaded, dict):
        return {}
    return {key: value for key, value in loaded.items() if key not in BULKY}


def payload(settings: Postgres, root: Path = ANALYSIS) -> dict:
    """Every block, plus the freeze receipt and — once it exists — the unblinding decision.

    A block whose table does not exist yet comes back **empty rather than raising**: the
    stages land one at a time and a page that 500s until the last one finishes hides the
    results that are already in.
    """
    data: dict[str, object] = {}
    for name, sql in BLOCKS.items():
        try:
            data[name] = fetch(settings, sql)
        except Exception:
            data[name] = []
    data["fusion"] = _read(root / "fusion.json")
    data["decision"] = _read(root / "decision.json")
    return data


def add_routes(api: APIRouter, settings: Postgres) -> None:
    """Register the step-6 detail route on the warehouse router."""

    @api.get(
        "/steps/step-6",
        response_model=Envelope,
        tags=["science"],
        summary=f"iteration 2 step 6's fused ranking, its routes and its nulls ({SOURCE})",
    )
    def it2_step_6() -> dict:
        """One ranking out of three, and the table that says which route carries it.

        The agreement matrix and the leave-one-out table are fetched by the same request and
        rendered on the same page on purpose: a fusion reported without its ablation is four
        correlated lists posing as four witnesses, and the page has to be able to say so.
        """
        return live(payload(settings), SOURCE)
