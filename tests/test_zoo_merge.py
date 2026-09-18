"""The deterministic merge layer: agreement, fusion, consensus, disagreement.

The RRF test is arithmetic done by hand in the docstring of the test itself — the whole claim
of reciprocal rank fusion is that it has no free parameter, so its output must be checkable
with a calculator rather than trusted.
"""

from __future__ import annotations

import pytest

from mva.zoo import merge, rank
from mva.zoo.pairs import Pair


def pair(gene: str, left: str, right: str, *, confirmed: bool = False) -> Pair:
    return Pair(gene=gene, left_id=left, right_id=right, phase="trans", is_confirmed=confirmed)


PAIRS = [
    pair("G1", "a", "b"),
    pair("G2", "c", "d", confirmed=True),
    pair("G3", "e", "f"),
]

CARDS = {
    "free1": {"key": "free1", "version": "1", "catalogue_adjacent": False, "licence": "MIT"},
    "free2": {"key": "free2", "version": "1", "catalogue_adjacent": False, "licence": "MIT"},
    "adjacent": {"key": "adjacent", "version": "1", "catalogue_adjacent": True, "licence": "x"},
}


# ── agreement matrix ─────────────────────────────────────────────────────────────────────


def test_matrix_is_symmetric_and_carries_n():
    scores = {
        "one": {"a": 1.0, "b": 2.0, "c": 3.0, "d": 4.0},
        "two": {"a": 1.0, "b": 2.0, "c": 3.0},
    }
    matrix = merge.agreement_matrix(scores)
    assert matrix.models == ("one", "two")
    assert matrix.cell("one", "two") == matrix.cell("two", "one")
    assert matrix.cell("one", "two")[1] == 3  # only three alleles are shared
    assert matrix.cell("one", "one") == (1.0, 4)


def test_a_perfectly_reversed_lane_scores_minus_one():
    scores = {"up": {"a": 1.0, "b": 2.0, "c": 3.0}, "down": {"a": 3.0, "b": 2.0, "c": 1.0}}
    assert merge.agreement_matrix(scores).cell("up", "down")[0] == pytest.approx(-1.0)


def test_too_few_shared_alleles_is_an_absent_number_not_a_zero():
    scores = {"one": {"a": 1.0, "b": 2.0}, "two": {"a": 1.0, "z": 2.0}}
    rho, n = merge.agreement_matrix(scores).cell("one", "two")
    assert (rho, n) == (None, 1)


def test_a_flat_lane_has_no_correlation_to_report():
    scores = {"flat": {"a": 1.0, "b": 1.0, "c": 1.0}, "varied": {"a": 1.0, "b": 2.0, "c": 3.0}}
    assert merge.agreement_matrix(scores).cell("flat", "varied")[0] is None


# ── reciprocal rank fusion ───────────────────────────────────────────────────────────────


def test_rrf_arithmetic_matches_the_hand_computed_sum():
    """Lane A ranks G1, G2, G3 (1, 2, 3); lane B ranks only G2, G3 (1, 2). k = 60.

    G1 = 1/61                 = 0.016393442...
    G2 = 1/62 + 1/61          = 0.032522474...
    G3 = 1/63 + 1/62          = 0.032002048...
    so the fused order is G2, G3, G1 — G1 leads one list but appears in only one of them.
    """
    a = rank.rank_pairs(PAIRS, {"a": 9, "b": 9, "c": 8, "d": 8, "e": 7, "f": 7}, model="a")
    b = rank.rank_pairs(PAIRS, {"c": 9, "d": 9, "e": 8, "f": 8}, model="b")
    fused = merge.rrf({"a": a, "b": b})
    assert [p.gene for p, _ in fused] == ["G2", "G3", "G1"]
    assert fused[0][1] == pytest.approx(1 / 62 + 1 / 61)
    assert fused[1][1] == pytest.approx(1 / 63 + 1 / 62)
    assert fused[2][1] == pytest.approx(1 / 61)


def test_k_damps_the_top_of_a_single_list():
    a = rank.rank_pairs(PAIRS, {"a": 9, "b": 9, "c": 8, "d": 8}, model="a")
    assert merge.rrf({"a": a}, k=0)[0][1] == pytest.approx(1.0)
    assert merge.rrf({"a": a}, k=60)[0][1] == pytest.approx(1 / 61)


def test_a_lane_that_did_not_rank_a_pair_contributes_nothing_for_it():
    a = rank.rank_pairs(PAIRS, {"a": 1, "b": 1}, model="a")
    fused = merge.rrf({"a": a})
    assert [p.gene for p, _ in fused] == ["G1"]


# ── consensus ────────────────────────────────────────────────────────────────────────────


SCORES = {
    # Two catalogue-free lanes rank G1, G3, G2 — the confirmed pair last.
    "free1": {"a": 9, "b": 9, "c": 1, "d": 1, "e": 5, "f": 5},
    "free2": {"a": 9, "b": 9, "c": 1, "d": 1, "e": 5, "f": 5},
    # The catalogue-adjacent lane ranks G2 first — exactly the "it may know the answer" case.
    "adjacent": {"a": 5, "b": 5, "c": 9, "d": 9, "e": 1, "f": 1},
}


def lanes() -> dict[str, rank.ModelRank]:
    """Two catalogue-free lanes that dislike the confirmed pair, one adjacent lane that loves it."""
    return rank.rank_per_model(PAIRS, SCORES)


def test_consensus_reports_both_ways_and_the_exclusion_is_visible():
    free = merge.consensus(lanes(), CARDS, exclude_adjacent=True)
    aware = merge.consensus(lanes(), CARDS, exclude_adjacent=False)
    assert free.excluded_lanes == ("adjacent",)
    assert free.lanes == ("free1", "free2")
    assert aware.excluded_lanes == ()
    assert free.rank == 3  # both catalogue-free lanes put the confirmed pair last
    assert free.percentile == pytest.approx(100.0)
    # Letting the adjacent lane vote lifts the confirmed pair one place: 2/63 + 1/61 beats
    # G3's 2/62 + 1/63 by 8e-6. That the ablation moves the answer at all is the finding.
    assert aware.rank == 2
    assert aware.fused_score == pytest.approx(2 / 63 + 1 / 61)


def test_consensus_says_nothing_when_no_pair_is_confirmed():
    plain = [pair("G1", "a", "b"), pair("G2", "c", "d")]
    ranks = rank.rank_per_model(plain, {"free1": {"a": 1, "b": 1, "c": 2, "d": 2}})
    assert merge.consensus(ranks, CARDS, exclude_adjacent=True).rank is None


def test_a_lane_missing_from_the_cards_is_never_guessed_to_be_adjacent():
    result = merge.consensus(lanes(), {}, exclude_adjacent=True)
    assert result.excluded_lanes == ()
    assert len(result.lanes) == 3


# ── disagreement ─────────────────────────────────────────────────────────────────────────


def test_disagreement_finds_the_allele_one_lane_loves_and_another_dislikes():
    scores = {
        "up": {f"x{i}": float(i) for i in range(10)},
        "down": {f"x{i}": float(9 - i) for i in range(10)},
    }
    rows = merge.disagreements(scores)
    # Ordered pairs: x9 is "up"'s best and "down"'s worst, x0 the mirror image. Both are
    # listed, because "A loves what B hates" and its converse are two separate findings.
    assert {(r.allele_id, r.high_model, r.low_model) for r in rows} == {
        ("x9", "up", "down"),
        ("x0", "down", "up"),
    }
    assert all(r.high_percentile == pytest.approx(10.0) for r in rows)
    assert all(r.low_percentile == pytest.approx(100.0) for r in rows)


def test_the_top_set_is_never_empty_even_for_a_tiny_lane():
    scores = {"up": {"a": 1.0, "b": 2.0}, "down": {"a": 2.0, "b": 1.0}}
    rows = merge.disagreements(scores, top=0.01, bottom=0.5)
    assert {r.allele_id for r in rows} == {"a", "b"}


def test_no_shared_allele_means_no_disagreement():
    scores = {"one": {"a": 1.0}, "two": {"z": 1.0}}
    assert merge.disagreements(scores) == []


def test_one_lane_alone_cannot_disagree():
    assert merge.disagreements({"only": {"a": 1.0, "b": 2.0}}) == []


def test_an_empty_lane_is_skipped_rather_than_crashing():
    assert merge.disagreements({"empty": {}, "full": {"a": 1.0, "b": 2.0}}) == []


# ── the merged JSON and its Markdown ─────────────────────────────────────────────────────


def merged() -> dict:
    return merge.merged_report(
        lanes(),
        CARDS,
        SCORES,
        run_id="run-1",
        sources=["results.it4_model_ranks"],
    )


def test_merged_json_carries_every_block_the_report_needs():
    payload = merged()
    assert set(payload) >= {
        "method",
        "run_id",
        "rrf_k",
        "lanes",
        "agreement",
        "consensus",
        "disagreements",
        "lineage",
    }
    assert payload["lineage"]["sources"] == ["results.it4_model_ranks"]
    assert [lane["model"] for lane in payload["lanes"]] == ["adjacent", "free1", "free2"]
    assert payload["consensus"]["catalogue_free"]["excluded_lanes"] == ["adjacent"]


def test_the_markdown_prints_the_json_and_marks_the_narrative_slot():
    payload = merged()
    text = merge.render_merged(payload, "Two lanes out of three put it last.", dated="2026-09-18")
    assert "<!-- narrative: hand-written 2026-09-18 -->" in text
    assert "Two lanes out of three put it last." in text
    assert "method `fusion`" in text
    assert "(DOI to verify)" in text
    # Every lane appears, and the RRF rank printed is the one the JSON holds.
    for model in CARDS:
        assert f"`{model}`" in text
    assert f"| {payload['consensus']['catalogue_free']['rank']} |" in text


def test_the_citation_does_not_assert_a_doi():
    assert "doi.org" not in merge.RRF_CITATION.lower()
    assert "DOI to verify" in merge.RRF_CITATION
