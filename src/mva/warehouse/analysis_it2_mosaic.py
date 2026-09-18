"""Iteration 2, step 8 — the callset reduced to what a mosaic model actually needs.

Entry 037 asked the karyogram question at the wrong grain. It averaged the **B-allele
fraction** (BAF — the share of reads carrying the non-reference allele at a heterozygous
call) inside each megabase, and a mosaic gain does not move that average: at cell fraction
*f* the heterozygous sites split into two bands symmetric about 0.5, so the mean stays
where it was. Its flat map is an upper bound whose limit was never measured.

These three derivations produce the inputs a test with power needs, and each is a
**sufficient statistic** rather than a summary — nothing the models need is thrown away:

``it2_mosaic_sites``    per chromosome and arm, how many heterozygous calls showed *k*
                        alternate reads out of *n*. For any likelihood that treats sites
                        as exchangeable — binomial, beta-binomial, a mixture of either —
                        the (k, n) counts carry the whole likelihood. ~20-40k rows per
                        chromosome instead of 2.8 million sites.
``it2_mosaic_depth``    per chromosome and arm, the depth histogram over **every** PASS
                        site. The negative-binomial half of the MAD-seq model needs this
                        and cannot use the table above: depth at a *heterozygous* call is
                        conditioned on that call existing, and a real monosomy has almost
                        no heterozygous calls at all.
``it2_mosaic_density``  per chromosome and arm, heterozygous calls per megabase and per
                        PASS site. Monosomy and copy-neutral loss of heterozygosity
                        **remove** heterozygous sites rather than shifting them, so the
                        count is the statistic and not a QC number.

**Why the grain is (chrom, arm) and not (chrom, position).** Two reasons, and they agree.
A mosaic event is tested per arm because one shifted arm inside 250 Mb of balanced
sequence disappears into a chromosome mean; and a table keyed by position is a table of
this child's genomic positions, which may not leave the database. Aggregating to the arm
is not a redaction applied afterwards — there is no position on these rows to withhold.
The cost is stated where it is paid: **a focal or sub-arm mosaic segment is invisible
here**, and only whole-arm and whole-chromosome events are testable.

**The parsing rules are 037's, deliberately.** ``PASS`` only; unphased ``0/1`` only; GT,
DP and AD located by reading each record's own FORMAT keys rather than by position; a
record with three allele depths has no single alternate and so has no BAF. Entry 037's
derivation is frozen iteration-1 evidence and is not edited to share code with this one —
instead the two are reconciled numerically: the heterozygous total here must equal the
2,778,844 calls ``baf_bins`` kept, and the step's methodology entry reports that check.
"""

from .analysis_karyogram import HET_GT
from .derivation import SOURCE, Derivation

__all__ = [
    "IT2_MOSAIC_DENSITY",
    "IT2_MOSAIC_DEPTH",
    "IT2_MOSAIC_DERIVATIONS",
    "IT2_MOSAIC_SITES",
]

#: One megabase, so a density here and a bin in ``baf_bins`` are the same unit.
BP_PER_MB = 1_000_000

#: The 25 canonical contigs, as 037 selected them: the delivered callset spells them bare,
#: and every name longer than two characters is an alternate haplotype or a patch.
CANONICAL = "length(chrom) <= 2"

#: The arm a call sits on, from the committed reference geometry. A call inside the
#: centromere itself is labelled ``cen`` rather than pushed to one side: pericentromeric
#: repeats are where allele balance is least trustworthy, and a row that says so can be
#: excluded by a caller, while a row silently folded into ``p`` cannot.
ARM = """
    CASE
        WHEN c.chrom IS NULL           THEN 'unplaced'
        WHEN f.pos < c.cen_start       THEN 'p'
        WHEN f.pos >= c.cen_end        THEN 'q'
        ELSE 'cen'
    END
"""

#: Every PASS record on a canonical contig, with its FORMAT fields split out by key and
#: its arm attached. Shared by all three derivations below, which is why each of them
#: counts the same denominator.
_PARSED = f"""
    WITH called AS (
        SELECT chrom,
               CAST(pos AS BIGINT)            AS pos,
               str_split(format, ':')         AS keys,
               str_split(sample_call, ':')    AS vals
        FROM {SOURCE}.variants_raw
        WHERE filter = 'PASS' AND {CANONICAL}
    ),
    fields AS (
        SELECT chrom, pos,
               list_extract(vals, coalesce(list_position(keys, 'GT'), 0))  AS gt,
               TRY_CAST(list_extract(vals, coalesce(list_position(keys, 'DP'), 0))
                        AS BIGINT)                                        AS dp,
               str_split(coalesce(
                   list_extract(vals, coalesce(list_position(keys, 'AD'), 0)), ''),
                   ',')                                                   AS ad
        FROM called
    ),
    armed AS (
        SELECT f.chrom,
               f.pos,
               f.gt,
               f.dp,
               f.ad,
               {ARM} AS arm
        FROM fields f
        LEFT JOIN {SOURCE}.cytoband_arms c ON c.chrom = f.chrom
    )
"""


IT2_MOSAIC_SITES = Derivation(
    name="it2_mosaic_sites",
    question=(
        "Per chromosome and arm, how many heterozygous PASS calls carried k alternate "
        "reads out of n total? The (k, n) counts are the sufficient statistic for every "
        "allele-balance model step 8 fits -- binomial, beta-binomial and their mixtures -- "
        "so nothing the test needs is lost, and no position survives the aggregation."
    ),
    depends_on=("variants_raw", "cytoband_arms"),
    sql=f"""
    {_PARSED},
    het AS (
        SELECT chrom, arm,
               TRY_CAST(ad[1] AS BIGINT) AS ad_ref,
               TRY_CAST(ad[2] AS BIGINT) AS ad_alt
        FROM armed
        WHERE gt = {HET_GT} AND len(ad) = 2
    )
    SELECT chrom,
           arm,
           ad_alt                AS k,
           ad_ref + ad_alt       AS n,
           count(*)              AS sites
    FROM het
    WHERE ad_ref IS NOT NULL AND ad_alt IS NOT NULL AND ad_ref + ad_alt > 0
    GROUP BY chrom, arm, k, n
    ORDER BY chrom, arm, n, k
    """,
)


IT2_MOSAIC_DEPTH = Derivation(
    name="it2_mosaic_depth",
    question=(
        "Per chromosome and arm, what is the read-depth histogram over every PASS call, "
        "heterozygous or not? A mosaic gain raises depth and a loss lowers it, and the "
        "depth at heterozygous calls alone cannot say so -- it is conditioned on the call "
        "existing, which a monosomy is precisely what removes."
    ),
    depends_on=("variants_raw", "cytoband_arms"),
    sql=f"""
    {_PARSED},
    depths AS (
        SELECT chrom, arm,
               -- The record's own DP where the caller wrote one, the two allele depths
               -- otherwise. Never a guess: a record with neither is dropped below.
               coalesce(dp,
                        TRY_CAST(ad[1] AS BIGINT) + TRY_CAST(ad[2] AS BIGINT)) AS depth
        FROM armed
    )
    SELECT chrom, arm, depth, count(*) AS sites
    FROM depths
    WHERE depth IS NOT NULL AND depth > 0
    GROUP BY chrom, arm, depth
    ORDER BY chrom, arm, depth
    """,
)


IT2_MOSAIC_DENSITY = Derivation(
    name="it2_mosaic_density",
    question=(
        "Per chromosome and arm, how many heterozygous calls are there per megabase and "
        "per PASS call? Monosomy and copy-neutral loss of heterozygosity remove "
        "heterozygous sites rather than shifting their balance, so this count is one of "
        "the five models' discriminating statistics and not a QC number."
    ),
    depends_on=("variants_raw", "cytoband_arms"),
    sql=f"""
    {_PARSED},
    flagged AS (
        SELECT chrom, arm,
               CASE WHEN gt = {HET_GT} AND len(ad) = 2 THEN 1 ELSE 0 END AS is_het
        FROM armed
    ),
    counted AS (
        SELECT chrom, arm, count(*) AS pass_sites, sum(is_het) AS het_sites
        FROM flagged
        GROUP BY chrom, arm
    ),
    -- The arm's span in the reference, so a density is per megabase of sequence rather
    -- than per row. Not mappability-corrected: an arm's callable fraction is unknown
    -- here, which is why the raw count and the per-PASS-site share travel beside it.
    spans AS (
        SELECT chrom, 'p' AS arm, cen_start AS span, acrocentric FROM {SOURCE}.cytoband_arms
        UNION ALL
        SELECT chrom, 'q', chrom_length - cen_end, acrocentric FROM {SOURCE}.cytoband_arms
        UNION ALL
        SELECT chrom, 'cen', cen_end - cen_start, acrocentric FROM {SOURCE}.cytoband_arms
    )
    SELECT c.chrom,
           c.arm,
           c.het_sites,
           c.pass_sites,
           s.span                                                      AS arm_bp,
           s.acrocentric,
           round(c.het_sites / (s.span / {BP_PER_MB}.0), 2)             AS het_per_mb,
           round(c.het_sites / CAST(c.pass_sites AS DOUBLE), 4)         AS het_share
    FROM counted c
    LEFT JOIN spans s ON s.chrom = c.chrom AND s.arm = c.arm
    ORDER BY c.chrom, c.arm
    """,
)


#: Registered in :data:`mva.warehouse.analysis.DERIVATIONS` so the runner, the CLI's
#: ``--only`` flag and the lineage edge all see them.
IT2_MOSAIC_DERIVATIONS: tuple[Derivation, ...] = (
    IT2_MOSAIC_SITES,
    IT2_MOSAIC_DEPTH,
    IT2_MOSAIC_DENSITY,
)
