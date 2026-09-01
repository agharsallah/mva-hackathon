"""The suppressed calls inside the candidate panel: what the caller saw but did not trust.

A VCF's ``FILTER`` column is not a delete. The caller **kept** the record and wrote why it
distrusted it — ``MQ40``, ``QD2``, ``LowQual`` — so a non-PASS record is a call with a
warning label, not an absence of evidence. Genome-wide that is 271,414 records
(``ideation/data-findings.md`` §3), and the reason it matters for this case is mechanical:
``MQ40`` fires where reads map ambiguously, which is exactly the repetitive and
subtelomeric sequence a real variant can hide in. Every other derivation in this warehouse
is PASS-only by design; this pair is the one that looks at what those threw away.

Two tables, because the question has two grains.

* :data:`PANEL_SUPPRESSED` — one row **per non-PASS record** in a panel gene, with the
  genotype evidence decoded and the annotation joined. The mining surface.
* :data:`PANEL_FILTER_CENSUS` — one row per ``(gene, FILTER value)`` over **every** record
  in the panel, PASS included. The census the PASS-vs-suppressed chart stacks.

Four conventions are load-bearing.

**The FILTER value is kept verbatim, ``;``-joined and all.** GATK writes every threshold a
record tripped into one string, so ``LowQual;QD2`` is a single record that failed two
tests, not two records. Splitting it into two reason rows would make the census sum to
more records than the panel holds. The verbatim string is therefore the census key, and
the stack over a gene adds up to that gene's record count exactly.

**One row per record, so a multi-allelic ALT stays comma-packed.** ``variants_raw`` keeps
``G -> A,C`` in one row while ``panel_annotations`` is one row per ALT. Joining naively
would turn one suppressed record into two, inflating the very count this table exists to
report. The join therefore picks the record's **most severe** annotated ALT — HIGH before
MODERATE before LOW before MODIFIER, ties broken by allele so the choice is deterministic.

**Annotation is a LEFT join and may be absent.** ``mva.warehouse.annotate.alleles`` selects
panel alleles with no FILTER predicate, so VEP was in fact asked about the suppressed ones
too — but the derivation must not assume it. An unannotated record gets
``annotated = false`` and **null** for every annotation-derived field, never ``false``.

**Contigs are bare on the callset side and ``chr``-prefixed on the panel side.** The strip
is the same one :mod:`mva.warehouse.analysis_pairs` performs; the Python side of that
bridge is :mod:`mva.pipeline.variant`, and nothing here builds a contig name by hand.
"""

from .analysis_pairs import HET_GENOTYPES
from .derivation import SOURCE, Derivation

#: The panel BED with its contig converted to the callset's spelling. Both derivations
#: open with it, so the interval test and the contig pushdown cannot drift apart.
PANEL_CTE = f"""
        panel AS (
            SELECT name                         AS gene,
                   replace(chrom, 'chr', '')    AS chrom,
                   start,
                   "end"
            FROM {SOURCE}.mva_panel_grch38
        )"""

#: VEP's severity buckets as a sort key. Used only to pick one annotation for a
#: multi-allelic record; it is a tie-break, never a score.
SEVERITY = ("CASE n.impact WHEN 'HIGH' THEN 1 WHEN 'MODERATE' THEN 2 "
            "WHEN 'LOW' THEN 3 ELSE 4 END")


PANEL_SUPPRESSED = Derivation(
    name="panel_suppressed",
    question=(
        "For every record the caller suppressed inside a candidate gene: which gene, "
        "which FILTER thresholds it tripped (verbatim, so a ;-joined value is one record "
        "that failed two tests), the genotype evidence behind it, and whatever VEP "
        "annotated for it. One row per record — a multi-allelic ALT stays comma-packed "
        "and joins to its most severe annotated allele, so the row count is the "
        "suppressed-record count and not an allele count. A suppressed heterozygous call "
        "in a candidate gene is where a second allele can hide, so the table exists to be "
        "read, not to be filtered out."),
    depends_on=("mva_panel_grch38", "variants_raw", "panel_annotations"),
    sql=f"""
        WITH {PANEL_CTE},
        raw AS (
            SELECT p.gene,
                   r.chrom,
                   CAST(r.pos AS BIGINT)         AS pos,
                   r.ref,
                   r.alt,
                   TRY_CAST(r.qual AS DOUBLE)    AS qual,
                   r.filter,
                   str_split(r.format, ':')      AS keys,
                   str_split(r.sample_call, ':') AS vals
            FROM {SOURCE}.variants_raw r
            JOIN panel p
              ON r.chrom = p.chrom
             AND CAST(r.pos AS BIGINT) BETWEEN p.start AND p."end"
            -- Named separately from the join so the server skips the other contigs
            -- instead of reading them and discarding the rows.
            WHERE r.chrom IN (SELECT chrom FROM panel)
              AND r.filter <> 'PASS'
        ),
        call AS (
            -- FORMAT is self-describing: the keys travel with the record, so every field
            -- is located by name and never by position.
            SELECT gene, chrom, pos, ref, alt, qual, filter,
                   list_extract(vals, coalesce(list_position(keys, 'GT'), 0))  AS gt,
                   TRY_CAST(list_extract(vals, coalesce(list_position(keys, 'DP'), 0))
                            AS BIGINT)                                         AS dp,
                   TRY_CAST(list_extract(vals, coalesce(list_position(keys, 'GQ'), 0))
                            AS BIGINT)                                         AS gq,
                   str_split(coalesce(
                       list_extract(vals, coalesce(list_position(keys, 'AD'), 0)), ''),
                       ',')                                                    AS ad
            FROM raw
        ),
        -- Two depths means one unambiguous ALT. A 1/2 record carries three and has no
        -- single alternate to attribute reads to, so vaf is NULL there — the same
        -- convention `panel_candidates` and `mva.viz.genotype` apply.
        depths AS (
            SELECT *,
                   CASE WHEN len(ad) = 2 THEN TRY_CAST(ad[1] AS BIGINT) END AS ad_ref,
                   CASE WHEN len(ad) = 2 THEN TRY_CAST(ad[2] AS BIGINT) END AS ad_alt
            FROM call
        ),
        -- One annotation per *record*: the most severe of the ALT alleles VEP covered.
        -- Without this a comma-packed record would fan out into one row per ALT.
        best AS (
            SELECT * FROM (
                SELECT d.chrom, d.pos, d.ref,
                       d.alt                                       AS record_alt,
                       n.alt                                       AS annotated_alt,
                       n.rsid, n.consequence, n.impact,
                       n.gnomad_af, n.gnomad_af_grpmax, n.clin_sig,
                       row_number() OVER (PARTITION BY d.chrom, d.pos, d.ref, d.alt
                                          ORDER BY {SEVERITY}, n.alt) AS pick
                FROM depths d
                JOIN {SOURCE}.panel_annotations n
                  ON n.chrom = d.chrom
                 AND n.pos   = d.pos
                 AND n.ref   = d.ref
                 AND list_contains(str_split(d.alt, ','), n.alt)
            )
            WHERE pick = 1
        )
        SELECT d.gene,
               d.chrom,
               d.pos,
               d.ref,
               d.alt,
               d.qual,
               d.filter,
               d.gt,
               d.dp,
               d.gq,
               d.ad_ref,
               d.ad_alt,
               round(d.ad_alt / nullif(d.ad_ref + d.ad_alt, 0), 4)  AS vaf,
               d.gt IN {HET_GENOTYPES}                              AS is_het,
               b.annotated_alt,
               b.rsid,
               b.consequence,
               b.impact,
               b.gnomad_af,
               b.gnomad_af_grpmax,
               b.clin_sig,
               b.chrom IS NOT NULL                                  AS annotated
        FROM depths d
        LEFT JOIN best b
               ON b.chrom      = d.chrom
              AND b.pos        = d.pos
              AND b.ref        = d.ref
              AND b.record_alt = d.alt
        ORDER BY d.gene, d.pos, d.ref, d.alt
    """,
)


PANEL_FILTER_CENSUS = Derivation(
    name="panel_filter_census",
    question=(
        "Per candidate gene and per FILTER value, how many records carry it? PASS is a "
        "row like any other, so the stack over one gene adds up to that gene's whole "
        "record count and the PASS share is read off the same table as the suppressed "
        "ones. The FILTER value is verbatim: GATK packs every threshold a record tripped "
        "into one ;-joined string, so `LowQual;QD2` is one record that failed two tests "
        "and counting it once under each reason would over-count the panel."),
    depends_on=("mva_panel_grch38", "variants_raw"),
    sql=f"""
        WITH {PANEL_CTE},
        raw AS (
            SELECT p.gene, p.chrom, r.filter
            FROM {SOURCE}.variants_raw r
            JOIN panel p
              ON r.chrom = p.chrom
             AND CAST(r.pos AS BIGINT) BETWEEN p.start AND p."end"
            WHERE r.chrom IN (SELECT chrom FROM panel)
        ),
        counted AS (
            SELECT gene, chrom, filter, count(*) AS n
            FROM raw
            GROUP BY gene, chrom, filter
        )
        SELECT gene,
               chrom,
               filter,
               filter = 'PASS'                                          AS is_pass,
               n,
               -- Cast because a window SUM widens to HUGEINT, which reaches the client
               -- as a Decimal and renders as `80.0` where the row count is 80.
               CAST(sum(n) OVER (PARTITION BY gene) AS BIGINT)           AS n_gene_all,
               round(100.0 * n / sum(n) OVER (PARTITION BY gene), 2)    AS pct_of_gene
        FROM counted
        -- PASS first, then the suppressed reasons heaviest first, so a chart that keeps
        -- the arrival order stacks the same way every run.
        ORDER BY gene, is_pass DESC, n DESC, filter
    """,
)


#: The suppressed-call half of the derivation registry.
SUPPRESSED_DERIVATIONS: tuple[Derivation, ...] = (PANEL_SUPPRESSED, PANEL_FILTER_CENSUS)
