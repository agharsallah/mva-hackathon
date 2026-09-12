"""Iteration 2, step 2 as JSON: what the bait recovered and what the alleles say.

``/api/steps`` shows every step's goal, claims and figure names. This route shows one
step's *tables*, because step 2 produced six of them and a figure filename is not a result.

**Positions are the whole design constraint here.** Four of the six tables
(``it2_read_alleles``, ``it2_sv_calls``, ``it2_exon_depth``, ``it2_phase_blocks``) carry
real genomic coordinates of this child. **None of their rows is served.** Every block below
is an aggregate computed in SQL — per gene, per tier, per structural-variant type, per
caller — so the surface carries gene symbols, counts, depths and lengths and no position
exists on it to withhold. That is stronger than filtering a column out of a payload: the
coordinates never leave the database.

The blocks are chosen to be the exhibits the page needs and nothing else, so adding a
column to a result table does not silently widen what the browser receives.
"""

from __future__ import annotations

from fastapi import APIRouter

from ..warehouse.postgres import ALIAS
from ..warehouse.settings import Postgres
from .queries.access import fetch
from .response import Envelope, live

SOURCE = "pg.results.it2_*"

#: How far below the median a gene's bait density has to fall before "nothing found here"
#: stops being a statement about the gene. Half, as entry 085 pre-registered.
REACHABLE_FRACTION = 0.5

#: The depth a baited interval is expected to clear; below it a gene's calls are thin.
DEPTH_FLOOR = 10.0

#: Each block is ``name -> SQL``. Aggregates only: see the module docstring.
BLOCKS: dict[str, str] = {
    # The pass, as the metric rows the loader wrote. No coordinates by construction.
    "funnel": f"""
        SELECT stage, metric, value, note
        FROM {ALIAS}.results.it2_bait_qc
        ORDER BY stage, metric
    """,
    # Per tier: how many genes, how many carry a biallelic candidate with the filter and
    # without it, and how many of the qualifying alleles the delivered callset never saw.
    "by_tier": f"""
        SELECT s.tier,
               count(*) AS genes,
               count(*) FILTER (s.biallelic) AS biallelic_filtered,
               sum(s.truncating) AS truncating,
               sum(s.clinvar_flagged) AS clinvar_flagged,
               sum(s.novel_qualifying) AS novel_qualifying,
               sum(s.unannotated_alleles) AS unannotated,
               count(*) FILTER (u.biallelic) AS biallelic_unfiltered
        FROM {ALIAS}.results.it2_scored_pairs s
        JOIN {ALIAS}.results.it2_read_pairs u ON u.symbol = s.symbol
        GROUP BY s.tier
        ORDER BY s.tier
    """,
    # Every gene the filter leaves standing, targets and decoys together and in the table's
    # own order. Gene symbols and counts only.
    "leads": f"""
        SELECT symbol, tier, rare_het, rare_hom_alt, truncating, clinvar_flagged,
               novel_qualifying, round(bait_density, 4) AS bait_density,
               round(mean_depth, 1) AS mean_depth
        FROM {ALIAS}.results.it2_scored_pairs
        WHERE biallelic
        ORDER BY truncating DESC, clinvar_flagged DESC, rare_het DESC, symbol
    """,
    "concordance": f"SELECT * FROM {ALIAS}.results.it2_concordance ORDER BY caller",
    "sv_consensus": f"""
        SELECT sv_type, bait_edge, spans_unbaited, consensus_calls, distinct_events,
               precision_prior, median_length, shortest, longest
        FROM {ALIAS}.results.it2_sv_consensus
        ORDER BY spans_unbaited, bait_edge, consensus_calls DESC
    """,
    # Depth per gene, not per interval: the interval rows carry coordinates.
    "depth": f"""
        SELECT d.symbol,
               b.tier,
               count(*) AS intervals,
               round(avg(d.mean_depth), 1) AS mean_depth,
               count(*) FILTER (d.mean_depth < {DEPTH_FLOOR}) AS below_floor
        FROM {ALIAS}.results.it2_exon_depth d
        JOIN {ALIAS}.results.it2_bait_density b ON b.symbol = d.symbol
        GROUP BY d.symbol, b.tier
        ORDER BY mean_depth
    """,
    # Phase blocks as a size distribution, never as intervals.
    "phase": f"""
        SELECT count(*) AS blocks,
               sum(variants) AS phased_variants,
               round(median("end" - start), 0) AS median_span,
               max("end" - start) AS longest_span,
               count(*) FILTER (variants >= 2) AS blocks_with_two_or_more
        FROM {ALIAS}.results.it2_phase_blocks
    """,
    # Which genes the bait could not reach. This is the row that has to travel beside every
    # "nothing found in this gene" the step produces.
    "unreachable": f"""
        SELECT symbol, tier, round(density, 4) AS density, round(lost, 4) AS lost
        FROM {ALIAS}.results.it2_bait_density
        WHERE density < (
            SELECT median(density) * {REACHABLE_FRACTION} FROM {ALIAS}.results.it2_bait_density
        )
        ORDER BY density
    """,
}


def payload(settings: Postgres) -> dict:
    """Every block, plus the target-versus-decoy contrast H020 is written about."""
    data = {name: fetch(settings, sql) for name, sql in BLOCKS.items()}
    data["contrast"] = _contrast(data["by_tier"])
    return data


def _contrast(by_tier: list[dict]) -> list[dict]:
    """Targets against decoys, filtered and unfiltered, from the per-tier block.

    Derived here rather than queried again so the two cannot disagree, and stated for both
    filters because the step's central finding is that they point opposite ways.
    """
    out = []
    for key, label in (
        ("biallelic_filtered", "rare and protein-altering"),
        ("biallelic_unfiltered", "any two variants"),
    ):
        targets = [row for row in by_tier if row["tier"] != "decoy"]
        decoys = [row for row in by_tier if row["tier"] == "decoy"]
        target_genes = sum(int(row["genes"]) for row in targets)
        decoy_genes = sum(int(row["genes"]) for row in decoys)
        target_hits = sum(int(row[key]) for row in targets)
        decoy_hits = sum(int(row[key]) for row in decoys)
        out.append(
            {
                "filter": label,
                "target_genes": target_genes,
                "target_biallelic": target_hits,
                "target_rate": target_hits / target_genes if target_genes else 0.0,
                "decoy_genes": decoy_genes,
                "decoy_biallelic": decoy_hits,
                "decoy_rate": decoy_hits / decoy_genes if decoy_genes else 0.0,
            }
        )
    return out


def add_routes(api: APIRouter, settings: Postgres) -> None:
    """Register the step-2 detail route on the warehouse router."""

    @api.get(
        "/steps/step-2",
        response_model=Envelope,
        tags=["science"],
        summary=f"iteration 2 step 2's result tables, as aggregates ({SOURCE})",
    )
    def it2_step_2() -> dict:
        """What the k-mer bait recovered and what the recovered reads say.

        Aggregates only. The four underlying tables carry real genomic positions and none
        of their rows is served; every block is grouped in SQL before it leaves the
        database.
        """
        return live(payload(settings), SOURCE)
