"""`mva.paths` — the repository-root anchor a server entry point uses at startup.

The bug it exists for: `mva-viz-api` started from `app/` resolved every repo-relative
reference default (`ressources/reference/structure_genes.tsv`, …) to nothing and answered
200 with an empty list, which reads as a finding rather than as a misconfiguration.
"""

import os
from pathlib import Path

from mva import paths


def test_repo_root_finds_this_checkout_regardless_of_cwd(tmp_path, monkeypatch):
    # The whole point: the answer comes from the module's own location, not the cwd.
    root = paths.repo_root()
    assert root is not None
    monkeypatch.chdir(tmp_path)
    assert paths.repo_root() == root
    assert all((root / marker).exists() for marker in paths.MARKERS)


def test_resolve_anchors_a_relative_path_and_leaves_an_absolute_one(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    resolved = paths.resolve("ressources/reference/structure_genes.tsv")
    assert resolved.is_absolute()
    assert resolved.is_file(), "the reference table must resolve from any working directory"
    absolute = tmp_path / "elsewhere.tsv"
    assert paths.resolve(absolute) == absolute


def test_anchor_cwd_moves_once_and_reports_nothing_when_already_home(tmp_path, monkeypatch):
    root = paths.repo_root()
    assert root is not None
    original = Path.cwd()
    try:
        os.chdir(tmp_path)
        assert paths.anchor_cwd() == tmp_path.resolve()
        assert Path.cwd().resolve() == root
        # Idempotent: a second call has nothing to say.
        assert paths.anchor_cwd() is None
    finally:
        os.chdir(original)
