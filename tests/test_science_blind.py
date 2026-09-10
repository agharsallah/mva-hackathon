"""The blind gate: an iteration-2 entry declares what it read, and reads nothing banned.

The gate is procedural — the candidate gene is written all over the repository, so this
cannot be a secret. What it buys is auditability: a reviewer reads the same ``## Inputs``
tables the gate reads, and the checklist in the report is generated from them.
"""

from pathlib import Path

import pytest

from mva.science import blind

ENTRY = """# 084 — A question

## Inputs

| Source | What |
|---|---|
| clinical | the 8 HPO terms |
| public | HPO release 2026-08-01 |

## Verdict

Nothing yet.
"""


def _write(root: Path, step: str, name: str, text: str) -> Path:
    path = root / "iteration2" / step / "methodology" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_an_entry_declaring_its_inputs_passes(tmp_path):
    _write(tmp_path, "step-1", "084-a.md", ENTRY)
    report = blind.check(tmp_path, "iteration2")
    assert report.ok
    assert report.blind
    assert report.entries[0].inputs[0].startswith("Source")


def test_an_entry_without_an_inputs_section_is_refused(tmp_path):
    _write(tmp_path, "step-1", "084-a.md", "# 084 — A question\n\nNo inputs table.\n")
    report = blind.check(tmp_path, "iteration2")
    assert not report.ok
    assert "no '## Inputs' section" in report.problems[0]


@pytest.mark.parametrize("banned", sorted(blind.FORBIDDEN_INPUTS))
def test_naming_an_iteration_one_candidate_table_is_refused(tmp_path, banned):
    _write(tmp_path, "step-1", "084-a.md", ENTRY.replace("the 8 HPO terms", banned))
    report = blind.check(tmp_path, "iteration2")
    assert not report.ok
    assert banned in report.problems[0]


def test_after_the_unblinding_entry_the_candidate_tables_are_allowed(tmp_path):
    _write(tmp_path, "step-1", "084-a.md", ENTRY)
    _write(
        tmp_path,
        "step-6",
        "090-unblind.md",
        ENTRY.replace("# 084 — A question", "# 090 — Unblinding\n\n**Unblinds:** yes"),
    )
    _write(
        tmp_path,
        "step-6",
        "091-compare.md",
        ENTRY.replace("the 8 HPO terms", "results.gene_biallelic"),
    )
    report = blind.check(tmp_path, "iteration2")
    assert report.ok
    assert not report.blind
    assert report.unblinded_by.name == "090-unblind.md"


def test_the_unblinding_entry_itself_may_name_them(tmp_path):
    _write(
        tmp_path,
        "step-6",
        "090-unblind.md",
        ENTRY.replace("the 8 HPO terms", "results.gene_biallelic") + "\n**Unblinds:** yes\n",
    )
    assert blind.check(tmp_path, "iteration2").ok


def test_an_iteration_with_no_entries_yet_is_vacuously_blind(tmp_path):
    report = blind.check(tmp_path, "iteration2")
    assert report.ok and report.blind and report.entries == ()
