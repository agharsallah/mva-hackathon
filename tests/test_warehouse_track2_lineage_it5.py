"""Iteration 5's Track 2 lineage: filed entries only, the clinical document by file name,
and the transfer case walked recursively under its own target names.

Every manifest here is fabricated in a temporary checkout; no genomic position appears.
"""

from __future__ import annotations

import json
from pathlib import Path

from mva.warehouse.submission_lineage import CLINICAL_FILE
from mva.warehouse.track2_lineage_it5 import IT5_DIR, it5_edges

ENTRY = "docs/iteration5/step-1/methodology/999-fake.md"


def _checkout(tmp_path: Path) -> Path:
    for relative, text in (
        (ENTRY, "# fake entry\n"),
        (CLINICAL_FILE, "# fake terms\n"),
        (f"{IT5_DIR}/filed.tsv", "a\tb\n1\t2\n"),
        (f"{IT5_DIR}/draft.tsv", "a\n1\n"),
    ):
        (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / relative).write_text(text, encoding="utf-8")
    inputs = [{"name": "raw", "path": "build/raw.tsv", "sha256": "b" * 64}]
    for table, entry in (("filed", ENTRY), ("draft", "docs/x/work/draft.md (draft)")):
        manifest = {
            "built_by": "tools/fake.py",
            "entry": entry,
            "inputs": inputs,
            "sources": {"clinical": "the 8 HPO terms (Challenge_Clinical_Phenotype_1.md)"},
        }
        path = tmp_path / IT5_DIR / f"{table}.provenance.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
    return tmp_path


def test_only_tables_whose_entry_is_filed_are_recorded(tmp_path: Path) -> None:
    edges = it5_edges(_checkout(tmp_path))
    assert {e["target_table"] for e in edges} == {"it5.filed"}
    assert all(e["target_rows"] == 1 for e in edges)


def test_the_clinical_document_named_by_file_name_gets_one_edge(tmp_path: Path) -> None:
    edges = it5_edges(_checkout(tmp_path))
    clinical = [e for e in edges if e["source_kind"] == "clinical"]
    assert [e["source_ref"] for e in clinical] == [CLINICAL_FILE]
    assert len(clinical[0]["source_sha256"]) == 64  # type: ignore[arg-type]  # a str digest


def test_the_transfer_case_is_walked_and_named_by_its_path(tmp_path: Path) -> None:
    """A transfer table shares a file name with the first case's and must not share a target."""
    root = _checkout(tmp_path)
    table = root / IT5_DIR / "transfer/r1/filed.tsv"
    table.parent.mkdir(parents=True, exist_ok=True)
    table.write_text("a\tb\n1\t2\n", encoding="utf-8")
    table.with_name("filed.provenance.json").write_text(
        json.dumps(
            {
                "built_by": "tools/fake.py --card blm",
                "entry": ENTRY,
                "inputs": [{"name": "raw", "path": "build/raw.tsv", "sha256": "c" * 64}],
                "sources": {"clinical": "none"},  # published literature: no patient, no HPO term
            }
        ),
        encoding="utf-8",
    )
    edges = it5_edges(root)
    assert {e["target_table"] for e in edges} == {"it5.filed", "it5.transfer.r1.filed"}
    transfer = [e for e in edges if e["target_table"] == "it5.transfer.r1.filed"]
    assert [e["source_kind"] for e in transfer] == ["file"]  # no clinical edge for that case
