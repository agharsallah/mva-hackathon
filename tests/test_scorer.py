"""The scorer seam: a faithful local replica of the challenge's evaluation code.

Purpose is rehearsal. Eighteen submissions exist for the whole team and each one returns
rank_points, f_max, full_match_rank and partial_match_rank. Being able to replay a probe
offline is what turns that reply into a decodable measurement instead of a surprise.

Expected values come from the scoring rules worked by hand, not from the implementation.
For a singles probe the F-score at the rank-k threshold reduces algebraically to
``F = 2 * tp / (k + 2)``: with k single-variant rows above the threshold, precision is
tp/k and recall is tp/2, so F = 2(tp/k)(tp/2) / (tp/k + tp/2) = 2tp/(k+2). Every f_max
literal below is that formula evaluated by hand.
"""

import pytest

from mva.pipeline import Row, Variant, score

A = Variant("chr15", 40143000, "T", "C")
B = Variant("chr15", 40143500, "G", "T")
TRUTH = frozenset({A, B})

DECOYS = [Variant("chr1", 1000 * i, "A", "G") for i in range(1, 12)]


def singles(order):
    """A type-S probe: one variant per row, epcr descending 0.99, 0.98, ..."""
    return [Row(v, epcr=round(0.99 - i / 100, 2)) for i, v in enumerate(order)]


# --- rank points -------------------------------------------------------------


def test_exact_pair_at_rank_one_scores_the_maximum():
    result = score([Row(A, B, epcr=1.0)], TRUTH)
    assert result.full_match_rank == 1
    assert result.rank_points == 100.0
    assert result.f_max == 1.0


@pytest.mark.parametrize(
    "rank,points", [(1, 100), (2, 50), (3, 50), (4, 25), (5, 25), (6, 10), (10, 10)]
)
def test_rank_point_tiers_follow_the_published_scale(rank, points):
    rows = [Row(d, epcr=round(1.0 - i / 100, 2)) for i, d in enumerate(DECOYS[:10])]
    rows[rank - 1] = Row(A, B, epcr=rows[rank - 1].epcr)
    assert score(rows, TRUTH).rank_points == float(points)


def test_row_beyond_rank_ten_earns_no_points():
    rows = [Row(d, epcr=round(1.0 - i / 100, 2)) for i, d in enumerate(DECOYS[:10])]
    assert score(rows, TRUTH).rank_points == 0.0


def test_one_true_variant_alone_earns_half_that_ranks_points():
    assert score([Row(A, epcr=1.0)], TRUTH).rank_points == 50.0


def test_true_variant_paired_with_a_wrong_partner_is_still_a_partial_match():
    result = score([Row(A, DECOYS[0], epcr=1.0)], TRUTH)
    assert result.partial_match_rank == 1
    assert result.full_match_rank is None
    assert result.rank_points == 50.0


def test_full_match_takes_precedence_over_a_better_ranked_partial_match():
    # A partial match at rank 1 alone would be worth 50; a full match at rank 6 is
    # worth 10. The scorer reports the full match and its 10 points regardless.
    rows = [Row(A, epcr=1.0)] + [
        Row(d, epcr=round(0.9 - i / 100, 2)) for i, d in enumerate(DECOYS[:4])
    ]
    rows.append(Row(A, B, epcr=0.5))
    result = score(rows, TRUTH)
    assert (result.full_match_rank, result.partial_match_rank) == (6, None)
    assert result.rank_points == 10.0


def test_nothing_matching_scores_zero():
    result = score(singles(DECOYS[:10]), TRUTH)
    assert result.rank_points == 0.0
    assert result.f_max == 0.0
    assert (result.full_match_rank, result.partial_match_rank) == (None, None)


# --- the oracle decode table -------------------------------------------------
# f_max for a singles probe with the true alleles at ranks i and j.


@pytest.mark.parametrize(
    "i,j,expected_f",
    [
        (1, 2, 4 / 4),  # both alleles top two -> tp=2 at k=2 -> 4/4 = 1.000
        (1, 3, 4 / 5),  # 0.800
        (2, 3, 4 / 5),  # 0.800
        (2, 4, 4 / 6),  # 0.667
        (2, 5, 4 / 7),  # 0.571
        (3, 5, 4 / 7),  # 0.571
        (3, 7, 4 / 9),  # 0.444
    ],
)
def test_singles_probe_f_max_identifies_the_second_allele(i, j, expected_f):
    order = list(DECOYS[:10])
    order[i - 1], order[j - 1] = A, B
    assert score(singles(order), TRUTH).f_max == pytest.approx(expected_f, abs=1e-9)


def test_second_allele_beyond_the_ambiguous_boundary_is_indistinguishable_from_absent():
    # With the first allele at rank 1, tp=1 gives F = 2/3 at k=1. A second allele at
    # rank 4 gives tp=2, F = 4/6 -- the same value. The scorer keeps the FIRST
    # threshold reaching the best F (the comparison is strictly greater-than), so both
    # cases report 2/3 at rank 1's epcr and cannot be told apart. This is the blind
    # spot a type-P pair probe exists to resolve.
    order = list(DECOYS[:10])
    order[0] = A
    absent = score(singles(order), TRUTH)

    order_with_b = list(order)
    order_with_b[3] = B
    at_rank_four = score(singles(order_with_b), TRUTH)

    assert absent.f_max == pytest.approx(2 / 3)
    assert at_rank_four.f_max == pytest.approx(2 / 3)
    assert absent.f_max_threshold == at_rank_four.f_max_threshold == 0.99


def test_low_ranked_noise_rows_cannot_reduce_f_max():
    # Secondary findings are genuinely free: the threshold sweep can stop above them.
    clean = score([Row(A, B, epcr=1.0)], TRUTH)
    noisy = score(
        [Row(A, B, epcr=1.0)]
        + [Row(d, epcr=round(0.5 - i / 100, 2)) for i, d in enumerate(DECOYS[:8])],
        TRUTH,
    )
    assert noisy.f_max == clean.f_max == 1.0
    assert noisy.rank_points == 100.0


def test_two_single_rows_holding_both_alleles_reach_f_max_one_but_only_partial_credit():
    # Splitting the pair across two rows maxes F-max yet forfeits the full match,
    # which is why the final strike must put the pair in ONE row.
    result = score([Row(A, epcr=0.99), Row(B, epcr=0.98)], TRUTH)
    assert result.f_max == 1.0
    assert result.full_match_rank is None
    assert result.rank_points == 50.0
