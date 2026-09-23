"""The Evo 2 lane's pure arithmetic: re-cropping to the model's context, right-padding.

An insertion's alt window is longer than its ref window, so a full 8,192-base window can
exceed the 1B model's trained context; ``fit`` is what keeps it inside. No Modal call, no weights.
"""

from __future__ import annotations

import pytest

pytest.importorskip("modal")

from mva.zoo.modal_apps import evo2
from mva.zoo.modal_contract import Item


def _insertion(length: int, inserted: int) -> Item:
    ref = ("ACGT" * length)[:length]
    c = length // 2
    alt = ref[: c + 1] + "T" * inserted + ref[c + 1 :]
    return Item(allele_id="x", ref=ref, alt=alt, center=c)


def test_fit_leaves_an_item_inside_the_context_alone() -> None:
    item = _insertion(64, 4)
    assert evo2.fit(item, max_len=80) == (item, False)


def test_fit_recrops_an_insertion_so_both_windows_fit_and_keep_the_change() -> None:
    item = _insertion(64, 10)
    out, cropped = evo2.fit(item, max_len=64)
    assert cropped
    assert len(out["alt"]) == 64 and len(out["ref"]) == 54
    c = out["center"]
    assert out["ref"][c] == item["ref"][item["center"]]
    assert out["alt"][c + 1 : c + 11] == "T" * 10
    # the windows still differ only by the inserted bases
    assert out["alt"][: c + 1] + out["alt"][c + 11 :] == out["ref"]


@pytest.mark.parametrize(("length", "padded"), [(1, 128), (128, 128), (8049, 8064), (8192, 8192)])
def test_pad_to_rounds_up_to_the_fp8_multiple(length: int, padded: int) -> None:
    assert evo2.pad_to(length) == padded
