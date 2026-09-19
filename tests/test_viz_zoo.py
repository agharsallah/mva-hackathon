"""``/api/zoo/*``: the envelope, the case that is never assumed, and the coordinate rule.

Three things are pinned here, and only one of them is shape.

**The case is configuration.** Every fixture below runs the routes against a *different*
case from the real one: a config in ``tmp_path`` whose gene is ``GENEG``, whose table prefix
is ``demo`` and whose docs folders are temporary. A route that hard-coded this project's
gene, iteration or table names fails immediately — which is the whole reusability claim of
iteration 4, tested rather than asserted.

**The database is real SQL over fake rows.** An in-memory DuckDB with ``ATTACH ':memory:'
AS pg`` stands in for the hosted PostgreSQL, exactly as :mod:`tests.test_zoo_cache` does,
loaded from ``fixtures/it4/`` (synthetic: ten invented genes, invented allele ids, invented
scores). The routes therefore run their own statements instead of a mock of them.

**No coordinate leaves.** :func:`test_no_response_carries_a_coordinate` walks every route's
whole payload and refuses a ``pos``/``chrom``-shaped key anywhere in it. The record table is
coordinate-free by construction; this is the test that keeps it that way when someone widens
a ``SELECT``.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import duckdb
import pytest
from fastapi.testclient import TestClient

from mva.viz import api_zoo_reads as reads
from mva.viz.app import create_app
from mva.warehouse.settings import Postgres

FIXTURES = Path("fixtures/it4")

#: The fixture's confirmed pair (``fixtures/it4/pairs.tsv``, row 1) — an invented gene.
CASE_GENE = "GENEG"

#: A table prefix that is not this project's, so a hard-coded ``it4_`` cannot pass.
PREFIX = "demo"

#: Keys that would be a genomic position. ``ref``/``alt`` are alleles rather than places,
#: but they are the other half of a coordinate and have no business in a response either.
FORBIDDEN_KEYS = {"pos", "position", "chrom", "chromosome", "start", "end", "ref", "alt"}

#: The lanes the fixture holds scores for. ``spliceai`` is deliberately left out of the
#: score cache below, so ``coverage`` has a declared-but-never-run lane to report as null.
SCORED_LANES = ("alphamissense", "esm1b", "revel")

CONFIG = """
[case]
label = "A fabricated case"
iteration = "demo-case"
table_prefix = "{prefix}"
confirmed_gene = "{gene}"

[run]
mode = "catalogue-free"
models = ["alphamissense", "esm1b", "revel", "spliceai"]
out_dir = "{out_dir}"
schema = "results"
warehouse_schema = "warehouse"

[merge]
method = "fusion"
rrf_k = 60

[paths]
reports_dir = "{reports_dir}"
docs_runs_dir = "{runs_dir}"
merged_report = "{merged}"
"""

RUN_ID = f"{PREFIX}-0123456789ab"


def _tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _table(name: str) -> str:
    return f"{PREFIX}_{name}"


@pytest.fixture
def warehouse() -> Iterator[duckdb.DuckDBPyConnection]:
    """The four zoo tables, under a prefix that is not this project's, from the fixtures."""
    connection = duckdb.connect()
    connection.execute("ATTACH ':memory:' AS pg")
    connection.execute("CREATE SCHEMA pg.results")
    connection.execute("CREATE SCHEMA pg.warehouse")
    _load_records(connection)
    _load_scores(connection)
    _load_ranks(connection)
    _load_lineage(connection)
    yield connection
    connection.close()


def _load_records(connection: duckdb.DuckDBPyConnection) -> None:
    """The coordinate columns of ``records.tsv`` are dropped: the table never carries them."""
    connection.execute(
        f"CREATE TABLE pg.results.{_table('allele_records')} ("
        "allele_id VARCHAR, gene VARCHAR, transcript VARCHAR, consequence VARCHAR, "
        "hgvs_c VARCHAR, hgvs_p VARCHAR, uniprot VARCHAR, is_read_only BOOLEAN, "
        "af_gnomad DOUBLE, clin_sig VARCHAR, built_at TIMESTAMP, source VARCHAR)"
    )
    for row in _tsv(FIXTURES / "records.tsv"):
        connection.execute(
            f"INSERT INTO pg.results.{_table('allele_records')} VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now(), 'fixtures/it4/records.tsv')",
            [
                row["allele_id"],
                row["gene"],
                row["transcript"],
                row["consequence"],
                row["hgvs_c"],
                row["hgvs_p"],
                row["uniprot"],
                row["is_read_only"] == "true",
                float(row["af_gnomad"]) if row["af_gnomad"] else None,
                row["clin_sig"] or None,
            ],
        )


def _load_scores(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        "CREATE TABLE pg.warehouse.allele_scores ("
        "allele_id VARCHAR, model VARCHAR, version VARCHAR, digest VARCHAR, score DOUBLE, "
        "aux VARCHAR, venue VARCHAR, licence VARCHAR, run_id VARCHAR, ts TIMESTAMP)"
    )
    for lane in SCORED_LANES:
        for row in _tsv(FIXTURES / "scores" / f"{lane}.tsv"):
            connection.execute(
                "INSERT INTO pg.warehouse.allele_scores VALUES "
                "(?, ?, ?, 'd0d0d0d0', ?, ?, 'laptop', 'CC-BY-NC-SA-4.0', ?, now())",
                [
                    row["allele_id"],
                    row["model"],
                    row["version"],
                    float(row["score"]),
                    json.dumps({"lane": lane}),
                    RUN_ID,
                ],
            )


def _load_ranks(connection: duckdb.DuckDBPyConnection) -> None:
    """One ranking per scored lane over the fixture's pairs, confirmed pair included."""
    connection.execute(
        f"CREATE TABLE pg.results.{_table('model_ranks')} ("
        "run_id VARCHAR, model VARCHAR, gene VARCHAR, left_allele_id VARCHAR, "
        "right_allele_id VARCHAR, phase VARCHAR, min_score DOUBLE, max_score DOUBLE, "
        '"rank" BIGINT, n_ranked BIGINT, percentile DOUBLE, unscored_pairs BIGINT, '
        "is_confirmed BOOLEAN, ts TIMESTAMP)"
    )
    pairs = _tsv(FIXTURES / "pairs.tsv")[:4]
    for lane in SCORED_LANES:
        for position, pair in enumerate(pairs, start=1):
            connection.execute(
                f"INSERT INTO pg.results.{_table('model_ranks')} VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())",
                [
                    RUN_ID,
                    lane,
                    pair["gene"],
                    pair["allele_id_left"],
                    pair["allele_id_right"],
                    pair["phase"],
                    0.5 / position,
                    0.9 / position,
                    position,
                    len(pairs),
                    round(100.0 * position / len(pairs), 4),
                    7,
                    pair["is_confirmed"] == "true",
                ],
            )


def _load_lineage(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        "CREATE TABLE pg.warehouse.data_lineage ("
        "produced_at TIMESTAMP, target_schema VARCHAR, target_table VARCHAR, "
        "target_rows BIGINT, source_kind VARCHAR, source_ref VARCHAR, "
        "source_version VARCHAR, source_sha256 VARCHAR, transform VARCHAR, "
        "tool VARCHAR, notes VARCHAR)"
    )
    for target, tool in (
        (_table("allele_records"), "mva.zoo.record"),
        ("allele_scores", "mva.zoo.cache"),
    ):
        connection.execute(
            "INSERT INTO pg.warehouse.data_lineage VALUES "
            "(now(), 'results', ?, 200, 'table', 'results.coding_alleles', 'v1', "
            "'abc', 'normalize', ?, 'a fabricated edge')",
            [target, tool],
        )
    connection.execute(
        "INSERT INTO pg.warehouse.data_lineage VALUES "
        "(now(), 'results', 'some_other_table', 1, 'table', 'x', 'v1', 'abc', 't', 'tool', '')"
    )


@pytest.fixture
def case_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A whole case on disk: the config, a run manifest, two reports and a merged report."""
    out_dir = tmp_path / "build"
    reports_dir = tmp_path / "docs" / "reports"
    runs_dir = tmp_path / "docs" / "runs"
    for folder in (out_dir, reports_dir, runs_dir):
        folder.mkdir(parents=True, exist_ok=True)

    config = tmp_path / "case.toml"
    config.write_text(
        CONFIG.format(
            prefix=PREFIX,
            gene=CASE_GENE,
            out_dir=out_dir,
            reports_dir=reports_dir,
            runs_dir=runs_dir,
            merged=tmp_path / "docs" / "report.md",
        ),
        encoding="utf-8",
    )
    (reports_dir / "alphamissense.md").write_text(
        "# AlphaMissense\n\n![the scores](../../figures/hist.svg)\n", encoding="utf-8"
    )
    (tmp_path / "docs" / "report.md").write_text("# The merged report\n\nThe zoo.\n", "utf-8")
    (runs_dir / f"{RUN_ID}.json").write_text(
        json.dumps(
            {
                "run_id": RUN_ID,
                "config_digest": "0123456789ab",
                "started_at": "2099-01-01T00:00:00+00:00",
                "wall_clock_seconds": 12.5,
                "dollars": 0.0,
                "models": dict.fromkeys(SCORED_LANES, "fixture-1"),
                "venues": dict.fromkeys(SCORED_LANES, "laptop"),
            }
        ),
        encoding="utf-8",
    )
    (out_dir / "merged.json").write_text(json.dumps(_merged()), encoding="utf-8")
    monkeypatch.setenv("MVA_ZOO_CONFIG", str(config))
    return tmp_path


def _merged() -> dict[str, Any]:
    left = _tsv(FIXTURES / "pairs.tsv")[0]["allele_id_left"]
    return {
        "run_id": RUN_ID,
        "method": "fusion",
        "rrf_k": 60,
        "generated_at": "2099-01-01T00:00:00+00:00",
        "agreement": {
            "models": list(SCORED_LANES),
            "cells": [
                {"a": "alphamissense", "b": "esm1b", "rho": 0.5, "n": 12},
                {"a": "esm1b", "b": "alphamissense", "rho": 0.5, "n": 12},
                {"a": "alphamissense", "b": "revel", "rho": None, "n": 2},
            ],
        },
        "consensus": {
            "catalogue_free": {
                "rank": 3,
                "n_pairs": 20,
                "fused_score": 0.01,
                "percentile": 15.0,
                "lanes": ["alphamissense", "esm1b"],
                "excluded_lanes": ["revel"],
                "k": 60,
            },
            "all_lanes": {
                "rank": 4,
                "n_pairs": 20,
                "fused_score": 0.02,
                "percentile": 20.0,
                "lanes": list(SCORED_LANES),
                "excluded_lanes": [],
                "k": 60,
            },
        },
        "disagreements": [
            {
                "allele_id": left,
                "high_model": "esm1b",
                "high_percentile": 1.0,
                "low_model": "alphamissense",
                "low_percentile": 90.0,
            }
        ],
        "lanes": [
            {
                "model": lane,
                "catalogue_adjacent": lane == "revel",
                "confirmed": {
                    "gene": CASE_GENE,
                    "left_percentile": 4.0,
                    "right_percentile": 6.0,
                },
            }
            for lane in SCORED_LANES
        ],
    }


@pytest.fixture
def client(
    case_root: Path, warehouse: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch
) -> TestClient:
    @contextmanager
    def fake_connect(_settings: Postgres) -> Iterator[duckdb.DuckDBPyConnection]:
        yield warehouse

    monkeypatch.setattr(reads, "connect", fake_connect)
    from mva.viz.cache import Cache

    return TestClient(create_app(cache=Cache(case_root / "cache"), origins=[], token=""))


def get(client: TestClient, path: str) -> dict:
    reply = client.get(path)
    assert reply.status_code == 200, reply.text
    body = reply.json()
    assert set(body) == {"data", "cached_at", "source"}
    assert body["source"]
    return body


# ---------------------------------------------------------------------------------------
# The case is configuration, never a constant
# ---------------------------------------------------------------------------------------


def test_the_case_route_reports_the_configured_case(client: TestClient) -> None:
    data = get(client, "/api/zoo/case")["data"]
    assert data["gene"] == CASE_GENE
    assert data["case"]["table_prefix"] == PREFIX
    assert data["tables"] == [
        f"{PREFIX}_allele_records",
        "allele_scores",
        f"{PREFIX}_model_ranks",
        f"{PREFIX}_model_reports",
    ]
    assert "iteration4" not in json.dumps(data)


def test_no_route_names_this_project_gene_or_iteration(client: TestClient) -> None:
    """The routes run on a different case; ``BUB1B`` may not appear in any of their replies."""
    for path in ROUTES:
        body = json.dumps(client.get(path).json())
        assert "BUB1B" not in body, path
        assert "it4_" not in body, path


# ---------------------------------------------------------------------------------------
# Models and coverage
# ---------------------------------------------------------------------------------------


def test_models_carry_their_card_and_measured_coverage(client: TestClient) -> None:
    rows = {row["key"]: row for row in get(client, "/api/zoo/models")["data"]}
    alpha = rows["alphamissense"]
    assert alpha["coverage"]["total"] == 200
    assert alpha["coverage"]["scored"] == 50
    assert alpha["coverage"]["fraction"] == pytest.approx(0.25)
    assert (
        sum(entry["scored"] for entry in alpha["coverage"]["by_consequence"].values())
        == alpha["coverage"]["scored"]
    )
    assert {"licence", "non_commercial", "catalogue_adjacent", "tier", "scope"} <= set(alpha)


def test_a_declared_lane_that_never_ran_has_null_coverage(client: TestClient) -> None:
    """Declared is not run. A lane with no cached score reports ``null``, never zero."""
    rows = {row["key"]: row for row in get(client, "/api/zoo/models")["data"]}
    assert rows["spliceai"]["coverage"] is None


def test_the_models_route_is_cached_and_refreshable(client: TestClient) -> None:
    assert get(client, "/api/zoo/models")["cached_at"]
    assert get(client, "/api/zoo/models?refresh=true")["cached_at"]


# ---------------------------------------------------------------------------------------
# Scores
# ---------------------------------------------------------------------------------------


def test_one_allele_carries_its_record_and_every_lane(client: TestClient) -> None:
    allele = _tsv(FIXTURES / "scores" / "alphamissense.tsv")[0]["allele_id"]
    data = get(client, f"/api/zoo/scores?allele_id={allele}")["data"]
    assert data["allele_id"] == allele
    assert set(data["record"]) >= {"gene", "consequence", "hgvs_c", "hgvs_p", "is_read_only"}
    assert {row["model"] for row in data["rows"]} <= set(SCORED_LANES)
    assert data["rows"][0]["aux"] == {"lane": data["rows"][0]["model"]}
    assert data["rows"][0]["ts"]


def test_an_unknown_allele_is_a_404(client: TestClient) -> None:
    assert client.get("/api/zoo/scores?allele_id=deadbeefdeadbeef").status_code == 404


def test_one_gene_carries_every_record_and_its_rows(client: TestClient) -> None:
    data = get(client, "/api/zoo/scores/gene/genea")["data"]
    assert data["gene"] == "GENEA"
    assert data["records"]
    assert data["scored_records"] <= len(data["records"])
    assert all("allele_id" in record for record in data["records"])


def test_an_unknown_gene_is_a_404(client: TestClient) -> None:
    assert client.get("/api/zoo/scores/gene/NOSUCHGENE").status_code == 404


# ---------------------------------------------------------------------------------------
# Ranking, merge, lineage
# ---------------------------------------------------------------------------------------


def test_ranks_report_each_lane_and_the_confirmed_pair(client: TestClient) -> None:
    data = get(client, "/api/zoo/ranks")["data"]
    assert data["run_id"] == RUN_ID
    lanes = {row["model"]: row for row in data["per_model"]}
    assert set(lanes) == set(SCORED_LANES)
    assert lanes["alphamissense"]["unscored_pairs"] == 7
    assert data["pairs_total"] == lanes["alphamissense"]["n_ranked"] + 7
    confirmed = lanes["alphamissense"]["confirmed"]
    assert confirmed["gene"] == CASE_GENE
    assert confirmed["rank"] == 1
    # The two allele percentiles are the merged report's, borrowed for the same run.
    assert confirmed["left_percentile"] == 4.0
    assert confirmed["right_percentile"] == 6.0


def test_ranks_never_claim_that_no_gene_was_skipped(client: TestClient) -> None:
    """The pair builder counts capped genes; nothing persists them. Absent, not empty."""
    data = get(client, "/api/zoo/ranks")["data"]
    assert data["skipped_genes"] == []
    assert data["skipped_genes_recorded"] is False


def test_an_unknown_run_is_a_404(client: TestClient) -> None:
    assert client.get("/api/zoo/ranks?run_id=nope").status_code == 404


def test_merge_gives_a_square_matrix_and_both_consensuses(client: TestClient) -> None:
    data = get(client, "/api/zoo/merge")["data"]
    size = len(data["matrix"]["models"])
    assert size == len(SCORED_LANES)
    assert all(len(row) == size for row in data["matrix"]["rho"])
    assert data["matrix"]["rho"][0][1] == 0.5
    # A cell the merge could not compute stays null rather than becoming a zero.
    assert data["matrix"]["rho"][0][2] is None
    assert data["consensus"]["catalogue_free"]["excluded_lanes"] == ["revel"]
    assert data["consensus"]["all_lanes"]["n"] == 20
    assert data["consensus"]["catalogue_free"]["fused"] == 0.01


def test_merge_names_the_gene_two_lanes_disagree_about(client: TestClient) -> None:
    row = get(client, "/api/zoo/merge")["data"]["disagreements"][0]
    assert row["top_model"] == "esm1b"
    assert row["bottom_model"] == "alphamissense"
    assert row["gene"], "the gene is joined in from the record table"


def test_merge_refuses_to_serve_another_runs_report(client: TestClient) -> None:
    assert client.get("/api/zoo/merge?run_id=other-run").status_code == 404


def test_lineage_is_narrowed_to_the_zoo_tables(client: TestClient) -> None:
    data = get(client, "/api/zoo/lineage")["data"]
    assert {row["target_table"] for row in data["rows"]} == {
        f"{PREFIX}_allele_records",
        "allele_scores",
    }
    one = get(client, "/api/zoo/lineage?table=allele_scores")["data"]
    assert {row["target_table"] for row in one["rows"]} == {"allele_scores"}


def test_a_table_outside_the_zoo_is_refused(client: TestClient) -> None:
    assert client.get("/api/zoo/lineage?table=variants_raw").status_code == 422


# ---------------------------------------------------------------------------------------
# The committed files
# ---------------------------------------------------------------------------------------


def test_runs_are_read_from_the_configured_folder(client: TestClient) -> None:
    rows = get(client, "/api/zoo/runs")["data"]
    assert [row["run_id"] for row in rows] == [RUN_ID]
    assert rows[0]["wall_clock_s"] == 12.5
    assert rows[0]["dollars"] == 0.0


def test_reports_list_the_merged_one_and_each_lane(client: TestClient) -> None:
    rows = get(client, "/api/zoo/reports")["data"]
    assert [row["key"] for row in rows] == ["merged", "alphamissense"]
    assert rows[1]["figures"] == ["../../figures/hist.svg"]


def test_one_report_comes_back_as_markdown(client: TestClient) -> None:
    data = get(client, "/api/zoo/reports/merged")["data"]
    assert data["markdown"].startswith("# The merged report")
    assert data["title"] == "The merged report"


def test_an_unknown_report_is_a_404(client: TestClient) -> None:
    assert client.get("/api/zoo/reports/nope").status_code == 404


# ---------------------------------------------------------------------------------------
# The coordinate rule
# ---------------------------------------------------------------------------------------

ROUTES = (
    "/api/zoo/case",
    "/api/zoo/models",
    "/api/zoo/ranks",
    "/api/zoo/merge",
    "/api/zoo/runs",
    "/api/zoo/reports",
    "/api/zoo/reports/merged",
    "/api/zoo/lineage",
    "/api/zoo/scores/gene/GENEA",
)


def _keys(payload: Any) -> Iterator[str]:
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield key
            yield from _keys(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _keys(item)


@pytest.mark.parametrize("path", ROUTES)
def test_no_response_carries_a_coordinate(client: TestClient, path: str) -> None:
    """Not one route may serve a position, on any nesting level of its payload."""
    body = client.get(path).json()
    leaked = sorted({key for key in _keys(body) if key.lower() in FORBIDDEN_KEYS})
    assert not leaked, f"{path} serves {leaked}"
