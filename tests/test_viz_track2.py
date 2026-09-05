"""The Track 2 endpoint: five TSVs, their manifests, the card, and the answer with no database.

A synthetic ``ressources/track2/`` is written into ``tmp_path`` and the reader is pointed at
it, so a failure here names the **contract** — the typing rule, the catalogue, the lineage
fallback, the hypothesis link — and never the real snapshot's current contents or the
network.

**Every value in this file is fabricated and no genomic position appears anywhere in it.**
Track 2 carries no patient data by construction: gene symbols, drug names, trial ids and
citations only.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mva.viz import queries, submissions_reader, track2, track2_catalog
from mva.viz import track2_reader as reader
from mva.viz.app import create_app
from mva.viz.cache import Cache
from mva.warehouse import track2_lineage as recorder

CARD = {
    "version": 3,
    "_standing": "written from the research record (H003-H009, methodology 070-074)",
    "gene": {"symbol": "GENEA", "uniprot": "P00000"},
    "mechanism": {"class": "loss-of-function", "status": "inferred from Track 1 (H009)"},
}

SNAPSHOT = {"built_at": "2099-01-01T00:00:00+00:00", "rows": {"targets": 2}}

TSV = {
    "targets": "symbol\trole\tdirection_ids\tpathways\tuniprot\n"
    "GENEA\tseed\tD1|D3\t\tP00000\n"
    "GENEB\tpathway\t\tR-HSA-1|R-HSA-2\tP00001\n",
    "drug_candidates": "drug_name\tdrug_id\ttarget_symbol\tmax_phase\tapproved\tfda_label\tatc\n"
    "DRUGONE\tCHEMBL1\tGENEA\t4\ttrue\tLBL1\tL01\n"
    "DRUGTWO\tCHEMBL2\tGENEB\t\tfalse\t\t\n",
    "trials": "nct_id\ttitle\tphase\tconditions\nNCT00000001\tA study\tPHASE2\tOne|Two\n",
    "literature": "pmid\ttitle\tyear\n12345678\tA paper\t2099\n",
    "pathways": "st_id\tdisplay_name\tmatched\tn_participants\n"
    "R-HSA-1\tA matching pathway\ttrue\t7\n",
}

MANIFEST = {
    "built_at": "2099-01-01T00:00:00+00:00",
    "code_version": "abc1234",
    "method": "a fabricated method sentence",
    "inputs": [
        {
            "name": "svc",
            "url": "https://svc.example/api",
            "version": None,
            "retrieved_from": "2099-01-01T00:00:00+00:00",
            "retrieved_at": "2099-01-01T00:01:00+00:00",
            "sha256": "a" * 64,
        }
    ],
}

REGISTER = {
    "hypotheses": [
        {
            "id": "H010",
            "step": "step-8",
            "statement": "a fabricated mechanism claim",
            "prediction": "a fabricated prediction",
            "refuted_by": "a fabricated refutation condition",
            "status": "proposed",
            "confidence": None,
            "revisions": 2,
        },
        {"id": "H003", "step": "step-2", "statement": "not a Track 2 claim", "revisions": 1},
    ]
}

ITERATION_README = """# Track 9 — iteration 1

**Standing:** built and rehearsed; **not uploaded**.

The verdict rests on H003 and H009.
"""

SELECTORS: dict = {
    "alleles": {
        "stop": {
            "table": "results.coding_candidates",
            "where": [["gene", "=", "GENEA"]],
        }
    },
    "rows": [{"variant": "stop", "epcr": 0.9, "label": "stop"}],
    "hypotheses": [],
}


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A repository root with a Track 2 snapshot, a register and one iteration folder."""
    directory = tmp_path / reader.TRACK2_DIR
    directory.mkdir(parents=True)
    (directory / "mechanism.json").write_text(json.dumps(CARD), encoding="utf-8")
    (directory / "snapshot.json").write_text(json.dumps(SNAPSHOT), encoding="utf-8")
    for table, text in TSV.items():
        (directory / f"{table}.tsv").write_text(text, encoding="utf-8")
        manifest = {
            **MANIFEST,
            "name": table,
            "outputs": [
                {
                    "path": f"{reader.TRACK2_DIR}/{table}.tsv",
                    "sha256": "f" * 64,
                    "rows": text.count("\n") - 1,
                }
            ],
        }
        (directory / f"{table}.provenance.json").write_text(json.dumps(manifest), encoding="utf-8")
    register = tmp_path / "docs"
    register.mkdir()
    (register / "science-register.json").write_text(json.dumps(REGISTER), encoding="utf-8")
    folder = tmp_path / "submissions" / "track9" / "iteration-1"
    folder.mkdir(parents=True)
    (folder / "README.md").write_text(ITERATION_README, encoding="utf-8")
    (folder / "spec.selectors.json").write_text(json.dumps(SELECTORS), encoding="utf-8")
    return tmp_path


# --- the reader --------------------------------------------------------------------


def test_a_row_is_typed_by_the_catalogue_and_an_empty_field_means_unknown(root: Path) -> None:
    _, rows = reader.read_table("drug_candidates", root)
    assert rows[0] == {
        "drug_name": "DRUGONE",
        "drug_id": "CHEMBL1",
        "target_symbol": "GENEA",
        "max_phase": 4,
        "approved": True,
        "fda_label": "LBL1",
        "atc": ["L01"],
    }
    unknown = rows[1]
    assert unknown["max_phase"] is None, "no source stated a phase — not zero"
    assert unknown["approved"] is False, "a checked negative, unlike max_phase"
    assert unknown["fda_label"] == "", "never checked; empty text, not false"
    assert unknown["atc"] == []


def test_a_list_field_is_split_on_the_pipe(root: Path) -> None:
    _, rows = reader.read_table("targets", root)
    assert rows[0]["direction_ids"] == ["D1", "D3"]
    assert rows[0]["pathways"] == []
    assert rows[1]["pathways"] == ["R-HSA-1", "R-HSA-2"]


def test_the_catalogue_quotes_the_manifest_and_describes_every_column(root: Path) -> None:
    header, rows = reader.read_table("pathways", root)
    entry = reader.catalog_entry("pathways", header, len(rows), root)
    assert entry["method"] == MANIFEST["method"]
    assert entry["code_version"] == "abc1234"
    assert entry["sha256"] == "f" * 64
    assert entry["inputs"] == [
        {
            "name": "svc",
            "url": "https://svc.example/api",
            "retrieved_at": "2099-01-01T00:01:00+00:00",
            "version": None,
            "sha256": "a" * 64,
        }
    ]
    assert [column["name"] for column in entry["columns"]] == header
    assert all(column["description"] for column in entry["columns"])


def test_every_column_the_snapshot_writes_has_a_description() -> None:
    """The dictionary is checked against the writer's own column order, not against a copy."""
    from mva.drugs import tables as writer

    declared = {
        "targets": writer.TARGET_COLUMNS,
        "drug_candidates": writer.CANDIDATE_COLUMNS,
        "trials": writer.TRIAL_COLUMNS,
        "literature": writer.LITERATURE_COLUMNS,
        "pathways": writer.PATHWAY_COLUMNS,
    }
    for table, columns in declared.items():
        missing = [name for name in columns if name not in track2_catalog.COLUMNS[table]]
        assert not missing, f"{table} columns with no plain-English description: {missing}"


def test_an_unknown_column_is_shown_with_a_null_description_not_a_guess() -> None:
    described = track2_catalog.describe("targets", ["symbol", "invented_column"])
    assert described[1] == {"name": "invented_column", "type": "string", "description": None}


def test_a_missing_snapshot_is_an_empty_answer_not_an_error(tmp_path: Path) -> None:
    rows, catalog = reader.tables(tmp_path)
    assert catalog == []
    assert all(value == [] for value in rows.values())
    assert reader.card(tmp_path) == {}


def test_a_cited_range_of_claims_is_expanded(root: Path) -> None:
    assert reader.cited_hypotheses(reader.card_text(root)) == [
        "H003",
        "H004",
        "H005",
        "H006",
        "H007",
        "H008",
        "H009",
    ]


def test_the_register_block_is_the_step_8_claims_as_filed(root: Path) -> None:
    rows = reader.register(REGISTER["hypotheses"], track2.STEP)
    assert [row["hypothesis_id"] for row in rows] == ["H010"]
    assert rows[0]["prediction"] == "a fabricated prediction"
    assert rows[0]["refuted_by"] == "a fabricated refutation condition"
    assert rows[0]["confidence"] is None, "no confidence is committed before the oracle replies"
    assert rows[0]["revision"] == 2


# --- the route ---------------------------------------------------------------------


@pytest.fixture
def client(root: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """The app pointed at the synthetic root, with every database read raising."""

    def unreachable(*args: object, **kwargs: object) -> list:
        raise RuntimeError("no credentials in this test")

    monkeypatch.setattr(queries.access, "fetch", unreachable)
    monkeypatch.setattr(reader, "DEFAULT_ROOT", root)
    monkeypatch.setattr(submissions_reader, "DEFAULT_ROOT", root)
    monkeypatch.chdir(root)
    return TestClient(create_app(cache=Cache(root / "cache")))


def test_the_endpoint_answers_with_the_envelope_and_every_block(client: TestClient) -> None:
    body = client.get("/api/track2").json()
    assert body["source"] == track2.SOURCE
    assert body["cached_at"] is not None
    data = body["data"]
    assert data["card"] == CARD
    assert data["summary"] == SNAPSHOT
    assert [entry["table"] for entry in data["catalog"]] == list(reader.TABLES)
    assert len(data["targets"]) == 2
    assert len(data["candidates"]) == 2
    assert [row["nct_id"] for row in data["trials"]] == ["NCT00000001"]
    assert [row["pmid"] for row in data["literature"]] == ["12345678"]
    assert [row["st_id"] for row in data["pathways"]] == ["R-HSA-1"]


def test_lineage_degrades_to_the_manifests_own_claims(client: TestClient) -> None:
    """No database: no edges, the exception class in the note, the sources still there."""
    lineage = client.get("/api/track2").json()["data"]["lineage"]
    assert lineage["available"] is False
    assert "RuntimeError" in lineage["note"]
    assert lineage["edges"] == []
    kinds = {source["kind"] for source in lineage["sources"]}
    assert kinds == {"card", "api", "submission", "table"}
    card = next(source for source in lineage["sources"] if source["kind"] == "card")
    assert card["ref"] == recorder.CARD_FILE
    assert card["version"] == "v3"
    assert len(card["sha256"]) == 64


def test_an_iteration_is_linked_by_the_claims_it_shares_with_the_card(
    client: TestClient,
) -> None:
    linked = client.get("/api/track2").json()["data"]["linked_iterations"]
    assert [(row["track"], row["number"], row["state"]) for row in linked] == [
        ("track9", 1, "ready")
    ]
    assert linked[0]["hypotheses"] == ["H003", "H009"]


def test_an_iteration_sharing_no_claim_is_not_linked(client: TestClient, root: Path) -> None:
    folder = root / "submissions" / "track9" / "iteration-2"
    folder.mkdir()
    (folder / "README.md").write_text("**Standing:** draft. It argues H001.\n", encoding="utf-8")
    (folder / "spec.selectors.json").write_text(json.dumps(SELECTORS), encoding="utf-8")
    linked = client.get("/api/track2?refresh=true").json()["data"]["linked_iterations"]
    assert [row["number"] for row in linked] == [1]


def test_the_strategy_is_the_static_plan_with_its_dependencies(client: TestClient) -> None:
    phases = client.get("/api/track2").json()["data"]["strategy"]
    assert [phase["id"] for phase in phases] == [
        "handoff",
        "snapshot",
        "ranking",
        "report",
        "verdicts",
        "merge",
    ]
    assert {phase["status"] for phase in phases} <= {"done", "open", "waiting"}
    known = {phase["id"] for phase in phases}
    for phase in phases:
        assert set(phase["depends_on"]) <= known, "a phase depends on something that exists"


def test_refresh_rebuilds_the_cached_payload(client: TestClient, root: Path) -> None:
    """The whole payload is one cache entry, so an edited table needs ``?refresh=true``."""
    first = client.get("/api/track2").json()["data"]
    path = root / reader.TRACK2_DIR / "pathways.tsv"
    path.write_text(TSV["pathways"] + "R-HSA-9\tAnother\tfalse\t0\n", encoding="utf-8")
    assert client.get("/api/track2").json()["data"] == first
    refreshed = client.get("/api/track2?refresh=true").json()["data"]
    assert [row["st_id"] for row in refreshed["pathways"]] == ["R-HSA-1", "R-HSA-9"]
