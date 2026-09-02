"""The karyogram derivation: heterozygous allele balance at 1 Mb resolution.

``results.allele_balance_flags`` averages every heterozygous call on a chromosome into one
number. That is the right grain for "is a whole chromosome present in the wrong number of
copies", and the wrong grain for mosaic variegated aneuploidy, where the event can be a
segment rather than a whole contig and is carried by only a fraction of the cells. One
shifted arm inside 250 Mb of balanced sequence disappears into the chromosome mean.

This module re-asks the same question per megabase.

**What the number means.** A heterozygous call is a position where the two inherited
copies differ. On two intact copies the sequencer should see the variant allele in about
half the reads, so the **B-allele fraction** (BAF — here the variant allele fraction of a
heterozygous call, ``alt_reads / (ref_reads + alt_reads)``) sits at ~0.5. Add a third copy
in some cells and the alleles stop being equally represented, so the bin's mean BAF drifts
off 0.5 and its mean read depth rises; lose a copy and it drifts the other way and the
depth falls. Both traces scale with the *fraction of cells* carrying the event, which is
why a low-fraction mosaic can leave no trace at all in a bulk callset.

**Where the floor is.** This reads the VCF, so it can only see what the caller wrote down:
one genotype and one allele-depth pair per site, already thresholded. That is a coarser
instrument than the reads themselves. A flat map here is therefore an upper bound on the
mosaic fraction at this resolution, never a proof of absence — the read-level path is the
lower floor.

Two conventions match the rest of the registry:

* **Only the ingest schema is read.** The input is ``variants_raw``, the lossless all-text
  layer, not the per-chromosome result table.
* **FORMAT is parsed by key, never by position.** ``GT:AD:DP`` is a convention, not a
  guarantee; a record may order its keys any way it likes, so the sample's values are
  located with ``list_position`` on the record's own FORMAT keys.
"""

from .derivation import SOURCE, Derivation

#: One bin is one megabase. Same divisor as ``variant_density_bins``, so the karyogram and
#: the density map share an x axis and a row can be joined bin-for-bin.
BIN_BP = 1_000_000

#: Below this many heterozygous calls a bin's mean is noise, not a measurement. The API
#: and the chart carry the flag rather than dropping the row — an empty bin is itself
#: information (a centromere, an acrocentric arm), and hiding it would leave a silent gap.
LOW_CONFIDENCE_N_HET = 20

#: Only unphased heterozygous calls. A ``0|1`` would be the same biology, but this callset
#: is single-sample and unphased, so admitting the phased spelling would widen the
#: predicate without widening the data. The test asserts the exclusion is deliberate.
HET_GT = "'0/1'"


BAF_BINS = Derivation(
    name="baf_bins",
    question=(
        "At 1 Mb resolution, does the B-allele fraction of heterozygous PASS calls stay "
        "at 0.5 and the read depth stay flat, or does any segment drift the way a mosaic "
        "gain or loss would? Per (chrom, mb): the count of heterozygous calls, their mean "
        "and median BAF, its spread, the share sitting inside 0.40-0.60, and mean depth. "
        "GT and AD are located by reading each record's own FORMAT keys, never by "
        "position; a record whose AD is missing, multi-allelic or unparsable is skipped "
        "rather than guessed at."
    ),
    depends_on=("variants_raw",),
    # `variants_raw` is five million all-text rows with no index, so this is a whole-genome
    # scan — the same cost `variant_density_bins` pays, and the same reason it is paid here
    # at derive time instead of inside an HTTP request.
    #
    # `//` is integer division; DuckDB's `/` is float division and would give one group per
    # position rather than one per megabase.
    sql=f"""
        WITH parsed AS (
            SELECT chrom,
                   CAST(pos AS BIGINT) // {BIN_BP}   AS mb,
                   str_split(format, ':')            AS keys,
                   str_split(sample_call, ':')       AS vals
            FROM {SOURCE}.variants_raw
            WHERE filter = 'PASS'
              AND length(chrom) <= 2
        ),
        called AS (
            SELECT chrom, mb,
                   list_extract(vals, coalesce(list_position(keys, 'GT'), 0))  AS gt,
                   TRY_CAST(list_extract(vals, coalesce(list_position(keys, 'DP'), 0))
                            AS BIGINT)                                        AS dp,
                   str_split(coalesce(
                       list_extract(vals, coalesce(list_position(keys, 'AD'), 0)), ''),
                       ',')                                                   AS ad
            FROM parsed
        ),
        -- Exactly two allele depths means one unambiguous ALT to attribute reads to. A
        -- 1/2 site carries three and has no single alternate, so it has no BAF; the same
        -- convention `panel_candidates` and `mva.viz.genotype` apply.
        het AS (
            SELECT chrom, mb, dp,
                   TRY_CAST(ad[1] AS BIGINT)  AS ad_ref,
                   TRY_CAST(ad[2] AS BIGINT)  AS ad_alt
            FROM called
            WHERE gt = {HET_GT} AND len(ad) = 2
        ),
        -- Depth for the bin is the record's own DP where the caller wrote one, and the
        -- two allele depths otherwise. Never a guess: a record with neither is dropped by
        -- the vaf test above it.
        scored AS (
            SELECT chrom, mb,
                   ad_alt / CAST(ad_ref + ad_alt AS DOUBLE)  AS vaf,
                   coalesce(dp, ad_ref + ad_alt)             AS depth
            FROM het
            WHERE ad_ref IS NOT NULL AND ad_alt IS NOT NULL
              AND ad_ref + ad_alt > 0
        )
        SELECT chrom,
               mb,
               count(*)                                          AS n_het,
               round(avg(vaf), 4)                                AS mean_vaf,
               round(median(vaf), 4)                             AS median_vaf,
               round(stddev_samp(vaf), 4)                        AS sd_vaf,
               round(avg(vaf) - 0.5, 4)                          AS vaf_deviation,
               round(100.0 * count(*) FILTER (WHERE vaf BETWEEN 0.40 AND 0.60)
                     / count(*), 1)                              AS pct_in_0_40_0_60,
               round(avg(depth), 1)                              AS mean_dp,
               count(*) < {LOW_CONFIDENCE_N_HET}                 AS low_confidence
        FROM scored
        GROUP BY chrom, mb
        ORDER BY chrom, mb
    """,
)


#: The karyogram half of the derivation registry.
KARYOGRAM_DERIVATIONS: tuple[Derivation, ...] = (BAF_BINS,)
