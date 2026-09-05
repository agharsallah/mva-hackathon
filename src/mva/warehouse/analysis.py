"""Derivations: analytics that read the ingested tables and write results back.

Each :class:`Derivation` is one named SQL statement producing one output table. They are
data, not code, which is the point — adding an analysis means appending a record here, and
the runner, the CLI, the provenance stamp and the tests all pick it up without changing.

Two conventions make the set safe to re-run at any time:

* **Input and output live in different schemas.** Derivations read from the ingest schema,
  which ``pg-ingest`` replaces wholesale, and write to the result schema, which it never
  touches. Re-ingesting therefore cannot destroy a derived table, and re-deriving cannot
  corrupt an input.
* **Every output is rebuilt, never appended to.** A derivation is a pure function of the
  tables beneath it, so a wrong result is fixed by fixing the inputs and running again.

The SQL is written against DuckDB, which is doing the computation; only the final table
lands in PostgreSQL. That is why these can join, aggregate and window freely without
worrying about what the server would make of it.

The registry is assembled from two files. This one holds everything derived from the
**delivery itself**; :mod:`mva.warehouse.analysis_reference` holds everything that
compares the delivery against the committed **public reference** tables. Both produce
:class:`~mva.warehouse.derivation.Derivation` records and both land in the same
:data:`DERIVATIONS` tuple, so the runner, the CLI and the tests see one registry.
"""

from .analysis_background import BACKGROUND_DERIVATIONS
from .analysis_clinvar import CLINVAR_DERIVATIONS
from .analysis_coding import CODING_DERIVATIONS
from .analysis_funnel import FUNNEL_DERIVATIONS
from .analysis_karyogram import KARYOGRAM_DERIVATIONS
from .analysis_pairs import PAIR_DERIVATIONS
from .analysis_reference import REFERENCE_DERIVATIONS
from .analysis_stats import STATS_DERIVATIONS
from .analysis_suppressed import SUPPRESSED_DERIVATIONS
from .derivation import SOURCE, Derivation, resolve

__all__ = [
    "CALLSET_DERIVATIONS",
    "DERIVATIONS",
    "PROVENANCE_TABLE",
    "SOURCE",
    "Derivation",
    "by_name",
    "resolve",
]

#: Derivations over the delivered callset and read profile.
CALLSET_DERIVATIONS: tuple[Derivation, ...] = (
    Derivation(
        name="panel_gene_density",
        question="Which candidate gene carries the most variation per base sequenced?",
        depends_on=("panel_variant_counts", "mva_panel_grch38"),
        sql=f"""
            SELECT p.gene,
                   p.chrom,
                   p.n_all,
                   p.n_pass,
                   p.n_all - p.n_pass                        AS n_filtered,
                   b."end" - b.start                         AS span_bp,
                   round(p.n_all * 1e6 / (b."end" - b.start), 1) AS variants_per_mb,
                   round(100.0 * p.n_pass / nullif(p.n_all, 0), 1) AS pct_pass
            FROM {SOURCE}.panel_variant_counts p
            JOIN {SOURCE}.mva_panel_grch38 b ON p.gene = b.name
            ORDER BY variants_per_mb DESC
        """,
    ),
    Derivation(
        name="contig_density",
        question="How does variant density vary across the chromosomes?",
        depends_on=("contig_counts",),
        sql=f"""
            SELECT chrom,
                   length,
                   n_records,
                   round(n_records * 1e6 / nullif(length, 0), 1) AS variants_per_mb,
                   round(100.0 * n_records
                         / sum(n_records) OVER (), 3)            AS pct_of_callset
            FROM {SOURCE}.contig_counts
            WHERE length > 1000000
            ORDER BY variants_per_mb DESC
        """,
    ),
    Derivation(
        name="allele_balance_flags",
        question="Does any chromosome deviate from the 0.50 heterozygous balance a "
        "diploid genome should show?",
        depends_on=("vcf_chrom_allele_balance",),
        sql=f"""
            SELECT chrom,
                   n_het,
                   mean_vaf,
                   mean_dp,
                   pct_in_0_40_0_60,
                   round(mean_vaf - 0.5, 4)                       AS vaf_deviation,
                   CASE WHEN mean_vaf < 0.45 OR mean_vaf > 0.55 THEN 'flagged'
                        ELSE 'balanced' END                       AS balance_call,
                   round(mean_dp / nullif(
                         avg(mean_dp) FILTER (WHERE chrom NOT IN ('X','Y'))
                         OVER (), 0), 3)                          AS dp_vs_autosomal
            FROM {SOURCE}.vcf_chrom_allele_balance
            ORDER BY abs(mean_vaf - 0.5) DESC
        """,
    ),
    Derivation(
        name="filter_impact",
        question="Which quality filters remove the most records?",
        depends_on=("filter_gt_counts",),
        sql=f"""
            SELECT label                                          AS filter_value,
                   count,
                   round(100.0 * count / sum(count) OVER (), 2)   AS pct_of_section,
                   rank() OVER (ORDER BY count DESC)              AS impact_rank
            FROM {SOURCE}.filter_gt_counts
            WHERE section = 'FILTER counts'
            ORDER BY count DESC
        """,
    ),
    Derivation(
        name="variant_density_bins",
        question="Where along each chromosome does variation and quality concentrate, "
        "at 1 Mb resolution?",
        depends_on=("variants_raw",),
        # `variants_raw` is five million all-text rows with no index, so a whole-genome
        # scan is ~60 s. Precomputing it here is what lets the viz API answer a
        # per-chromosome density request from a table of a few thousand rows instead of
        # re-scanning the callset on an HTTP request.
        #
        # `//` is integer division. DuckDB's `/` is *float* division, so `pos / 1000000`
        # would produce a fractional bin and one group per position.
        sql=f"""
            SELECT chrom,
                   CAST(pos AS BIGINT) // 1000000                     AS mb,
                   count(*)                                           AS n,
                   count(*) FILTER (WHERE filter = 'PASS')            AS pass_n,
                   count(*) FILTER (WHERE TRY_CAST(qual AS DOUBLE) < 30)
                                                                      AS low_qual_n,
                   round(avg(TRY_CAST(qual AS DOUBLE)), 1)            AS mean_qual
            FROM {SOURCE}.variants_raw
            WHERE length(chrom) <= 2
            GROUP BY chrom, mb
            ORDER BY chrom, mb
        """,
    ),
    Derivation(
        name="stats_sn",
        question="What are the callset's headline counts, as bcftools measured them?",
        depends_on=("stats_summary",),
        # `stats_summary` holds bcftools-stats output verbatim: one tab-delimited line per
        # row, section code in column 1. Parsing it into typed tables *here* rather than
        # in the API means the numbers a chart shows are a table with lineage, not a
        # regex that ran inside a web request.
        sql=f"""
            SELECT rtrim(split_part(line, chr(9), 3), ':')             AS metric,
                   CAST(split_part(line, chr(9), 4) AS BIGINT)         AS value
            FROM {SOURCE}.stats_summary
            WHERE line LIKE 'SN' || chr(9) || '%'
            ORDER BY line_no
        """,
    ),
    Derivation(
        name="stats_tstv",
        question="What is the transition/transversion ratio — the callset's cheapest "
        "sanity check against a random error process?",
        depends_on=("stats_summary",),
        sql=f"""
            SELECT CAST(split_part(line, chr(9), 3) AS BIGINT)         AS ts,
                   CAST(split_part(line, chr(9), 4) AS BIGINT)         AS tv,
                   CAST(split_part(line, chr(9), 5) AS DOUBLE)         AS ratio
            FROM {SOURCE}.stats_summary
            WHERE line LIKE 'TSTV' || chr(9) || '%'
        """,
    ),
    Derivation(
        name="stats_dp",
        question="How is per-record read depth distributed across the callset?",
        depends_on=("stats_summary",),
        # DP layout: code, id, bin, n_genotypes, pct_genotypes, n_sites, pct_sites.
        # This is a single-sample callset, so the genotype columns are zero and the site
        # columns carry the distribution.
        sql=f"""
            SELECT CAST(split_part(line, chr(9), 3) AS INTEGER)        AS bin,
                   CAST(split_part(line, chr(9), 6) AS BIGINT)         AS count,
                   CAST(split_part(line, chr(9), 7) AS DOUBLE)         AS pct
            FROM {SOURCE}.stats_summary
            WHERE line LIKE 'DP' || chr(9) || '%'
            ORDER BY bin
        """,
    ),
    Derivation(
        name="stats_st",
        question="Which base substitutions dominate, and are they transitions?",
        depends_on=("stats_summary",),
        sql=f"""
            SELECT split_part(line, chr(9), 3)                         AS sub_type,
                   CAST(split_part(line, chr(9), 4) AS BIGINT)         AS count,
                   split_part(line, chr(9), 3)
                       IN ('A>G', 'G>A', 'C>T', 'T>C')                 AS is_transition
            FROM {SOURCE}.stats_summary
            WHERE line LIKE 'ST' || chr(9) || '%'
            ORDER BY count DESC
        """,
    ),
    Derivation(
        name="stats_idd",
        question="How long are the insertions and deletions, and is the length spectrum "
        "the expected exponential decay?",
        depends_on=("stats_summary",),
        # IDD layout: code, id, length, count, n_genotypes, mean_vaf. Negative length is
        # a deletion, positive an insertion.
        sql=f"""
            SELECT CAST(split_part(line, chr(9), 3) AS INTEGER)        AS length,
                   CAST(split_part(line, chr(9), 4) AS BIGINT)         AS count
            FROM {SOURCE}.stats_summary
            WHERE line LIKE 'IDD' || chr(9) || '%'
            ORDER BY length
        """,
    ),
    Derivation(
        name="sequencing_yield",
        question="What did each lane contribute, and is the read-1/read-2 balance sane?",
        depends_on=("fastq_profile",),
        sql=f"""
            SELECT regexp_extract(file, '_(L00[0-9])_', 1)        AS lane,
                   sum(est_reads)                                 AS est_reads,
                   round(sum(est_gbases), 2)                      AS est_gbases,
                   round(sum(bytes) / 1e9, 2)                     AS gigabytes,
                   count(*)                                       AS n_files
            FROM {SOURCE}.fastq_profile
            GROUP BY lane
            ORDER BY lane
        """,
    ),
)

#: Every derivation the runner knows about, in execution order.
DERIVATIONS: tuple[Derivation, ...] = (
    CALLSET_DERIVATIONS
    + REFERENCE_DERIVATIONS
    + KARYOGRAM_DERIVATIONS
    + PAIR_DERIVATIONS
    + FUNNEL_DERIVATIONS
    + STATS_DERIVATIONS
    + BACKGROUND_DERIVATIONS
    + SUPPRESSED_DERIVATIONS
    + CLINVAR_DERIVATIONS
    + CODING_DERIVATIONS
)

#: Written alongside the outputs so a result in the database can be traced to a run.
PROVENANCE_TABLE = "derivation_runs"


def by_name(name: str) -> Derivation:
    """Look one derivation up, with a helpful error listing the alternatives."""
    for derivation in DERIVATIONS:
        if derivation.name == name:
            return derivation
    known = ", ".join(item.name for item in DERIVATIONS)
    raise KeyError(f"unknown derivation {name!r}; known: {known}")
