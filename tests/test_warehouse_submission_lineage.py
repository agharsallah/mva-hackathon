"""Recording a submission's lineage: the edges it implies, and appending them twice.

The edge list is append-only, so the interesting property is not "the write happened" but
"the second write is a no-op". An in-memory DuckDB stands in for the hosted PostgreSQL —
the production connection is DuckDB with the server attached as ``pg``, so attaching an
in-memory database under the same alias exercises the real SQL rather than a mock of it.

Every value here is fabricated. No genomic position appears: a selector spec is a table
plus a ``WHERE`` clause by design, and that is the whole point of recording it.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from mva.warehouse import submission_lineage
from mva.warehouse.lineage_edges import ensure_lineage_table

SCHEMA = "warehouse"

SELECTORS: dict = {
    "alleles": {
        "stop": {
            "table": "results.coding_candidates",
            "where": [["gene", "=", "GENEA"], ["consequence", "like", "%stop_gained%"]],
        },
        "missense": {
            "table": "results.coding_candidates",
            "where": [["gene", "=", "GENEA"], ["gnomad_af", "is", None]],
        },
        "intron": {
            "table": "results.panel_candidates",
            "where": [["gene", "=", "GENEA"]],
        },
    },
    "rows": [
        {"variant": "stop", "partner": "missense", "epcr": 0.9, "label": "stop+missense"},
        {"variant": "intron", "epcr": 0.2, "label": "intron"},
    ],
    "hypotheses": [],
}

DIGEST = "aaaabbbbccccddddeeeeffff0000111122223333444455556666777788889999"

README = f"""# Track 9 — iteration 3

**Standing:** built and rehearsed; **not uploaded**.

| Predictions CSV | `build/submission/track9_submission_v3.csv` | sha256 `{DIGEST}` |
"""


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A repository root holding one iteration folder and the clinical document."""
    folder = tmp_path / "submissions" / "track9" / "iteration-3"
    folder.mkdir(parents=True)
    (folder / "spec.selectors.json").write_text(json.dumps(SELECTORS), encoding="utf-8")
    (folder / "README.md").write_text(README, encoding="utf-8")
    clinical = tmp_path / submission_lineage.CLINICAL_FILE
    clinical.parent.mkdir(parents=True)
    clinical.write_text("HP:0002859 Rhabdomyosarcoma\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def folder(root: Path) -> Path:
    return root / "submissions" / "track9" / "iteration-3"


@pytest.fixture
def connection(tmp_path: Path):
    """DuckDB with an in-memory database attached under the alias production uses."""
    con = duckdb.connect()
    con.execute("ATTACH ':memory:' AS pg")
    con.execute(f"CREATE SCHEMA pg.{SCHEMA}")
    ensure_lineage_table(con, SCHEMA)
    return con


def recorded(connection) -> list[tuple]:
    return connection.execute(
        f"SELECT target_schema, target_table, target_rows, source_kind, source_ref, "
        f"source_version, source_sha256, tool, notes "
        f"FROM pg.{SCHEMA}.data_lineage ORDER BY source_kind, source_ref"
    ).fetchall()


def test_the_planned_edges_are_one_per_table_plus_the_file_and_the_clinical_document(
    folder: Path, root: Path
) -> None:
    edges = submission_lineage.planned_edges(folder, root)
    assert [(edge["source_kind"], edge["source_ref"]) for edge in edges] == [
        ("table", "results.coding_candidates"),
        ("table", "results.panel_candidates"),
        ("file", "submissions/track9/iteration-3/spec.selectors.json"),
        ("clinical", submission_lineage.CLINICAL_FILE),
    ]
    assert all(edge["target_schema"] == "submissions" for edge in edges)
    assert all(edge["target_table"] == "track9/iteration-3" for edge in edges)
    assert all(edge["target_rows"] == 2 for edge in edges)
    assert all(edge["tool"] == "resolve_submission_spec" for edge in edges)


def test_the_two_files_are_recorded_by_digest_and_the_csv_only_by_claim(
    folder: Path, root: Path
) -> None:
    """The predictions CSV holds coordinates and is never hashed here — only quoted."""
    by_kind = {edge["source_kind"]: edge for edge in submission_lineage.planned_edges(folder, root)}
    assert len(str(by_kind["file"]["source_sha256"])) == 64
    assert len(str(by_kind["clinical"]["source_sha256"])) == 64
    assert by_kind["clinical"]["source_version"] == submission_lineage.CLINICAL_VERSION
    assert by_kind["file"]["notes"] == f"csv sha256 {DIGEST}"


def test_a_readme_with_no_digest_says_so_rather_than_inventing_one(
    folder: Path, root: Path
) -> None:
    (folder / "README.md").write_text("# no digest here\n", encoding="utf-8")
    edges = submission_lineage.planned_edges(folder, root)
    assert edges[0]["notes"] == "csv sha256 not recorded in the README"


def test_appending_writes_every_edge_once(connection, folder: Path, root: Path) -> None:
    edges = submission_lineage.planned_edges(folder, root)
    result = submission_lineage.append_edges(connection, SCHEMA, edges)
    assert (result.appended, result.already_present) == (4, 0)
    assert len(recorded(connection)) == 4
    assert "4 edge(s) appended" in result.describe()


def test_appending_again_is_a_no_op(connection, folder: Path, root: Path) -> None:
    """The edge list is append-only; a second resolve must not double every row."""
    edges = submission_lineage.planned_edges(folder, root)
    submission_lineage.append_edges(connection, SCHEMA, edges)
    before = recorded(connection)
    result = submission_lineage.append_edges(connection, SCHEMA, edges)
    assert (result.appended, result.already_present) == (0, 4)
    assert recorded(connection) == before


def test_a_changed_selector_file_is_a_new_edge_not_an_edit(
    connection, folder: Path, root: Path
) -> None:
    """A different digest is a different file, so the honest record is one more edge."""
    submission_lineage.append_edges(
        connection, SCHEMA, submission_lineage.planned_edges(folder, root)
    )
    changed = json.loads(json.dumps(SELECTORS))
    changed["alleles"]["intron"]["where"].append(["is_rare_recessive", "=", True])
    (folder / "spec.selectors.json").write_text(json.dumps(changed), encoding="utf-8")
    result = submission_lineage.append_edges(
        connection, SCHEMA, submission_lineage.planned_edges(folder, root)
    )
    assert (result.appended, result.already_present) == (1, 3)
    files = [row for row in recorded(connection) if row[3] == "file"]
    assert len({row[6] for row in files}) == 2, "two digests, two edges, nothing updated"


def test_edges_for_a_different_iteration_do_not_count_as_present(
    connection, folder: Path, root: Path
) -> None:
    other = root / "submissions" / "track9" / "iteration-4"
    other.mkdir()
    (other / "spec.selectors.json").write_text(json.dumps(SELECTORS), encoding="utf-8")
    (other / "README.md").write_text(README, encoding="utf-8")
    submission_lineage.append_edges(
        connection, SCHEMA, submission_lineage.planned_edges(folder, root)
    )
    result = submission_lineage.append_edges(
        connection, SCHEMA, submission_lineage.planned_edges(other, root)
    )
    assert result.appended == 4
    assert len(recorded(connection)) == 8


def test_a_missing_clinical_document_is_an_empty_digest_not_a_failure(
    folder: Path, root: Path
) -> None:
    (root / submission_lineage.CLINICAL_FILE).unlink()
    edges = submission_lineage.planned_edges(folder, root)
    clinical = next(edge for edge in edges if edge["source_kind"] == "clinical")
    assert clinical["source_sha256"] == ""
