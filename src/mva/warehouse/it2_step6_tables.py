"""Load iteration 2's step-6 fusion tables into the warehouse, with their lineage.

Same shape as :mod:`mva.warehouse.it2_step5_tables`, and for the same reason: the rows are
produced in Python — a reciprocal-rank-fusion score, a leave-one-out rank, a declared
dependency edge — so this module's job is to put them where SQL and the dashboard can read
them, and to record where each one came from.

**Step 6's inputs are the other steps' outputs, and the lineage says so.** Every table here
names three sources: the ranking tables it fused (``derived``), the eight clinical terms
(``clinical``, because two of the three ranking routes ordered genes by those terms and the
fused score therefore carries them), and the **frozen export** (``file``) whose sha256 is
written into methodology entry 108 before the comparison against iteration 1 existed. That
third row is unusual and deliberate: the artifact is the evidence that the ranking was not
steered, so it belongs in the lineage rather than only in prose.

**No coordinate and no residue.** A pair is ``gene | consequence class:rsid | class:rsid``, a
route is a name, an edge is two names. There is no position on this surface to withhold.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import lineage
from .postgres import ALIAS, safe_identifier

__all__ = ["CALLSET_REF", "SCHEMAS", "TOOL", "Loaded", "load"]

#: One row per table: the columns, written out rather than sniffed, because these schemas
#: are a promise the analysis SQL and the dashboard both read.
SCHEMAS: dict[str, tuple[tuple[str, str], ...]] = {
    "it2_fusion_routes": (
        ("route", "VARCHAR"),
        # "pair", "gene" or "allele": what the route actually ordered. A gene-unit route's
        # rank is inherited by every pair in the gene, which is why the unit has to travel
        # with the row — a reader who does not know it will read ties as agreement.
        ("unit", "VARCHAR"),
        ("source_step", "VARCHAR"),
        ("source_table", "VARCHAR"),
        ("admitted", "BOOLEAN"),
        ("weight_primary", "DOUBLE"),
        ("weight_sensitivity", "DOUBLE"),
        # The measurement that admitted or disqualified the route, in words, with its
        # interval. This column is the instrument-trust exhibit.
        ("statistic", "VARCHAR"),
        ("inputs", "VARCHAR"),
        ("reason", "VARCHAR"),
        ("measured_by", "VARCHAR"),
    ),
    "it2_fusion_ranks": (
        ("route", "VARCHAR"),
        ("pair_id", "VARCHAR"),
        ("gene", "VARCHAR"),
        ("rank", "BIGINT"),
        # True when the rank came from the pair's gene or one of its alleles rather than
        # from the pair itself: 206 of 233 rows, and the reason the top of the ranking is
        # three genes rather than twenty.
        ("inherited", "BOOLEAN"),
    ),
    "it2_fusion_scores": (
        ("fused_rank", "BIGINT"),
        ("pair_id", "VARCHAR"),
        ("gene", "VARCHAR"),
        ("rrf_score", "DOUBLE"),
        # The same pair's rank under measured-error-rate weights. Beside the primary rank,
        # never instead of it.
        ("rank_sensitivity", "BIGINT"),
        # How many of {reads, VCF, HPO, literature} speak for the pair once routes sharing
        # an input are collapsed. 1 means four routes and one witness.
        ("independent_evidence", "BIGINT"),
        ("inputs", "VARCHAR"),
        ("read_confirmed", "BOOLEAN"),
        ("single_copy", "BOOLEAN"),
        ("no_cn_loss", "BOOLEAN"),
        ("shape", "VARCHAR"),
        ("phase", "VARCHAR"),
        ("tier", "VARCHAR"),
        ("is_target", "BOOLEAN"),
        ("is_decoy", "BOOLEAN"),
        ("curated", "BOOLEAN"),
        ("reachable", "BOOLEAN"),
        ("unphaseable", "BOOLEAN"),
        ("combined_lr", "DOUBLE"),
        # How many scored hypotheses this coordinate-free key stood for. 1 for almost every
        # row; the exceptions are where removing the position lost a distinction.
        ("collapsed_rows", "BIGINT"),
    ),
    "it2_fusion_loo": (
        ("removed", "VARCHAR"),
        ("fused_rank", "BIGINT"),
        ("pair_id", "VARCHAR"),
        ("gene", "VARCHAR"),
        ("rrf_score", "DOUBLE"),
        ("rank_with_all", "BIGINT"),
        ("delta", "BIGINT"),
    ),
    "it2_route_edges": (
        ("source", "VARCHAR"),
        ("target", "VARCHAR"),
        ("consumed", "VARCHAR"),
        # True when the edge is a *shared raw input* rather than one route consuming
        # another's output. These are the edges the independent-evidence count collapses.
        ("shared_input", "BOOLEAN"),
    ),
}

#: What each table is, in the words the lineage row carries.
TRANSFORMS: dict[str, str] = {
    "it2_fusion_routes": (
        "one row per route: what it ordered, whether it was admitted, the measurement that "
        "admitted or disqualified it, and its weight under both schemes; a route measured "
        "to order nothing is kept at weight 0 rather than deleted"
    ),
    "it2_fusion_ranks": (
        "one row per (route, pair) the route placed inside its top 50, with whether the "
        "rank was stated for the pair or inherited from its gene or one of its alleles"
    ),
    "it2_fusion_scores": (
        "reciprocal rank fusion at k = 60 over the admitted routes, equal weights, absent "
        "from a route = rank 51; beside it the rank under measured-error-rate weights, the "
        "read route's confirmation triple, and the independent-evidence count"
    ),
    "it2_fusion_loo": (
        "the fusion re-run once per admitted route with that route silenced, top 20 each, "
        "with the delta against the all-routes rank - the table that answers whether any "
        "single instrument carries the result"
    ),
    "it2_route_edges": (
        "the route-dependency graph, declared rather than derived from the code: which "
        "route consumed which other's output, and which raw inputs two routes share"
    ),
}

#: The rankings that were fused, named once and quoted in every lineage row.
CALLSET_REF = (
    "results.it2_targets (step 1) + results.it2_lr_pairs (step 4) + "
    "results.it2_knowledge_ranks (step 5) + results.it2_kmer_pairs, results.it2_exon_cn (steps 2-3)"
)
CLINICAL_REF = "ressources/hackathon-rules/Challenge_Clinical_Phenotype_1.md"
CLINICAL_TRANSFORM = (
    "two of the three admitted ranking routes ordered genes by the proband's own terms - the "
    "symptom ranker directly, the likelihood ratio through its phenotype lane - so the fused "
    "score carries the clinical document even though no term is read here"
)
FROZEN_TRANSFORM = (
    "the fused ranking was written to build/it2/step-6/fused-ranking.tsv and hashed before "
    "any iteration-1 table was read; the digest below is the one methodology entry 108 quotes"
)
TOOL = "mva-warehouse pg-load-it2-step6"


@dataclass(frozen=True)
class Loaded:
    """One table after loading: what it is called and how many rows arrived."""

    table: str
    rows: int
    source: Path


def _create(connection, schema: str, table: str, columns: tuple[tuple[str, str], ...]) -> str:
    """Replace the table: rebuilding from the TSV is the only way it is ever written, so a
    partial old copy left behind would be a silent mixture of two runs."""
    qualified = f"{ALIAS}.{safe_identifier(schema)}.{safe_identifier(table)}"
    body = ", ".join(f'"{name}" {sql_type}' for name, sql_type in columns)
    connection.execute(f"DROP TABLE IF EXISTS {qualified}")
    connection.execute(f"CREATE TABLE {qualified} ({body})")
    return qualified


def _load_tsv(
    connection, schema: str, table: str, path: Path, columns: tuple[tuple[str, str], ...]
) -> int:
    qualified = _create(connection, schema, table, columns)
    names = ", ".join(f'"{name}"' for name, _ in columns)
    casts = ", ".join(f"CAST(NULLIF(\"{name}\", '') AS {sql_type})" for name, sql_type in columns)
    connection.execute(
        f"INSERT INTO {qualified} ({names}) "
        f"SELECT {casts} FROM read_csv(?, delim='\t', header=true, all_varchar=true, "
        f"quote='\"', escape='\"')",
        [str(path)],
    )
    counted = connection.execute(f"SELECT count(*) FROM {qualified}").fetchone()
    return int((counted or [0])[0])


def load(connection, *, schema: str, result_schema: str, out_dir: Path) -> list[Loaded]:
    """Load every step-6 table present in ``out_dir``, and record its lineage.

    A table whose TSV is absent is skipped rather than created empty: an empty table and a
    stage that did not run look identical in SQL, and only one of them is a result.
    """
    summary_path = out_dir / "fusion.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    frozen = summary.get("frozen", {})
    constants = summary.get("constants", {})
    version = " ".join(
        f"{name}={value}"
        for name, value in (
            ("k", constants.get("k", "")),
            ("top", constants.get("top_per_route", "")),
            ("missing", constants.get("missing_rank", "")),
            ("seed", constants.get("seed", "")),
        )
    )
    lineage.ensure_tables(connection, schema)

    loaded: list[Loaded] = []
    for table, columns in SCHEMAS.items():
        path = out_dir / "tables" / f"{table}.tsv"
        if not path.exists():
            continue
        rows = _load_tsv(connection, result_schema, table, path, columns)
        loaded.append(Loaded(table=table, rows=rows, source=path))
        lineage.record(
            connection,
            schema,
            target_schema=result_schema,
            target_table=table,
            target_rows=rows,
            source_kind="derived",
            source_ref=CALLSET_REF,
            source_version=version,
            transform=TRANSFORMS[table],
            tool=TOOL,
            notes="the read route contributes a confirmation triple and no rank",
        )
        lineage.record(
            connection,
            schema,
            target_schema=result_schema,
            target_table=table,
            target_rows=rows,
            source_kind="clinical",
            source_ref=CLINICAL_REF,
            transform=CLINICAL_TRANSFORM,
            tool=TOOL,
        )
        lineage.record(
            connection,
            schema,
            target_schema=result_schema,
            target_table=table,
            target_rows=rows,
            source_kind="file",
            source_ref=str(frozen.get("file", "build/it2/step-6/fused-ranking.tsv")),
            source_version=str(frozen.get("frozen_at", "")),
            source_sha256=str(frozen.get("sha256", "")),
            transform=FROZEN_TRANSFORM,
            tool=TOOL,
        )
    return loaded
