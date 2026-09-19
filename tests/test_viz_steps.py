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
    data = route.payload(_Settings(), "iteration2", docs_root=docs, repo_root=docs)
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
    data = route.payload(_Settings(), "iteration2", docs_root=docs, repo_root=docs)
    assert all(not s["hypotheses"] for s in data["steps"])


def test_a_row_written_before_the_iteration_column_existed_belongs_to_iteration_one(patched):
    docs = patched([_row("H001", "step-1", iteration=None)])
    first = route.payload(_Settings(), "iteration1", docs_root=docs, repo_root=docs)
    assert any(s["hypotheses"] for s in first["steps"])


def test_the_blinding_checklist_comes_from_the_gate_not_from_prose(patched, tmp_path):
    docs = patched([])
    entry = docs / "iteration2" / "step-1" / "methodology" / "084-x.md"
    entry.parent.mkdir(parents=True)
    entry.write_text("# 084\n\n## Inputs\n\n| clinical | the HPO terms |\n", encoding="utf-8")
    data = route.payload(_Settings(), "iteration2", docs_root=docs, repo_root=docs)
    step_one = next(s for s in data["steps"] if s["slug"] == "step-1")
    assert step_one["entries"][0]["entry"] == "084-x.md"
    assert step_one["entries"][0]["declares_inputs"]
    assert data["blind"]["still_blind"]


def test_an_entry_that_breaks_the_blinding_surfaces_as_a_problem(patched, tmp_path):
    docs = patched([])
    entry = docs / "iteration2" / "step-1" / "methodology" / "084-x.md"
    entry.parent.mkdir(parents=True)
    entry.write_text("# 084\n\n## Inputs\n\n| results.gene_biallelic |\n", encoding="utf-8")
    data = route.payload(_Settings(), "iteration2", docs_root=docs, repo_root=docs)
    assert data["blind"]["problems"]


def test_figures_are_listed_per_step_and_an_undrawn_step_has_none(patched, tmp_path):
    docs = patched([])
    folder = tmp_path / "figures" / "track1" / "iteration2" / "step-1"
    folder.mkdir(parents=True)
    (folder / "recall.png").write_bytes(b"")
    (folder / ".hidden").write_bytes(b"")
    data = route.payload(_Settings(), "iteration2", docs_root=docs, repo_root=tmp_path)
    by_slug = {s["slug"]: s for s in data["steps"]}
    assert [f["name"] for f in by_slug["step-1"]["figures"]] == ["recall.png"]
    assert by_slug["step-1"]["figures"][0]["url"].endswith(
        "/api/steps/iteration2/step-1/figure/recall.png"
    )
    assert by_slug["step-4"]["figures"] == []


def test_a_figure_declared_outside_the_convention_is_still_listed(patched, tmp_path):
    """Iteration 1 and the Track 2 renderer wrote figures before the per-step directory
    convention existed. A step that names them must not read as having drawn nothing."""
    docs = patched([])
    declared = tmp_path / "figures" / "track2" / "rung-funnel.png"
    declared.parent.mkdir(parents=True)
    declared.write_bytes(b"")
    data = route.payload(_Settings(), "iteration2", docs_root=docs, repo_root=tmp_path)
    step_seven = next(s for s in data["steps"] if s["slug"] == "step-7")
    assert [f["name"] for f in step_seven["figures"]] == ["rung-funnel.png"]
    assert step_seven["figures"][0]["path"] == "figures/track2/rung-funnel.png"


def test_every_step_names_the_track_it_feeds(patched):
    docs = patched([])
    data = route.payload(_Settings(), "iteration2", docs_root=docs, repo_root=docs)
    by_slug = {s["slug"]: s["track"] for s in data["steps"]}
    assert by_slug["step-6"] == "track1"
    assert by_slug["step-7"] == "track2"


def test_an_entry_row_carries_its_number_and_its_own_heading(patched, tmp_path):
    docs = patched([])
    entry = docs / "iteration2" / "step-1" / "methodology" / "084-the-blind-target-set.md"
    entry.parent.mkdir(parents=True)
    entry.write_text("# 084 - Which genes do the symptoms nominate?\n", encoding="utf-8")
    data = route.payload(_Settings(), "iteration2", docs_root=docs, repo_root=docs)
    row = next(s for s in data["steps"] if s["slug"] == "step-1")["entries"][0]
    assert row["number"] == "084"
    assert row["title"] == "Which genes do the symptoms nominate?"
    assert row["url"].endswith("/entry/084-the-blind-target-set.md")


def test_a_figure_the_step_never_drew_is_a_404_naming_what_it_did(tmp_path):
    """The name is looked up in the declared rows, so a traversal is simply not a match."""
    folder = tmp_path / "figures" / "track1" / "iteration2" / "step-1"
    folder.mkdir(parents=True)
    (folder / "recall.png").write_bytes(b"")
    assert route.step_figure_path(
        "iteration2", "step-1", "recall.png", repo_root=tmp_path
    ).is_file()
    with pytest.raises(HTTPException) as raised:
        route.step_figure_path("iteration2", "step-1", "../../../etc/passwd", repo_root=tmp_path)
    assert raised.value.status_code == 404
    assert "recall.png" in raised.value.detail


def test_an_entry_is_served_only_when_the_gate_walked_it(tmp_path):
    entry = tmp_path / "iteration2" / "step-1" / "methodology" / "084-x.md"
    entry.parent.mkdir(parents=True)
    entry.write_text("# 084 - x\n", encoding="utf-8")
    assert route.step_entry_path("iteration2", "step-1", "084-x.md", docs_root=tmp_path) == entry
    with pytest.raises(HTTPException) as raised:
        route.step_entry_path("iteration2", "step-1", "085-y.md", docs_root=tmp_path)
    assert raised.value.status_code == 404


def test_an_unknown_iteration_is_a_404_naming_the_ones_that_exist(patched):
    docs = patched([])
    with pytest.raises(HTTPException) as raised:
        route.payload(_Settings(), "iteration99", docs_root=docs, repo_root=docs)
    assert raised.value.status_code == 404
    assert "iteration1" in raised.value.detail
