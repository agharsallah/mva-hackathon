"""The VCF-reading seam: turning records into calls the ranker can reason about."""
from pathlib import Path

from mva.pipeline import Variant, read_calls

FIXTURE = Path(__file__).parent / "fixtures" / "mini.vcf"


def calls():
    return read_calls(FIXTURE)


def test_reads_every_alt_allele_including_multiallelic():
    # 11 records, but 40146000 is a 1/2 site carrying two ALT alleles. Splitting
    # multiallelics is mandatory: the scorer has no concept of a comma-separated ALT.
    assert len(calls()) == 12


def test_contigs_are_translated_to_submission_form():
    assert {c.variant.chrom for c in calls()} == {"chr15"}


def test_heterozygous_call_carries_depth_and_allele_balance():
    c = next(c for c in calls() if c.variant.pos == 40141000)
    assert c.is_het
    assert c.depth == 48
    assert c.vaf == 0.5


def test_multiallelic_site_yields_two_het_calls():
    both = [c for c in calls() if c.variant.pos == 40146000]
    assert len(both) == 2
    assert {c.variant.alt for c in both} == {"AT", "ATT"}
    # A 1/2 genotype carries one copy of each ALT — each is heterozygous, and the
    # pair of them is itself a compound-heterozygous configuration.
    assert all(c.is_het for c in both)


def test_homozygous_call_is_not_heterozygous():
    c = next(c for c in calls() if c.variant.pos == 40145000)
    assert not c.is_het


def test_phase_group_and_haplotype_are_exposed():
    c = next(c for c in calls() if c.variant.pos == 40143500)
    assert c.phase_set == "40143000_T_C"
    assert c.phase_gt == "1|0"


def test_unphased_call_has_no_phase_set():
    c = next(c for c in calls() if c.variant.pos == 40144000)
    assert c.phase_set is None


def test_filter_status_is_preserved_not_dropped():
    # Non-PASS records matter: a suppressed call is a prime hiding place for the
    # second allele, so filtering is a ranking decision, never a parsing one.
    c = next(c for c in calls() if c.variant.pos == 40148000)
    assert c.filters == ("LowQual", "QD2")
    assert not c.is_pass
    assert next(c for c in calls() if c.variant.pos == 40141000).is_pass


def test_right_aligned_indel_is_read_verbatim():
    # Normalization is a separate, explicit step; the reader must not silently alter
    # alleles or we lose the ability to test that normalization happened.
    c = next(c for c in calls() if c.variant.pos == 40147000)
    assert c.variant == Variant("chr15", 40147000, "CTT", "C")
