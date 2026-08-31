"""The candidate waterfall: how five million records become a handful of candidate pairs.

One derivation, :data:`CANDIDATE_FUNNEL`, one row per filter stage. A funnel is the
pipeline's *argument*: every row is the claim "this filter is justified, and here is what
it cost". Read top to bottom it is the whole case-narrowing story in nine numbers.

Three conventions are load-bearing and easy to get wrong.

**The funnel has two scopes, and the boundary is real.** Stages 1–3 are measurable over
the whole callset. Stages 4–9 are measurable *only inside the eight-gene candidate panel*,
because that is the only region annotation exists for — 874 VEP-annotated alleles, nothing
genome-wide. There is no genome-wide ranking in this repository and this table must not
imply one, so ``scope`` labels every row and the first panel row carries no
``of_previous_pct``: it is not a subset of the row above it.

**The unit changes from record to allele at stage 5.** ``variants_raw`` keeps a
multi-allelic site comma-packed (one record, ``G -> A,C``) while ``panel_annotations`` is
one row per ALT. An allele count can therefore exceed the record count above it, and does.
That is a widening in the picture and a correct one; the note says so rather than hiding it.

**No contig is re-normalised here.** The panel BED is ``chr``-prefixed and the callset is
bare; ``mva.pipeline.variant.to_vcf_contig`` is the repository's single owner of that
bridge (``docs/step-0/notes/chr-prefix-bridge.md``) and a second normaliser in SQL is
exactly the failure mode that note forbids. So the interval stage reads the already-counted
``panel_variant_counts`` rather than re-joining the BED, and the annotation stages join by
``chrom``/``pos``/``ref``/ALT-membership on the bare side only.
"""

from .analysis_reference import PROTEIN_ALTERING, RARE_RECESSIVE_AF
from .derivation import SOURCE, Derivation


def het(column: str) -> str:
    """SQL predicate: ``column`` holds a genotype naming two *different* real alleles.

    Written generically rather than as ``gt IN ('0/1', '1/2')`` so the same expression
    survives a callset that emits ``0/2``, ``2/3`` or a phased ``0|1``. Phasing is
    normalised to ``/`` by the caller before this predicate sees the value, because a
    phased heterozygote is still a heterozygote.

    A homozygous call cannot be half of a compound heterozygote — that needs two
    *different* broken copies, one per parent — so equality of the two allele indices is
    the thing being excluded, along with the VCF's ``.`` for "not called".
    """
    left, right = f"str_split({column}, '/')[1]", f"str_split({column}, '/')[2]"
    return (f"len(str_split({column}, '/')) = 2 "
            f"AND {left} NOT IN ('.', '') AND {right} NOT IN ('.', '') "
            f"AND {left} <> {right}")


#: Pulls GT out of a record by reading its own FORMAT keys, never by position, and
#: flattens the phase separator. Same technique as ``panel_candidates``.
GT = ("replace(list_extract(str_split(sample_call, ':'), "
      "coalesce(list_position(str_split(format, ':'), 'GT'), 0)), '|', '/')")

#: Printed into the notes so the scope change is legible in the table itself, not only in
#: the chart that renders it.
SCOPE_CHANGE = ("SCOPE CHANGE — annotation exists only inside the 8-gene panel, so every "
                "stage below counts panel records only. ")


CANDIDATE_FUNNEL = Derivation(
    name="candidate_funnel",
    question=(
        "How does the delivered callset narrow to a candidate compound-heterozygous pair, "
        "and what does each filter cost? Nine stages in two scopes: three measurable over "
        "the whole callset, six measurable only inside the eight-gene candidate panel, "
        "which is the only region VEP annotation exists for. of_previous_pct is NULL "
        "wherever the row is not a subset of the row above it — at the genome→panel scope "
        "change — rather than reporting a ratio between two different populations."),
    depends_on=("variants_raw", "panel_variant_counts", "panel_annotations"),
    sql=f"""
        WITH raw AS (
            SELECT chrom,
                   CAST(pos AS BIGINT)  AS pos,
                   ref,
                   alt,
                   filter,
                   {GT}                 AS gt
            FROM {SOURCE}.variants_raw
        ),
        genome AS (
            SELECT count(*)                                        AS n_all,
                   count(*) FILTER (WHERE filter = 'PASS')         AS n_pass,
                   count(*) FILTER (WHERE filter = 'PASS'
                                      AND ({het('gt')}))           AS n_pass_het
            FROM raw
        ),
        -- The interval stage is already counted, per gene, by the profiler that ran
        -- bcftools over the panel BED. Reading it here is what keeps the chr-prefix
        -- bridge in one place; see the module docstring.
        intervals AS (
            SELECT CAST(sum(n_all) AS BIGINT)  AS n_all,
                   CAST(sum(n_pass) AS BIGINT) AS n_pass,
                   CAST(count(*) AS BIGINT)    AS n_genes
            FROM {SOURCE}.panel_variant_counts
        ),
        -- The panel spans 8 contigs of 25. Naming them from the annotation table lets the
        -- server skip the rest without inventing a contig-name convention.
        panel_raw AS (
            SELECT * FROM raw
            WHERE chrom IN (SELECT DISTINCT chrom FROM {SOURCE}.panel_annotations)
        ),
        -- One row per annotated allele. ALT is matched by list membership because the
        -- callset packs a multi-allelic site into one comma-joined string, and a
        -- substring test would match A against AT.
        allele AS (
            SELECT a.chrom, a.pos, a.ref, a.alt,
                   any_value(a.gene)                                    AS gene,
                   any_value(a.impact)                                  AS impact,
                   any_value(a.gnomad_af)                               AS gnomad_af,
                   bool_or(r.filter = 'PASS')                           AS any_pass,
                   bool_or(r.filter = 'PASS' AND ({het('r.gt')}))       AS pass_het
            FROM {SOURCE}.panel_annotations a
            JOIN panel_raw r
                   ON r.chrom = a.chrom
                  AND r.pos   = a.pos
                  AND r.ref   = a.ref
                  AND list_contains(str_split(r.alt, ','), a.alt)
            GROUP BY a.chrom, a.pos, a.ref, a.alt
        ),
        annotated AS (
            SELECT * FROM allele WHERE any_pass
        ),
        rare AS (
            SELECT * FROM annotated
            WHERE gnomad_af IS NULL OR gnomad_af < {RARE_RECESSIVE_AF}
        ),
        altering AS (
            SELECT * FROM rare WHERE impact IN {PROTEIN_ALTERING}
        ),
        het_altering AS (
            SELECT * FROM altering WHERE pass_het
        ),
        paired AS (
            SELECT gene, count(*) AS k
            FROM het_altering
            GROUP BY gene
            HAVING count(*) >= 2
        ),
        shape AS (
            SELECT CAST(coalesce(sum(k), 0) AS BIGINT)         AS n_alleles,
                   CAST(count(*) AS BIGINT)                    AS n_genes,
                   CAST(coalesce(sum(k * (k - 1) // 2), 0) AS BIGINT) AS n_pairs
            FROM paired
        ),
        counted AS (
            SELECT (SELECT count(*) FROM allele)        AS n_matched,
                   (SELECT count(*) FROM annotated)     AS n_annotated,
                   (SELECT count(*) FROM rare)          AS n_rare,
                   (SELECT count(*) FROM altering)      AS n_altering,
                   (SELECT count(*) FROM het_altering)  AS n_het_altering,
                   (SELECT count(*) FROM {SOURCE}.panel_annotations) AS n_declared
        ),
        stages(stage_no, stage, scope, n, nested, note) AS (
            SELECT 1,
                   'records called',
                   'genome',
                   CAST(g.n_all AS BIGINT),
                   false,
                   'COUNT(*) over the delivered callset. Every record the variant caller '
                   'emitted, before any judgement is applied.'
            FROM genome g
            UNION ALL
            SELECT 2, 'FILTER = PASS', 'genome', CAST(g.n_pass AS BIGINT), true,
                   'The caller''s own veto. A suppressed record carries a filter label '
                   '(MQ40, QD2, LowQual) saying which quality test it failed.'
            FROM genome g
            UNION ALL
            SELECT 3, 'heterozygous call', 'genome', CAST(g.n_pass_het AS BIGINT), true,
                   'GT names two different non-missing alleles (0/1, 1/2, ...), read from '
                   'each record''s own FORMAT keys. A homozygous call cannot be half of a '
                   'compound heterozygote, which needs two different broken copies.'
            FROM genome g
            UNION ALL
            SELECT 4, 'inside a panel interval', 'panel', CAST(i.n_pass AS BIGINT), false,
                   '{SCOPE_CHANGE}' ||
                   'PASS records inside the ' || i.n_genes || ' candidate-gene intervals '
                   '(BED, 20 kb padding), of ' || i.n_all || ' records there in total. '
                   'Not a subset of the row above: it counts PASS records of every '
                   'genotype, so no percentage of that row would mean anything.'
            FROM intervals i
            UNION ALL
            SELECT 5, 'VEP-annotated allele', 'panel', CAST(c.n_annotated AS BIGINT), true,
                   'Unit changes from record to allele: a multi-allelic record carries one '
                   'annotation per ALT, so this can exceed the record count above it. ' ||
                   c.n_declared || ' alleles are annotated in total; ' ||
                   (c.n_declared - c.n_matched) || ' match no callset record and ' ||
                   (c.n_matched - c.n_annotated) || ' matched only a filtered one.'
            FROM counted c
            UNION ALL
            SELECT 6, 'rare in gnomAD', 'panel', CAST(c.n_rare AS BIGINT), true,
                   'gnomAD AF below {RARE_RECESSIVE_AF} or absent entirely (absent is not '
                   'frequency zero — the database simply has no row). {RARE_RECESSIVE_AF} '
                   'is the recessive cutoff: the dominant 1e-3 would drop real carrier '
                   'alleles from a compound-heterozygous search.'
            FROM counted c
            UNION ALL
            SELECT 7, 'protein-altering', 'panel', CAST(c.n_altering AS BIGINT), true,
                   'VEP IMPACT HIGH (truncates the protein) or MODERATE (swaps an amino '
                   'acid). LOW and MODIFIER cannot change the protein sequence.'
            FROM counted c
            UNION ALL
            SELECT 8, 'in a gene carrying two or more', 'panel', CAST(s.n_alleles AS BIGINT), true,
                   'Of the row above, ' || c.n_het_altering || ' are heterozygous, and '
                   'these fall in ' || s.n_genes || ' gene(s) carrying at least two — the '
                   'compound-heterozygous shape. Shape only: phase is unproven, and with '
                   'one sample and no parents this callset cannot prove it.'
            FROM shape s, counted c
            UNION ALL
            SELECT 9, 'candidate pairs', 'panel', CAST(s.n_pairs AS BIGINT), false,
                   'Every within-gene pairing of the alleles above: k*(k-1)/2 per gene. '
                   'Unit changes from allele to pair, so a gene with more than three '
                   'alleles yields more pairs than alleles.'
            FROM shape s
        )
        SELECT stage_no,
               stage,
               scope,
               n,
               CASE WHEN nested
                    THEN round(100.0 * n / nullif(lag(n) OVER (ORDER BY stage_no), 0), 4)
               END                                      AS of_previous_pct,
               note
        FROM stages
        ORDER BY stage_no
    """,
)


#: The waterfall half of the derivation registry.
FUNNEL_DERIVATIONS: tuple[Derivation, ...] = (CANDIDATE_FUNNEL,)
