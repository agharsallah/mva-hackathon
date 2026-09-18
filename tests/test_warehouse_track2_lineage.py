"""Recording the Track 2 tables' lineage: the edges they imply, and appending them twice.

The edge list is append-only, so the interesting property is not "the write happened" but
"the second write is a no-op". An in-memory DuckDB stands in for the hosted PostgreSQL —
the production connection is DuckDB with the server attached as ``pg``, so attaching an
in-memory database under the same alias exercises the real SQL rather than a mock of it.

Every value here is fabricated: two synthetic manifests naming two hosts and a card with a
made-up version. No genomic position appears — a drug table names genes and molecules, and
a manifest names URLs, digests and counts.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import duckdb
import pytest

from mva.warehouse import track2_lineage
from mva.warehouse.lineage_edges import ensure_lineage_table

SCHEMA = "warehouse"

CARD = {"version": 7, "gene": "GENEA", "disease": "a fabricated syndrome"}

TARGETS_MANIFEST = {
    "name": "targets",
    "built_at": "2099-01-01T00:00:00+00:00",
    "code_version": "abc1234",
    "method": "expand the card's seeds through the pathway service",
    "inputs": [
        {
            "name": "pathwaydb",
            "url": "https://pathwaydb.example/ContentService",
            "version": None,
            "retrieved_from": "2099-01-01T00:00:00+00:00",
            "retrieved_at": "2099-01-01T00:01:00+00:00",
            "sha256": "a" * 64,
        }
    ],
    "outputs": [{"path": "ressources/track2/targets.tsv", "rows": 12}],
}

CANDIDATES_MANIFEST = {
    "name": "drug_candidates",
    "method": "one query per target against two drug services",
    "inputs": [
        {
            "name": "drugs-one",
            "url": "https://drugs.example/api/v4/graphql",
            "version": "release 24.1",
            "retrieved_from": "2099-01-01T00:02:00+00:00",
            "retrieved_at": "2099-01-01T00:03:00+00:00",
            "sha256": "b" * 64,
        },
        {
            "name": "drugs-one-again",
            "url": "https://drugs.example/api/v4/molecule",
            "version": None,
            "retrieved_from": "2099-01-01T00:04:00+00:00",
            "retrieved_at": "2099-01-01T00:05:00+00:00",
            "sha256": "c" * 64,
        },
        {
            "name": "drugs-two",
            "url": "https://other.example/api",
            "version": None,
            "retrieved_from": "2099-01-01T00:06:00+00:00",
            "retrieved_at": "2099-01-01T00:07:00+00:00",
            "sha256": "d" * 64,
        },
    ],
    "outputs": [{"path": "ressources/track2/drug_candidates.tsv", "rows": 40}],
}


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A repository root holding a card and two of the five manifests."""
    directory = tmp_path / track2_lineage.TRACK2_DIR
    directory.mkdir(parents=True)
    (directory / "mechanism.json").write_text(json.dumps(CARD), encoding="utf-8")
    (directory / "targets.provenance.json").write_text(
        json.dumps(TARGETS_MANIFEST), encoding="utf-8"
    )
    (directory / "drug_candidates.provenance.json").write_text(
        json.dumps(CANDIDATES_MANIFEST), encoding="utf-8"
    )
    return tmp_path


@pytest.fixture
def connection():
    """DuckDB with an in-memory database attached under the alias production uses."""
    con = duckdb.connect()
    con.execute("ATTACH ':memory:' AS pg")
    con.execute(f"CREATE SCHEMA pg.{SCHEMA}")
    ensure_lineage_table(con, SCHEMA)
    return con


def recorded(connection) -> list[tuple]:
    return connection.execute(
        f"SELECT target_table, source_kind, source_ref FROM pg.{SCHEMA}.data_lineage "
        f"WHERE target_schema = 'track2' ORDER BY target_table, source_kind, source_ref"
    ).fetchall()


def test_a_table_names_its_card_its_api_hosts_and_the_track_1_iteration(root: Path) -> None:
    edges = track2_lineage.table_edges(root / track2_lineage.TRACK2_DIR, "targets", root)
    assert [(edge["source_kind"], edge["source_ref"]) for edge in edges] == [
        ("card", track2_lineage.CARD_FILE),
        ("api", "pathwaydb.example"),
        ("submission", track2_lineage.SOURCE_ITERATION),
        # the fabricated card is version 7, past the version that first carried
        # iteration 2's measured facts, so the second submission edge is expected
        ("submission", track2_lineage.SOURCE_ITERATION_V3),
    ]
    assert all(edge["target_schema"] == "track2" for edge in edges)
    assert all(edge["target_rows"] == 12 for edge in edges)
    assert all(edge["tool"] == track2_lineage.TOOL for edge in edges)
    assert edges[0]["transform"] == TARGETS_MANIFEST["method"]


def test_the_card_is_recorded_by_version_and_digest(root: Path) -> None:
    card = track2_lineage.table_edges(root / track2_lineage.TRACK2_DIR, "targets", root)[0]
    expected = hashlib.sha256(json.dumps(CARD).encode("utf-8")).hexdigest()
    assert card["source_version"] == "v7"
    assert card["source_sha256"] == expected


def test_two_inputs_on_one_host_are_one_edge_with_a_rolled_up_digest(root: Path) -> None:
    """A host is the unit, not an input row: two endpoints of one API are one source."""
    edges = track2_lineage.table_edges(root / track2_lineage.TRACK2_DIR, "drug_candidates", root)
    hosts = [edge["source_ref"] for edge in edges if edge["source_kind"] == "api"]
    assert hosts == ["drugs.example", "other.example"]
    merged = next(edge for edge in edges if edge["source_ref"] == "drugs.example")
    assert (
        merged["source_sha256"] == hashlib.sha256(("b" * 64 + "c" * 64).encode("utf-8")).hexdigest()
    )


def test_a_stated_release_is_used_and_a_silent_api_gets_its_retrieval_window(
    root: Path,
) -> None:
    """The window is not a version and is never labelled one; it is what there is."""
    edges = track2_lineage.table_edges(root / track2_lineage.TRACK2_DIR, "drug_candidates", root)
    by_ref = {edge["source_ref"]: edge for edge in edges}
    assert by_ref["drugs.example"]["source_version"] == "release 24.1"
    assert by_ref["other.example"]["source_version"] == (
        "retrieved 2099-01-01T00:06:00+00:00..2099-01-01T00:07:00+00:00"
    )


def test_only_the_derived_tables_name_the_target_set(root: Path) -> None:
    """``targets`` cannot be derived from itself; ``drug_candidates`` is."""
    directory = root / track2_lineage.TRACK2_DIR
    targets = track2_lineage.table_edges(directory, "targets", root)
    candidates = track2_lineage.table_edges(directory, "drug_candidates", root)
    assert not [edge for edge in targets if edge["source_kind"] == "table"]
    assert [edge["source_ref"] for edge in candidates if edge["source_kind"] == "table"] == [
        track2_lineage.TARGET_TABLE_REF
    ]


def test_a_table_with_no_manifest_contributes_no_edges(root: Path) -> None:
    """A checkout whose snapshot never ran has nothing to declare for that table."""
    assert track2_lineage.table_edges(root / track2_lineage.TRACK2_DIR, "trials", root) == []
    planned = track2_lineage.planned_edges(root)
    assert {str(edge["target_table"]) for edge in planned} == {"targets", "drug_candidates"}


def test_appending_writes_every_edge_once(connection, root: Path) -> None:
    edges = track2_lineage.planned_edges(root)
    result = track2_lineage.append_edges(connection, SCHEMA, edges)
    assert (result.appended, result.already_present) == (len(edges), 0)
    assert len(recorded(connection)) == len(edges)
    assert f"{len(edges)} edge(s) appended" in result.describe()


def test_appending_again_is_a_no_op(connection, root: Path) -> None:
    """The edge list is append-only; a second run must not double every row."""
    edges = track2_lineage.planned_edges(root)
    track2_lineage.append_edges(connection, SCHEMA, edges)
    before = recorded(connection)
    again = track2_lineage.append_edges(connection, SCHEMA, edges)
    assert (again.appended, again.already_present) == (0, len(edges))
    assert recorded(connection) == before


def test_a_changed_card_is_a_new_edge_not_an_edit(connection, root: Path) -> None:
    """Idempotency keys on the digest, so a revised card records itself as a new source."""
    track2_lineage.append_edges(connection, SCHEMA, track2_lineage.planned_edges(root))
    before = len(recorded(connection))
    (root / track2_lineage.CARD_FILE).write_text(
        json.dumps({**CARD, "version": 8}), encoding="utf-8"
    )
    again = track2_lineage.append_edges(connection, SCHEMA, track2_lineage.planned_edges(root))
    assert again.appended == 2, "one new card edge per table that has a manifest"
    assert len(recorded(connection)) == before + 2


LADDER_MANIFEST = {
    "name": "evidence_ladder",
    "built_by": "tools/track2_enrich.py",
    "method": "one row per (drug, direction), rung = max(automated, curated)",
    "inputs": [
        {
            "name": "track2.drug_candidates",
            "path": "ressources/track2/drug_candidates.tsv",
            "sha256": "e" * 64,
        },
        {"name": "track2.evidence", "path": "ressources/track2/evidence.tsv", "sha256": "f" * 64},
        {"name": "openfda", "url": "https://labels.example/drug/label.json", "sha256": "1" * 64},
    ],
    "outputs": [{"path": "ressources/track2/evidence_ladder.tsv", "rows": 5}],
}


def test_a_step_7_table_points_at_the_tables_it_read_and_names_its_own_tool(root: Path) -> None:
    directory = root / track2_lineage.TRACK2_DIR
    (directory / "evidence_ladder.provenance.json").write_text(
        json.dumps(LADDER_MANIFEST), encoding="utf-8"
    )
    edges = track2_lineage.table_edges(directory, "evidence_ladder", root)
    kinds = [(edge["source_kind"], edge["source_ref"]) for edge in edges]
    assert ("api", "labels.example") in kinds
    assert ("table", "track2.drug_candidates") in kinds
    assert ("table", "track2.evidence") in kinds
    table_edge = next(e for e in edges if e["source_ref"] == "track2.evidence")
    assert table_edge["source_sha256"] == "f" * 64
    assert all(edge["tool"] == "tools/track2_enrich.py" for edge in edges)
    assert "evidence_ladder" in track2_lineage.ALL_TABLES


def test_a_decoy_input_keeps_its_folder_in_the_reference() -> None:
    assert (
        track2_lineage._table_ref("ressources/track2/decoys/XDH/drug_candidates.tsv")
        == "track2.decoys.XDH.drug_candidates"
    )


def test_a_card_below_version_3_writes_no_iteration_2_edge(tmp_path: Path) -> None:
    directory = tmp_path / track2_lineage.TRACK2_DIR
    directory.mkdir(parents=True)
    (directory / "mechanism.json").write_text(json.dumps({"version": 2}), encoding="utf-8")
    (directory / "targets.provenance.json").write_text(
        json.dumps(TARGETS_MANIFEST), encoding="utf-8"
    )
    edges = track2_lineage.table_edges(directory, "targets", tmp_path)
    refs = [edge["source_ref"] for edge in edges]
    assert track2_lineage.SOURCE_ITERATION in refs
    assert track2_lineage.SOURCE_ITERATION_V3 not in refs
