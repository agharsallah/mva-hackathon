"""``/api/steps``: the research journey, assembled rather than written.

The point of this endpoint is that a new step — or a whole new iteration — needs no
hand-written prose anywhere. The tests pin the three joins that make that true: the step
map supplies the goals, the register supplies the claims *of that iteration*, and the
blind gate supplies the checklist.
"""

import pytest
from fastapi import HTTPException

from mva.science import steps as steps_module
from mva.viz import steps as route


class _Settings:
    schema = "warehouse"
    result_schema = "results"


def _register(rows, exists=True):
    return {"table_exists": exists, "rows": rows}


def _row(hid, step, revision=1, iteration="iteration2", **extra):
    base = {
        "hypothesis_id": hid,
        "revision": revision,
        "step": step,
        "status": "proposed",
        "iteration": iteration,
    }
    return base | extra


@pytest.fixture
def patched(monkeypatch, tmp_path):
    def _patch(rows, exists=True):
        monkeypatch.setattr(route, "register", lambda *a, **k: _register(rows, exists))
        return tmp_path

    return _patch


def test_every_declared_step_appears_even_with_an_empty_register(patched):
    docs = patched([], exists=False)
    data = route.payload(_Settings(), "iteration2", docs_root=docs, figures_root=docs)
    assert [s["slug"] for s in data["steps"]] == [
        s.slug for s in steps_module.steps_for("iteration2")
    ]
    assert data["register_exists"] is False


def test_only_the_latest_revision_of_a_claim_is_shown():
    rows = [
        _row("H001", "step-1", 1, status="proposed"),
        _row("H001", "step-1", 2, status="refuted"),
    ]
    assert route._latest_by_id(rows) == [rows[1]]


def test_a_claim_from_another_iteration_is_not_shown(patched):
    docs = patched([_row("H001", "step-1", iteration="iteration1")])
    data = route.payload(_Settings(), "iteration2", docs_root=docs, figures_root=docs)
    assert all(not s["hypotheses"] for s in data["steps"])


def test_a_row_written_before_the_iteration_column_existed_belongs_to_iteration_one(patched):
    docs = patched([_row("H001", "step-1", iteration=None)])
    first = route.payload(_Settings(), "iteration1", docs_root=docs, figures_root=docs)
    assert any(s["hypotheses"] for s in first["steps"])


def test_the_blinding_checklist_comes_from_the_gate_not_from_prose(patched, tmp_path):
    docs = patched([])
    entry = docs / "iteration2" / "step-1" / "methodology" / "084-x.md"
    entry.parent.mkdir(parents=True)
    entry.write_text("# 084\n\n## Inputs\n\n| clinical | the HPO terms |\n", encoding="utf-8")
    data = route.payload(_Settings(), "iteration2", docs_root=docs, figures_root=docs)
    step_one = next(s for s in data["steps"] if s["slug"] == "step-1")
    assert step_one["entries"][0]["entry"] == "084-x.md"
    assert step_one["entries"][0]["declares_inputs"]
    assert data["blind"]["still_blind"]


def test_an_entry_that_breaks_the_blinding_surfaces_as_a_problem(patched, tmp_path):
    docs = patched([])
    entry = docs / "iteration2" / "step-1" / "methodology" / "084-x.md"
    entry.parent.mkdir(parents=True)
    entry.write_text("# 084\n\n## Inputs\n\n| results.gene_biallelic |\n", encoding="utf-8")
    data = route.payload(_Settings(), "iteration2", docs_root=docs, figures_root=docs)
    assert data["blind"]["problems"]


def test_figures_are_listed_per_step_and_an_undrawn_step_has_none(patched, tmp_path):
    docs = patched([])
    folder = tmp_path / "iteration2" / "step-1"
    folder.mkdir(parents=True)
    (folder / "recall.png").write_bytes(b"")
    (folder / ".hidden").write_bytes(b"")
    data = route.payload(_Settings(), "iteration2", docs_root=docs, figures_root=tmp_path)
    by_slug = {s["slug"]: s for s in data["steps"]}
    assert by_slug["step-1"]["figures"] == ["recall.png"]
    assert by_slug["step-4"]["figures"] == []


def test_an_unknown_iteration_is_a_404_naming_the_ones_that_exist(patched):
    docs = patched([])
    with pytest.raises(HTTPException) as raised:
        route.payload(_Settings(), "iteration99", docs_root=docs, figures_root=docs)
    assert raised.value.status_code == 404
    assert "iteration1" in raised.value.detail
