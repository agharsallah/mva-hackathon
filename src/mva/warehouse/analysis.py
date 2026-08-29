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
"""

from dataclasses import dataclass

#: Placeholder replaced with the fully-qualified ingest schema before execution.
SOURCE = "{src}"


@dataclass(frozen=True)
class Derivation:
    """One analysis: a name, what it answers, and the SELECT that answers it."""

    name: str
    question: str
    sql: str
    depends_on: tuple[str, ...] = ()


DERIVATIONS: tuple[Derivation, ...] = (
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

#: Written alongside the outputs so a result in the database can be traced to a run.
PROVENANCE_TABLE = "derivation_runs"


def by_name(name: str) -> Derivation:
    """Look one derivation up, with a helpful error listing the alternatives."""
    for derivation in DERIVATIONS:
        if derivation.name == name:
            return derivation
    known = ", ".join(item.name for item in DERIVATIONS)
    raise KeyError(f"unknown derivation {name!r}; known: {known}")


def resolve(sql: str, source_schema: str) -> str:
    """Point a derivation's SQL at a concrete schema."""
    return sql.replace(SOURCE, source_schema)
