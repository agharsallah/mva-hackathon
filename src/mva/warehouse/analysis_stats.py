"""Derivations over the ``bcftools stats`` sections :mod:`mva.warehouse.analysis` leaves raw.

``warehouse.stats_summary`` is the delivered ``vcf_stats_summary.txt`` loaded verbatim:
one row per line, ``line_no`` plus ``line``, the section code in tab-separated column 1.
It is a text blob with lineage, not a table — every typed number the app shows has to be
parsed out of it by a derivation, so the chart reads a column instead of a regex.

**The census, measured, not assumed.** The delivered file holds **200 lines and seven
section codes**, and nothing else — no ``#`` header comments, no other section::

    SELECT split_part(line, chr(9), 1) AS code, count(*)
    FROM pg.warehouse.stats_summary GROUP BY code ORDER BY 2 DESC
    -- IDD 120 · DP 55 · ST 12 · SN 9 · AF 2 · SiS 1 · TSTV 1

Five of the seven were already parsed in :mod:`mva.warehouse.analysis`: ``SN`` →
``stats_sn``, ``TSTV`` → ``stats_tstv``, ``DP`` → ``stats_dp``, ``ST`` → ``stats_st``,
``IDD`` → ``stats_idd``. This module claims the sixth, ``AF``. The seventh, ``SiS``, gets
no table of its own — see below.

**Sections that are absent, and therefore not derived.** ``QUAL`` (the call-quality
histogram), ``HWE``, ``PSC``/``PSI`` (per-sample counters), ``ID``, ``FS``, ``ICS`` and
``GCsAF`` appear in a full ``bcftools stats`` run and appear **nowhere** in this file. The
publisher shipped a reduced stats file; there is no QUAL distribution to serve, and the
per-record QUAL that *is* available comes from ``variants_raw`` via
``variant_density_bins`` (``mean_qual``, ``low_qual_n`` per megabase) instead.

**``SiS`` is not a second table, because it is the same row.** ``bcftools`` prints the
singleton counters twice: once as ``SiS`` keyed by allele count, and again as the first
``AF`` bin keyed by frequency. In the delivered file the two lines carry byte-identical
counters (2,536,505 SNPs · 1,665,690 ts · 870,815 tv · 644,292 indels), so a ``stats_sis``
table would be one duplicated row. The information ``SiS`` adds is its *key*: the bin is
``AC = 1``, which is what licenses the zygosity reading below.

**Why the ``AF`` section is a zygosity split and not a frequency spectrum.** AF here is
computed from the record's own ``AC``/``AN``, and this callset has **one sample**, so
``AN = 2`` everywhere and ``AC`` can only be 1 or 2. Two bins, therefore, and they mean
*heterozygous* and *homozygous alternate* — not "rare in the population" and "common in
the population". Reading them as population frequency is the exact error
``ideation/data-findings.md`` §2.5 warns about. The identity was checked against the
independent genotype counter, and it is exact::

    AF bin 0.00 alleles = 2,536,505 + 644,292 = 3,180,797
    genotype counts     = 3,047,077 (0/1) + 2 x 66,860 (1/2) = 3,180,797
    AF bin 0.99 alleles = 1,552,121 + 346,146 = 1,898,267
    genotype counts     = 1,898,267 (1/1)

The label is still emitted conditionally: :data:`STATS_AF` reads the ``SN`` sample count
and writes ``zygosity = NULL`` on anything but a single-sample callset, so the reading
cannot silently outlive the assumption that produces it.
"""

from .derivation import SOURCE, Derivation

#: Columns of an ``AF`` line, 1-based, as ``bcftools stats`` documents them in its own
#: header comment: ``AF``, id, allele frequency, SNPs, transitions, transversions, indels,
#: repeat-consistent, repeat-inconsistent, not applicable. The last three are indel-repeat
#: annotation, which needs ``bcftools stats -f <fasta>``; that flag was not used, so all
#: three collapse to ``0 / 0 / <every indel>`` and none of them is derived.
AF_FREQUENCY, AF_SNPS, AF_TS, AF_TV, AF_INDELS = 3, 4, 5, 6, 7

#: The bin boundary that separates the two single-sample bins. ``bcftools`` emits the
#: ``AC = 1`` bin at ``0.000000`` and the ``AC = AN`` bin at ``0.990000``; anything below
#: this is the singleton bin. Not 0.5: the singleton bin is *labelled* 0, not 0.5, because
#: ``bcftools`` reuses the singleton row as the first frequency bin.
SINGLETON_BIN_MAX = 0.5


def _field(index: int) -> str:
    """One tab-separated field of ``line``, 1-based, the way every stats derivation reads."""
    return f"split_part(line, chr(9), {index})"


STATS_AF = Derivation(
    name="stats_af",
    question=(
        "How does the callset split between heterozygous and homozygous-alternate "
        "alleles, and does each half pass the transition/transversion sanity check on "
        "its own? Parsed from the bcftools stats AF section. With one sample AN is "
        "always 2, so the section's two 'allele frequency' bins are AC=1 and AC=2 — a "
        "zygosity split, NOT a population frequency: reading it as one would be the "
        "error data-findings 2.5 warns about. Ts/Tv per bin is the point of the table: "
        "heterozygous calls are where false positives concentrate, and a random error "
        "process drags Ts/Tv toward 0.5, so the two bins disagreeing is a signal the "
        "callset-wide ratio hides."
    ),
    depends_on=("stats_summary",),
    # Only the ingest schema is read, per the registry's rule — `stats_sn` is a result
    # table and may not be an input, so the sample count is re-parsed from the SN line
    # here. Same `split_part` shape as `stats_sn` itself, which is the duplication that
    # rule buys.
    sql=f"""
        WITH samples AS (
            SELECT CAST({_field(4)} AS BIGINT)                       AS n
            FROM {SOURCE}.stats_summary
            WHERE line LIKE 'SN' || chr(9) || '%number of samples:%'
        ),
        af AS (
            SELECT CAST({_field(AF_FREQUENCY)} AS DOUBLE)            AS af_bin,
                   CAST({_field(AF_SNPS)}      AS BIGINT)            AS n_snps,
                   CAST({_field(AF_TS)}        AS BIGINT)            AS n_ts,
                   CAST({_field(AF_TV)}        AS BIGINT)            AS n_tv,
                   CAST({_field(AF_INDELS)}    AS BIGINT)            AS n_indels
            FROM {SOURCE}.stats_summary
            WHERE line LIKE 'AF' || chr(9) || '%'
        )
        SELECT af_bin,
               -- Null rather than a wrong word: on a multi-sample callset these bins are
               -- real allele frequencies and neither label applies.
               CASE WHEN (SELECT n FROM samples) IS DISTINCT FROM 1 THEN NULL
                    WHEN af_bin < {SINGLETON_BIN_MAX}       THEN 'heterozygous'
                    ELSE 'homozygous alternate' END                  AS zygosity,
               n_snps,
               n_ts,
               n_tv,
               n_indels,
               n_snps + n_indels                                     AS n_alleles,
               round(n_ts / nullif(CAST(n_tv AS DOUBLE), 0), 3)      AS ts_tv,
               round(100.0 * (n_snps + n_indels)
                     / nullif(sum(n_snps + n_indels) OVER (), 0), 2) AS pct_of_alleles
        FROM af
        ORDER BY af_bin
    """,
)


#: The raw-stats half of the derivation registry.
STATS_DERIVATIONS: tuple[Derivation, ...] = (STATS_AF,)
