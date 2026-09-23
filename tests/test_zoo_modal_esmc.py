"""The ESM-C lane's pure logic: which items it scores, how it groups them, the ratio it reads.

No Modal call, no weights, no patient data: ubiquitin (a public protein) and invented ids.
``modal`` is only in the ``zoo-ml`` group, so a stand-in module is installed when it is absent;
the functions under test never touch it.
"""

from __future__ import annotations

import importlib
import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest

from mva.zoo.modal_contract import Item


@pytest.fixture(scope="module")
def esmc() -> ModuleType:
    try:
        importlib.import_module("modal")
    except ImportError:
        sys.modules["modal"] = MagicMock()
    return importlib.import_module("mva.zoo.modal_apps.esmc")


def _swap(seq: str, spot: int, letter: str, allele: str = "a") -> Item:
    return Item(allele_id=allele, ref=seq, alt=seq[:spot] + letter + seq[spot + 1 :], center=spot)


def test_plan_keeps_one_substitution_and_skips_the_rest(esmc: ModuleType) -> None:
    seq = esmc.UBIQUITIN
    good = _swap(seq, 5, "A", "good")
    two = Item(allele_id="two", ref=seq, alt="W" + good["alt"][1:], center=5)
    same = Item(allele_id="same", ref=seq, alt=seq, center=5)
    off = Item(allele_id="off", ref=seq, alt=good["alt"], center=len(seq))
    wrong_center = Item(allele_id="wrong", ref=seq, alt=good["alt"], center=6)
    stop = _swap(seq, 5, "*", "stop")
    indel = Item(allele_id="indel", ref=seq, alt=seq + "A", center=5)
    planned = esmc.plan([good, two, same, off, wrong_center, stop, indel])
    assert [p.allele_id for p in planned] == ["good"]
    assert planned[0].spot == 5 and planned[0].ref == seq[5] and planned[0].alt == "A"


def test_smoke_items_score_eight_and_skip_one(esmc: ModuleType) -> None:
    items = esmc.smoke_items()
    assert len(items) == 9 and len(esmc.plan(items)) == 8


def test_by_length_groups_never_mix_lengths(esmc: ModuleType) -> None:
    seq = esmc.UBIQUITIN
    items = [_swap(seq, 3, "A", f"l{i}") for i in range(5)]
    items += [_swap(seq[:40], 3, "A", f"s{i}") for i in range(3)]
    groups = esmc.by_length(esmc.plan(items), batch=2)
    assert sorted(len(g) for g in groups) == [1, 1, 2, 2, 2]
    assert all(len({len(p.window) for p in g}) == 1 for g in groups)
    assert sum(len(g) for g in groups) == 8


def test_llr_is_alt_minus_ref(esmc: ModuleType) -> None:
    assert esmc.llr({"K": -0.1, "E": -2.6}, "K", "E") == pytest.approx(-2.5)
