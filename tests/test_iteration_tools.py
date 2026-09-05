"""The iteration tools: the folder gate and the scaffolder, on a throwaway repository."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gate():
    return load("check_iteration")


@pytest.fixture(scope="module")
def scaffold():
    return load("new_iteration")


SELECTORS = {
    "alleles": {
        "a": {"table": "results.t", "where": [["gene", "=", "G"]]},
        "b": {"table": "results.t", "where": [["gene", "=", "H"]]},
    },
    "rows": [
        {"variant": "a", "partner": "b", "epcr": 0.9},
        {"variant": "a", "epcr": 0.1, "finding_type": "secondary"},
    ],
    "hypotheses": [
        {"label": "ab", "alleles": ["a", "b"], "prior": 0.8},
        {"label": "a?", "alleles": ["a", "_unknown_1"], "prior": 0.2},
    ],
}
FORM = {str(n): f"answer {n}" for n in range(7, 19)} | {"8": "1"}


def make_repo(tmp_path: Path, state: str = "ready") -> Path:
    root = tmp_path / "repo"
    folder = root / "submissions" / "track1" / "iteration-1"
    folder.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    standing = {"draft": "draft — nothing built", "ready": "built and rehearsed; **not uploaded**"}[
        state
    ]
    csv = root / "build" / "submission" / "track1_submission_v1.csv"
    csv.parent.mkdir(parents=True)
    csv.write_bytes(b"proband_id\nPROBAND01\n")
    import hashlib

    digest = hashlib.sha256(csv.read_bytes()).hexdigest()
    (folder / "README.md").write_text(
        f"# Track 1 — iteration 1\n\n**Standing:** {standing}.\n\n"
        f"CSV `build/submission/track1_submission_v1.csv` sha256 `{digest}`\n"
    )
    (folder / "report.md").write_text("# Report\n\n**Standing:** written.\n")
    (folder / "spec.selectors.json").write_text(json.dumps(SELECTORS))
    (folder / "methods-form.json").write_text(json.dumps(FORM))
    (folder / "decode-table.md").write_text("| a |\n")
    time.sleep(0.01)
    (folder / "user_track1_report.pdf").write_bytes(b"%PDF")
    (folder / "user_track1_methods_form.xlsx").write_bytes(b"PK")
    steps = root / "src" / "mva" / "science"
    steps.mkdir(parents=True)
    (steps / "steps.py").write_text('ITERATION = "iteration1"\n')
    (root / "docs" / "iteration1").mkdir(parents=True)
    (root / "docs" / "iteration1" / "README.md").write_text(
        "# Iteration 1\n\n**Standing:** open.\n"
    )
    return root


def test_a_complete_ready_folder_passes(gate, tmp_path):
    root = make_repo(tmp_path)
    report = gate.check_folder(root / "submissions/track1/iteration-1", root)
    assert report.state == "ready"
    assert report.problems == []


def test_a_stale_pdf_and_a_placeholder_fail(gate, tmp_path):
    root = make_repo(tmp_path)
    folder = root / "submissions/track1/iteration-1"
    time.sleep(0.01)
    (folder / "report.md").write_text("# Report\n\n**Standing:** written.\n\nTODO finish §3\n")
    problems = gate.check_folder(folder, root).problems
    assert any("older than report.md" in p for p in problems)
    assert any("placeholder" in p for p in problems)


def test_form_abstract_limit_and_model_number(gate, tmp_path):
    root = make_repo(tmp_path)
    folder = root / "submissions/track1/iteration-1"
    form = FORM | {"18": "word " * 501, "8": "2", "12": ""}
    (folder / "methods-form.json").write_text(json.dumps(form))
    os.utime(folder / "user_track1_methods_form.xlsx")
    problems = gate.check_folder(folder, root).problems
    assert any("501 words" in p for p in problems)
    assert any("model number" in p for p in problems)
    assert any("row 12 unanswered" in p for p in problems)


def test_selector_consistency(gate, tmp_path):
    root = make_repo(tmp_path)
    folder = root / "submissions/track1/iteration-1"
    bad = json.loads(json.dumps(SELECTORS))
    bad["rows"][1]["variant"] = "zzz"
    bad["rows"][1]["epcr"] = 0.95  # not descending
    bad["alleles"]["a"]["pos"] = 123
    (folder / "spec.selectors.json").write_text(json.dumps(bad))
    problems = gate.check_folder(folder, root).problems
    assert any("'zzz' is not a declared allele" in p for p in problems)
    assert any("strictly descending" in p for p in problems)
    assert any("carries a position" in p for p in problems)


def test_wrong_digest_fails_and_draft_is_lenient(gate, tmp_path):
    root = make_repo(tmp_path)
    (root / "build/submission/track1_submission_v1.csv").write_bytes(b"changed")
    assert any(
        "sha256 does not match" in p
        for p in gate.check_folder(root / "submissions/track1/iteration-1", root).problems
    )
    draft = make_repo(tmp_path / "d", state="draft")
    folder = draft / "submissions/track1/iteration-1"
    for name in ("user_track1_report.pdf", "user_track1_methods_form.xlsx", "decode-table.md"):
        (folder / name).unlink()
    report = gate.check_folder(folder, draft)
    assert report.state == "draft" and report.problems == []


def test_frozen_folder_with_uncommitted_changes_fails(gate, tmp_path):
    root = make_repo(tmp_path)
    folder = root / "submissions/track1/iteration-1"
    readme = folder / "README.md"
    readme.write_text(
        readme.read_text().replace("**Standing:**", "> **Frozen:** 2026-09-06\n\n**Standing:**")
    )
    problems = gate.check_folder(
        folder, root
    ).problems  # nothing committed yet: everything is a change
    assert any("uncommitted changes" in p for p in problems)


def test_scaffolder_freezes_opens_and_bumps(scaffold, tmp_path):
    root = make_repo(tmp_path)
    # the scaffolder reads the step map from <root>/src; give it a two-step map
    (root / "src/mva/science/steps.py").write_text(
        'ITERATION = "iteration1"\n'
        "class S:\n"
        "    def __init__(self, slug, title, goal):\n"
        "        self.slug, self.title, self.goal = slug, title, goal\n"
        "def research_steps():\n"
        "    return [S('step-1', 'One', 'Goal one?'), S('step-6', 'Six', 'Goal six?')]\n"
    )
    plan = scaffold.Plan(root, "track1", 1, "partial match rank 1", True, "2026-09-06")
    scaffold.run(plan, dry_run=False)

    assert (
        "**Frozen:** 2026-09-06" in (root / "submissions/track1/iteration-1/README.md").read_text()
    )
    assert "**Frozen:** 2026-09-06" in (root / "docs/iteration1/README.md").read_text()
    assert (root / "docs/iteration2/step-1/README.md").is_file()
    assert (root / "docs/iteration2/step-6/methodology/README.md").is_file()
    assert "Goal six?" in (root / "docs/iteration2/README.md").read_text()
    new = root / "submissions/track1/iteration-2"
    assert json.loads((new / "methods-form.json").read_text())["8"] == "2"
    assert json.loads((new / "spec.selectors.json").read_text()) == SELECTORS
    assert "partial match rank 1" in (new / "README.md").read_text()
    assert 'ITERATION = "iteration2"' in (root / "src/mva/science/steps.py").read_text()
    with pytest.raises(SystemExit, match="already exists"):
        scaffold.run(plan, dry_run=False)


def test_scaffolder_dry_run_writes_nothing(scaffold, tmp_path, capsys):
    root = make_repo(tmp_path)
    (root / "src/mva/science/steps.py").write_text(
        'ITERATION = "iteration1"\n'
        "class S:\n    def __init__(s, a, b, c): s.slug, s.title, s.goal = a, b, c\n"
        "def research_steps(): return [S('step-1', 'One', 'Goal?')]\n"
    )
    plan = scaffold.Plan(root, "track1", 1, "no match", True, "2026-09-06")
    scaffold.run(plan, dry_run=True)
    assert not (root / "docs/iteration2").exists()
    assert "would write" in capsys.readouterr().out
    shutil.rmtree(root)
