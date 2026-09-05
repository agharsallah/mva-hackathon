"""The probe designer: a submission read as a measurement over a hypothesis space.

Every expectation is derived by hand from the scoring rules, not recomputed the way the
code computes it — the same discipline ``test_scorer.py`` follows.
"""

from __future__ import annotations

import math

import pytest

from mva.pipeline.probe_design import Hypothesis, design, entropy, reply_key
from mva.pipeline.submission import Row
from mva.pipeline.variant import Variant

A = Variant("chr15", 100, "T", "G")  # the strong allele
B = Variant("chr15", 200, "T", "G")  # its presumed partner
C = Variant("chr15", 300, "C", "T")  # alternative partner 1
D = Variant("chr15", 400, "A", "G")  # alternative partner 2
E = Variant("chr2", 500, "G", "A")  # an allele in another gene


def pair(x: Variant, y: Variant, epcr: float) -> Row:
    return Row(x, y, epcr=epcr)


def single(x: Variant, epcr: float) -> Row:
    return Row(x, epcr=epcr)


def hyp(label: str, *alleles: Variant, prior: float = 1.0) -> Hypothesis:
    return Hypothesis(frozenset(alleles), label, prior)


SPACE = [
    hyp("A+B", A, B),
    hyp("A+C", A, C),
    hyp("A+D", A, D),
    hyp("B+C", B, C),
    hyp("neither", E, Variant("chr2", 600, "C", "G")),
]


class TestEntropy:
    def test_uniform_over_four_is_two_bits(self):
        assert entropy([1, 1, 1, 1]) == pytest.approx(2.0)

    def test_a_certainty_has_no_entropy(self):
        assert entropy([1.0]) == 0.0
        assert entropy([0.0, 3.0]) == 0.0

    def test_weights_need_not_be_normalised(self):
        assert entropy([2, 2]) == pytest.approx(entropy([0.5, 0.5]))


class TestHypothesis:
    def test_rejects_an_empty_or_triple_answer_key(self):
        with pytest.raises(ValueError):
            Hypothesis(frozenset(), "empty")
        with pytest.raises(ValueError):
            Hypothesis(frozenset({A, B, C}), "triple")

    def test_rejects_a_negative_prior(self):
        with pytest.raises(ValueError):
            Hypothesis(frozenset({A}), "neg", prior=-1)


class TestDesign:
    def test_a_pair_at_rank_one_alone_cannot_tell_partners_apart(self):
        # One row {A,B}. Truth A+B → full match. Truth A+C or A+D → partial at rank 1,
        # F = 0.5 in both cases: indistinguishable. B+C likewise partial at rank 1.
        found = design([pair(A, B, 0.99)], SPACE)
        by_label = {tuple(h.label for h in o.hypotheses): o for o in found.outcomes}
        assert ("A+B",) in by_label
        assert by_label[("A+B",)].reply.full_match_rank == 1
        ambiguous = next(k for k in by_label if "A+C" in k)
        assert set(ambiguous) == {"A+C", "A+D", "B+C"}
        assert found.max_ambiguity == 3

    def test_singles_below_the_pair_name_the_partner_but_not_which_member_it_joins(self):
        # Pair {A,B} at rank 1, then singles C, D. Truth A+C: at threshold row 2 the
        # predicted set is {A,B,C}, tp=2 → P=2/3, R=1, F=0.8 > 0.5 → f_max 0.8 at 0.98.
        # Truth B+C produces the *same* reply: the pair row intersects either way, and the
        # single names C without saying whether A or B was the true member. Truth A+D:
        # predicted {A,B,C,D} at row 3, tp=2 → P=0.5, R=1, F=2/3 at 0.97 — distinct from C.
        rows = [pair(A, B, 0.99), single(C, 0.98), single(D, 0.97)]
        found = design(rows, SPACE)
        labels = {frozenset(h.label for h in o.hypotheses): o for o in found.outcomes}
        assert frozenset({"A+C", "B+C"}) in labels
        assert labels[frozenset({"A+C", "B+C"})].reply.f_max == pytest.approx(0.8)
        assert frozenset({"A+D"}) in labels
        assert labels[frozenset({"A+D"})].reply.f_max == pytest.approx(2 / 3)
        assert found.max_ambiguity == 2

    def test_alternative_pair_rows_decode_by_full_match_rank(self):
        rows = [pair(A, B, 0.99), pair(A, C, 0.98), pair(A, D, 0.97)]
        found = design(rows, SPACE)
        ranks = {
            o.hypotheses[0].label: o.reply.full_match_rank for o in found.outcomes if o.decisive
        }
        assert ranks["A+B"] == 1
        assert ranks["A+C"] == 2
        assert ranks["A+D"] == 3

    def test_expected_posterior_entropy_is_the_mass_weighted_residual(self):
        # Five equiprobable truths; the only non-decisive reply is {A+C, B+C} with mass
        # 2/5 and one bit left inside it → expected posterior 0.4 bits, gain log2(5) − 0.4.
        rows = [pair(A, B, 0.99), single(C, 0.98), single(D, 0.97)]
        found = design(rows, SPACE)
        assert found.prior_entropy == pytest.approx(math.log2(5))
        assert found.expected_posterior_entropy == pytest.approx(0.4)
        assert found.expected_information_gain == pytest.approx(math.log2(5) - 0.4)

    def test_alternative_pair_rows_are_fully_decisive(self):
        rows = [pair(A, B, 0.99), pair(A, C, 0.98), pair(A, D, 0.97), pair(B, C, 0.96)]
        found = design(rows, SPACE)
        assert found.max_ambiguity == 1
        assert found.expected_posterior_entropy == pytest.approx(0.0)

    def test_priors_weight_the_expected_gain(self):
        space = [hyp("A+B", A, B, prior=8), hyp("A+C", A, C, prior=1), hyp("A+D", A, D, prior=1)]
        found = design([pair(A, B, 0.99)], space)
        # Reply "full match": mass 0.8, posterior entropy 0. Reply "partial": mass 0.2,
        # two equiprobable survivors → 1 bit. Expected posterior = 0.2 bits.
        assert found.expected_posterior_entropy == pytest.approx(0.2)
        assert found.outcomes[0].mass == pytest.approx(0.8)

    def test_reply_key_drops_the_derived_fields(self):
        rows = [pair(A, B, 0.99)]
        found = design(rows, [hyp("A+B", A, B)])
        key = reply_key(found.outcomes[0].reply)
        assert key == (1, None, 1.0, 0.99)

    def test_an_empty_space_is_refused(self):
        with pytest.raises(ValueError):
            design([pair(A, B, 0.99)], [])
