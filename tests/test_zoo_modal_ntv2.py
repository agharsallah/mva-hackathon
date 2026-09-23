"""The NT-v2 lane's pure arithmetic: tokenisation spans and where the LLR is read.

The container checks our span tokeniser against the published one on every start; these tests
pin the rules that check relies on. No Modal call, no weights.
"""

from __future__ import annotations

import pytest

pytest.importorskip("modal")

from mva.zoo.modal_apps import ntv2


def test_spans_are_greedy_six_mers_with_single_letter_fallback() -> None:
    seq = "A" * 6 + "C" * 3 + "N" + "G" * 7
    assert ntv2.kmer_spans(seq) == [(0, 6), (6, 7), (7, 8), (8, 9), (9, 10), (10, 16), (16, 17)]


def test_clean_maps_non_acgtn_to_n() -> None:
    assert ntv2.clean("acgtRyN") == "ACGTNNN"


def test_encode_prefixes_cls_and_truncates() -> None:
    vocab = {"AAAAAA": 5, "A": 1}
    ids = ntv2.encode("A" * (6 * ntv2.MAX_TOKENS + 3), vocab, cls_id=0)
    assert ids[0] == 0 and len(ids) == ntv2.MAX_TOKENS and set(ids[1:]) == {5}


def test_llr_site_only_for_changes_inside_one_six_mer() -> None:
    ref = "ACGTAC" * 4
    snv = ref[:12] + "T" + ref[13:]
    assert ntv2.llr_site(ref, snv, 12) == 2
    across = ref[:11] + "A" + "T" + ref[13:]  # two changes spanning a token boundary
    assert ntv2.llr_site(ref, across, 12) == -1
    assert ntv2.llr_site(ref, ref[:12] + ref[13:], 12) == -1  # deletion
    assert ntv2.llr_site(ref, ref, 12) == -1  # no change


def test_llr_site_refuses_a_change_to_n() -> None:
    ref = "ACGTAC" * 4
    assert ntv2.llr_site(ref, ref[:12] + "N" + ref[13:], 12) == -1


def test_synthetic_items_are_random_bases_with_the_change_at_center() -> None:
    items = ntv2.synthetic_items(length=600)
    assert len(items) == 8
    for item in items:
        assert item["allele_id"].startswith("synthetic-")
        assert item["ref"][: item["center"] - 40] == item["alt"][: item["center"] - 40]
