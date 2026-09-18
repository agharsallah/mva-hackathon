"""Iteration 2, step 8 as JSON: what the sample shows, and how small an event it could show.

``/api/steps`` serves every step's goal and claims. This route serves step 8's *tables*,
because the finding is a pair of numbers that only mean something together: a deviation that
did not exceed its null, and the smallest cell fraction that deviation could have caught.
Publishing the first without the second would be publishing entry 037 again.

**Nothing here can carry a coordinate**, and not because anything is filtered. The three
derivations behind these tables aggregated the callset to ``(chromosome, arm)`` before they
were written, so a row is a contig, an arm, a model name, a fraction and a count. There is
no position on the surface to withhold.

**The constants block is served beside every table on purpose.** The fold centre and the
over-dispersion are fitted once for the whole sample and every number on the page depends on
them — a reader who cannot see that the fold was taken around 0.493 rather than 0.5 cannot
check the deviation it produced.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from ..warehouse.postgres import ALIAS
from ..warehouse.settings import Postgres
from .queries.access import fetch
from .response import Envelope, live

SOURCE = "pg.results.it2_mosaic_*"

#: Where the stage writes the numbers no table holds: the fitted constants, the arm-geometry
#: check and the simulation's own parameters.
ANALYSIS = Path("build/it2/step-8")

#: Keys of ``analysis.json`` held back from the payload: the SQL blocks below already serve
#: the same rows, and shipping both invites the page and the database to disagree.
BULKY = frozenset({"bdev", "models", "multi", "limits", "density"})

#: Each block is ``name -> SQL``, one per exhibit, so adding a column to a result table does
#: not silently widen what the browser receives.
BLOCKS: dict[str, str] = {
    # Every contig's fold-over deviation beside the null its own depths generate. The null
    # columns travel with the observation because a shared threshold would have flagged
    # every shallow contig.
    "bdev": f"""
        SELECT chrom, arm, n_sites, mean_depth, bdev, null_mean, null_sd, null_p95,
               z, p_value, rho, centre, measurable, exceeds_null
        FROM {ALIAS}.results.it2_mosaic_bdev
        ORDER BY arm, CASE WHEN chrom ~ '^[0-9]+$' THEN CAST(chrom AS INTEGER) ELSE 99 END, chrom
    """,
    # The published fraction estimator, its value on null draws, and the difference. All
    # three, because the gap between the first two is a result about the instrument.
    "fractions": f"""
        SELECT chrom, arm, f_raw, f_null, f_hat, f_low, f_high, upper_sites, centre
        FROM {ALIAS}.results.it2_mosaic_fractions
        ORDER BY CASE WHEN chrom ~ '^[0-9]+$' THEN CAST(chrom AS INTEGER) ELSE 99 END, chrom
    """,
    # The five fits per contig, with the margin that decides whether the ranking is a call.
    "models": f"""
        SELECT chrom, model, fraction, tract, depth_dispersion, log_likelihood,
               parameters, observations, bic
        FROM {ALIAS}.results.it2_mosaic_models
        ORDER BY CASE WHEN chrom ~ '^[0-9]+$' THEN CAST(chrom AS INTEGER) ELSE 99 END,
                 chrom, bic
    """,
    "verdicts": f"""
        SELECT chrom, call, best, runner_up, delta_bic, fraction, trisomy_vs_cnloh, confident
        FROM {ALIAS}.results.it2_mosaic_verdicts
        ORDER BY CASE WHEN chrom ~ '^[0-9]+$' THEN CAST(chrom AS INTEGER) ELSE 99 END, chrom
    """,
    # The number every negative result on the page has to be quoted with.
    "limits": f"""
        SELECT * FROM {ALIAS}.results.it2_mosaic_limits
        ORDER BY statistic,
                 CASE WHEN chrom ~ '^[0-9]+$' THEN CAST(chrom AS INTEGER) ELSE 99 END, chrom
    """,
    # Heterozygous calls per megabase and per PASS call: what a monosomy moves and allele
    # balance cannot see.
    "density": f"""
        SELECT chrom, arm, het_sites, pass_sites, arm_bp, acrocentric, het_per_mb, het_share
        FROM {ALIAS}.results.it2_mosaic_density
        ORDER BY CASE WHEN chrom ~ '^[0-9]+$' THEN CAST(chrom AS INTEGER) ELSE 99 END,
                 chrom, arm
    """,
    # Recovery *and* false positives when several contigs are abnormal at once, which is
    # what variegated means and what every median denominator here assumes away.
    "multi": f"""
        SELECT fraction, affected, n_affected, recall, false_positive_rate,
               replicates, chromosomes_tested
        FROM {ALIAS}.results.it2_mosaic_multi
        ORDER BY n_affected, fraction
    """,
}


def _read(path: Path) -> dict:
    """One analysis file, or an empty object — an absent stage renders as an absent block."""
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(loaded, dict):
        return {}
    return loaded


def payload(settings: Postgres, root: Path = ANALYSIS) -> dict:
    """Every block, plus the constants and the arm-geometry check the run recorded.

    A block whose table does not exist yet comes back **empty rather than raising**: the
    stages land one at a time — the simulation is hours behind the SQL — and a page that
    500s until the last one finishes hides the results that are already in.
    """
    data: dict[str, object] = {}
    for name, sql in BLOCKS.items():
        try:
            data[name] = fetch(settings, sql)
        except Exception:
            data[name] = []
    analysis = _read(root / "analysis.json")
    data["constants"] = {
        key: value for key, value in (analysis.get("constants") or {}).items() if key not in BULKY
    }
    data["baseline"] = analysis.get("baseline") or {}
    return data


def add_routes(api: APIRouter, settings: Postgres) -> None:
    """Register the step-8 detail route on the warehouse router."""

    @api.get(
        "/steps/step-8",
        response_model=Envelope,
        tags=["science"],
        summary=f"iteration 2 step 8's mosaic bound, model comparison and limits ({SOURCE})",
    )
    def it2_step_8() -> dict:
        """The re-test of the flat karyogram, and the limit that makes its answer mean something.

        The deviation table and the limit table are fetched by the same request and rendered
        on the same page deliberately: "no chromosome exceeds its null" is not a result on
        its own, and the page has to be unable to show one without the other.
        """
        return live(payload(settings), SOURCE)
