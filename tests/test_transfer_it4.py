"""tools/transfer_it4.py relabel: MVA text is replaced, recorded, and manifests re-hashed."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

from mva.drugs import provenance

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "transfer_it4", ROOT / "tools" / "transfer_it4.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _case(tmp_path: Path) -> tuple[Path, Path, Path]:
    home = tmp_path / "CASE"
    (home / "generators").mkdir(parents=True)
    table = home / "generators" / "lincs.tsv"
    table.write_text("drug\tevidence\nx\treverses the BUB1B-loss signature\n", encoding="utf-8")
    sha, size = provenance.digest(table)
    manifest = home / "generators" / "lincs.provenance.json"
    entry = {"path": provenance.repo_relative(table), "sha256": sha, "bytes": size, "rows": 1}
    manifest.write_text(json.dumps({"outputs": [entry]}), encoding="utf-8")
    rules = {
        "substitutions": [
            {"file": str(table), "from": "BUB1B-loss", "to": "BLM-loss", "gap": 7},
            {"file": str(table), "from": "never present", "to": "x", "gap": 0},
        ]
    }
    (home / "relabel.json").write_text(json.dumps(rules), encoding="utf-8")
    return home, table, manifest


def test_relabel_replaces_records_and_rehashes(tool: ModuleType, tmp_path: Path) -> None:
    home, table, manifest = _case(tmp_path)
    assert tool.do_relabel(home) == 0
    assert "BLM-loss" in table.read_text() and "BUB1B" not in table.read_text()
    recorded = json.loads((home / "transfer.provenance.json").read_text())
    assert [s["replaced"] for s in recorded["substitutions"]] == [1, 0]
    digest = json.loads(manifest.read_text())["outputs"][0]
    assert (digest["sha256"], digest["bytes"]) == provenance.digest(table)


def test_scan_skips_the_case_file(tool: ModuleType, tmp_path: Path, capsys) -> None:
    home, _, _ = _case(tmp_path)
    (home / "case.json").write_text('{"note": "the child"}', encoding="utf-8")
    tool.do_scan(home)
    out = capsys.readouterr().out
    assert "lincs.tsv" in out and "case.json" not in out
