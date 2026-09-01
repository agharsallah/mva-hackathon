"""The second wave of observations for ``qc_observed_expected``.

:mod:`mva.warehouse.analysis_reference` owns the derivation; this module owns the SQL
fragments that were added to it after the first twelve comparisons, so the two can be
extended independently. Both are spliced into the one derivation — a norm and its
observation have to meet inside a single statement for the verdict to be a join rather
than a second table someone has to line up by hand.

Three conventions carry over and one is new.

**An observation is computed whether or not a norm exists for it.** The derivation
``JOIN``s observations to ``warehouse.qc_norms``, so a metric we can measure but cannot
cite lands in no row at all. That is deliberate: the measurement is here, ready, and the
table stays silent until a citable range is added to ``ressources/reference/qc_norms.tsv``.
Nothing is ever graded against an invented band.

**``IDD`` and ``SN`` count different things.** ``SN``'s *number of indels* counts indel
**records**; the ``IDD`` histogram counts indel **alleles** and therefore totals higher on
a callset with multi-allelic sites. The 1–2 bp share is a fraction *of the IDD histogram*,
computed from IDD's own total, never against the ``SN`` figure.

**A ``1/2`` call is heterozygous.** ``bcftools stats`` reports it as a multi-allelic site
and ``filter_gt_counts`` keeps it in its own bucket, so the per-genome heterozygote count
is ``0/1 + 1/2``, not ``0/1`` alone. The existing het/hom *ratio* rows deliberately use
``0/1`` only, matching how the ratio is defined in the literature they cite; the new count
row is a count of heterozygous calls and includes both.

**dbSNP membership is measured twice, on purpose.** The published 99.2% is a per-genome
membership rate for a *finished* callset. Ours is measured over every delivered record —
including the ones the caller itself vetoed. Restricting to ``PASS`` is the honest
comparison, and the difference between the two numbers is itself the diagnostic: it says
how much of the shortfall is filter noise and how much is real novelty.
"""

from .derivation import SOURCE

#: Extra CTEs, spliced immediately before the ``observed`` CTE in ``QC_OBSERVED_EXPECTED``.
#: Every one ends with a comma because it is inserted into the middle of a ``WITH`` list.
EXTRA_CTES = f"""
        -- The indel *length* histogram. `abs(len) <= 2` is one bucket in each direction:
        -- a 1 bp or 2 bp insertion and a 1 bp or 2 bp deletion all count. Its own total is
        -- the denominator — see the module docstring on why SN's indel count is not.
        idd_short AS (
            SELECT sum(n)                                        AS total,
                   sum(n) FILTER (WHERE abs(len) <= 2)           AS short
            FROM (
                SELECT CAST(split_part(line, chr(9), 3) AS INTEGER) AS len,
                       CAST(split_part(line, chr(9), 4) AS DOUBLE)  AS n
                FROM {SOURCE}.stats_summary
                WHERE line LIKE 'IDD' || chr(9) || '%'
            )
        ),
        -- PASS-only dbSNP membership, twice: over every PASS record, and over PASS
        -- **biallelic SNVs** alone. Two published figures exist and they describe
        -- different populations — one counts all small variants, the other counts SNPs —
        -- so each gets the observation that actually matches it. `length(alt) = 1` also
        -- rejects a comma-packed multi-allelic ALT, which is what makes it biallelic.
        -- One pass over the raw layer, not two.
        dbsnp_pass AS (
            SELECT 100.0 * count(*) FILTER (WHERE id <> '.')
                   / nullif(count(*), 0)                                    AS pct,
                   100.0 * count(*) FILTER (WHERE id <> '.'
                                            AND length(ref) = 1
                                            AND length(alt) = 1)
                   / nullif(count(*) FILTER (WHERE length(ref) = 1
                                             AND length(alt) = 1), 0)       AS pct_snv
            FROM {SOURCE}.variants_raw
            WHERE filter = 'PASS'
        ),
"""

#: Extra ``observed`` rows, spliced after the last existing ``UNION ALL`` block. Each is
#: an observation only — it surfaces as a table row exactly when ``qc_norms`` carries a
#: matching ``metric``, and is silently absent otherwise.
EXTRA_OBSERVED = """
            UNION ALL SELECT 'snv_to_indel_ratio',
                   'SNVs per indel',
                   (SELECT value FROM sn WHERE metric = 'number of SNPs')
                   / nullif((SELECT value FROM sn WHERE metric = 'number of indels'), 0),
                   'stats_summary SN (number of SNPs over number of indels)'
            UNION ALL SELECT 'het_count_per_genome',
                   'Heterozygous calls',
                   (SELECT het FROM gt) + coalesce(
                       (SELECT value FROM sn WHERE metric = 'number of multiallelic sites'),
                       0),
                   'filter_gt_counts 0/1 plus stats_summary SN multiallelic sites (a 1/2 call is heterozygous)'
            UNION ALL SELECT 'multiallelic_site_fraction',
                   'Multiallelic (1/2) sites as a share of records',
                   100.0 * (SELECT value FROM sn WHERE metric = 'number of multiallelic sites')
                   / nullif((SELECT value FROM sn WHERE metric = 'number of records'), 0),
                   'stats_summary SN (multiallelic sites over records)'
            UNION ALL SELECT 'indel_length_1_2bp_share',
                   'Indels 1-2 bp long',
                   100.0 * (SELECT short FROM idd_short)
                   / nullif((SELECT total FROM idd_short), 0),
                   'stats_summary IDD (|length| <= 2 over the whole histogram)'
            UNION ALL SELECT 'dbsnp_membership_rate_pass_only',
                   'Records carrying a dbSNP rsID, PASS only',
                   (SELECT pct FROM dbsnp_pass),
                   'variants_raw (id <> ''.'' among filter = ''PASS'')'
            UNION ALL SELECT 'dbsnp_membership_rate_pass_snv',
                   'Biallelic SNVs carrying a dbSNP rsID, PASS only',
                   (SELECT pct_snv FROM dbsnp_pass),
                   'variants_raw (id <> ''.'' among filter = ''PASS'' with one-base REF and ALT)'
"""
