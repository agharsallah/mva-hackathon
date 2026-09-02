"""The one object the landing page needs — every headline number in a single request.

Assembled from nine small tables and the read-store's ``runs`` dimension. Every field is
read from a table rather than restated here, so nothing on the front page can drift away
from what the pipeline actually measured; the only literal is the oracle budget, and it
is imported from the module that owns it.

One connection for the lot. Each ``ATTACH`` to the hosted PostgreSQL costs a round trip
plus authentication, so nine separate ``fetch`` calls would spend most of the request
opening and closing the same connection.
"""

from ..warehouse.postgres import attached
from ..warehouse.probes import BUDGET
from ..warehouse.settings import Postgres
from .queries.access import CANONICAL, rows


def overview(settings: Postgres) -> dict:
    """Assemble the headline object. One PostgreSQL connection, one object-store read."""
    with attached(settings, read_only=True) as connection:
        summary = {
            row["metric"]: row["value"]
            for row in rows(connection, "SELECT metric, value FROM pg.results.stats_sn")
        }
        ratio = rows(connection, "SELECT ratio FROM pg.results.stats_tstv")
        counts = _one(
            connection,
            f"""
            SELECT count(*)                                    AS all_contigs,
                   count(*) FILTER (WHERE {CANONICAL})         AS canonical_contigs
            FROM pg.warehouse.contig_counts
        """,
        )
        passing = _one(
            connection,
            """
            SELECT coalesce(sum(count), 0) AS pass_variants
            FROM pg.warehouse.filter_gt_counts
            WHERE section = 'FILTER counts' AND label = 'PASS'
        """,
        )
        coverage = _one(
            connection,
            """
            SELECT max(value) FILTER (WHERE key = 'est_raw_coverage_x') AS est_coverage_x
            FROM pg.warehouse.profile_scalars
        """,
        )
        # Mean mapped depth is not stored as a scalar anywhere; it is the het-weighted
        # mean of the per-chromosome depths, restricted to autosomes so a sex chromosome
        # at half depth cannot pull the genome-wide figure down.
        depth = _one(
            connection,
            """
            SELECT round(sum(n_het * mean_dp) / nullif(sum(n_het), 0), 1) AS mean_depth_x
            FROM pg.results.allele_balance_flags
            WHERE chrom NOT IN ('X', 'Y', 'M')
        """,
        )
        delivery = _one(
            connection,
            """
            SELECT count(*)                        AS delivery_objects,
                   coalesce(sum(size_bytes), 0)    AS delivery_bytes,
                   bool_and(hash_verified)         AS all_hashes_verified
            FROM pg.warehouse.source_objects
        """,
        )
        spent = _one(
            connection, "SELECT count(*) AS probe_budget_spent FROM pg.warehouse.probe_ledger"
        )

    return {
        "total_variants": _int(summary.get("number of records")),
        "pass_variants": _int(passing.get("pass_variants")),
        "snps": _int(summary.get("number of SNPs")),
        "indels": _int(summary.get("number of indels")),
        "multiallelic_sites": _int(summary.get("number of multiallelic sites")),
        "tstv": ratio[0]["ratio"] if ratio else None,
        "samples": _int(summary.get("number of samples")),
        **_reads(),
        "est_coverage_x": coverage.get("est_coverage_x"),
        "mean_depth_x": depth.get("mean_depth_x"),
        "canonical_contigs": _int(counts.get("canonical_contigs")),
        "all_contigs": _int(counts.get("all_contigs")),
        "delivery_objects": _int(delivery.get("delivery_objects")),
        "delivery_bytes": _int(delivery.get("delivery_bytes")),
        "all_hashes_verified": bool(delivery.get("all_hashes_verified")),
        "probe_budget_total": BUDGET,
        "probe_budget_spent": _int(spent.get("probe_budget_spent")),
    }


def _reads() -> dict:
    """Read totals from the store's eight-row ``runs`` table, or nulls if it is down.

    Degrading rather than failing is deliberate: the object store and the database are
    separate services, and a landing page should still show the callset when only one of
    the two is reachable.
    """
    from .readstore import totals

    try:
        return totals()
    except Exception:
        return {"total_reads": None, "read_length": None}


def _one(connection, sql: str) -> dict:
    found = rows(connection, sql)
    return found[0] if found else {}


def _int(value) -> int | None:
    return None if value is None else int(value)
