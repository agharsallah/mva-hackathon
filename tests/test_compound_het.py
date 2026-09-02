"""The compound-heterozygote seam.

A compound heterozygote needs one variant on *each* haplotype. Two rare variants in the
same gene are not enough — if they sit on the same haplotype the second allele is still
wild-type and the gene is not knocked out. Sentieon emits physical phasing (PGT/PID) for
variants close enough to share reads, and 770,458 records in the real callset carry it,
so a meaningful fraction of pairs can be resolved without parental sequencing.
"""

from pathlib import Path

from mva.pipeline import Phase, candidate_pairs, read_calls

FIXTURE = Path(__file__).parent / "fixtures" / "mini.vcf"


def pairs_by_position():
    return {
        (p.left.variant.pos, p.right.variant.pos): p for p in candidate_pairs(read_calls(FIXTURE))
    }


def test_same_phase_group_same_haplotype_is_cis():
    # 40142000 and 40142100 are both 0|1 in phase group 40142000_C_T: both variants
    # ride the same haplotype, leaving the other copy of the gene intact.
    assert pairs_by_position()[(40142000, 40142100)].phase is Phase.CIS


def test_same_phase_group_opposite_haplotypes_is_trans():
    # 40143000 is 0|1 and 40143500 is 1|0 in one phase group: one variant per copy.
    assert pairs_by_position()[(40143000, 40143500)].phase is Phase.TRANS


def test_cis_pairs_are_excluded_from_compound_het_candidates():
    assert not pairs_by_position()[(40142000, 40142100)].is_compound_het_candidate
    assert pairs_by_position()[(40143000, 40143500)].is_compound_het_candidate


def test_unphased_pair_is_reported_as_unknown_not_discarded():
    # No phasing evidence either way. Without parents these stay live candidates.
    p = pairs_by_position()[(40144000, 40144800)]
    assert p.phase is Phase.UNKNOWN
    assert p.is_compound_het_candidate


def test_two_alts_at_one_site_are_trans_by_construction():
    # A 1/2 genotype means one ALT on each haplotype — that is a compound
    # heterozygote proven by the genotype itself, with no phasing needed.
    p = pairs_by_position()[(40146000, 40146000)]
    assert p.phase is Phase.TRANS


def test_homozygous_variants_are_not_paired():
    # 40145000 is 1/1: it is its own second hit, not half of a pair.
    assert not any(40145000 in key for key in pairs_by_position())


def test_pairs_are_reported_once_in_positional_order():
    keys = list(pairs_by_position())
    assert keys == sorted(keys)
    assert len(keys) == len(set(keys))
