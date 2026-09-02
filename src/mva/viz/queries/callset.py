"""Whole-callset shape: quality, composition, coverage, and the candidate funnel.

Every function here reads a derived table, never ``variants_raw`` — see the package
docstring for why that distinction is the difference between a 4-second request and a
60-second one.
"""

from ...pipeline.variant import to_vcf_contig
from ...warehouse.settings import Postgres
from . import access


def allele_balance(settings: Postgres) -> list[dict]:
    return access.table(
        settings, "results", "allele_balance_flags", "ORDER BY abs(vaf_deviation) DESC"
    )


def contig_density(settings: Postgres) -> list[dict]:
    return access.table(settings, "results", "contig_density", "ORDER BY variants_per_mb DESC")


def density_bins(settings: Postgres, chrom: str | None = None) -> list[dict]:
    """1 Mb bins, whole genome or one chromosome. Bare contig names, as delivered."""
    where = "WHERE chrom = ?" if chrom else ""
    return access.fetch(
        settings,
        f"SELECT chrom, mb, n, pass_n, low_qual_n, mean_qual "
        f"FROM pg.results.variant_density_bins {where} ORDER BY chrom, mb",
        [to_vcf_contig(chrom)] if chrom else None,
    )


def baf_bins(settings: Postgres, chrom: str | None = None) -> list[dict]:
    """Heterozygous allele balance per 1 Mb bin, whole genome or one chromosome.

    The per-megabase counterpart of ``allele_balance``, precomputed by the ``baf_bins``
    derivation. ``low_confidence`` travels with the row so the chart can render a thin bin
    as unmeasured rather than as signal; the row is never dropped, because an empty
    stretch is itself information.
    """
    where = "WHERE chrom = ?" if chrom else ""
    return access.fetch(
        settings,
        f"SELECT chrom, mb, n_het, mean_vaf, median_vaf, sd_vaf, vaf_deviation, "
        f"pct_in_0_40_0_60, mean_dp, low_confidence "
        f"FROM pg.results.baf_bins {where} ORDER BY chrom, mb",
        [to_vcf_contig(chrom)] if chrom else None,
    )


def filters(settings: Postgres) -> list[dict]:
    return access.table(settings, "results", "filter_impact", "ORDER BY impact_rank")


def genotypes(settings: Postgres) -> list[dict]:
    return access.fetch(
        settings,
        "SELECT label, count FROM pg.warehouse.filter_gt_counts "
        "WHERE section = 'genotype counts' ORDER BY count DESC",
    )


def depth_distribution(settings: Postgres) -> list[dict]:
    return access.table(settings, "results", "stats_dp", "ORDER BY bin")


def substitutions(settings: Postgres) -> list[dict]:
    return access.table(settings, "results", "stats_st", "ORDER BY count DESC")


def indel_lengths(settings: Postgres) -> list[dict]:
    return access.table(settings, "results", "stats_idd", "ORDER BY length")


def observed_expected(settings: Postgres) -> list[dict]:
    """Each QC metric this callset can be measured against, with its published range."""
    return access.table(settings, "results", "qc_observed_expected", "ORDER BY metric")


def candidate_funnel(settings: Postgres) -> list[dict]:
    """The ranking waterfall, one row per filter stage, in stage order.

    Two scopes in one table: ``scope = 'genome'`` rows are measured over the whole
    callset, ``scope = 'panel'`` rows only inside the eight-gene candidate panel, which is
    the only region annotation exists for. ``of_previous_pct`` is **null** wherever the
    row is not a subset of the row above it — at the scope change — rather than dividing
    two different populations.
    """
    return access.table(settings, "results", "candidate_funnel", "ORDER BY stage_no")


def tstv(settings: Postgres) -> dict:
    """The transition/transversion ratio as a single object."""
    found = access.table(settings, "results", "stats_tstv")
    return found[0] if found else {"ts": None, "tv": None, "ratio": None}


def zygosity_split(settings: Postgres) -> list[dict]:
    """The bcftools ``AF`` section, parsed — two rows on a single-sample callset.

    ``zygosity`` is the reading, and it is **null** on anything but one sample, where the
    bins really are population allele frequencies. See
    :mod:`mva.warehouse.analysis_stats` for why AF here is a het/hom split.
    """
    return access.table(settings, "results", "stats_af", "ORDER BY af_bin")


def vcf_fields(settings: Postgres) -> list[dict]:
    """Every FILTER, INFO and FORMAT field the callset's own VCF header declares.

    The callset's schema documentation, written by the caller that produced it. Ordered
    so the three kinds stay grouped and stable across requests.
    """
    return access.fetch(
        settings,
        "SELECT kind, id, description FROM pg.warehouse.vcf_fields "
        "ORDER BY CASE kind WHEN 'FILTER' THEN 0 WHEN 'INFO' THEN 1 ELSE 2 END, "
        "id",
    )


def sequencing_yield(settings: Postgres) -> list[dict]:
    """What each flowcell lane contributed, estimated from the delivered FASTQ bytes.

    Estimated, not counted: ``est_reads`` and ``est_gbases`` come from a file's compressed
    size and its first read's length, because counting means decompressing 79 GB. The
    counted figures live in ``/api/reads/runs``, which reads the converted parquet store —
    the two together are what make the estimate's error measurable.
    """
    return access.table(settings, "results", "sequencing_yield", "ORDER BY lane")
