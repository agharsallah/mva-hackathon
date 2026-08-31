"""Every warehouse read the viz API makes, as one function per endpoint.

Two rules govern this module, and both exist to keep an HTTP request from becoming a
whole-genome scan:

* **Charts read derived tables, never the callset.** ``variants_raw`` is five million
  all-text rows with no index; the cheapest full aggregate over it is ~60 s. Anything a
  chart needs is precomputed by a :mod:`~mva.warehouse.analysis` derivation, so the
  request reads a few thousand rows.
* **The one exception pushes its filter down.** The locus endpoint has to touch the
  callset, so it always constrains ``chrom``, which PostgreSQL can satisfy without
  reading the other 24 chromosomes (~4.4 s instead of ~21 s).

Rows come back as dicts with JSON-safe values, because a chart component should not have
to know that PostgreSQL hands DuckDB a ``Decimal`` and a naive ``datetime``.
"""

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from ..pipeline.variant import to_vcf_contig
from ..warehouse.postgres import attached
from ..warehouse.settings import Postgres
from . import genotype

#: Canonical contigs are the ones whose name is at most two characters — 1..22, X, Y, M.
#: The same predicate is used by every derivation, so the API and the tables agree.
CANONICAL = "length(chrom) <= 2"


def jsonable(value):
    """One value in a shape ``json.dumps`` accepts."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", "replace")
    return value


def rows(connection, sql: str, params: list | None = None) -> list[dict]:
    """Run one statement on an open connection and return JSON-safe dicts."""
    cursor = connection.execute(sql, params or [])
    columns = [description[0] for description in cursor.description or ()]
    return [{column: jsonable(value) for column, value in zip(columns, row)}
            for row in cursor.fetchall()]


def fetch(settings: Postgres, sql: str, params: list | None = None) -> list[dict]:
    """Attach, run one read-only statement, detach."""
    with attached(settings, read_only=True) as connection:
        return rows(connection, sql, params)


def table(settings: Postgres, schema: str, name: str, order: str = "") -> list[dict]:
    """A whole (small) table, optionally ordered."""
    from ..warehouse.postgres import safe_identifier

    qualified = f"pg.{safe_identifier(schema)}.{safe_identifier(name)}"
    return fetch(settings, f"SELECT * FROM {qualified} {order}")


# ── genome ───────────────────────────────────────────────────────────────────────────

def allele_balance(settings: Postgres) -> list[dict]:
    return table(settings, "results", "allele_balance_flags",
                 "ORDER BY abs(vaf_deviation) DESC")


def contig_density(settings: Postgres) -> list[dict]:
    return table(settings, "results", "contig_density", "ORDER BY variants_per_mb DESC")


def density_bins(settings: Postgres, chrom: str | None = None) -> list[dict]:
    """1 Mb bins, whole genome or one chromosome. Bare contig names, as delivered."""
    where = "WHERE chrom = ?" if chrom else ""
    return fetch(settings,
                 f"SELECT chrom, mb, n, pass_n, low_qual_n, mean_qual "
                 f"FROM pg.results.variant_density_bins {where} ORDER BY chrom, mb",
                 [to_vcf_contig(chrom)] if chrom else None)


# ── callset ──────────────────────────────────────────────────────────────────────────

def filters(settings: Postgres) -> list[dict]:
    return table(settings, "results", "filter_impact", "ORDER BY impact_rank")


def genotypes(settings: Postgres) -> list[dict]:
    return fetch(settings,
                 "SELECT label, count FROM pg.warehouse.filter_gt_counts "
                 "WHERE section = 'genotype counts' ORDER BY count DESC")


def depth_distribution(settings: Postgres) -> list[dict]:
    return table(settings, "results", "stats_dp", "ORDER BY bin")


def substitutions(settings: Postgres) -> list[dict]:
    return table(settings, "results", "stats_st", "ORDER BY count DESC")


def indel_lengths(settings: Postgres) -> list[dict]:
    return table(settings, "results", "stats_idd", "ORDER BY length")


def tstv(settings: Postgres) -> dict:
    """The transition/transversion ratio as a single object."""
    found = table(settings, "results", "stats_tstv")
    return found[0] if found else {"ts": None, "tv": None, "ratio": None}


# ── panel ────────────────────────────────────────────────────────────────────────────

def panel_genes(settings: Postgres, bed: Path | None = None) -> list[dict]:
    """The candidate panel with its density, coordinates and annotation.

    Three sources, joined here rather than in a derivation because two of them are the
    same table at different grains and the third is a committed file: density comes from
    ``results.panel_gene_density``, the interval from ``warehouse.panel_variant_counts``,
    and ``ensembl_id``/``note`` from the panel BED's comment-documented extra columns,
    which the staged table drops.
    """
    from .panelbed import annotations

    found = fetch(settings, """
        SELECT d.gene, d.chrom, c.start, c."end", d.n_all, d.n_pass, d.n_filtered,
               d.span_bp, d.variants_per_mb, d.pct_pass
        FROM pg.results.panel_gene_density d
        JOIN pg.warehouse.panel_variant_counts c ON c.gene = d.gene
        ORDER BY d.variants_per_mb DESC
    """)
    extra = annotations(bed)
    for row in found:
        row.update(extra.get(row["gene"], {"ensembl_id": None, "note": None}))
    return found


def gene_region(settings: Postgres, gene: str) -> tuple[str, int, int]:
    """A panel gene's interval as ``(bare chrom, start, end)``, ready for a query.

    The panel is chr-prefixed and the callset is bare, so the name is converted by
    :func:`~mva.pipeline.variant.to_vcf_contig` — the repo's single owner of that
    bridge. Building the bare name with a ``removeprefix`` here would be a second
    normalizer, which is exactly the failure mode the chr-prefix rule forbids.
    """
    found = fetch(settings,
                  'SELECT chrom, start, "end" FROM pg.warehouse.mva_panel_grch38 '
                  "WHERE name = ?", [gene])
    if not found:
        raise LookupError(gene)
    row = found[0]
    return to_vcf_contig(row["chrom"]), int(row["start"]), int(row["end"])


def locus(settings: Postgres, gene: str) -> list[dict]:
    """Every variant in a panel gene, with its genotype evidence decoded.

    The only endpoint that reads the callset. ``chrom`` is constrained first so the
    server can skip the other contigs; ``pos`` is cast for the range test and the sort
    because the column is text, where ``'999' > '1000'``.
    """
    chrom, start, end = gene_region(settings, gene)
    found = fetch(settings, f"""
        SELECT pos, ref, alt, qual, filter, format, sample_call
        FROM pg.warehouse.variants_raw
        WHERE chrom = ? AND CAST(pos AS BIGINT) BETWEEN ? AND ?
        ORDER BY CAST(pos AS BIGINT)
    """, [chrom, start, end])

    decoded = []
    for row in found:
        call = genotype.decode(row.pop("format"), row.pop("sample_call"))
        decoded.append({
            "pos": int(row["pos"]),
            "ref": row["ref"],
            # Multiallelic ALT stays comma-packed exactly as delivered: splitting it
            # here would invent rows the callset does not have.
            "alt": row["alt"],
            "qual": _float(row["qual"]),
            "filter": row["filter"],
            **call.as_dict(),
        })
    return decoded


# ── provenance ───────────────────────────────────────────────────────────────────────

def lineage(settings: Postgres) -> list[dict]:
    return fetch(settings, """
        SELECT produced_at, target_schema, target_table, target_rows, source_kind,
               source_ref, source_version, source_sha256, transform, tool, notes
        FROM pg.warehouse.data_lineage ORDER BY produced_at DESC
    """)


def derivations(settings: Postgres) -> list[dict]:
    return fetch(settings, "SELECT run_at, derivation, question, n_rows "
                           "FROM pg.results.derivation_runs ORDER BY run_at DESC")


def sources(settings: Postgres) -> list[dict]:
    return fetch(settings, """
        SELECT file_name, kind, role, size_bytes, hash_verified, sha256_source,
               version_id, lane, read_num
        FROM pg.warehouse.source_objects ORDER BY file_name
    """)


def probe_ledger(settings: Postgres) -> list[dict]:
    return fetch(settings, """
        SELECT probe_id, logged_at, track, probe_type, payload, n_rows, response,
               score, rationale
        FROM pg.warehouse.probe_ledger ORDER BY probe_id
    """)


def _float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
