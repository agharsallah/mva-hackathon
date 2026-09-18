"""Iteration 2, step 4 as JSON: the genome-wide ranking, its arithmetic, and its nulls.

``/api/steps`` shows every step's goal, claims and figure names. This route shows one step's
*tables*, because the result of step 4 is an ordering over 11,465 genes and the only honest
way to read an ordering is to see what it was built from.

**Six blocks, and three of them exist to argue against the first.**

``leaders``       the top of the ranking, each row carrying the arithmetic that produced it
``lanes``         how many alleles each calibrated lane could score at all
``groups``        target, decoy, curated and uncurated genes side by side
``uncurated``     the highest-placed genes nobody has ever curated a phenotype for
``nulls``         the permuted draws, as a distribution to read the leader against
``phenotype_bins`` the measured recall curve, as the likelihood ratio it was turned into

**Nothing served here has a position.** A hypothesis is a gene, a shape, the lanes that
scored it, and a ratio; an allele is named by its consequence class and its dbSNP
identifier. The coordinates stay in ``build/``.

**The leader is served beside its own null.** A likelihood ratio of 341,000 means nothing on
its own — something is always at the top of 11,465 genes — so the block that names the
leader and the block that says how high a random symptom set gets are fetched by the same
request and rendered on the same page.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from ..warehouse.postgres import ALIAS
from ..warehouse.settings import Postgres
from .queries.access import fetch
from .response import Envelope, live

SOURCE = "pg.results.it2_lr_pairs + it2_ptrans + it2_lr_nulls"

#: How many rows of the ordering the page shows. The table has one row per gene; a page
#: showing all 11,465 is a download, not a result.
LEADERS = 25

#: Where the run leaves the numbers no SQL table holds — the permutation p-value, the AUC
#: and its bootstrap interval, the measured recall bins. Read from the build directory for
#: the same reason the figures are: they are outputs of a fit, not rows of a table.
ANALYSIS = Path("build/it2/step-4")

#: Each block is ``name -> SQL``. Aggregates and the top of the ordering; see the docstring.
BLOCKS: dict[str, str] = {
    # The ordering itself, with the arithmetic and the P(trans) state on every row.
    "leaders": f"""
        SELECT gene_rank, gene, shape, phase, tier, is_target, is_decoy, curated,
               phenotype_rank, hypotheses, combined_lr, baseline, unphaseable,
               biallelic_confirmed, behind_leader, within_one_order,
               p_trans, p_trans_state, terms
        FROM {ALIAS}.results.it2_lr_top_pairs
        ORDER BY gene_rank
        LIMIT {LEADERS}
    """,
    # What the ranking was actually built from: a lane that answers for one allele in
    # twenty is a lane the ordering barely used, whatever its published calibration.
    "lanes": f"""
        SELECT lane_class, scored_by, allele_slots, percent
        FROM {ALIAS}.results.it2_lr_lane_coverage
        ORDER BY allele_slots DESC
    """,
    # Targets against their matched decoys, and both against the rest of the genome.
    "groups": f"""
        SELECT grouping, genes, median_lr, p90_lr, max_lr, genes_over_100, genes_over_1000
        FROM {ALIAS}.results.it2_lr_target_decoy
        ORDER BY median_lr DESC
    """,
    # The genes the symptom ranker could not score at all — the 73.6 % step 4 exists for.
    "uncurated": f"""
        SELECT gene_rank, gene, shape, combined_lr, is_decoy, entered_by_network
        FROM {ALIAS}.results.it2_lr_uncurated
        ORDER BY gene_rank
        LIMIT {LEADERS}
    """,
    # The permuted draws as a histogram: how high a random seven-term set reaches.
    "nulls": f"""
        WITH scaled AS (
            SELECT log10(greatest(top_lr, 1e-6)) AS logged, genes_above_observed
            FROM {ALIAS}.results.it2_lr_nulls
        ),
        -- Fixed-width buckets of a quarter of a decade, computed by flooring rather than
        -- with `width_bucket`: this DuckDB build does not carry that function, and a
        -- histogram is not worth a version constraint on the whole warehouse.
        bucketed AS (
            SELECT floor(logged * 4) / 4 AS low, logged, genes_above_observed FROM scaled
        )
        SELECT low,
               low + 0.25                            AS high,
               count(*)                              AS draws,
               round(avg(genes_above_observed), 3)   AS mean_above_observed
        FROM bucketed
        GROUP BY low
        ORDER BY low
    """,
    # How many hypotheses of each shape exist, which is the denominator every posterior on
    # this page is quoted against.
    "shapes": f"""
        SELECT shape,
               count(*)                                   AS hypotheses,
               count(DISTINCT gene)                       AS genes,
               round(median(combined_lr), 4)              AS median_lr,
               round(max(combined_lr), 4)                 AS max_lr
        FROM {ALIAS}.results.it2_lr_pairs
        GROUP BY shape
        ORDER BY hypotheses DESC
    """,
}


def payload(settings: Postgres, root: Path = ANALYSIS) -> dict:
    """Every block, plus the fitted numbers no table holds.

    A block whose table does not exist yet comes back **empty rather than raising**, the
    same rule step 3's route follows: the stages land one at a time, and a page that 500s
    until the last one finishes hides the results that are already in.
    """
    data: dict[str, object] = {}
    for name, sql in BLOCKS.items():
        try:
            data[name] = fetch(settings, sql)
        except Exception:
            data[name] = []
    data["ranking"] = _read(root / "ranking.json")
    data["nulls_summary"] = _read(root / "nulls.json")
    data["ptrans_summary"] = _read(root / "ptrans.json")
    data["coverage"] = _read(root / "insilico-coverage.json")
    data["network"] = _read(root / "network.json")
    return data


def _read(path: Path) -> dict:
    """One analysis file, or an empty object — an absent stage renders as an absent block."""
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return _strip(loaded) if isinstance(loaded, dict) else {}


#: Keys held back from the served payload: they are long tables the SQL blocks already
#: serve, and shipping both invites the page and the database to disagree. The
#: genotype-only ablation is **not** held back — no SQL block carries it, and it is the
#: control that says how much of the ordering the symptoms are doing.
BULKY = frozenset({"top_genes", "inheritance_reasons", "lead"})


def _strip(data: dict) -> dict:
    return {key: value for key, value in data.items() if key not in BULKY}


def add_routes(api: APIRouter, settings: Postgres) -> None:
    """Register the step-4 detail route on the warehouse router."""

    @api.get(
        "/steps/step-4",
        response_model=Envelope,
        tags=["science"],
        summary=f"iteration 2 step 4's ranking, lanes and nulls ({SOURCE})",
    )
    def it2_step_4() -> dict:
        """The genome-wide likelihood-ratio ranking, with the nulls that qualify it.

        Every row names a gene, a shape and a ratio; no coordinate is served, and the
        arithmetic behind each leader is carried on the row so the ordering can be checked
        rather than believed.
        """
        return live(payload(settings), SOURCE)
