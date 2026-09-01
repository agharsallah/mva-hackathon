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


def baf_bins(settings: Postgres, chrom: str | None = None) -> list[dict]:
    """Heterozygous allele balance per 1 Mb bin, whole genome or one chromosome.

    The per-megabase counterpart of ``allele_balance``, precomputed by the ``baf_bins``
    derivation. ``low_confidence`` travels with the row so the chart can render a thin bin
    as unmeasured rather than as signal; the row is never dropped, because an empty
    stretch is itself information.
    """
    where = "WHERE chrom = ?" if chrom else ""
    return fetch(settings,
                 f"SELECT chrom, mb, n_het, mean_vaf, median_vaf, sd_vaf, vaf_deviation, "
                 f"pct_in_0_40_0_60, mean_dp, low_confidence "
                 f"FROM pg.results.baf_bins {where} ORDER BY chrom, mb",
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


def observed_expected(settings: Postgres) -> list[dict]:
    """Each QC metric this callset can be measured against, with its published range."""
    return table(settings, "results", "qc_observed_expected", "ORDER BY metric")


def candidate_funnel(settings: Postgres) -> list[dict]:
    """The ranking waterfall, one row per filter stage, in stage order.

    Two scopes in one table: ``scope = 'genome'`` rows are measured over the whole
    callset, ``scope = 'panel'`` rows only inside the eight-gene candidate panel, which is
    the only region annotation exists for. ``of_previous_pct`` is **null** wherever the
    row is not a subset of the row above it — at the scope change — rather than dividing
    two different populations.
    """
    return table(settings, "results", "candidate_funnel", "ORDER BY stage_no")


def tstv(settings: Postgres) -> dict:
    """The transition/transversion ratio as a single object."""
    found = table(settings, "results", "stats_tstv")
    return found[0] if found else {"ts": None, "tv": None, "ratio": None}


def zygosity_split(settings: Postgres) -> list[dict]:
    """The bcftools ``AF`` section, parsed — two rows on a single-sample callset.

    ``zygosity`` is the reading, and it is **null** on anything but one sample, where the
    bins really are population allele frequencies. See
    :mod:`mva.warehouse.analysis_stats` for why AF here is a het/hom split.
    """
    return table(settings, "results", "stats_af", "ORDER BY af_bin")


def vcf_fields(settings: Postgres) -> list[dict]:
    """Every FILTER, INFO and FORMAT field the callset's own VCF header declares.

    The callset's schema documentation, written by the caller that produced it. Ordered
    so the three kinds stay grouped and stable across requests.
    """
    return fetch(settings,
                 "SELECT kind, id, description FROM pg.warehouse.vcf_fields "
                 "ORDER BY CASE kind WHEN 'FILTER' THEN 0 WHEN 'INFO' THEN 1 ELSE 2 END, "
                 "id")


# ── reads ────────────────────────────────────────────────────────────────────────────

def sequencing_yield(settings: Postgres) -> list[dict]:
    """What each flowcell lane contributed, estimated from the delivered FASTQ bytes.

    Estimated, not counted: ``est_reads`` and ``est_gbases`` come from a file's compressed
    size and its first read's length, because counting means decompressing 79 GB. The
    counted figures live in ``/api/reads/runs``, which reads the converted parquet store —
    the two together are what make the estimate's error measurable.
    """
    return table(settings, "results", "sequencing_yield", "ORDER BY lane")


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


def panel_constraint(settings: Postgres, bed: Path | None = None) -> list[dict]:
    """The candidate panel graded against gnomAD constraint and ClinVar.

    One derived table plus the same two BED-only columns ``panel_genes`` merges, so a
    chart can show "this gene, this intolerant, this often already classified" without a
    second request. ``chrom`` is ``chr``-prefixed, as the panel delivers it.
    """
    from .panelbed import annotations

    found = table(settings, "results", "panel_gene_constraint",
                  "ORDER BY loeuf NULLS LAST, gene")
    extra = annotations(bed)
    for row in found:
        row.update(extra.get(row["gene"], {"ensembl_id": None, "note": None}))
    return found


def panel_background(settings: Postgres) -> list[dict]:
    """Each panel gene's density and PASS share next to the background it sits in.

    Eight rows off the ``panel_gene_background`` derivation, which did the whole-genome
    1 Mb bin aggregate at derive time. The z-scores are standard deviations from that bin
    distribution; a **null** z means the background had no usable spread, never zero. The
    PASS-share z is a *callability* reading — mappability, repeats — not a pathogenicity
    one. ``chrom`` is ``chr``-prefixed, as the panel delivers it.
    """
    return table(settings, "results", "panel_gene_background",
                 "ORDER BY z_pass_vs_contig NULLS LAST, gene")


def panel_candidates(settings: Postgres, gene: str | None = None) -> list[dict]:
    """Every annotated panel allele with its genotype evidence, optionally one gene.

    Reads the ``panel_candidates`` derivation, which has already done the expensive part —
    joining 874 annotations to the five-million-row callset. 874 rows unfiltered, so no
    cache. An unknown gene yields no rows and is reported as :class:`LookupError`, because
    every gene the table knows has at least one row.
    """
    where = "WHERE gene = ?" if gene else ""
    found = fetch(settings, f"""
        SELECT chrom, pos, ref, alt, rsid, gene, consequence, impact,
               gnomad_af, gnomad_af_grpmax, clin_sig, qual, filter, gt, dp, vaf,
               is_rare_recessive, is_protein_altering
        FROM pg.results.panel_candidates {where}
        ORDER BY gene, pos, alt
    """, [gene] if gene else None)
    if gene and not found:
        raise LookupError(gene)
    return found


def het_pairs(settings: Postgres, gene: str) -> list[dict]:
    """One gene's heterozygous PASS alleles — the members of its compound-het pair grid.

    Reads the ``panel_het_pairs`` derivation, so the request is a few hundred rows and no
    cross product happens in SQL; :mod:`mva.viz.phase` builds the pairs. An empty result
    is ambiguous — a gene with no het PASS allele looks exactly like a misspelt gene — so
    the panel is consulted before answering, and only a name it does not know is a
    :class:`LookupError`.
    """
    found = fetch(settings, """
        SELECT gene, chrom, pos, ref, alt, allele_ix, gt, qual, dp, vaf, pgt, pid,
               rsid, consequence, impact, gnomad_af, gnomad_af_grpmax, clin_sig,
               annotated, is_rare_recessive, is_protein_altering
        FROM pg.results.panel_het_pairs WHERE gene = ?
        ORDER BY pos, allele_ix
    """, [gene])
    if not found:
        gene_region(settings, gene)
    return found


def clinvar_presence(settings: Postgres, gene: str | None = None) -> dict:
    """Every ClinVar P/LP panel site the callset was checked for, summarised and listed.

    Two halves, both off the ``clinvar_presence`` derivation, which has already done the
    join to the five-million-row callset.

    * ``summary`` is one row per **panel gene**, counted off the panel BED with a LEFT
      join, so a gene ClinVar has classified nothing in appears with ``n_plp = 0`` rather
      than vanishing. That absence is a result.
    * ``sites`` is deliberately **not** every P/LP row. It is the rows that are present,
      plus the rows that could never be compared (``comparable = false``). The measured
      absences — the overwhelming majority — are carried as counts in ``summary``, because
      shipping two thousand rows of "nothing was called here" per request would say
      nothing the counts do not.

    ``present`` is a **lower bound**: matching is exact on (chrom, pos, ref) plus ALT list
    membership with no left-alignment on either side, so an indel spelled differently in
    ClinVar and in the callset reads as absent.
    """
    # The summary counts off the panel BED and the site list off the derivation, so the
    # optional gene filter names a different column in each.
    by_panel = "AND b.name = ?" if gene else ""
    by_site = "AND p.gene = ?" if gene else ""
    params = [gene] if gene else None
    summary = fetch(settings, f"""
        SELECT b.name                                                AS gene,
               count(p.variation_id)                                 AS n_plp,
               count(*) FILTER (WHERE p.comparable)                  AS n_comparable,
               count(*) FILTER (WHERE p.comparable IS FALSE)         AS n_uncomparable,
               count(*) FILTER (WHERE p.present)                     AS n_present,
               count(*) FILTER (WHERE p.present AND p.filter = 'PASS')
                                                                     AS n_present_pass,
               count(*) FILTER (WHERE p.is_het)                      AS n_present_het,
               count(*) FILTER (WHERE p.present IS FALSE)            AS n_absent
        FROM pg.warehouse.mva_panel_grch38 b
        LEFT JOIN pg.results.clinvar_presence p ON p.gene = b.name
        WHERE 1 = 1 {by_panel}
        GROUP BY b.name
        ORDER BY n_present DESC, n_plp DESC, b.name
    """, params)
    if gene and not summary:
        raise LookupError(gene)
    sites = fetch(settings, f"""
        SELECT gene, chrom, pos, ref, alt, rsid, variation_id, clnsig, clnrevstat,
               review_stars, condition, comparable, present, gt, filter, qual, dp,
               allele_ix, vaf, carries_alt, is_het
        FROM pg.results.clinvar_presence p
        WHERE (p.present OR p.present IS NULL) {by_site}
        ORDER BY gene, pos, alt
    """, params)
    return {"summary": summary, "sites": sites}


def panel_filter_census(settings: Postgres) -> list[dict]:
    """Every panel gene's records counted per FILTER value, PASS included.

    Always the whole panel — 20 rows over 8 genes — because the chart it feeds compares
    genes against each other. ``filter`` is verbatim, so a ``;``-joined value is one
    record that tripped two thresholds and the stack over a gene sums to ``n_gene_all``.
    """
    return table(settings, "results", "panel_filter_census",
                 "ORDER BY gene, is_pass DESC, n DESC, filter")


def panel_suppressed(settings: Postgres, gene: str | None = None) -> list[dict]:
    """The non-PASS records inside the panel, optionally one gene.

    Reads the ``panel_suppressed`` derivation: 20 rows for the whole panel, so no cache and
    no gene filter is needed for cost — the parameter exists because the table below the
    chart shows one gene at a time. Unlike ``panel_candidates`` an empty result is **not**
    a :class:`LookupError`: a panel gene with nothing suppressed is the good outcome, and
    the caller validates the name against the census instead.
    """
    where = "WHERE gene = ?" if gene else ""
    return fetch(settings, f"""
        SELECT gene, chrom, pos, ref, alt, qual, filter, gt, dp, gq, ad_ref, ad_alt, vaf,
               is_het, annotated_alt, rsid, consequence, impact, gnomad_af,
               gnomad_af_grpmax, clin_sig, annotated
        FROM pg.results.panel_suppressed {where}
        ORDER BY gene, pos, ref, alt
    """, [gene] if gene else None)


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
