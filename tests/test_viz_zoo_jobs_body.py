"""``POST /api/zoo/score`` with the **real** job body: adapter, coverage, cache, lineage.

:mod:`tests.test_viz_zoo_jobs` pins the routes, the guard and the payload shaping with the job
body replaced. What it cannot see is the body itself — the four calls ``mva-zoo score`` makes —
and the property step 3 rests on (entry 122): **a re-run of the same alleles inserts nothing**,
because the cache key is ``(model, version, allele_id)``. These tests run that body through the
route, end to end, on synthetic data:

* the records are ``fixtures/it4/records.tsv`` (200 invented alleles on a fake chromosome),
  written as the ``records.parquet`` step 1 produces;
* the warehouse is an in-memory DuckDB with a ``pg`` catalogue attached — the production
  connection *is* DuckDB with Postgres attached as ``pg``, so the SQL is the real SQL. The
  one replacement is :func:`mva.warehouse.postgres.attached`, the function that would open the
  hosted server; the route, the job manager, the adapter, the cache and the lineage writer are
  all the production code;
* the lane is ``alphamissense`` from the real registry: a warehouse column, joined in SQL.

No network, no real warehouse, no patient value.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import duckdb
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mva.reads.api.jobs import Manager
from mva.viz import api_zoo_jobs
from mva.viz.api_zoo_case import Case
from mva.viz.api_zoo_reads import Tables
from mva.viz.auth import guard_dependencies
from mva.warehouse import postgres
from mva.warehouse.settings import Postgres
from mva.zoo.case_config import Config
from mva.zoo.types import ALLELE_SCORES_TABLE

TOKEN = "a-shared-secret"
FIXTURES = Path("fixtures/it4")
SCHEMA = "warehouse"
MODEL = "alphamissense"

CONFIG = """
[case]
label = "A fabricated case"
iteration = "demo-case"
table_prefix = "demo"
confirmed_gene = "GENEA"

[run]
mode = "catalogue-free"
models = ["alphamissense"]
out_dir = "{out_dir}"
schema = "results"
warehouse_schema = "warehouse"
"""


@pytest.fixture
def warehouse(tmp_path: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    """``pg.warehouse.it2_insilico_annotations`` holding the fixture's AlphaMissense scores.

    Keyed by coordinate like the real table: the lane computes the allele id in SQL and joins,
    so a fixture score only lands if the id the SQL computes matches the record's.
    """
    con = duckdb.connect()
    con.execute("ATTACH ':memory:' AS pg")
    con.execute(f"CREATE SCHEMA pg.{SCHEMA}")
    con.execute(
        f"""
        CREATE TABLE pg.{SCHEMA}.it2_insilico_annotations AS
        SELECT r.chrom, r.pos, r.ref, r.alt, s.score AS am_pathogenicity,
               'likely_pathogenic' AS am_class
        FROM read_csv(?, delim='\t', header=true) r
        JOIN read_csv(?, delim='\t', header=true) s USING (allele_id)
        """,
        [str(FIXTURES / "records.tsv"), str(FIXTURES / "scores" / f"{MODEL}.tsv")],
    )
    yield con
    con.close()


@pytest.fixture
def case(tmp_path: Path) -> Case:
    """A case whose ``out_dir`` holds the fixture records as ``records.parquet``."""
    out_dir = tmp_path / "build"
    out_dir.mkdir()
    con = duckdb.connect()
    con.execute(
        "CREATE TEMP TABLE raw AS SELECT * FROM read_csv(?, delim='\t', header=true)",
        [str(FIXTURES / "records.tsv")],
    )
    con.execute("COPY raw TO ? (FORMAT parquet)", [str(out_dir / "records.parquet")])
    con.close()
    path = tmp_path / "case.toml"
    path.write_text(CONFIG.format(out_dir=out_dir), encoding="utf-8")
    config = Config.load(path)
    return Case(config=config, tables=Tables.of(config))


@pytest.fixture
def client(
    case: Case, tmp_path: Path, warehouse: duckdb.DuckDBPyConnection, monkeypatch
) -> TestClient:
    """The real routes and the real job body, with the hosted server swapped for ``warehouse``."""

    @contextlib.contextmanager
    def attached(_settings: Postgres, read_only: bool = False) -> Iterator[Any]:
        yield warehouse  # left open: the test reads it back after the job

    monkeypatch.setattr(postgres, "attached", attached)
    app = FastAPI()
    app.include_router(
        api_zoo_jobs.router(
            Postgres.from_env(), TOKEN, case=case, manager=Manager(tmp_path / "jobs", workers=1)
        ),
        dependencies=guard_dependencies(TOKEN),
    )
    return TestClient(app)


def score(client: TestClient, body: dict[str, Any]) -> dict[str, Any]:
    """Submit, long-poll to a terminal state, return the job as the API serves it."""
    headers = {"X-API-Key": TOKEN}
    reply = client.post("/api/zoo/score", json=body, headers=headers)
    assert reply.status_code == 200, reply.text
    job_id = reply.json()["data"]["job_id"]
    done = client.get(f"/api/zoo/jobs/{job_id}/wait", params={"timeout": 30}, headers=headers)
    assert done.status_code == 200, done.text
    return done.json()["data"]


def scored_ids(n: int) -> list[str]:
    """The first ``n`` allele ids the fixture gives AlphaMissense a score for, sorted."""
    rows = duckdb.execute(
        "SELECT allele_id FROM read_csv(?, delim='\t', header=true) ORDER BY allele_id LIMIT ?",
        [str(FIXTURES / "scores" / f"{MODEL}.tsv"), n],
    ).fetchall()
    return [str(row[0]) for row in rows]


def cached(warehouse: duckdb.DuckDBPyConnection) -> int:
    return int(
        warehouse.execute(f"SELECT count(*) FROM pg.{SCHEMA}.{ALLELE_SCORES_TABLE}").fetchone()[0]
    )


def lineage_rows(warehouse: duckdb.DuckDBPyConnection) -> list[tuple]:
    return warehouse.execute(
        f"SELECT transform, target_rows FROM pg.{SCHEMA}.data_lineage "
        f"WHERE transform = 'it4-score:{MODEL}' ORDER BY produced_at"
    ).fetchall()


def test_a_score_job_writes_the_cache_and_one_lineage_edge(client, warehouse):
    ids = scored_ids(3)
    job = score(client, {"model": MODEL, "allele_ids": ids})

    assert job["state"] == "done", job["error"]
    summary = job["summary"]
    assert summary["model"] == MODEL
    assert summary["mode"] == "catalogue-free"  # the case's own mode
    assert (summary["requested"], summary["inserted"], summary["skipped"]) == (3, 3, 0)
    assert summary["coverage"] == {"scored": 3, "total": 3, "fraction": 1.0}
    assert cached(warehouse) == 3
    assert lineage_rows(warehouse) == [(f"it4-score:{MODEL}", 3)]
    # The rows come back sorted, each stamped with the mode that produced it.
    assert [row["allele_id"] for row in job["rows"]] == ids
    assert all(row["aux"]["mode"] == "catalogue-free" for row in job["rows"])


def test_a_re_run_of_the_same_alleles_inserts_nothing(client, warehouse):
    """Entry 122's no-op proof, through the API: the second pass is all ``skipped``."""
    ids = scored_ids(3)
    score(client, {"model": MODEL, "allele_ids": ids})

    again = score(client, {"model": MODEL, "allele_ids": ids})

    assert (again["summary"]["inserted"], again["summary"]["skipped"]) == (0, 3)
    assert cached(warehouse) == 3
    # Every attempt leaves an edge — the edge list records attempts, the table records state.
    assert sorted((rows for _, rows in lineage_rows(warehouse)), reverse=True) == [3, 0]


def test_the_aware_mode_does_not_re_score_what_the_free_mode_cached(client, warehouse):
    """The cache key has no mode in it; a lane that ignores ``clin_sig`` scores the same."""
    ids = scored_ids(2)
    score(client, {"model": MODEL, "allele_ids": ids})
    aware = score(client, {"model": MODEL, "allele_ids": ids, "mode": "aware"})
    assert aware["summary"]["mode"] == "aware"
    assert aware["summary"]["inserted"] == 0
    assert cached(warehouse) == 2


def test_a_whole_callset_run_answers_with_its_summary_only(client, warehouse):
    job = score(client, {"model": MODEL})
    summary = job["summary"]
    assert summary["requested"] == 200  # every fixture record was asked about
    assert summary["inserted"] == summary["coverage"]["scored"] == cached(warehouse)
    assert job["rows"] == []  # read them back through GET /api/zoo/scores instead


@pytest.mark.parametrize(
    ("body", "error"),
    [
        ({"model": MODEL, "allele_ids": ["no-such-allele"]}, "holds no record"),
        ({"model": MODEL, "mode": "not-a-mode"}, "unknown mode"),
    ],
)
def test_a_request_the_body_cannot_serve_fails_the_job_and_writes_nothing(
    client, warehouse, body, error
):
    job = score(client, body)
    assert job["state"] == "failed"
    assert error in job["error"]
    assert job["summary"] is None
    assert not warehouse.execute(
        "SELECT 1 FROM duckdb_tables() WHERE database_name = 'pg' AND table_name = ?",
        [ALLELE_SCORES_TABLE],
    ).fetchall()


def test_a_body_that_is_not_the_contract_is_a_422(client):
    headers = {"X-API-Key": TOKEN}
    for body in ({}, {"model": ""}, {"model": MODEL, "allele_ids": "not-a-list"}):
        assert client.post("/api/zoo/score", json=body, headers=headers).status_code == 422, body
