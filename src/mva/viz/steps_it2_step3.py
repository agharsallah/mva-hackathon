"""Iteration 2, step 3 as JSON: what the reads say with no aligner and no caller in the chain.

``/api/steps`` shows every step's goal, claims and figure names. This route shows one step's
*tables*, because step 3 produced six of them and a figure filename is not a result.

**Nothing served here has a position or a sequence, by construction rather than by
filtering.** A genotype is already stored as a gene, an ordinal within that gene and two
counts; an alternate k-mer spells a base this child carries and never leaves ``build/``.
Every block below aggregates further — per tier, per origin, per reachability class — so the
surface carries symbols, counts and fitted parameters and there is no coordinate on it to
withhold.

**Every block that reports an absence carries the reason an absence is possible.** Entry 093
measured which genes the bait reaches and the aligner could place reads in; a gene excluded
by that gate keeps its row and its flag, because "nothing found" and "nothing could have
been found" are different results and the page must be able to tell them apart.
"""

from __future__ import annotations

from fastapi import APIRouter

from ..warehouse.postgres import ALIAS
from ..warehouse.settings import Postgres
from .queries.access import fetch
from .response import Envelope, live

SOURCE = "pg.results.it2_kmer_* + it2_mapq_profile + it2_exon_cn"

#: Probe pairs an allele needs before its agreement means anything. One probe cannot
#: disagree with itself.
MIN_PROBES = 3

#: The tiers step 1 actually nominated. Named explicitly rather than defined as "not a
#: decoy": the bait pads each target by up to 50 kb, so most of the alleles typed here are
#: in neighbouring genes the target set never chose, and counting those as targets would
#: compare a symptom-derived gene list against a matched null it does not contain.
TARGET_TIERS = ("core", "mechanism-term", "net")

#: The matched null the target tiers are read against (entry 084).
DECOY_TIER = "decoy"

#: Each block is ``name -> SQL``. Aggregates only: see the module docstring.
BLOCKS: dict[str, str] = {
    # The fitted model and its quality checks, as the metric rows the loader wrote.
    "calibration": f"""
        SELECT stage, metric, value, note
        FROM {ALIAS}.results.it2_kmer_calibration
        ORDER BY metric
    """,
    # What the second instrument said, per tier and per class. The `novel` split is the
    # step's headline: those are the alleles the delivered callset never reported.
    "confirmation": f"""
        SELECT tier, novel, alleles, fully_probed, no_call, confirmed,
               confirmed_fraction, in_unreachable_gene, mean_posterior
        FROM {ALIAS}.results.it2_kmer_confirmation
        ORDER BY novel, tier
    """,
    # The distribution of calls, which is what a reader checks a confirmation rate against.
    "calls": f"""
        SELECT tier, call,
               count(*) AS alleles,
               count(*) FILTER (probes >= {MIN_PROBES}) AS fully_probed,
               count(*) FILTER (probes_agreeing = probes AND probes >= {MIN_PROBES})
                   AS unanimous,
               round(avg(posterior), 6) AS mean_posterior
        FROM {ALIAS}.results.it2_kmer_genotypes
        GROUP BY tier, call
        ORDER BY tier, call
    """,
    # Probe design: how many alleles got their three windows, and how many got none.
    "probes": f"""
        SELECT origin,
               sum(alleles) AS alleles,
               sum(probes_kept) AS probes_kept,
               sum(alleles_fully_probed) AS alleles_fully_probed,
               sum(alleles_without_probe) AS alleles_without_probe,
               round(sum(alleles_fully_probed) * 1.0 / nullif(sum(alleles), 0), 6)
                   AS fully_probed_fraction
        FROM {ALIAS}.results.it2_kmer_probes
        GROUP BY origin
        ORDER BY origin
    """,
    # H029: does a gene the gate excluded yield a confident genotype anyway?
    "reach": f"""
        SELECT reachable, sparse_bait, mapq_refused, genes, alleles,
               confident_calls, confident_and_unanimous, confident_fraction
        FROM {ALIAS}.results.it2_kmer_reach
        ORDER BY reachable DESC, sparse_bait, mapq_refused
    """,
    # The genes still standing once every call has been through the second instrument,
    # with the density and reachability any claim about them has to be read against.
    "leads": f"""
        SELECT symbol, tier, reachable, round(bait_density, 4) AS bait_density,
               confirmed_het, confirmed_novel
        FROM {ALIAS}.results.it2_kmer_pairs
        WHERE biallelic_confirmed
        ORDER BY confirmed_het DESC, symbol
    """,
    # Stage 0: where the aligner was unsure. The gate that decides what may be reported.
    "mapq": f"""
        SELECT tier,
               count(*) AS genes,
               count(*) FILTER (NOT reachable) AS unreachable,
               count(*) FILTER (sparse_bait) AS sparse_bait,
               count(*) FILTER (mapq_refused) AS mapq_refused,
               round(median(mapq0_fraction), 6) AS median_mapq0_fraction,
               round(max(mapq0_fraction), 6) AS max_mapq0_fraction
        FROM {ALIAS}.results.it2_mapq_profile
        GROUP BY tier
        ORDER BY tier
    """,
    # Copy number, at whatever resolution each region earned.
    "copy_number": f"""
        SELECT tier,
               count(*) AS regions,
               count(*) FILTER (NOT pooled) AS exon_scale,
               count(*) FILTER (pooled) AS pooled,
               count(*) FILTER (cn_local IS NULL) AS without_local_denominator,
               count(*) FILTER (below_null_band) AS below_null_band,
               round(median(coalesce(cn_local, cn_genome_wide)), 4) AS median_copy_number,
               round(median(denominator_disagreement), 4) AS median_disagreement
        FROM {ALIAS}.results.it2_exon_cn
        GROUP BY tier
        ORDER BY tier
    """,
    "copy_number_band": f"""
        SELECT percentile, low, high, median, regions
        FROM {ALIAS}.results.it2_cn_null
    """,
}


def payload(settings: Postgres) -> dict:
    """Every block, plus the target-versus-decoy contrast the step is obliged to report."""
    data = {name: fetch(settings, sql) for name, sql in BLOCKS.items()}
    data["contrast"] = _contrast(data["confirmation"])
    return data


def _contrast(confirmation: list[dict]) -> list[dict]:
    """Targets against decoys, split by whether the delivered callset had seen the allele.

    Derived from the confirmation block rather than queried again so the two cannot
    disagree. Reported for both because H020 is refuted: a target-gene result does not
    outweigh a decoy-gene one before the filter, and a rate quoted for only one side invites
    exactly that reading.
    """
    out = []
    for novel, label in ((False, "reported by the delivered callset"), (True, "vendor-unreported")):
        rows = [row for row in confirmation if bool(row["novel"]) is novel]
        targets = [row for row in rows if row["tier"] in TARGET_TIERS]
        decoys = [row for row in rows if row["tier"] == DECOY_TIER]
        target_probed = sum(int(row["fully_probed"] or 0) for row in targets)
        decoy_probed = sum(int(row["fully_probed"] or 0) for row in decoys)
        target_hits = sum(int(row["confirmed"] or 0) for row in targets)
        decoy_hits = sum(int(row["confirmed"] or 0) for row in decoys)
        out.append(
            {
                "allele_set": label,
                "target_alleles": target_probed,
                "target_confirmed": target_hits,
                "target_rate": target_hits / target_probed if target_probed else 0.0,
                "decoy_alleles": decoy_probed,
                "decoy_confirmed": decoy_hits,
                "decoy_rate": decoy_hits / decoy_probed if decoy_probed else 0.0,
            }
        )
    return out


def add_routes(api: APIRouter, settings: Postgres) -> None:
    """Register the step-3 detail route on the warehouse router."""

    @api.get(
        "/steps/step-3",
        response_model=Envelope,
        tags=["science"],
        summary=f"iteration 2 step 3's result tables, as aggregates ({SOURCE})",
    )
    def it2_step_3() -> dict:
        """What the reads say when neither an aligner nor a caller is asked.

        Every block is an aggregate; the tables behind them carry gene symbols and counts
        and no coordinate, and the probe sequences never leave the build directory.
        """
        return live(payload(settings), SOURCE)
