"""The per-iteration data catalogue and the ``/api/iterations`` overview.

A synthetic repository is written into ``tmp_path`` — two methodology entries, a few data
files with and without manifests, a lineage ledger held in memory — so each test names one
rule of the contract: what counts as a mention, when a dataset is ``produced`` rather than
``cited``, which manifest belongs to which file, and what the answer is with no database.

**Every value here is fabricated; no genomic position appears anywhere in this file.**
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mva.viz import (
    iteration_catalog,
    iteration_manifest,
    iterations,
    queries,
    submissions_audit,
    submissions_reader,
)
from mva.viz.app import create_app
from mva.viz.cache import Cache
from mva.viz.submissions_lineage import Ledger

ENTRY_A = "docs/iteration9/step-1/methodology/901-the-first-run.md"
ENTRY_B = "docs/iteration9/step-2/methodology/902-the-second-run.md"

TEXT_A = """# 901 — the first run

Ran `mva-warehouse pg-load-x` into results.alpha_scores, then read `beta_calls` and
results.it9_* (a glob, not a table). The ledger is warehouse.data_lineage; the file
x/results.tsv is not a table. Wrote ressources/demo/made.tsv with tools/make_demo.py; read
ressources/demo/card.json, ressources/demo/named.tsv, ressources/demo/bare.tsv and
ressources/demo/made.provenance.json. Scratch: build/it9/scratch.parquet.
"""

TEXT_B = """# 902 — the second run

Read results.alpha_scores and `gamma` (a word two schemas share). Objects under
s3://bucket/source were read.
"""

EDGE_ALPHA = {
    "target_schema": "results",
    "target_table": "alpha_scores",
    "target_rows": 12,
    "source_kind": "table",
    "source_ref": "warehouse.raw",
    "source_sha256": "",
    "tool": "mva-warehouse pg-load-x",
    "produced_at": "2099-01-01T00:00:00",
    "notes": "",
    "is_current": True,
}
EDGE_BETA = EDGE_ALPHA | {
    "target_table": "beta_calls",
    "tool": "tools/other.py",
    "notes": "entry docs/iteration9/step-1/methodology/901-the-first-run.md",
}
EDGE_RAW = EDGE_ALPHA | {
    "target_schema": "warehouse",
    "target_table": "raw",
    "source_kind": "object",
    "source_ref": "s3://bucket/source/delivery.vcf.gz",
    "source_sha256": "f" * 64,
    "tool": "mva-warehouse vcf-ingest",
}
EDGE_CARD_INPUT = EDGE_ALPHA | {
    "target_table": "from_bare",
    "source_kind": "file",
    "source_ref": "ressources/demo/bare.tsv",
    "source_sha256": "e" * 64,
}
LEDGER = Ledger([EDGE_ALPHA, EDGE_BETA, EDGE_RAW, EDGE_CARD_INPUT], True, "4 edges")
KNOWN = {"results.gamma", "track2.gamma", "results.alpha_scores"}


def write(root: Path, relative: str, content: str | dict) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(content) if isinstance(content, dict) else content
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    iteration_manifest.clear()
    write(tmp_path, ENTRY_A, TEXT_A)
    write(tmp_path, ENTRY_B, TEXT_B)
    write(tmp_path, "ressources/demo/made.tsv", "a\n1\n")
    write(
        tmp_path,
        "ressources/demo/made.provenance.json",
        {
            "built_by": "tools/make_demo.py",
            "built_at": "2099-01-02T00:00:00+00:00",
            "inputs": [{"name": "results.alpha_scores", "sha256": "d" * 64}],
            "outputs": [{"path": "ressources/demo/made.tsv", "rows": 1, "sha256": "c" * 64}],
            "card": {"path": "ressources/demo/card.json"},
        },
    )
    write(tmp_path, "ressources/demo/card.json", {"_standing": "hand-written", "history": []})
    write(tmp_path, "ressources/demo/named.tsv", "a\n")
    write(tmp_path, "ressources/demo/group_provenance.json", {"outputs": {"named.tsv": 7}})
    write(tmp_path, "ressources/demo/bare.tsv", "a\n")
    return tmp_path


@pytest.fixture
def catalog(repo: Path) -> dict:
    return iteration_catalog.build(repo, [ENTRY_A, ENTRY_B], LEDGER, KNOWN, tracked=None)


def by_ref(catalog: dict) -> dict[str, dict]:
    return {row["ref"]: row for row in catalog["datasets"]}


def test_mentions_keep_tables_and_data_files_and_drop_everything_else(catalog: dict) -> None:
    refs = set(by_ref(catalog))
    assert {"results.alpha_scores", "results.beta_calls"} <= refs
    # a glob, a file extension, the bookkeeping ledger and a manifest are not datasets
    assert not any(ref.startswith("results.it9") for ref in refs)
    assert "results.tsv" not in refs
    assert "warehouse.data_lineage" not in refs
    assert "ressources/demo/made.provenance.json" not in refs
    # a bare name two schemas share is ambiguous, so it is not guessed
    assert not any(ref.endswith(".gamma") for ref in refs)


def test_a_table_is_produced_by_notes_citing_the_entry_or_by_its_named_tool(
    catalog: dict,
) -> None:
    rows = by_ref(catalog)
    assert rows["results.beta_calls"]["role"] == "produced"  # the edge cites 901
    assert rows["results.alpha_scores"]["role"] == "produced"  # 901 names its tool
    assert rows["results.alpha_scores"]["entries"] == ["901", "902"]
    assert rows["results.alpha_scores"]["steps"] == ["iteration9/step-1", "iteration9/step-2"]
    assert rows["results.alpha_scores"]["lineage"] == "edge"
    assert rows["results.alpha_scores"]["inputs"] == [{"ref": "warehouse.raw", "sha256": ""}]


def test_a_file_is_matched_to_the_manifest_that_lists_it_as_an_output(catalog: dict) -> None:
    rows = by_ref(catalog)
    made = rows["ressources/demo/made.tsv"]
    assert made["lineage"] == "manifest"
    assert made["rows"] == 1
    assert made["role"] == "produced"  # 901 names the manifest's producer
    named = rows["ressources/demo/named.tsv"]
    assert named["provenance"] == "ressources/demo/group_provenance.json"
    assert named["rows"] == 7


def test_a_manifest_naming_a_file_as_an_input_does_not_describe_it(catalog: dict) -> None:
    card = by_ref(catalog)["ressources/demo/card.json"]
    assert card["provenance"] == "ressources/demo/card.json"  # its own standing line
    assert card["built_by"].startswith("hand-authored")


def test_a_file_the_ledger_records_as_an_input_has_edge_lineage(catalog: dict) -> None:
    bare = by_ref(catalog)["ressources/demo/bare.tsv"]
    assert bare["lineage"] == "edge"
    assert bare["sha256"] == "e" * 64


def test_a_build_file_without_a_manifest_is_uncommitted_and_has_no_lineage(catalog: dict) -> None:
    scratch = by_ref(catalog)["build/it9/scratch.parquet"]
    assert (scratch["lineage"], scratch["committed"], scratch["exists"]) == ("none", False, False)


def test_an_object_prefix_resolves_through_the_ledger(catalog: dict) -> None:
    raw = by_ref(catalog)["s3://bucket/source"]
    assert (raw["kind"], raw["lineage"], raw["sha256"]) == ("raw", "edge", "f" * 64)


def test_coverage_counts_what_the_rows_say(catalog: dict) -> None:
    rows = catalog["datasets"]
    assert catalog["coverage"]["datasets"] == len(rows)
    assert catalog["coverage"]["with_lineage"] == sum(r["lineage"] != "none" for r in rows)
    assert rows[0]["role"] == "produced"  # produced rows sort first


def test_with_no_ledger_the_catalogue_still_lists_what_the_entries_name(repo: Path) -> None:
    dead = Ledger([], False, "warehouse unreachable (RuntimeError)")
    catalog = iteration_catalog.build(repo, [ENTRY_A], dead)
    assert catalog["available"] is False
    assert "RuntimeError" in catalog["note"]
    assert by_ref(catalog)["results.alpha_scores"]["lineage"] == "none"


def test_a_probe_filed_under_another_track_is_not_this_folders_reply() -> None:
    probes = [{"track": "1", "rationale": "iteration 1, see submissions/track1/iteration-1"}]
    assert submissions_audit.probes_for(probes, 1, None, "track1") == probes
    assert submissions_audit.probes_for(probes, 1, None, "track2") == []


def test_a_research_row_links_the_tracks_it_has_steps_for() -> None:
    catalog = {"entries": [ENTRY_A, ENTRY_B], "datasets": [], "coverage": {}}
    row = iterations.research_row(
        "iteration2",
        Counter({"supported": 2, "refuted": 1}),
        catalog,
        {"track1/iteration-2": ["docs/iteration2/step-1/methodology/084-x.md"]},
    )
    assert row["routes"]["track1"] == "/track1/iteration2"
    assert row["submissions"] == ["track1/iteration-2"]
    assert row["claims"] == {"refuted": 1, "supported": 2}
    assert row["entries"] == {"count": 2, "first": "901", "last": "902"}


def test_the_overview_route_answers_with_no_database(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unreachable(*args: object, **kwargs: object) -> list:
        raise RuntimeError("no credentials in this test")

    monkeypatch.setattr(queries.access, "fetch", unreachable)
    monkeypatch.setattr(iterations, "register", unreachable)
    monkeypatch.setattr(submissions_reader, "DEFAULT_ROOT", repo)
    client = TestClient(create_app(cache=Cache(repo / "cache")))
    body = client.get("/api/iterations").json()
    assert body["source"] == iterations.SOURCE
    data = body["data"]
    assert data["ledger"]["available"] is False
    names = [row["iteration"] for row in data["research"]]
    assert "iteration9" in names
    row = data["research"][names.index("iteration9")]
    assert row["declared"] is False
    assert row["catalog"]["coverage"]["datasets"] > 0
