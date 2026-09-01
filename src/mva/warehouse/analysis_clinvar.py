"""The ClinVar presence cross-check: is a site somebody already called pathogenic in ours?

The other reference joins go *outward* — take an allele the callset has and ask what the
world knows about it. This one goes **inward**: take every site the world has already
classified pathogenic or likely pathogenic (P/LP) inside the candidate panel and ask
whether the proband's callset contains it at all.

Both answers are results.

* A P/LP site called **heterozygous and PASS** is a direct lead: a clinical lab has
  already argued this exact allele causes disease, and the child carries one copy of it.
* A P/LP site that is **absent** is an informative negative. ClinVar holds ~84 P/LP
  records in BUB1B; if the callset carries none of them, the case is not a re-run of a
  previously reported family, and the report should say so instead of leaving the
  question open.

Three properties of the data decide the SQL.

**ClinVar is not a callset.** Three rows in the committed extract carry ``alt = '.'`` and
the longest ``ref`` is 7,027 characters — placeholders and large reference alleles that no
VCF ALT string can equal. Those rows are marked ``comparable = false`` and their
``present`` is **NULL**, not ``false``: an uncomparable row is not an absent one.

**The match is exact-string, so presence is a lower bound.** Neither side is
left-aligned or trimmed, so the same insertion spelled ``T -> TA`` here and ``TA -> TAA``
there does not join. For SNVs this is exact; for indels a real match can be missed. The
number this table produces is therefore a **floor** on presence, never a ceiling, and
every consumer says so.

**A record listing an ALT is not the same as a genotype carrying it.** ``variants_raw``
keeps a multi-allelic site comma-packed (``G -> A,C`` in one row), so the ClinVar allele is
found by *list membership*, and its position in that list is its allele index. A ``0/1``
genotype on a ``G -> A,C`` record carries ``A`` and not ``C``. ``present`` says the callset
has a record for the allele; ``carries_alt`` says the genotype actually contains it. They
differ, and conflating them would invent a carrier.
"""

from .analysis_reference import PLP_PREDICATE
from .derivation import SOURCE, Derivation

#: ClinVar's review status, in plain words, is an *assertion-quality* tier, not a
#: confidence in the classification. The gold-star mapping is NCBI's own
#: (https://www.ncbi.nlm.nih.gov/clinvar/docs/review_status/); it is written here rather
#: than in the browser so the number is a column with lineage.
REVIEW_STARS = """
    CASE clnrevstat
        WHEN 'practice_guideline'                                        THEN 4
        WHEN 'reviewed_by_expert_panel'                                  THEN 3
        WHEN 'criteria_provided,_multiple_submitters,_no_conflicts'      THEN 2
        WHEN 'criteria_provided,_single_submitter'                       THEN 1
        WHEN 'criteria_provided,_conflicting_classifications'            THEN 1
        WHEN 'no_assertion_criteria_provided'                            THEN 0
        WHEN 'no_classification_provided'                                THEN 0
    END
"""

#: A row ClinVar states as an alternate allele a VCF could also state. ``.`` is ClinVar's
#: "no alternate given" placeholder and matches nothing by construction.
COMPARABLE = "ref IS NOT NULL AND alt IS NOT NULL AND alt <> '.'"


CLINVAR_PRESENCE = Derivation(
    name="clinvar_presence",
    question=(
        "For every ClinVar pathogenic / likely-pathogenic site inside the candidate "
        "panel: is that exact allele present in this callset, and if so at what genotype, "
        "FILTER and read fraction? One row per P/LP ClinVar record in a panel gene, "
        "present or not — the absences are the point as much as the hits. Matching is "
        "exact (chrom, pos, ref) plus ALT list membership, with no left-alignment on "
        "either side, so `present` is a LOWER BOUND: an indel spelled differently in the "
        "two sources will read as absent. A row ClinVar gives no alternate allele for "
        "(alt = '.') is `comparable = false` and its `present` is NULL, never false."),
    depends_on=("mva_panel_grch38", "clinvar_panel", "variants_raw"),
    sql=f"""
        WITH panel AS (
            -- The panel BED owns "which genes are the panel". Its 20 kb padding pulls
            -- ~10 flanking genes into the ClinVar extract; naming the genes from the BED
            -- rather than listing them keeps this derivation case-agnostic and keeps the
            -- flanking rows out.
            SELECT DISTINCT name AS gene FROM {SOURCE}.mva_panel_grch38
        ),
        plp AS (
            SELECT c.gene,
                   c.chrom,
                   c.pos,
                   c.ref,
                   c.alt,
                   c.rsid,
                   c.variation_id,
                   c.clnsig,
                   c.clnrevstat,
                   c.condition,
                   ({REVIEW_STARS})     AS review_stars,
                   ({COMPARABLE})       AS comparable
            -- `panel` carries only `gene`, so every other bare column below is
            -- unambiguously ClinVar's and the shared predicates need no rewriting.
            FROM {SOURCE}.clinvar_panel c
            JOIN panel p ON p.gene = c.gene
            WHERE {PLP_PREDICATE}
        ),
        raw AS (
            -- ClinVar contigs are bare and so are the callset's, so no prefix bridge is
            -- needed here. The contig list is named from `plp` so the server skips the
            -- other 17 contigs rather than reading and discarding them.
            SELECT chrom,
                   CAST(pos AS BIGINT)          AS pos,
                   ref,
                   alt,
                   TRY_CAST(qual AS DOUBLE)     AS qual,
                   filter,
                   str_split(format, ':')       AS keys,
                   str_split(sample_call, ':')  AS vals
            FROM {SOURCE}.variants_raw
            WHERE chrom IN (SELECT DISTINCT chrom FROM plp)
        ),
        call AS (
            -- Every FORMAT field is located by name off the record's own keys. The
            -- callset carries at least GT:AD:DP:GQ:PL, but a record ordered differently
            -- would otherwise hand back the depth as the genotype.
            SELECT chrom, pos, ref, alt, qual, filter,
                   list_extract(vals, coalesce(list_position(keys, 'GT'), 0))  AS gt,
                   TRY_CAST(list_extract(vals, coalesce(list_position(keys, 'DP'), 0))
                            AS BIGINT)                                         AS dp,
                   str_split(coalesce(
                       list_extract(vals, coalesce(list_position(keys, 'AD'), 0)), ''),
                       ',')                                                    AS ad
            FROM raw
        ),
        hit AS (
            SELECT p.*,
                   d.qual                                             AS call_qual,
                   d.filter                                           AS call_filter,
                   d.gt,
                   d.dp,
                   d.chrom IS NOT NULL                                AS matched,
                   -- Which ALT of a comma-packed record this is. 1 on a biallelic site.
                   list_position(str_split(d.alt, ','), p.alt)        AS allele_ix,
                   -- An unmatched row has no AD list at all; an empty one keeps the
                   -- arithmetic below total instead of evaluating over NULL.
                   coalesce(d.ad, []::VARCHAR[])                      AS ad
            FROM plp p
            LEFT JOIN call d
                   ON p.comparable
                  AND d.chrom = p.chrom
                  AND d.pos   = p.pos
                  AND d.ref   = p.ref
                  AND list_contains(str_split(d.alt, ','), p.alt)
        ),
        -- GT is split on both separators: an unphased call writes `0/1` and a phased one
        -- `0|1`, and a caller may emit either for the same evidence.
        genotype AS (
            SELECT *,
                   list_filter(str_split_regex(coalesce(gt, ''), '[/|]'),
                               x -> x <> '.' AND x <> '')             AS alleles
            FROM hit
        )
        SELECT gene,
               chrom,
               pos,
               ref,
               alt,
               rsid,
               variation_id,
               clnsig,
               clnrevstat,
               review_stars,
               condition,
               comparable,
               -- NULL, not false, wherever the row could never have matched.
               CASE WHEN comparable THEN matched END                  AS present,
               gt,
               call_filter                                            AS filter,
               call_qual                                              AS qual,
               dp,
               allele_ix,
               round(TRY_CAST(ad[allele_ix + 1] AS BIGINT)
                     / nullif(list_sum([TRY_CAST(x AS BIGINT) FOR x IN ad]), 0),
                     4)                                               AS vaf,
               -- The record lists the allele; does the genotype actually contain it?
               CASE WHEN NOT matched THEN NULL
                    ELSE list_contains(alleles, CAST(allele_ix AS VARCHAR))
               END                                                    AS carries_alt,
               -- Heterozygous *for this allele*: the genotype contains it and is not two
               -- copies of it. `1/2` is het for both of its alleles.
               CASE WHEN NOT matched THEN NULL
                    ELSE list_contains(alleles, CAST(allele_ix AS VARCHAR))
                         AND len(list_distinct(alleles)) > 1
               END                                                    AS is_het
        FROM genotype
        ORDER BY gene, present DESC NULLS LAST, pos, alt
    """,
)


#: The ClinVar-presence half of the derivation registry.
CLINVAR_DERIVATIONS: tuple[Derivation, ...] = (CLINVAR_PRESENCE,)
