"""The ranking seam: turning candidate pairs into an ordered submission.

Functional annotation is the input we do not have locally yet, so it enters through an
Annotator port. Tests drive it with a fake carrying known consequences; a real VEP or
Ensembl backend swaps in behind the same interface without touching ranking logic.

The proband's own VCF cannot supply this: its INFO/AF is within-sample (0.5 or 1.0 for a
single sample) and carries no population frequency, no consequence and no pathogenicity
prediction. Only the dbSNP membership flag is usable raw, and it is a weak novelty proxy.
"""
import pytest

from mva.annotation import Annotation, DictAnnotator
from mva.ranking import rank_pairs
from mva.variant import Variant

A = Variant("chr15", 40143000, "T", "C")   # rare stop-gain
B = Variant("chr15", 40143500, "G", "T")   # rare missense
COMMON = Variant("chr15", 40144000, "A", "C")
BENIGN = Variant("chr15", 40144800, "C", "G")

ANNOTATOR = DictAnnotator({
    A: Annotation(gene="BUB1B", consequence="stop_gained", gnomad_af=0.0),
    B: Annotation(gene="BUB1B", consequence="missense_variant", gnomad_af=1e-5),
    COMMON: Annotation(gene="BUB1B", consequence="missense_variant", gnomad_af=0.21),
    BENIGN: Annotation(gene="BUB1B", consequence="intron_variant", gnomad_af=1e-4),
})


def score_of(left, right, **kw):
    ranked = rank_pairs([(left, right)], ANNOTATOR, **kw)
    return ranked[0].score


def test_unannotated_variant_is_not_a_crash():
    # A variant the annotator has never seen must rank low, not raise: the genome-wide
    # run will always contain variants outside any cache.
    unknown = Variant("chr7", 1234, "A", "G")
    assert score_of(unknown, unknown) == pytest.approx(0.0, abs=0.5)


def test_two_rare_damaging_variants_outrank_a_common_pair():
    assert score_of(A, B) > score_of(COMMON, BENIGN)


def test_a_common_variant_drags_its_pair_down():
    # A gnomAD AF of 0.21 is far too frequent for a variant causing a disease with
    # fewer than 50 known patients worldwide.
    assert score_of(A, B) > score_of(A, COMMON)


def test_loss_of_function_outranks_missense_at_equal_frequency():
    assert score_of(A, A) > score_of(B, B)


def test_pairs_come_back_sorted_best_first():
    ranked = rank_pairs([(COMMON, BENIGN), (A, B), (A, COMMON)], ANNOTATOR)
    assert [(p.left, p.right) for p in ranked][0] == (A, B)
    assert [p.score for p in ranked] == sorted((p.score for p in ranked), reverse=True)


def test_pairs_spanning_two_genes_are_rejected():
    # Compound heterozygosity is a statement about ONE gene: one damaged copy each.
    # Two variants in different genes are two unrelated carriers, not a diagnosis.
    other = Variant("chr5", 900000, "A", "G")
    annotator = DictAnnotator({
        **ANNOTATOR.by_variant,
        other: Annotation(gene="TRIP13", consequence="stop_gained", gnomad_af=0.0),
    })
    assert rank_pairs([(A, other)], annotator) == []


def test_a_gene_prior_lifts_the_expected_mva_genes():
    # MVA is caused by biallelic variants in a small, known gene set. Encoding that as
    # an explicit, inspectable prior beats hiding it in a threshold.
    with_prior = rank_pairs([(A, B)], ANNOTATOR, gene_prior={"BUB1B": 2.0})[0].score
    assert with_prior > score_of(A, B)
