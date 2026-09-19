"""The written half of a step is complete, sourced, and in step with the figures on disk.

The gate exists because a chart with no caption is decoration and a step with no summary is
a folder. These tests pin the four ways that can go wrong.
"""

import json

import pytest

from mva.viz import steps_narrative as narrative


def _complete(**overrides) -> dict:
    base = {
        "step": "step-1",
        "iteration": "iteration9",
        "summary": "It ran.",
        "why": "Because nothing else could answer it.",
        "verdict": "H001 supported.",
        "inherits": {"steps": [], "what": "nothing; it is first"},
        "hands_to": {"steps": ["step-2"], "what": "step 2 ranks what this one normalised"},
        "figures": [{"name": "a.png", "reads": "one bar per lane", "means": "the lanes agree"}],
        "sources": ["README.md"],
    }
    return base | overrides


def test_a_complete_narrative_validates(tmp_path):
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    narrative.validate(_complete(), repo_root=tmp_path, figures=["a.png"], where="w")


def test_a_figure_with_no_caption_fails(tmp_path):
    """The whole point: a step that drew something nobody read does not pass."""
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    with pytest.raises(narrative.NarrativeError, match=r"figures with no caption: \['b.png'\]"):
        narrative.validate(_complete(), repo_root=tmp_path, figures=["a.png", "b.png"], where="w")


def test_a_caption_for_a_figure_that_was_never_drawn_fails(tmp_path):
    """Drift the other way is just as wrong: the page would describe a file that is not there."""
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    with pytest.raises(narrative.NarrativeError, match="did not draw"):
        narrative.validate(_complete(), repo_root=tmp_path, figures=[], where="w")


def test_a_source_that_does_not_exist_fails(tmp_path):
    """An unsourced narrative is the same defect the evidence ledger already refuses."""
    with pytest.raises(narrative.NarrativeError, match="does not exist"):
        narrative.validate(_complete(), repo_root=tmp_path, figures=["a.png"], where="w")


@pytest.mark.parametrize("field", ["summary", "why", "verdict"])
def test_an_empty_prose_field_fails(tmp_path, field):
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    with pytest.raises(narrative.NarrativeError, match=field):
        narrative.validate(
            _complete(**{field: "   "}), repo_root=tmp_path, figures=["a.png"], where="w"
        )


def test_a_join_without_its_steps_fails(tmp_path):
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    with pytest.raises(narrative.NarrativeError, match="hands_to needs"):
        narrative.validate(
            _complete(hands_to={"what": "something"}),
            repo_root=tmp_path,
            figures=["a.png"],
            where="w",
        )


def test_a_step_with_no_narrative_reads_as_none(tmp_path):
    """Absent is a state, not an error — the page says so and the gate decides if it is allowed."""
    assert narrative.read(tmp_path, "iteration9", "step-1", repo_root=tmp_path, figures=[]) is None


def test_read_validates_what_it_loads(tmp_path):
    folder = tmp_path / "iteration9" / "step-1"
    folder.mkdir(parents=True)
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    (folder / narrative.NARRATIVE).write_text(json.dumps(_complete()), encoding="utf-8")
    loaded = narrative.read(tmp_path, "iteration9", "step-1", repo_root=tmp_path, figures=["a.png"])
    assert loaded is not None and loaded["verdict"] == "H001 supported."
    with pytest.raises(narrative.NarrativeError):
        narrative.read(
            tmp_path, "iteration9", "step-1", repo_root=tmp_path, figures=["a.png", "c.png"]
        )
