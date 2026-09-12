"""Iteration 2, step 2 — what the read-derived alleles say, as SQL over the loaded tables.

Three questions, one derivation each, and each one is a claim's test rather than a summary:

``it2_concordance``   do two callers that share no code with the vendor's agree with the
                      delivered callset where both call? (H022)
``it2_read_pairs``    does any gene carry a biallelic candidate in the read-derived calls,
                      and does the decoy set carry as many? (H016, H020)
``it2_sv_consensus``  which structural variants are supported by two *method classes*,
                      away from the bait's edges? (H023)

**Nothing here filters before it counts.** ``it2_read_alleles`` holds every record both
callers emitted, including ones that failed their own filters, because a row that was
never written cannot be reconsidered — and H022's concordance is a statement about what the
callers said, not about what survived a filter of ours.

**Every per-gene result carries that gene's bait density.** The off-target gate failed at
8.79 % (entry 085), and the per-gene reachability it was proxying for is the number a
"nothing found in this gene" has to be read against. Joining it here rather than leaving it
in another table is what stops an absence being quoted without it.
"""

from .derivation import RESULT, SOURCE, Derivation

__all__ = ["IT2_CONCORDANCE", "IT2_DERIVATIONS", "IT2_READ_PAIRS", "IT2_SV_CONSENSUS"]

#: Bin width for the interval join, as :mod:`mva.warehouse.analysis_coding` uses.
BIN = 100_000

#: Heterozygous genotypes, in every spelling the callers use.
HET = "('0/1', '1/0', '0|1', '1|0')"

#: Homozygous-ALT genotypes.
HOM_ALT = "('1/1', '1|1')"

#: A call within this many bases of a baited interval's boundary is a bait-edge call: the
#: coverage cliff and unpaired mates there are what a read-pair caller reads as a deletion.
#: Measured rather than assumed — 14.1 % of recovered fragments matched on one mate only
#: (entry 087), which is the empirical size of this zone.
BAIT_EDGE_BP = 1_000


IT2_CONCORDANCE = Derivation(
    name="it2_concordance",
    question=(
        "Where both a read-derived caller and the delivered callset emit a genotype at the "
        "same substitution, how often do they agree? (H022)"
    ),
    depends_on=("it2_read_alleles", "variants_raw"),
    sql=f"""
    WITH delivered AS (
        SELECT chrom,
               CAST(pos AS BIGINT) AS pos,
               ref,
               alt,
               split_part(sample_call, ':', 1) AS genotype,
               filter
        FROM {SOURCE}.variants_raw
        -- Single-base substitutions only. Normalisation is a no-op for these, so a
        -- disagreement is a disagreement about the genotype and not about the spelling;
        -- variants_raw is layer 1 and unnormalised, and indels there are not comparable
        -- to a normalised call without a left-alignment this query cannot do.
        WHERE length(ref) = 1 AND length(alt) = 1
          AND alt IN ('A', 'C', 'G', 'T')
    ),
    ours AS (
        SELECT caller, chrom, pos, ref, alt, genotype, filters
        FROM {RESULT}.it2_read_alleles
        WHERE length(ref) = 1 AND length(alt) = 1
          AND alt IN ('A', 'C', 'G', 'T')
    ),
    shared AS (
        SELECT o.caller,
               o.chrom, o.pos, o.ref, o.alt,
               o.genotype AS ours,
               d.genotype AS delivered,
               o.filters AS our_filters,
               d.filter AS delivered_filter
        FROM ours o
        JOIN delivered d
          ON o.chrom = d.chrom AND o.pos = d.pos AND o.ref = d.ref AND o.alt = d.alt
    )
    SELECT caller,
           count(*) AS co_called,
           count(*) FILTER (
               replace(replace(ours, '|', '/'), '1/0', '0/1')
               = replace(replace(delivered, '|', '/'), '1/0', '0/1')
           ) AS agreed,
           round(
               count(*) FILTER (
                   replace(replace(ours, '|', '/'), '1/0', '0/1')
                   = replace(replace(delivered, '|', '/'), '1/0', '0/1')
               ) * 1.0 / nullif(count(*), 0), 6
           ) AS concordance,
           count(*) FILTER (delivered_filter = 'PASS') AS delivered_pass,
           round(
               count(*) FILTER (
                   delivered_filter = 'PASS'
                   AND replace(replace(ours, '|', '/'), '1/0', '0/1')
                     = replace(replace(delivered, '|', '/'), '1/0', '0/1')
               ) * 1.0 / nullif(count(*) FILTER (delivered_filter = 'PASS'), 0), 6
           ) AS concordance_at_pass
    FROM shared
    GROUP BY caller
    ORDER BY caller
    """,
)


IT2_READ_PAIRS = Derivation(
    name="it2_read_pairs",
    question=(
        "Which genes carry two heterozygous or one homozygous read-derived allele, and does "
        "the decoy set carry as many per gene? (H016, H020)"
    ),
    depends_on=("it2_read_alleles", "it2_exon_depth", "it2_bait_density", "coding_regions"),
    sql=f"""
    WITH exons AS (
        SELECT chrom, start, "end", gene,
               CAST(start / {BIN} AS BIGINT) AS lo,
               CAST("end" / {BIN} AS BIGINT) AS hi
        FROM {SOURCE}.coding_regions
    ),
    exon_bins AS (
        SELECT chrom, start, "end", gene, lo + offset AS bin
        FROM exons, LATERAL (SELECT unnest(range(0, hi - lo + 1)) AS offset)
    ),
    called AS (
        SELECT caller, chrom, pos, ref, alt, genotype, filters,
               CAST(pos / {BIN} AS BIGINT) AS bin
        FROM {RESULT}.it2_read_alleles
    ),
    -- One row per (gene, allele): an allele inside a gene's coding interval, whichever
    -- caller found it. Both callers are kept so agreement is visible per allele.
    in_gene AS (
        SELECT DISTINCT e.gene, c.caller, c.chrom, c.pos, c.ref, c.alt, c.genotype, c.filters
        FROM called c
        JOIN exon_bins e
          ON c.chrom = e.chrom AND c.bin = e.bin
         AND c.pos BETWEEN e.start AND e."end"
    ),
    per_gene AS (
        SELECT gene,
               count(DISTINCT (chrom, pos, ref, alt)) AS alleles,
               count(DISTINCT (chrom, pos, ref, alt)) FILTER (genotype IN {HET}) AS het,
               count(DISTINCT (chrom, pos, ref, alt)) FILTER (genotype IN {HOM_ALT}) AS hom_alt,
               count(DISTINCT caller) AS callers
        FROM in_gene
        GROUP BY gene
    )
    SELECT d.symbol,
           d.tier,
           coalesce(p.alleles, 0) AS alleles,
           coalesce(p.het, 0) AS het,
           coalesce(p.hom_alt, 0) AS hom_alt,
           coalesce(p.callers, 0) AS callers,
           (coalesce(p.het, 0) >= 2 OR coalesce(p.hom_alt, 0) >= 1) AS biallelic,
           d.density AS bait_density,
           round(dep.mean_depth, 2) AS mean_depth
    FROM {RESULT}.it2_bait_density d
    LEFT JOIN per_gene p ON p.gene = d.symbol
    LEFT JOIN (
        SELECT symbol, avg(mean_depth) AS mean_depth
        FROM {RESULT}.it2_exon_depth
        GROUP BY symbol
    ) dep ON dep.symbol = d.symbol
    ORDER BY biallelic DESC, het DESC, d.symbol
    """,
)


IT2_SV_CONSENSUS = Derivation(
    name="it2_sv_consensus",
    question=(
        "Which structural variants are supported by two different method classes, away from "
        "the bait's edges, and how much does short-read precision allow us to trust each "
        "type? (H023)"
    ),
    depends_on=("it2_sv_calls",),
    sql=f"""
    WITH calls AS (
        SELECT * FROM {RESULT}.it2_sv_calls WHERE sv_type <> 'BND'
    ),
    -- Truvari's criteria, written out: same type and contig, both breakpoints within a
    -- slop window, and reciprocal overlap of at least half. An ad hoc distance test could
    -- be tuned after seeing the answer; this cannot.
    paired AS (
        SELECT a.caller AS caller_a, b.caller AS caller_b,
               a.method_class AS class_a, b.method_class AS class_b,
               a.chrom, a.pos, a.end_pos, a.sv_type, a.sv_len,
               a.bait_edge OR b.bait_edge AS bait_edge,
               a.precision_prior,
               a.genotype
        FROM calls a
        JOIN calls b
          ON a.chrom = b.chrom
         AND a.sv_type = b.sv_type
         AND a.method_class <> b.method_class
         AND abs(a.pos - b.pos) <= {BAIT_EDGE_BP}
         AND abs(a.end_pos - b.end_pos) <= {BAIT_EDGE_BP}
         AND (
              least(a.end_pos, b.end_pos) - greatest(a.pos, b.pos)
             ) * 1.0
             / nullif(greatest(a.end_pos - a.pos, b.end_pos - b.pos), 0) >= 0.5
    )
    SELECT sv_type,
           bait_edge,
           count(*) AS consensus_calls,
           count(DISTINCT (chrom, pos, end_pos)) AS distinct_events,
           round(min(precision_prior), 3) AS precision_prior,
           round(median(sv_len), 0) AS median_length
    FROM paired
    GROUP BY sv_type, bait_edge
    ORDER BY bait_edge, consensus_calls DESC
    """,
)


#: Registered in :data:`mva.warehouse.analysis.DERIVATIONS` so the runner, the CLI's
#: ``--only`` choices and the provenance page all pick them up without a second list.
IT2_DERIVATIONS = (IT2_CONCORDANCE, IT2_READ_PAIRS, IT2_SV_CONSENSUS)
