"""The submissions endpoint: one iteration folder, parsed, and the answer with no database.

A synthetic ``submissions/track9/iteration-3/`` is written into ``tmp_path`` and the reader
is pointed at it, so a failure here names the **contract** — the state rule, the decode
table, the selector ranking, the figure URL — and never the real folder's current contents
or the network.

**Every value in this file is fabricated and no genomic position appears anywhere in it.**
The selector spec is coordinate-free by construction (a table plus a ``WHERE`` clause), and
a fixture that carried a position would be teaching exactly the shape this surface exists
to refuse.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from mva.viz import (
    queries,
    submissions,
    submissions_audit,
    submissions_lineage,
    submissions_reader,
)
from mva.viz.app import create_app
from mva.viz.cache import Cache
from mva.viz.submissions_reader import PositionInSelectorError

TRACK = "track9"
NUMBER = 3

README = """# Track 9 — iteration 3 (2099-01-01)

**Standing:** built and rehearsed 2099-01-01; **not uploaded** (0 of 6 submissions spent).

## What to upload

| Deliverable | File | Notes |
|---|---|---|
| Predictions CSV | `build/submission/track9_submission_v3.csv` — gitignored | sha256 \
`aaaabbbbccccddddeeeeffff0000111122223333444455556666777788889999`; rows follow the spec |

## Which steps contributed, and where their evidence lives

| Step | Contribution | Methodology |
|---|---|---|
| 2 annotate | GENEA the only qualifying gene (H001) | [069](../../../docs/note-069.md) |
| 3 phenotype | GENEA first among the biallelic genes | [070](../../../docs/note-070.md), \
[071](../../../docs/note-071.md) |

## After the upload

Nothing yet.
"""

DECODE = """| Reply: full match rank | partial match rank | F-max | survivors |
|---|---|---|---|
| 1 | — | 1.000 | stop+missense |
| — | 1 | 0.500 | stop+unseen |

Prior entropy 1.000 bits · **expected information gain 0.500 bits**.

Rows, in rank order: 1. stop+missense; 2. `GENEB` stop_gained (secondary)
"""

SELECTORS: dict = {
    "alleles": {
        "stop": {
            "table": "results.coding_candidates",
            "where": [["gene", "=", "GENEA"], ["consequence", "like", "%stop_gained%"]],
        },
        "missense": {
            "table": "results.panel_candidates",
            "where": [["gene", "=", "GENEA"], ["gnomad_af", "is", None]],
        },
    },
    "rows": [
        {
            "variant": "stop",
            "partner": "missense",
            "epcr": 0.9,
            "finding_type": "primary",
            "label": "stop+missense",
            "notes": "H:H001 | GENEA | compound heterozygote",
        },
        {
            "variant": "missense",
            "epcr": 0.4,
            "finding_type": "secondary",
            "label": "GENEB carrier (secondary)",
            "notes": "secondary | GENEB | reported, not scored",
        },
    ],
    "hypotheses": [{"label": "stop+missense", "alleles": ["stop", "missense"], "prior": 0.8}],
}

METHODS = {"7": "someone", "8": "3", "10": "ten", "9": "nine"}

REPORT = "# Report\n\nThe pair in GENEA is the claim; see H002 and H001.\n"

REGISTER = {
    "generator": "mva-science export",
    "hypotheses": [
        {
            "id": "H001",
            "step": "step-2",
            "statement": "A recessive loss-of-function pair in GENEA explains the phenotype.",
            "status": "supported",
            "confidence": 0.9,
            "reasoning": "two independent methods agree",
            "revisions": 2,
        },
        {
            "id": "H055",
            "step": "step-9",
            "statement": "Not argued by this iteration.",
            "status": "proposed",
            "confidence": None,
            "revisions": 1,
        },
    ],
}

PROBES = [
    {
        "probe_id": 1,
        "track": "1",
        "payload": "…",
        "response": "full match rank 1",
        "score": 1.0,
        "rationale": "Iteration 3, see submissions/track9/iteration-3",
    },
    {
        "probe_id": 2,
        "track": "1",
        "payload": "…",
        "response": "no match",
        "score": 0.0,
        "rationale": "iteration 1, an earlier folder",
    },
    {
        "probe_id": 3,
        "track": "1",
        "payload": "…",
        "response": "no match",
        "score": 0.0,
        "rationale": "a rehearsal that names no iteration",
        "payload_sha256": "aaaabbbbccccddddeeeeffff0000111122223333444455556666777788889999",
    },
]


def write_iteration(root: Path, readme: str = README) -> Path:
    """A complete, synthetic iteration folder plus the figure and register it points at."""
    folder = root / "submissions" / TRACK / f"iteration-{NUMBER}"
    folder.mkdir(parents=True)
    (folder / "README.md").write_text(readme, encoding="utf-8")
    (folder / "report.md").write_text(REPORT, encoding="utf-8")
    (folder / "decode-table.md").write_text(DECODE, encoding="utf-8")
    (folder / "spec.selectors.json").write_text(json.dumps(SELECTORS), encoding="utf-8")
    (folder / "methods-form.json").write_text(json.dumps(METHODS), encoding="utf-8")
    (folder / "someone_track9_report.pdf").write_bytes(b"%PDF-1.4 not really")
    (folder / "someone_track9_methods_form.xlsx").write_bytes(b"PK not really")
    (folder / ".DS_Store").write_bytes(b"junk")

    figures = root / "figures" / TRACK
    figures.mkdir(parents=True)
    (figures / "track9-funnel.png").write_bytes(b"\x89PNG\r\n\x1a\n not really")
    (figures / "notes.txt").write_text("not a figure", encoding="utf-8")

    docs = root / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "science-register.json").write_text(json.dumps(REGISTER), encoding="utf-8")
    return folder


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    return write_iteration(tmp_path)


@pytest.fixture
def iteration(folder: Path, tmp_path: Path) -> dict:
    return submissions_reader.read(folder, tmp_path)


# --- the reader --------------------------------------------------------------------


def test_the_folder_parses_into_the_contract_shape(iteration: dict) -> None:
    assert iteration["track"] == TRACK
    assert iteration["number"] == NUMBER
    assert iteration["folder"] == f"submissions/{TRACK}/iteration-{NUMBER}"
    assert iteration["state"] == "ready"
    assert iteration["uploaded"] is False
    assert iteration["standing"].startswith("built and rehearsed")
    assert "**" not in iteration["standing"]


def test_the_csv_is_described_by_claim_and_never_carried(iteration: dict) -> None:
    """Path, digest and row count — the file itself holds coordinates and is gitignored."""
    assert iteration["csv"]["path"] == "build/submission/track9_submission_v3.csv"
    assert iteration["csv"]["sha256"].startswith("aaaabbbb")
    assert iteration["csv"]["rows"] == 2


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("**Standing:** draft, still filling the funnel section", "draft"),
        ("**Standing:** built and rehearsed; **not uploaded**", "ready"),
        ("**Frozen:** uploaded 2099-01-02, reply pending", "frozen"),
        ("**Standing:** something nobody thought of", "draft"),
    ],
)
def test_the_state_comes_from_the_readmes_own_declaration(line: str, expected: str) -> None:
    """The same precedence tools/check_iteration.py enforces: frozen > ready > draft."""
    assert submissions_reader.state(f"# Title\n\n{line}\n") == expected


def test_a_frozen_folder_reports_itself_as_uploaded(tmp_path: Path) -> None:
    readme = README.replace(
        "**Standing:** built and rehearsed 2099-01-01; **not uploaded** "
        "(0 of 6 submissions spent).",
        "**Frozen:** uploaded 2099-01-02; reply pending.",
    )
    folder = write_iteration(tmp_path, readme)
    iteration = submissions_reader.read(folder, tmp_path)
    assert (iteration["state"], iteration["uploaded"]) == ("frozen", True)


def test_deliverables_are_typed_and_hidden_files_are_not_deliverables(iteration: dict) -> None:
    kinds = {row["name"]: row["kind"] for row in iteration["deliverables"]}
    assert kinds == {
        "README.md": "readme",
        "report.md": "report-md",
        "decode-table.md": "decode-table",
        "spec.selectors.json": "selectors",
        "methods-form.json": "methods-json",
        "someone_track9_report.pdf": "report-pdf",
        "someone_track9_methods_form.xlsx": "methods-xlsx",
    }
    assert all(
        row["bytes"] > 0 and row["modified"].endswith("+00:00") for row in iteration["deliverables"]
    )


def test_the_decode_table_keeps_the_table_the_summary_and_the_row_order(iteration: dict) -> None:
    decode = iteration["decode_table"]
    assert decode["columns"] == [
        "Reply: full match rank",
        "partial match rank",
        "F-max",
        "survivors",
    ]
    assert decode["rows"][0] == ["1", "—", "1.000", "stop+missense"]
    assert len(decode["rows"]) == 2, "the separator row is not a row"
    assert decode["summary"].startswith("Prior entropy 1.000 bits")
    assert "**" not in decode["summary"]
    assert decode["row_order"].startswith("Rows, in rank order:")
    assert "`" not in decode["row_order"]


def test_selector_rows_are_ranked_in_the_order_the_scorer_reads_them(iteration: dict) -> None:
    rows = iteration["selectors"]["rows"]
    assert [row["rank"] for row in rows] == [1, 2]
    assert rows[0]["partner"] == "missense"
    assert rows[1]["partner"] is None
    assert rows[1]["finding_type"] == "secondary"
    assert set(iteration["selectors"]["alleles"]) == {"stop", "missense"}


def test_a_selector_carrying_a_position_is_refused_rather_than_served(tmp_path: Path) -> None:
    """The committed spec is coordinate-free by construction; a ``pos`` key is a leak."""
    folder = write_iteration(tmp_path)
    leaking = json.loads(json.dumps(SELECTORS))
    leaking["alleles"]["stop"]["pos"] = 1
    (folder / "spec.selectors.json").write_text(json.dumps(leaking), encoding="utf-8")
    with pytest.raises(PositionInSelectorError, match="carries a position"):
        submissions_reader.read(folder, tmp_path)


def test_methods_form_rows_are_ordered_numerically_not_as_strings(iteration: dict) -> None:
    assert [row["row"] for row in iteration["methods_form"]] == ["7", "8", "9", "10"]


def test_contributions_resolve_every_methodology_link_to_a_repository_path(
    iteration: dict,
) -> None:
    contributions = iteration["contributions"]
    assert [row["step"] for row in contributions] == ["2 annotate", "3 phenotype"]
    assert contributions[0]["methodology"] == [{"label": "069", "path": "docs/note-069.md"}]
    assert [link["path"] for link in contributions[1]["methodology"]] == [
        "docs/note-070.md",
        "docs/note-071.md",
    ]


def test_hypothesis_ids_are_swept_from_readme_report_and_selectors(iteration: dict) -> None:
    assert iteration["hypotheses"] == ["H001", "H002"]


def test_only_pngs_are_figures_and_each_carries_the_url_that_serves_it(iteration: dict) -> None:
    assert iteration["figures"] == [
        {
            "slug": "track9-funnel",
            "path": f"figures/{TRACK}/track9-funnel.png",
            "url": f"/api/submissions/{TRACK}/{NUMBER}/figure/track9-funnel",
        }
    ]


def test_a_report_citing_figures_is_illustrated_by_those_and_not_the_track_folder(
    tmp_path: Path,
) -> None:
    folder = write_iteration(tmp_path)
    drawn = tmp_path / "figures" / "it9"
    drawn.mkdir()
    (drawn / "b-volcano.svg").write_text("<svg/>", encoding="utf-8")
    (drawn / "a-rank.png").write_bytes(b"\x89PNG")
    (folder / "report.md").write_text(
        "![](../../../figures/it9/b-volcano.svg) then figures/it9/a-rank.png, "
        "figures/it9/never-drawn.svg and figures/it9/b-volcano.svg again\n",
        encoding="utf-8",
    )
    iteration = submissions_reader.read(folder, tmp_path)
    assert [f["path"] for f in iteration["figures"]] == [
        "figures/it9/b-volcano.svg",
        "figures/it9/a-rank.png",
    ]
    figure = submissions.figure_path(tmp_path, iteration, "b-volcano")
    assert figure.name == "b-volcano.svg"
    with pytest.raises(HTTPException):
        submissions.figure_path(tmp_path, iteration, "track9-funnel")


def test_the_report_is_returned_verbatim(iteration: dict) -> None:
    assert iteration["report"]["markdown"] == REPORT
    assert iteration["report"]["path"] == f"submissions/{TRACK}/iteration-{NUMBER}/report.md"


def test_iterations_sort_numerically_so_ten_comes_after_two(tmp_path: Path) -> None:
    for number in (2, 10):
        (tmp_path / "submissions" / TRACK / f"iteration-{number}").mkdir(parents=True)
    (tmp_path / "submissions" / TRACK / "iteration-notanumber").mkdir()
    found = submissions_reader.iteration_folders(tmp_path)
    assert [path.name for path in found] == ["iteration-2", "iteration-10"]


# --- the audit ---------------------------------------------------------------------


def test_probes_match_an_iteration_by_rationale_or_by_payload_digest() -> None:
    matched = submissions_audit.probes_for(PROBES, NUMBER, PROBES[2]["payload_sha256"])
    assert [probe["probe_id"] for probe in matched] == [1, 3]


def test_register_rows_cover_only_the_claims_this_iteration_argues() -> None:
    rows = submissions_audit.revisions_for(REGISTER["hypotheses"], ["H001", "H002"])
    assert [row["hypothesis_id"] for row in rows] == ["H001"], "H002 is not in the register"
    assert rows[0]["revision"] == 2
    assert rows[0]["recorded_at"] == "", "the export carries no per-revision timestamp"


# --- the routes --------------------------------------------------------------------


@pytest.fixture
def client(folder: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """The app pointed at the synthetic root, with every database read raising."""

    def unreachable(*args: object, **kwargs: object) -> list:
        raise RuntimeError("no credentials in this test")

    monkeypatch.setattr(queries.access, "fetch", unreachable)
    monkeypatch.setattr(submissions_reader, "DEFAULT_ROOT", tmp_path)
    return TestClient(create_app(cache=Cache(tmp_path / "cache")))


def test_the_endpoint_answers_with_the_envelope_and_one_iteration(client: TestClient) -> None:
    body = client.get("/api/submissions").json()
    assert body["source"] == submissions.SOURCE
    assert body["cached_at"] is not None
    iterations = body["data"]["iterations"]
    assert [(it["track"], it["number"]) for it in iterations] == [(TRACK, NUMBER)]


def test_lineage_degrades_to_the_sources_disk_alone_proves(client: TestClient) -> None:
    """No database: no edges, the exception class in the note, the disk sources still there."""
    lineage = client.get("/api/submissions").json()["data"]["iterations"][0]["lineage"]
    assert lineage["available"] is False
    assert "RuntimeError" in lineage["note"]
    assert lineage["edges"] == []
    kinds = {source["kind"] for source in lineage["sources"]}
    assert kinds == {"clinical", "file", "table"}
    tables = {source["ref"] for source in lineage["sources"] if source["kind"] == "table"}
    assert tables == {
        "results.coding_candidates",
        "results.panel_candidates",
        "results.gene_biallelic",
        "warehouse.hpo_gene_scores",
    }


def test_an_unreadable_probe_ledger_is_an_empty_audit_not_an_error(client: TestClient) -> None:
    audit = client.get("/api/submissions").json()["data"]["iterations"][0]["audit"]
    assert audit["probes"] == []
    assert [row["hypothesis_id"] for row in audit["register"]] == ["H001"]


def test_the_report_route_serves_the_markdown_verbatim(client: TestClient) -> None:
    body = client.get(f"/api/submissions/{TRACK}/{NUMBER}/report").json()
    assert body["data"]["markdown"] == REPORT


def test_an_unknown_iteration_is_a_404(client: TestClient) -> None:
    assert client.get(f"/api/submissions/{TRACK}/99/report").status_code == 404


def test_the_figure_route_serves_the_png_and_404s_on_anything_else(client: TestClient) -> None:
    base = f"/api/submissions/{TRACK}/{NUMBER}/figure"
    found = client.get(f"{base}/track9-funnel")
    assert found.status_code == 200
    assert found.headers["content-type"] == "image/png"
    assert client.get(f"{base}/no-such-figure").status_code == 404
    assert client.get(f"{base}/..%2F..%2Fetc%2Fpasswd").status_code == 404


def test_refresh_rebuilds_the_cached_payload(client: TestClient, folder: Path) -> None:
    """The whole payload is one cache entry, so a folder edit needs ``?refresh=true``."""
    first = client.get("/api/submissions").json()["data"]["iterations"][0]
    (folder / "report.md").write_text("# Changed\n", encoding="utf-8")
    assert client.get("/api/submissions").json()["data"]["iterations"][0] == first
    refreshed = client.get("/api/submissions?refresh=true").json()["data"]["iterations"][0]
    assert refreshed["report"]["markdown"] == "# Changed\n"


# --- the lineage walk, without a database --------------------------------------------


EDGES = [
    {
        "produced_at": "2099-01-01T00:00:00",
        "target_schema": "results",
        "target_table": "coding_candidates",
        "target_rows": 10,
        "source_kind": "table",
        "source_ref": "warehouse.variants_raw",
        "source_version": "",
        "source_sha256": "",
        "transform": "annotate",
        "tool": "mva-warehouse",
        "notes": "",
        "is_current": True,
    },
    {
        "produced_at": "2099-01-01T00:00:00",
        "target_schema": "results",
        "target_table": "coding_candidates",
        "target_rows": 10,
        "source_kind": "reference",
        "source_ref": "Ensembl VEP REST",
        "source_version": "116",
        "source_sha256": "",
        "transform": "annotate",
        "tool": "mva-warehouse",
        "notes": "",
        "is_current": True,
    },
    {
        "produced_at": "2098-12-01T00:00:00",
        "target_schema": "warehouse",
        "target_table": "variants_raw",
        "target_rows": 99,
        "source_kind": "object",
        "source_ref": "s3://mva/delivery/callset.vcf.gz",
        "source_version": "v1",
        "source_sha256": "d" * 64,
        "transform": "load",
        "tool": "mva-warehouse",
        "notes": "",
        "is_current": True,
    },
    {
        "produced_at": "2097-01-01T00:00:00",
        "target_schema": "results",
        "target_table": "unrelated_table",
        "target_rows": 1,
        "source_kind": "table",
        "source_ref": "warehouse.variants_raw",
        "source_version": "",
        "source_sha256": "",
        "transform": "something else",
        "tool": "mva-warehouse",
        "notes": "",
        "is_current": True,
    },
]


def test_the_walk_follows_source_ref_back_to_the_raw_callset_and_stops_there() -> None:
    collected = submissions_lineage.walk(EDGES, ["results.coding_candidates"])
    targets = {(edge["target_schema"], edge["target_table"]) for edge in collected}
    assert targets == {("results", "coding_candidates"), ("warehouse", "variants_raw")}
    assert not any(edge["target_table"] == "unrelated_table" for edge in collected)


def test_a_reachable_ledger_names_the_raw_object_and_the_reference_inputs(
    folder: Path, tmp_path: Path
) -> None:
    ledger = submissions_lineage.Ledger(EDGES, True, "4 edges")
    lineage = submissions_lineage.build(
        ledger, tmp_path, folder, TRACK, NUMBER, ["results.coding_candidates"]
    )
    assert lineage["available"] is True
    by_kind = {source["kind"]: source for source in lineage["sources"]}
    assert by_kind["raw"]["ref"] == "s3://mva/delivery/callset.vcf.gz"
    assert by_kind["raw"]["sha256"] == "d" * 64
    assert by_kind["reference"]["ref"] == "Ensembl VEP REST"
    assert by_kind["reference"]["version"] == "116"


def test_edges_recorded_for_the_iteration_itself_are_included(folder: Path, tmp_path: Path) -> None:
    own = {
        "produced_at": "2099-02-01T00:00:00",
        "target_schema": "submissions",
        "target_table": f"{TRACK}/iteration-{NUMBER}",
        "target_rows": 2,
        "source_kind": "clinical",
        "source_ref": "ressources/hackathon-rules/Challenge_Clinical_Phenotype_1.md",
        "source_version": "8 HPO terms",
        "source_sha256": "e" * 64,
        "transform": "resolve selectors",
        "tool": "resolve_submission_spec",
        "notes": "",
        "is_current": True,
    }
    ledger = submissions_lineage.Ledger([*EDGES, own], True, "5 edges")
    lineage = submissions_lineage.build(ledger, tmp_path, folder, TRACK, NUMBER, [])
    assert own in lineage["edges"]


def test_a_panel_iteration_walks_from_the_tables_its_entries_recorded(
    folder: Path, tmp_path: Path
) -> None:
    """No selectors, but the contributions link an entry whose recorder cited it in notes."""
    entry = "docs/iteration9/step-2/methodology/200-a-sweep.md"
    recorded = {
        **EDGES[0],
        "target_schema": "track9",
        "target_table": "it9.sweep",
        "source_kind": "file",
        "source_ref": "https://example.org/release.csv",
        "source_version": "20Q2",
        "notes": f"entry {entry}; the primary screen",
    }
    ledger = submissions_lineage.Ledger([*EDGES, recorded], True, "5 edges")
    contributions = [{"step": "step 2", "methodology": [{"label": "200", "path": entry}]}]
    cited = submissions_lineage.entry_tables(
        ledger, submissions_lineage.contribution_entries(contributions)
    )
    assert cited == ["track9.it9.sweep"]
    (folder / "spec.selectors.json").unlink()
    lineage = submissions_lineage.build(ledger, tmp_path, folder, TRACK, NUMBER, [], cited)
    assert recorded in lineage["edges"]
    refs = {(s["kind"], s["ref"]) for s in lineage["sources"]}
    assert ("file", "https://example.org/release.csv") in refs
    assert ("table", "track9.it9.sweep") not in refs, "a cited table is walked, not a selector"
    assert not any(s["ref"].endswith("spec.selectors.json") for s in lineage["sources"])
