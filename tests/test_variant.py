"""The variant identity seam.

The scorer matches on exact (chrom, pos, ref, alt) equality with no normalization of
the chromosome field, so the representation we submit must be pinned down here rather
than improvised at submission time.
"""
import pytest

from mva.pipeline import Variant


def test_vcf_contig_gains_chr_prefix_for_submission():
    # The proband VCF was called against a no-chr reference: its contigs are "15",
    # not "chr15". The scorer compares chrom strings verbatim, so submitting "15"
    # is a silent miss.
    v = Variant.from_vcf("15", 40143000, "T", "C")
    assert v.chrom == "chr15"


def test_submission_chrom_is_accepted_unchanged():
    assert Variant.from_vcf("chr15", 40143000, "T", "C").chrom == "chr15"


def test_alleles_are_upper_cased():
    # The scorer upper-cases ref/alt before comparing; matching that here means a
    # lower-case allele from a downstream tool cannot cause a mismatch.
    v = Variant.from_vcf("15", 40143000, "t", "c")
    assert (v.ref, v.alt) == ("T", "C")


def test_equality_ignores_construction_route():
    assert Variant.from_vcf("15", 40143000, "T", "C") == Variant("chr15", 40143000, "T", "C")


def test_mitochondrial_contig_maps_to_chrM():
    # The VCF calls it "M"; GRCh38 chr-prefixed naming is "chrM".
    assert Variant.from_vcf("M", 5000, "A", "G").chrom == "chrM"


def test_position_must_be_positive():
    with pytest.raises(ValueError):
        Variant.from_vcf("15", 0, "T", "C")
