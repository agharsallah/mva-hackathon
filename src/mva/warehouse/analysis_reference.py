"""Derivations that compare the delivery against the committed public reference tables.

Three questions, three tables. Each one is a *join between the patient's data and what
normal looks like*, which is the only form in which a raw count becomes a judgement:

* :data:`panel_gene_constraint` — per candidate gene, how much variation we called next to
  how much damage healthy people tolerate (gnomAD) and what labs have already classified
  there (ClinVar).
* :data:`panel_candidates` — per annotated allele, the VEP consequence next to the
  genotype evidence the callset actually carries for it.
* :data:`qc_observed_expected` — per QC metric, the measured value next to the published
  range, with a verdict.

Two conventions are load-bearing and easy to get wrong.

**Only the ingest schema is read.** A derivation may not read ``results``, because
``pg-derive`` has no ordering guarantee between derivations and a result table is not an
input. ``qc_observed_expected`` therefore re-parses ``stats_summary`` itself rather than
reading ``results.stats_sn`` / ``stats_tstv`` / ``stats_idd``. The parsing is a copy of
those three derivations' ``split_part`` expressions; the duplication buys schema
discipline and is asserted equal by a test.

**Contigs are bare on the callset side and ``chr``-prefixed on the panel side.** Staging
strips the prefix from ``gnomad_constraint`` on the way in, so gnomAD joins the callset by
gene symbol with no contig involved. ``panel_gene_constraint.chrom`` is deliberately
``chr``-prefixed, matching what ``/api/panel/genes`` already returns.
"""

from .analysis_reference_qc import EXTRA_CTES, EXTRA_OBSERVED
from .derivation import SOURCE, Derivation

#: ClinVar's germline classification is free text with ``|``- and ``/``-packed multi-values.
#: ``Pathogenic``, ``Likely_pathogenic``, ``Pathogenic/Likely_pathogenic``,
#: ``Pathogenic|Affects`` and ``Pathogenic/Likely_pathogenic/Pathogenic,_low_penetrance``
#: all share the substring ``athogenic`` — and so does
#: ``Conflicting_classifications_of_pathogenicity``, which is the opposite of an assertion
#: and is excluded. Matching the substring rather than enumerating the literals is what
#: keeps the predicate correct when NCBI adds another combined value.
PLP_PREDICATE = "clnsig LIKE '%athogenic%' AND clnsig NOT LIKE '%Conflicting%'"

#: ``Benign``, ``Likely_benign`` and ``Benign/Likely_benign``, minus the conflicting rows.
BENIGN_PREDICATE = "clnsig LIKE '%enign%' AND clnsig NOT LIKE '%Conflicting%'"

#: ``Uncertain_significance``. No combined form of it exists in the extracted subset.
VUS_PREDICATE = "clnsig LIKE '%Uncertain%'"

#: The recessive allele-frequency cutoff, from ``qc_norms.rare_af_threshold_recessive``.
#: **Not** 1e-3: that is the *dominant* threshold, and filtering a compound-heterozygous
#: search at it can drop a real allele (Pedersen 2021, PMID 34267211).
RARE_RECESSIVE_AF = "0.01"

#: VEP's own severity buckets. ``HIGH`` is truncating, ``MODERATE`` is missense-like.
PROTEIN_ALTERING = "('HIGH', 'MODERATE')"


PANEL_GENE_CONSTRAINT = Derivation(
    name="panel_gene_constraint",
    question=(
        "For each candidate gene: how much did we call, how badly do healthy people "
        "tolerate breaking it (gnomAD v4.1 constraint), and what has ClinVar already "
        "classified there? P/LP counts rows whose clnsig contains 'athogenic' and not "
        "'Conflicting' — so Pathogenic, Likely_pathogenic, Pathogenic/Likely_pathogenic "
        "and Pathogenic|… combinations count, while "
        "Conflicting_classifications_of_pathogenicity does not. A gene with no gnomAD row "
        "(the constraint file is autosomes-only) gets NULL metrics, never zero."
    ),
    depends_on=("mva_panel_grch38", "panel_variant_counts", "gnomad_constraint", "clinvar_panel"),
    sql=f"""
        WITH panel AS (
            SELECT coalesce(b.name, c.gene)     AS gene,
                   coalesce(b.chrom, c.chrom)   AS chrom,
                   c.n_all,
                   c.n_pass
            FROM {SOURCE}.mva_panel_grch38 b
            FULL OUTER JOIN {SOURCE}.panel_variant_counts c ON c.gene = b.name
        ),
        -- Gene symbol is not a key in gnomAD: six symbols carry more than one canonical
        -- protein-coding transcript. Pick the MANE Select one, then the lowest transcript
        -- id, so the choice is deterministic across runs rather than whatever the scan
        -- happened to emit first.
        one_transcript AS (
            SELECT gene, transcript, loeuf, pli, mis_z, oe_lof, lof_obs, lof_exp
            FROM (
                SELECT g.*,
                       row_number() OVER (PARTITION BY g.gene
                                          ORDER BY g.mane_select DESC NULLS LAST,
                                                   g.transcript) AS pick
                FROM {SOURCE}.gnomad_constraint g
                WHERE g.gene IS NOT NULL
            )
            WHERE pick = 1
        ),
        clinvar AS (
            SELECT gene,
                   count(*) FILTER (WHERE {PLP_PREDICATE})    AS clinvar_plp,
                   count(*) FILTER (WHERE {VUS_PREDICATE})    AS clinvar_vus,
                   count(*) FILTER (WHERE {BENIGN_PREDICATE}) AS clinvar_benign
            FROM {SOURCE}.clinvar_panel
            GROUP BY gene
        )
        SELECT p.gene,
               p.chrom,
               p.n_all,
               p.n_pass,
               g.loeuf,
               g.pli,
               g.mis_z,
               g.oe_lof,
               g.lof_obs,
               g.lof_exp,
               g.transcript                        AS gnomad_transcript,
               v.clinvar_plp,
               v.clinvar_vus,
               v.clinvar_benign
        FROM panel p
        LEFT JOIN one_transcript g ON g.gene = p.gene
        LEFT JOIN clinvar v        ON v.gene = p.gene
        ORDER BY g.loeuf NULLS LAST, p.gene
    """,
)


PANEL_CANDIDATES = Derivation(
    name="panel_candidates",
    question=(
        "For every annotated allele in the candidate panel: the VEP consequence and "
        "population frequency next to the genotype evidence the callset carries. "
        "ALT is matched by list membership — variants_raw keeps a multi-allelic site "
        "comma-packed (G -> A,C in one row) while the annotations are one row per ALT, so "
        "the join tests that the annotated allele is an element of the split list rather "
        "than a substring of the packed string, which would match A against AT. GT and DP "
        "are located by reading the record's own FORMAT keys, never by position."
    ),
    depends_on=("panel_annotations", "variants_raw"),
    sql=f"""
        WITH raw AS (
            SELECT chrom,
                   CAST(pos AS BIGINT)          AS pos,
                   ref,
                   alt,
                   TRY_CAST(qual AS DOUBLE)     AS qual,
                   filter,
                   str_split(format, ':')       AS keys,
                   str_split(sample_call, ':')  AS vals
            FROM {SOURCE}.variants_raw
            -- The panel spans 8 contigs of 25. Naming them from the annotation table keeps
            -- the derivation case-agnostic while still letting the server skip the rest.
            WHERE chrom IN (SELECT DISTINCT chrom FROM {SOURCE}.panel_annotations)
        ),
        call AS (
            SELECT chrom, pos, ref, alt, qual, filter,
                   list_extract(vals, coalesce(list_position(keys, 'GT'), 0))  AS gt,
                   TRY_CAST(list_extract(vals, coalesce(list_position(keys, 'DP'), 0))
                            AS BIGINT)                                        AS dp,
                   str_split(coalesce(
                       list_extract(vals, coalesce(list_position(keys, 'AD'), 0)), ''),
                       ',')                                                   AS ad
            FROM raw
        ),
        -- Two depths means one unambiguous ALT. A 1/2 site carries three (ref, alt1, alt2)
        -- and has no single alternate to attribute reads to, so vaf is NULL there — the
        -- same convention `mva.viz.genotype` applies at the locus endpoint.
        depths AS (
            SELECT *,
                   CASE WHEN len(ad) = 2 THEN TRY_CAST(ad[1] AS BIGINT) END AS ad_ref,
                   CASE WHEN len(ad) = 2 THEN TRY_CAST(ad[2] AS BIGINT) END AS ad_alt
            FROM call
        )
        SELECT a.chrom,
               a.pos,
               a.ref,
               a.alt,
               a.rsid,
               a.gene,
               a.consequence,
               a.impact,
               a.gnomad_af,
               a.gnomad_af_grpmax,
               a.clin_sig,
               d.qual,
               d.filter,
               d.gt,
               d.dp,
               round(d.ad_alt / nullif(d.ad_ref + d.ad_alt, 0), 4)          AS vaf,
               (a.gnomad_af IS NULL OR a.gnomad_af < {RARE_RECESSIVE_AF})   AS is_rare_recessive,
               a.impact IN {PROTEIN_ALTERING}                               AS is_protein_altering
        FROM {SOURCE}.panel_annotations a
        LEFT JOIN depths d
               ON d.chrom = a.chrom
              AND d.pos   = a.pos
              AND d.ref   = a.ref
              AND list_contains(str_split(d.alt, ','), a.alt)
        ORDER BY a.gene, a.pos, a.alt
    """,
)


QC_OBSERVED_EXPECTED = Derivation(
    name="qc_observed_expected",
    question=(
        "For every QC norm this callset can actually be measured against: the observed "
        "value, the published range, and a verdict. Only metrics with both a norm and an "
        "observation are emitted — a metric with no measurable counterpart (a coding-only "
        "Ts/Tv, an SV count, a trio de-novo count, an AF threshold) is skipped rather than "
        "guessed. Observations are re-parsed from stats_summary here rather than read from "
        "results.stats_*, because a derivation reads the ingest schema only."
    ),
    depends_on=("qc_norms", "stats_summary", "filter_gt_counts", "profile_scalars", "variants_raw"),
    sql=f"""
        WITH sn AS (
            SELECT rtrim(split_part(line, chr(9), 3), ':')      AS metric,
                   CAST(split_part(line, chr(9), 4) AS DOUBLE)  AS value
            FROM {SOURCE}.stats_summary
            WHERE line LIKE 'SN' || chr(9) || '%'
        ),
        tstv AS (
            SELECT CAST(split_part(line, chr(9), 5) AS DOUBLE)  AS ratio
            FROM {SOURCE}.stats_summary
            WHERE line LIKE 'TSTV' || chr(9) || '%'
        ),
        idd AS (
            SELECT sum(CASE WHEN CAST(split_part(line, chr(9), 3) AS INTEGER) > 0
                            THEN CAST(split_part(line, chr(9), 4) AS DOUBLE) END) AS ins,
                   sum(CASE WHEN CAST(split_part(line, chr(9), 3) AS INTEGER) < 0
                            THEN CAST(split_part(line, chr(9), 4) AS DOUBLE) END) AS del
            FROM {SOURCE}.stats_summary
            WHERE line LIKE 'IDD' || chr(9) || '%'
        ),
        gt AS (
            SELECT CAST(sum(count) FILTER (WHERE label = '0/1') AS DOUBLE) AS het,
                   CAST(sum(count) FILTER (WHERE label = '1/1') AS DOUBLE) AS hom
            FROM {SOURCE}.filter_gt_counts
            WHERE section = 'genotype counts'
        ),
        cov AS (
            SELECT TRY_CAST(max(value) AS DOUBLE) AS x
            FROM {SOURCE}.profile_scalars
            WHERE key = 'est_raw_coverage_x'
        ),
        -- The one observation that needs the callset itself: `id` is the dbSNP rsID column
        -- and `.` is the VCF's "absent". A ~21 s whole-table scan is fine here and would
        -- not be inside an HTTP request, which is why it is precomputed.
        dbsnp AS (
            SELECT 100.0 * count(*) FILTER (WHERE id <> '.')
                   / nullif(count(*), 0) AS pct
            FROM {SOURCE}.variants_raw
        ),
        {EXTRA_CTES}
        observed(metric, label, obs, observed_from) AS (
            SELECT 'tstv_genome_wide',
                   'Transition/transversion ratio',
                   (SELECT ratio FROM tstv),
                   'stats_summary TSTV'
            UNION ALL SELECT 'het_hom_ratio_eur',
                   'Heterozygous / homozygous-ALT call ratio',
                   (SELECT het / nullif(hom, 0) FROM gt),
                   'filter_gt_counts genotype counts (0/1 over 1/1)'
            UNION ALL SELECT 'het_hom_ratio_afr',
                   'Heterozygous / homozygous-ALT call ratio',
                   (SELECT het / nullif(hom, 0) FROM gt),
                   'filter_gt_counts genotype counts (0/1 over 1/1)'
            UNION ALL SELECT 'het_hom_ratio_amr',
                   'Heterozygous / homozygous-ALT call ratio',
                   (SELECT het / nullif(hom, 0) FROM gt),
                   'filter_gt_counts genotype counts (0/1 over 1/1)'
            UNION ALL SELECT 'variant_sites_per_genome',
                   'Variant records called',
                   (SELECT value FROM sn WHERE metric = 'number of records'),
                   'stats_summary SN'
            UNION ALL SELECT 'snv_per_genome',
                   'SNVs called',
                   (SELECT value FROM sn WHERE metric = 'number of SNPs'),
                   'stats_summary SN'
            UNION ALL SELECT 'snv_per_genome_30x',
                   'SNVs called',
                   (SELECT value FROM sn WHERE metric = 'number of SNPs'),
                   'stats_summary SN'
            UNION ALL SELECT 'indel_per_genome',
                   'Indels called',
                   (SELECT value FROM sn WHERE metric = 'number of indels'),
                   'stats_summary SN'
            UNION ALL SELECT 'indel_per_genome_30x',
                   'Indels called',
                   (SELECT value FROM sn WHERE metric = 'number of indels'),
                   'stats_summary SN'
            UNION ALL SELECT 'insertion_deletion_ratio',
                   'Insertions per deletion',
                   (SELECT ins / nullif(del, 0) FROM idd),
                   'stats_summary IDD (sum of positive lengths over negative)'
            UNION ALL SELECT 'dbsnp_membership_rate_per_genome',
                   'Records carrying a dbSNP rsID',
                   (SELECT pct FROM dbsnp),
                   'variants_raw (id <> ''.'')'
            UNION ALL SELECT 'mean_coverage_wgs',
                   'Raw sequencing coverage',
                   (SELECT x FROM cov),
                   'profile_scalars est_raw_coverage_x (yield-based, pre-alignment)'
            {EXTRA_OBSERVED}
        )
        SELECT o.metric,
               o.label,
               o.obs                                          AS observed,
               n.expected_low,
               n.expected_high,
               n.unit,
               CASE WHEN o.obs IS NULL              THEN 'unknown'
                    WHEN o.obs < n.expected_low     THEN 'below'
                    WHEN o.obs > n.expected_high    THEN 'above'
                    ELSE 'within' END                         AS verdict,
               n.applies_to,
               n.source,
               o.observed_from
        FROM observed o
        JOIN {SOURCE}.qc_norms n ON n.metric = o.metric
        WHERE o.obs IS NOT NULL
        ORDER BY o.metric
    """,
)


#: The reference-comparison half of the derivation registry.
REFERENCE_DERIVATIONS: tuple[Derivation, ...] = (
    PANEL_GENE_CONSTRAINT,
    PANEL_CANDIDATES,
    QC_OBSERVED_EXPECTED,
)
