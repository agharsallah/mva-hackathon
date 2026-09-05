"""The cross-check: our replica and the organisers' scorer grade the same bytes alike.

Expectations are hand-derived from the published scoring rules, as in ``test_scorer.py``.
The organisers' file is a checked-in resource; when it is missing the module reports that
and the tests that need it are skipped rather than failed.
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

from mva.pipeline.scorer import ScoreResult, score
from mva.pipeline.scorer_reference import (
    DEFAULT_REFERENCE,
    compare,
    grade_with_reference,
    load_reference,
)
from mva.pipeline.submission import Row, read_submission, write_submission
from mva.pipeline.variant import Variant

ROOT = Path(__file__).resolve().parents[1]
A = Variant("chr15", 1_000_001, "T", "G")
B = Variant("chr15", 1_000_002, "T", "G")
C = Variant("chr15", 1_000_003, "A", "G")
E = Variant("chr2", 1_000_004, "G", "A")


@pytest.fixture(scope="module")
def reference():
    module = load_reference(ROOT / DEFAULT_REFERENCE)
    if module is None:
        pytest.skip("organisers' evaluation.py not checked out")
    return module


@pytest.fixture
def csv_path(tmp_path) -> Path:
    rows = [Row(A, B, epcr=0.95), Row(A, C, epcr=0.3), Row(E, epcr=0.05, finding_type="secondary")]
    path = tmp_path / "sub.csv"
    with path.open("w", newline="") as handle:
        write_submission(rows, handle)
    return path


def test_missing_reference_is_reported_not_raised(tmp_path):
    assert load_reference(tmp_path / "nowhere.py") is None


def test_compare_is_empty_when_every_exposed_field_matches():
    a = ScoreResult(1, None, 100.0, 1.0, 0.95, 1)
    b = ScoreResult(1, None, 100.0, 1.0, 0.95, 7)  # internal count differs, not exposed
    assert compare(a, b) == []


def test_compare_names_the_field_that_differs():
    a = ScoreResult(1, None, 100.0, 1.0, 0.95, 1)
    b = ScoreResult(None, 1, 50.0, 0.5, 0.95, 1)
    assert [d.field for d in compare(a, b)] == [
        "full_match_rank",
        "partial_match_rank",
        "rank_points",
        "f_max",
    ]


@pytest.mark.parametrize(
    ("truth", "expected"),
    [
        (frozenset({A, B}), (1, None, 100.0, 1.0)),  # the pair at rank 1
        (frozenset({A, C}), (2, None, 50.0, 0.8)),  # alternative pair at rank 2
        # partner is the secondary row: partial at rank 1; F-max peaks once row 3 is admitted
        # (tp 2, fp 2, fn 0 -> precision 0.5, recall 1 -> 0.667), not at the pair's threshold
        (frozenset({A, E}), (None, 1, 50.0, 0.667)),
        (
            frozenset({Variant("chr9", 1, "A", "T"), Variant("chr9", 2, "A", "T")}),
            (None, None, 0.0, 0.0),
        ),
    ],
)
def test_reference_and_replica_agree_on_hand_derived_replies(reference, csv_path, truth, expected):
    theirs = grade_with_reference(reference, csv_path, truth)
    ours = score(read_submission(StringIO(csv_path.read_text())), truth)
    assert compare(ours, theirs) == []
    assert (
        theirs.full_match_rank,
        theirs.partial_match_rank,
        theirs.rank_points,
        round(theirs.f_max, 3),
    ) == expected
