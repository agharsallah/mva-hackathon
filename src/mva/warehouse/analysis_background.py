"""Is a panel gene's variant density and PASS share *normal* for where it sits?

``results.panel_gene_density`` says a gene carries N variants per megabase and passes P %
of them. Neither number means anything on its own: 200 variants/Mb is unremarkable on one
chromosome and an outlier on another, and a 50 % PASS share is alarming only if the
surrounding sequence passes at 99 %. The reading needs a **background** — what the rest of
the chromosome, and the rest of the genome, look like.

**The background is the per-megabase bin distribution, not a contig average.** A contig
mean is one number and hides its own spread; a gene that sits two standard deviations off
that mean is only interesting if the spread is small. So the comparison population here is
every 1 Mb window of the callset — the same windows ``variant_density_bins`` computes —
and the statistic is a **z-score** (how many standard deviations from the background mean
a value sits). One bin is one megabase, so a bin's record count *is* a density in
variants/Mb and is directly comparable to a gene's ``variants_per_mb``.

**What a low PASS-share z means, and what it does not.** A gene whose records are
suppressed far more often than its chromosome's windows is a statement about
**callability** — mappability, repeats, segmental duplication, telomere-proximal sequence
— never about pathogenicity. It says the evidence there is harder to trust, in either
direction.

Three conventions are load-bearing.

**Only the ingest schema is read.** A derivation may not read ``results``, because
``pg-derive`` has no ordering guarantee between derivations and a result table is not an
input. The bin distribution is therefore recomputed here from ``variants_raw`` rather than
read from ``results.variant_density_bins`` — the same duplication, for the same reason,
that ``qc_observed_expected`` pays when it re-parses ``stats_summary``. A test asserts the
binning expression is the one ``variant_density_bins`` uses.

**Contigs are bare on the callset side and ``chr``-prefixed on the panel side.** The bins
come from ``variants_raw`` (bare) and the gene rows from ``mva_panel_grch38``
(``chr``-prefixed), so the join strips the prefix with ``replace(chrom, 'chr', '')``, the
same expression :mod:`mva.warehouse.analysis_pairs` and :mod:`mva.warehouse.reference` use.
The emitted ``chrom`` stays ``chr``-prefixed, matching ``panel_gene_density`` and
``/api/panel/genes``.

**A zero spread yields no z, never a zero.** ``stddev_samp`` of a single bin is NULL and a
contig whose bins are all identical would divide by zero, so both are guarded and the
z-score comes back NULL — an unmeasurable comparison, rendered as a gap rather than as
agreement.
"""

from .derivation import SOURCE, Derivation

#: One bin is one megabase. Same divisor as ``variant_density_bins`` and ``baf_bins``, so
#: a bin's record count reads directly as variants per megabase.
BIN_BP = 1_000_000

#: Below this many records a bin's PASS *share* is a ratio of very small numbers: one
#: suppressed record in a three-record window is 67 %, which would widen the background
#: spread with noise rather than with biology. Such bins still count toward the **density**
#: distribution — an empty stretch is a real property of the reference — but are left out
#: of the PASS-share distribution. The density z is therefore computed over every window
#: and the PASS z over the well-covered ones.
MIN_BIN_N_FOR_PASS = 100

#: Conventional two-sigma line. Inside it a gene is ordinary for its background; outside it
#: is worth a sentence. It is a triage threshold, not a test with a p-value attached.
Z_NOTABLE = 2.0


PANEL_GENE_BACKGROUND = Derivation(
    name="panel_gene_background",
    question=(
        "For each candidate gene: is its variant density and its PASS share normal for "
        "its chromosome and for the genome, or an outlier? The background is the "
        "distribution over 1 Mb windows of the callset — one window is one megabase, so a "
        "window's record count is a density directly comparable to the gene's. Each gene "
        "gets a z-score (standard deviations from the background mean) against its own "
        "contig's windows and against the whole genome's. A low PASS-share z is a "
        "callability statement — mappability, repeats — never a pathogenicity one. Bins "
        f"under {MIN_BIN_N_FOR_PASS} records are excluded from the PASS-share background "
        "only, where a ratio of tiny counts would be noise. A contig with no usable "
        "spread yields NULL, never zero."),
    depends_on=("variants_raw", "contig_counts", "panel_variant_counts",
                "mva_panel_grch38"),
    # `variants_raw` is five million all-text rows with no index, so the bin aggregate is a
    # whole-genome scan — the same cost `variant_density_bins` and `baf_bins` already pay,
    # and the reason it is paid here at derive time rather than inside an HTTP request.
    #
    # `//` is integer division. DuckDB's `/` is float division and would produce one group
    # per position instead of one per megabase.
    sql=f"""
        WITH bins AS (
            SELECT chrom,
                   CAST(pos AS BIGINT) // {BIN_BP}          AS mb,
                   count(*)                                 AS n,
                   count(*) FILTER (WHERE filter = 'PASS')  AS pass_n
            FROM {SOURCE}.variants_raw
            WHERE length(chrom) <= 2
            GROUP BY chrom, mb
        ),
        -- A bin's PASS share is NULL below the floor, so `avg` and `stddev_samp` skip it
        -- without dropping the bin from the density distribution.
        scored AS (
            SELECT chrom,
                   n,
                   CASE WHEN n >= {MIN_BIN_N_FOR_PASS}
                        THEN 100.0 * pass_n / n END         AS pct_pass,
                   n                                        AS n_records,
                   pass_n
            FROM bins
        ),
        contig_background AS (
            SELECT chrom,
                   count(*)                                 AS n_bins,
                   avg(n)                                   AS mean_density,
                   stddev_samp(n)                           AS sd_density,
                   count(pct_pass)                          AS n_bins_pass,
                   avg(pct_pass)                            AS mean_pct_pass,
                   stddev_samp(pct_pass)                    AS sd_pct_pass,
                   100.0 * sum(pass_n) / nullif(sum(n_records), 0) AS pct_pass_overall
            FROM scored
            GROUP BY chrom
        ),
        genome_background AS (
            SELECT count(*)                                 AS n_bins,
                   avg(n)                                   AS mean_density,
                   stddev_samp(n)                           AS sd_density,
                   count(pct_pass)                          AS n_bins_pass,
                   avg(pct_pass)                            AS mean_pct_pass,
                   stddev_samp(pct_pass)                    AS sd_pct_pass,
                   100.0 * sum(pass_n) / nullif(sum(n_records), 0) AS pct_pass_overall
            FROM scored
        ),
        -- The contig's own density, from the delivered per-contig counts rather than from
        -- the bins: `contig_counts` divides by the *reference* length, so a chromosome's
        -- unsequenced stretches count against it, which is the honest denominator.
        contig_span AS (
            SELECT c.chrom,
                   c.length,
                   c.n_records,
                   c.n_records * 1e6 / nullif(c.length, 0)  AS variants_per_mb
            FROM {SOURCE}.contig_counts c
            WHERE length(c.chrom) <= 2
        ),
        genome_span AS (
            SELECT sum(n_records) * 1e6 / nullif(sum(length), 0) AS variants_per_mb
            FROM contig_span
        ),
        gene AS (
            SELECT p.gene,
                   b.chrom                                          AS chrom,
                   replace(b.chrom, 'chr', '')                      AS bare_chrom,
                   p.n_all,
                   p.n_pass,
                   b."end" - b.start                                AS span_bp,
                   p.n_all * 1e6 / nullif(b."end" - b.start, 0)     AS variants_per_mb,
                   100.0 * p.n_pass / nullif(p.n_all, 0)            AS pct_pass
            FROM {SOURCE}.panel_variant_counts p
            JOIN {SOURCE}.mva_panel_grch38 b ON p.gene = b.name
        )
        SELECT g.gene,
               g.chrom,
               g.n_all,
               g.n_pass,
               g.span_bp,
               round(g.variants_per_mb, 1)              AS gene_variants_per_mb,
               round(g.pct_pass, 2)                     AS gene_pct_pass,
               round(s.variants_per_mb, 1)              AS contig_variants_per_mb,
               round(cb.pct_pass_overall, 2)            AS contig_pct_pass,
               round(gs.variants_per_mb, 1)             AS genome_variants_per_mb,
               round(gb.pct_pass_overall, 2)            AS genome_pct_pass,
               cb.n_bins                                AS contig_n_bins,
               round(cb.mean_density, 1)                AS contig_bin_mean_density,
               round(cb.sd_density, 1)                  AS contig_bin_sd_density,
               round(cb.mean_pct_pass, 2)               AS contig_bin_mean_pct_pass,
               round(cb.sd_pct_pass, 2)                 AS contig_bin_sd_pct_pass,
               gb.n_bins                                AS genome_n_bins,
               round(gb.mean_density, 1)                AS genome_bin_mean_density,
               round(gb.sd_density, 1)                  AS genome_bin_sd_density,
               round(gb.mean_pct_pass, 2)               AS genome_bin_mean_pct_pass,
               round(gb.sd_pct_pass, 2)                 AS genome_bin_sd_pct_pass,
               round((g.variants_per_mb - cb.mean_density)
                     / nullif(cb.sd_density, 0), 2)     AS z_density_vs_contig,
               round((g.variants_per_mb - gb.mean_density)
                     / nullif(gb.sd_density, 0), 2)     AS z_density_vs_genome,
               round((g.pct_pass - cb.mean_pct_pass)
                     / nullif(cb.sd_pct_pass, 0), 2)    AS z_pass_vs_contig,
               round((g.pct_pass - gb.mean_pct_pass)
                     / nullif(gb.sd_pct_pass, 0), 2)    AS z_pass_vs_genome
        FROM gene g
        LEFT JOIN contig_background cb ON cb.chrom = g.bare_chrom
        LEFT JOIN contig_span       s  ON s.chrom  = g.bare_chrom
        CROSS JOIN genome_background gb
        CROSS JOIN genome_span       gs
        ORDER BY greatest(coalesce(abs(z_density_vs_contig), 0),
                          coalesce(abs(z_pass_vs_contig), 0)) DESC, g.gene
    """,
)


#: The background-comparison half of the derivation registry.
BACKGROUND_DERIVATIONS: tuple[Derivation, ...] = (PANEL_GENE_BACKGROUND,)
