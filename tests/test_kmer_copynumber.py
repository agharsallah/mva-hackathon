"""Copy number from k-mer counts: the two denominators, the resolution rule, and the band.

Counts are constructed rather than simulated, because every assertion here is about
arithmetic and bookkeeping — "is this exon deep enough to estimate on its own", "which
denominator was used", "is this below what normal looks like on this sample".
"""

import numpy as np
import pytest

from mva.kmer.copynumber import (
    DIPLOID,
    MIN_EXON_KMERS,
    Estimate,
    Region,
    below_band,
    estimate,
    null_band,
    pool_thin_exons,
    summarise,
)


def region(gene: str, label: str, level: float, kmers: int = MIN_EXON_KMERS) -> Region:
    """An exon whose k-mers all read at ``level`` — noise is not what these tests are about."""
    return Region(gene=gene, label=label, counts=np.full(kmers, level, dtype=float))


def test_a_region_at_the_flank_level_reads_as_two_copies():
    """The scale, stated once: diploid is 2.0."""
    rows = estimate([region("GENE", "GENE|1", 20.0)], {"GENE": 20.0}, genome_median=20.0)
    assert rows[0].local == pytest.approx(DIPLOID)


def test_a_region_at_half_the_flank_level_reads_as_one_copy():
    """A heterozygous deletion: one copy left, so half the reads."""
    rows = estimate([region("GENE", "GENE|1", 10.0)], {"GENE": 20.0}, genome_median=20.0)
    assert rows[0].local == pytest.approx(1.0)


def test_the_local_flank_and_the_genome_disagree_when_the_neighbourhood_is_unusual():
    """Not an error term. A region whose flank is deeper than the genome is a fact about
    that sequence, and it travels beside the number rather than being averaged away."""
    rows = estimate([region("GENE", "GENE|1", 20.0)], {"GENE": 20.0}, genome_median=10.0)
    assert rows[0].local == pytest.approx(2.0)
    assert rows[0].genome_wide == pytest.approx(4.0)
    assert rows[0].disagreement == pytest.approx(1.0)


def test_a_gene_with_too_few_flanking_kmers_has_no_local_denominator_and_says_so():
    """Reported as absent rather than filled in from the genome and left looking local."""
    rows = estimate([region("GENE", "GENE|1", 20.0)], {}, genome_median=20.0)
    assert rows[0].local is None
    assert rows[0].disagreement is None
    assert rows[0].best == rows[0].genome_wide


def test_the_local_estimate_is_the_one_to_read_where_it_exists():
    rows = estimate([region("GENE", "GENE|1", 20.0)], {"GENE": 40.0}, genome_median=20.0)
    assert rows[0].best == rows[0].local == pytest.approx(1.0)


def test_an_exon_with_enough_kmers_is_estimated_on_its_own():
    kept, report = pool_thin_exons([region("GENE", "GENE|1", 20.0, kmers=MIN_EXON_KMERS)])
    assert report["exon_scale"] == 1 and report["pooled_exons"] == 0
    assert kept[0].label == "GENE|1" and not kept[0].pooled


def test_a_thin_exon_is_pooled_into_its_gene_and_labelled_pooled():
    """GeneToCN's smallest validated unit is 5.5 kb and it called 268 gene-specific k-mers
    unreliable. A coding exon is often a few hundred bases, so the exon scale is conditional
    — it runs where it is supported and says "pooled" where it is not."""
    thin = [region("GENE", "GENE|1", 20.0, kmers=10), region("GENE", "GENE|2", 20.0, kmers=20)]
    kept, report = pool_thin_exons(thin)
    assert report == {"exon_scale": 0, "pooled_exons": 2, "pooled_genes": 1}
    assert len(kept) == 1
    assert kept[0].pooled and kept[0].label == "GENE" and kept[0].kmers == 30


def test_pooling_is_per_gene_so_two_thin_genes_do_not_become_one():
    kept, report = pool_thin_exons(
        [region("A", "A|1", 20.0, kmers=5), region("B", "B|1", 20.0, kmers=5)]
    )
    assert report["pooled_genes"] == 2
    assert sorted(row.label for row in kept) == ["A", "B"]


def test_a_gene_with_one_fat_exon_and_one_thin_one_keeps_both_at_their_own_resolution():
    kept, report = pool_thin_exons(
        [region("G", "G|1", 20.0, kmers=MIN_EXON_KMERS), region("G", "G|2", 20.0, kmers=9)]
    )
    assert report == {"exon_scale": 1, "pooled_exons": 1, "pooled_genes": 1}
    assert {row.label for row in kept} == {"G|1", "G"}


def test_the_null_band_is_measured_not_imported():
    """ "Low" depends on this sample's depth, this bait's density and this run's dispersion,
    none of which a published cut-off knows about."""
    values = list(np.linspace(1.6, 2.4, 1000))
    band = null_band(values, percentile=2.5)
    assert band.regions == 1000
    assert band.low < 1.7 < band.median < 2.3 < band.high
    assert band.contains(2.0) and not band.contains(1.0)


def test_a_region_inside_the_band_is_not_a_deletion_however_low_it_sounds():
    band = null_band(list(np.linspace(1.2, 2.8, 1000)))
    rows = [Estimate("G", "G|1", 400, False, 10.0, 1.35, 1.35)]
    assert band.contains(1.35)
    assert below_band(rows, band) == []


def test_a_region_under_the_band_is_a_deletion_candidate():
    band = null_band(list(np.linspace(1.8, 2.2, 1000)))
    rows = [Estimate("G", "G|1", 400, False, 5.0, 1.0, 1.0)]
    assert below_band(rows, band) == rows


def test_the_band_reads_the_estimate_that_should_be_read():
    """A gene with no local denominator is judged on its genome-wide one, not skipped."""
    band = null_band(list(np.linspace(1.8, 2.2, 1000)))
    rows = [Estimate("G", "G|1", 400, False, 5.0, None, 0.9)]
    assert below_band(rows, band) == rows


def test_an_empty_null_band_is_a_zero_band_rather_than_an_exception():
    band = null_band([])
    assert band.regions == 0 and band.low == band.high == 0.0


def test_infinite_values_do_not_enter_the_band():
    band = null_band([2.0, 2.0, float("inf"), float("nan"), 2.0])
    assert band.regions == 3


def test_the_summary_reports_resolution_and_both_denominators():
    band = null_band(list(np.linspace(1.8, 2.2, 1000)))
    rows = [
        Estimate("A", "A|1", 400, False, 20.0, 2.0, 2.0),
        Estimate("B", "B", 50, True, 20.0, 2.0, 4.0),
        Estimate("C", "C|1", 400, False, 5.0, None, 0.5),
    ]
    report = summarise(rows, band)
    assert report["regions"] == 3
    assert report["exon_scale"] == 2 and report["pooled"] == 1
    assert report["without_local_denominator"] == 1
    assert report["below_band"] == 1 and report["below_band_labels"] == ["C|1"]
    assert report["median_denominator_disagreement"] == pytest.approx(0.5)


def test_a_region_with_no_kmers_reads_as_zero_rather_than_dividing_by_nothing():
    empty = Region(gene="G", label="G|1", counts=np.empty(0))
    rows = estimate([empty], {"G": 20.0}, genome_median=20.0)
    assert rows[0].kmers == 0 and rows[0].local == 0.0
