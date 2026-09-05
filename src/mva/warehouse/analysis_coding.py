"""Layer 2 — the genome-wide coding scan, as three stacked derivations.

The panel-first route (``analysis_pairs``, ``analysis_reference``) asks *"what is in these
eight genes?"*. This module asks the unbiased question the methods form rewards: *"across
every protein-coding gene, which genes carry a candidate biallelic set of rare,
protein-altering alleles, and does the panel's answer survive that comparison?"*

Three tables, each built on the one before (the first use of ``{res}``):

1. ``coding_alleles`` — every ALT allele the proband carries inside a coding interval
   (:mod:`mva.warehouse.reference_coding`), one row per (gene, allele), **every FILTER
   value kept** so step 4's suppressed-call question can be asked on the same table.
2. ``coding_candidates`` — the same rows with their VEP annotation joined on, plus the
   three flags every downstream ranking uses: rare, protein-altering, ClinVar P/LP.
3. ``gene_biallelic`` — one row per gene: how many rare protein-altering alleles it holds
   by zygosity and filter status, whether that amounts to a biallelic candidate, and where
   the gene sits in the panel-blind phenotype ranking. Ordered so the top row is the
   genome-wide answer.

The join to the coding intervals is binned: both sides carry ``pos // 100000``, the
intervals are exploded to one row per bin they touch, and the range test runs only within
a bin. Without it DuckDB would hash on ``chrom`` alone and test five million positions
against ten thousand intervals per contig.
"""

from .analysis_pairs import HET_GENOTYPES, MULTI_ALLELIC
from .analysis_reference import PROTEIN_ALTERING, RARE_RECESSIVE_AF
from .derivation import RESULT, SOURCE, Derivation

__all__ = [
    "BIN",
    "CODING_ALLELES",
    "CODING_CANDIDATES",
    "CODING_DERIVATIONS",
    "GENE_BIALLELIC",
    "HOM_ALT_GENOTYPES",
    "PLP_CLIN_SIG",
    "PROBAND_TERM_SET",
]

#: Bin width for the interval join. 100 kb: ~170 variants and ~8 coding intervals per bin.
BIN = 100_000

#: Homozygous-ALT genotypes. ``2/2`` names the second ALT of a multi-allelic record.
HOM_ALT_GENOTYPES = "('1/1', '1|1', '2/2', '2|2')"

#: Genotypes whose only ALT allele is the first one listed.
_FIRST_ALT_ONLY = "('0/1', '1/0', '0|1', '1|0', '1/1', '1|1')"

#: VEP's ``clin_sig`` is ``;``-joined lower-case terms, one per submitter classification.
#: ``pathogenic`` also matches ``likely_pathogenic`` (wanted) and
#: ``conflicting_interpretations_of_pathogenicity`` (not wanted). A site some labs call
#: benign and others pathogenic (``benign;pathogenic``) is a conflict too, spelled
#: differently — VEP lists the terms, ClinVar's own file would say Conflicting — so any
#: benign term disqualifies as well. Mirrors ``analysis_reference.PLP_PREDICATE``.
PLP_CLIN_SIG = (
    "coalesce(clin_sig, '') LIKE '%pathogenic%' "
    "AND coalesce(clin_sig, '') NOT LIKE '%conflicting%' "
    "AND coalesce(clin_sig, '') NOT LIKE '%benign%'"
)

_PLP_ON_N = PLP_CLIN_SIG.replace("clin_sig", "n.clin_sig")

#: The phenotype term set the gene ranking is read from: the child's own seven terms,
#: without the parental miscarriage term (step-3 entry 067 §5, hypothesis H002).
PROBAND_TERM_SET = "proband-only"


CODING_ALLELES = Derivation(
    name="coding_alleles",
    question=(
        "Which ALT alleles does the proband carry inside any coding interval, genome-wide? "
        "One row per (gene, allele) for every genotype that carries the allele — "
        "heterozygous, homozygous, or one of two ALTs at a multi-allelic site — with the "
        "record's FILTER, depth, allele fraction and physical phasing carried raw. Every "
        "FILTER value is kept so the suppressed-call question can be asked of this table."
    ),
    depends_on=("coding_regions", "variants_raw"),
    sql=f"""
        WITH region AS (
            SELECT gene, gene_id, chrom, start, "end",
                   unnest(range(start // {BIN}, "end" // {BIN} + 1)) AS bin
            FROM {SOURCE}.coding_regions
        ),
        raw AS (
            SELECT chrom,
                   CAST(pos AS BIGINT)          AS pos,
                   ref,
                   alt,
                   filter,
                   TRY_CAST(qual AS DOUBLE)     AS qual,
                   str_split(format, ':')       AS keys,
                   str_split(sample_call, ':')  AS vals
            FROM {SOURCE}.variants_raw
            WHERE length(chrom) <= 2
        ),
        hit AS (
            SELECT r.*, g.gene, g.gene_id
            FROM raw r
            JOIN region g
              ON g.chrom = r.chrom
             AND g.bin   = r.pos // {BIN}
             AND r.pos BETWEEN g.start AND g."end"
        ),
        call AS (
            SELECT gene, gene_id, chrom, pos, ref, alt, filter, qual,
                   list_extract(vals, coalesce(list_position(keys, 'GT'), 0))  AS gt,
                   TRY_CAST(list_extract(vals, coalesce(list_position(keys, 'DP'), 0))
                            AS BIGINT)                                         AS dp,
                   list_extract(vals, coalesce(list_position(keys, 'PGT'), 0)) AS pgt,
                   list_extract(vals, coalesce(list_position(keys, 'PID'), 0)) AS pid,
                   str_split(coalesce(
                       list_extract(vals, coalesce(list_position(keys, 'AD'), 0)), ''),
                       ',')                                                    AS ad
            FROM hit
        ),
        carrier AS (
            SELECT * FROM call
            WHERE gt IN {HET_GENOTYPES} OR gt IN {HOM_ALT_GENOTYPES}
        ),
        -- One row per ALT allele the genotype actually carries: index 1 for 0/1 and 1/1,
        -- index 2 for 2/2, both for 1/2. Joining a two-row index relation keeps the
        -- ordering explicit instead of relying on UNNEST.
        allele AS (
            SELECT c.gene, c.gene_id, c.chrom, c.pos, c.ref,
                   str_split(c.alt, ',')[i.ix]                          AS alt,
                   i.ix                                                 AS allele_ix,
                   c.gt, c.filter, c.qual, c.dp, c.pgt, c.pid,
                   CASE WHEN c.gt IN {MULTI_ALLELIC}     THEN 'multi'
                        WHEN c.gt IN {HOM_ALT_GENOTYPES} THEN 'hom'
                        ELSE 'het' END                                  AS zygosity,
                   TRY_CAST(c.ad[i.ix + 1] AS BIGINT)                    AS ad_alt,
                   list_sum([TRY_CAST(x AS BIGINT) FOR x IN c.ad])       AS ad_total
            FROM carrier c
            JOIN (SELECT 1 AS ix UNION ALL SELECT 2 AS ix) i
              ON c.gt IN {MULTI_ALLELIC}
              OR (i.ix = 1 AND c.gt IN {_FIRST_ALT_ONLY})
              OR (i.ix = 2 AND c.gt IN ('2/2', '2|2'))
            WHERE str_split(c.alt, ',')[i.ix] IS NOT NULL
        )
        SELECT gene, gene_id, chrom, pos, ref, alt, allele_ix, gt, zygosity, filter, qual, dp,
               round(ad_alt / nullif(ad_total, 0), 4) AS vaf,
               pgt, pid
        FROM allele
        ORDER BY chrom, pos, alt, gene
    """,
)


CODING_CANDIDATES = Derivation(
    name="coding_candidates",
    question=(
        "For every coding allele the proband carries: its VEP consequence, impact, gnomAD "
        "frequency and ClinVar significance beside the genotype evidence, and the three "
        "flags the ranking uses — rare (gnomAD AF absent or below the recessive cutoff), "
        "protein-altering (HIGH or MODERATE impact), ClinVar pathogenic or likely "
        "pathogenic. NULL flags mean VEP never saw the allele, not that it failed."
    ),
    depends_on=("coding_annotations",),
    sql=f"""
        SELECT a.*,
               n.rsid,
               n.consequence,
               n.impact,
               n.gnomad_af,
               n.gnomad_af_grpmax,
               n.clin_sig,
               n.chrom IS NOT NULL                                       AS annotated,
               CASE WHEN n.chrom IS NULL THEN NULL
                    ELSE (n.gnomad_af IS NULL
                          OR n.gnomad_af < {RARE_RECESSIVE_AF}) END       AS is_rare_recessive,
               CASE WHEN n.chrom IS NULL THEN NULL
                    ELSE n.impact IN {PROTEIN_ALTERING} END               AS is_protein_altering,
               CASE WHEN n.chrom IS NULL THEN NULL
                    ELSE n.gnomad_af IS NULL END                         AS is_novel,
               CASE WHEN n.chrom IS NULL THEN NULL
                    ELSE ({_PLP_ON_N}) END                               AS is_clinvar_plp
        FROM {RESULT}.coding_alleles a
        LEFT JOIN {SOURCE}.coding_annotations n
               ON n.chrom = a.chrom
              AND n.pos   = a.pos
              AND n.ref   = a.ref
              AND n.alt   = a.alt
        ORDER BY a.chrom, a.pos, a.alt, a.gene
    """,
)


GENE_BIALLELIC = Derivation(
    name="gene_biallelic",
    question=(
        "Which genes carry a candidate biallelic set — at least two rare protein-altering "
        "alleles in heterozygous PASS calls (or two ALTs at one multi-allelic site), or one "
        "in a homozygous PASS call — and where does each such gene rank in the phenotype "
        "ranking that never read the callset? Non-PASS alleles are counted separately so a "
        "gene one suppressed call short of biallelic is visible rather than dropped."
    ),
    depends_on=("hpo_gene_scores",),
    sql=f"""
        WITH cand AS (
            SELECT * FROM {RESULT}.coding_candidates
            WHERE is_rare_recessive AND is_protein_altering
        ),
        per_gene AS (
            SELECT gene, gene_id, chrom,
                   count(*) FILTER (WHERE filter = 'PASS' AND zygosity = 'het')   AS n_het_pass,
                   count(*) FILTER (WHERE filter = 'PASS' AND zygosity = 'multi') AS n_multi_pass,
                   count(*) FILTER (WHERE filter = 'PASS' AND zygosity = 'hom')   AS n_hom_pass,
                   count(*) FILTER (WHERE filter <> 'PASS')                       AS n_nonpass,
                   count(*) FILTER (WHERE filter = 'PASS' AND impact = 'HIGH')    AS n_lof_pass,
                   count(*) FILTER (WHERE filter = 'PASS' AND is_clinvar_plp)     AS n_plp_pass,
                   count(*) FILTER (WHERE filter = 'PASS' AND is_novel)           AS n_novel_pass,
                   min(gnomad_af)                                                 AS min_gnomad_af,
                   string_agg(consequence
                              || CASE WHEN filter = 'PASS' THEN '' ELSE '(' || filter || ')' END,
                              ';' ORDER BY pos, alt)                              AS consequences
            FROM cand
            GROUP BY gene, gene_id, chrom
        ),
        pheno AS (
            SELECT gene_symbol, rank AS phenotype_rank, score AS phenotype_score
            FROM {SOURCE}.hpo_gene_scores
            WHERE term_set = '{PROBAND_TERM_SET}'
        )
        SELECT p.*,
               (p.n_het_pass + p.n_multi_pass >= 2
                OR p.n_hom_pass >= 1)                              AS biallelic_pass,
               (p.n_het_pass + p.n_multi_pass + p.n_nonpass >= 2
                OR p.n_hom_pass >= 1)                              AS biallelic_with_rescue,
               h.phenotype_rank,
               h.phenotype_score
        FROM per_gene p
        LEFT JOIN pheno h ON h.gene_symbol = p.gene
        ORDER BY biallelic_pass DESC, p.n_plp_pass DESC, p.n_lof_pass DESC,
                 h.phenotype_rank NULLS LAST, p.gene
    """,
)


#: The layer-2 third of the registry, in the order it must run.
CODING_DERIVATIONS: tuple[Derivation, ...] = (CODING_ALLELES, CODING_CANDIDATES, GENE_BIALLELIC)
