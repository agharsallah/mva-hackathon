"""``/api/zoo/score``, ``/api/zoo/run``, ``/api/zoo/jobs/*``: the guard, the job, the payload.

The job **bodies** are injected (:class:`mva.viz.api_zoo_jobs.Runners`), so these tests run the
real routes, the real job manager and the real payload shaping without a warehouse — what is
replaced is exactly one function per verb, and nothing is monkey-patched. Two properties get
most of the attention because they are the ones that would hurt:

* **An open API may read the zoo, never spend the machine.** With ``MVA_VIZ_TOKEN`` empty both
  ``POST``s answer 403 and say why. With it set, the usual ``X-API-Key`` guard applies on top.
* **No coordinate leaves.** A lane's ``aux`` is free-form JSON it wrote itself, so a lane that
  echoes a position into it must not be able to publish one through this route.

The case is a fabricated one in ``tmp_path`` (gene ``GENEG``, prefix ``demo``), exactly as
:mod:`tests.test_viz_zoo` does it, so a route that hard-coded this project's case fails here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mva.reads.api.jobs import Manager
from mva.viz import api_zoo_jobs
from mva.viz.api_zoo_case import Case
from mva.viz.api_zoo_reads import Tables
from mva.viz.auth import guard_dependencies
from mva.warehouse.settings import Postgres
from mva.zoo.case_config import Config

TOKEN = "a-shared-secret"
PREFIX = "demo"
CASE_GENE = "GENEG"

CONFIG = """
[case]
label = "A fabricated case"
iteration = "demo-case"
table_prefix = "{prefix}"
confirmed_gene = "{gene}"

[run]
mode = "catalogue-free"
models = ["alphamissense", "spliceai"]
out_dir = "{out_dir}"
schema = "results"
warehouse_schema = "warehouse"
"""

#: What a scoring job hands back. ``aux`` carries a position on purpose: the route has to
#: strip it, and a test that never sends one could not tell.
SUMMARY: dict[str, Any] = {
    "model": "alphamissense",
    "version": "2023-10",
    "mode": "catalogue-free",
    "run_id": "score-0123456789ab",
    "requested": 2,
    "inserted": 0,
    "skipped": 2,
    "coverage": {"scored": 2, "total": 2, "fraction": 1.0},
    "incomplete": "",
    "wall_clock_seconds": 0.42,
    "rows": [
        {
            "allele_id": "abc123",
            "model": "alphamissense",
            "version": "2023-10",
            "score": 0.91,
            "aux": {"class": "likely_pathogenic", "chrom": "15", "pos": 40161234},
            "venue": "laptop",
            "ts": "2099-01-01T00:00:00",
        }
    ],
}

MANIFEST: dict[str, Any] = {
    "run_id": "demo-0123456789ab",
    "config_digest": "0123456789ab",
    "stages": [{"stage": "normalize", "seconds": 0.1, "rows": 2, "note": "2 records"}],
    "outputs": ["docs/demo-case/report.md"],
    "wall_clock_seconds": 0.5,
    "dollars": 0.0,
}

FORBIDDEN_KEYS = {"pos", "position", "chrom", "chromosome", "start", "end", "ref", "alt"}


@pytest.fixture
def case(tmp_path: Path) -> Case:
    path = tmp_path / "case.toml"
    path.write_text(
        CONFIG.format(prefix=PREFIX, gene=CASE_GENE, out_dir=tmp_path / "build"), "utf-8"
    )
    config = Config.load(path)
    return Case(config=config, tables=Tables.of(config))


def build(
    case: Case,
    tmp_path: Path,
    *,
    token: str = TOKEN,
    score: Any = None,
    run: Any = None,
) -> TestClient:
    """One app holding only these routes, with both job bodies replaced by callables."""
    runners = api_zoo_jobs.Runners(
        score=score or (lambda _settings, _case, _request: dict(SUMMARY)),
        run=run or (lambda _case, _request: dict(MANIFEST)),
    )
    app = FastAPI()
    app.include_router(
        api_zoo_jobs.router(
            Postgres.from_env(),
            token,
            case=case,
            manager=Manager(tmp_path / "jobs", workers=1),
            runners=runners,
        ),
        dependencies=guard_dependencies(token),
    )
    return TestClient(app)


def submit(client: TestClient, body: dict, path: str = "/api/zoo/score") -> dict:
    reply = client.post(path, json=body, headers={"X-API-Key": TOKEN})
    assert reply.status_code == 200, reply.text
    return reply.json()["data"]


def wait(client: TestClient, job_id: str) -> dict:
    reply = client.get(
        f"/api/zoo/jobs/{job_id}/wait", params={"timeout": 10}, headers={"X-API-Key": TOKEN}
    )
    assert reply.status_code == 200, reply.text
    return reply.json()["data"]


# ── the guard ────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("path", "body"),
    [("/api/zoo/score", {"model": "alphamissense"}), ("/api/zoo/run", {})],
)
def test_an_open_api_refuses_to_compute_and_says_why(case, tmp_path, path, body):
    client = build(case, tmp_path, token="")
    reply = client.post(path, json=body)
    assert reply.status_code == 403
    assert "MVA_VIZ_TOKEN is empty" in reply.json()["detail"]
    assert "the read routes do not" in reply.json()["detail"]


def test_a_wrong_key_is_refused_before_the_route_is_reached(case, tmp_path):
    client = build(case, tmp_path)
    assert client.post("/api/zoo/score", json={"model": "alphamissense"}).status_code == 401
    reply = client.post(
        "/api/zoo/score", json={"model": "alphamissense"}, headers={"X-API-Key": "wrong"}
    )
    assert reply.status_code == 401


def test_the_read_routes_are_reachable_on_an_open_api(case, tmp_path):
    """They can only report on jobs that were never allowed to start, so they stay open."""
    client = build(case, tmp_path, token="")
    reply = client.get("/api/zoo/jobs")
    assert reply.status_code == 200
    assert reply.json()["data"] == []


# ── the scoring job ──────────────────────────────────────────────────────────────────────


def test_a_scoring_job_comes_back_with_an_id_then_a_summary(case, tmp_path):
    client = build(case, tmp_path)
    submitted = submit(client, {"model": "alphamissense", "allele_ids": ["abc123", "def456"]})
    assert submitted["job_id"]
    assert submitted["verb"] == "zoo-score"
    assert submitted["case"]["confirmed_gene"] == CASE_GENE

    done = wait(client, submitted["job_id"])
    assert done["state"] == "done"
    assert done["summary"]["inserted"] == 0
    assert done["summary"]["skipped"] == 2  # the idempotence the cache key gives
    assert done["summary"]["coverage"] == {"scored": 2, "total": 2, "fraction": 1.0}
    assert "rows" not in done["summary"]  # the rows are a sibling field, not part of it
    assert [row["allele_id"] for row in done["rows"]] == ["abc123"]


def test_the_rows_are_dropped_when_no_allele_ids_were_asked_for(case, tmp_path):
    """A whole-callset run answers with its summary; the rows are read back through /scores."""
    client = build(case, tmp_path)
    job = submit(client, {"model": "alphamissense"})
    assert job["params"]["alleles"] is None
    done = wait(client, job["job_id"])
    assert done["summary"]["requested"] == 2
    assert done["rows"] == []


def test_a_position_in_a_lane_s_aux_never_leaves_the_api(case, tmp_path):
    client = build(case, tmp_path)
    done = wait(
        client, submit(client, {"model": "alphamissense", "allele_ids": ["abc123"]})["job_id"]
    )
    aux = done["rows"][0]["aux"]
    assert aux == {"class": "likely_pathogenic"}
    assert not _coordinates(done)


def test_a_failing_job_reports_the_error_rather_than_a_summary(case, tmp_path):
    def explode(_settings, _case, _request):
        raise RuntimeError("the adapter could not open its table")

    client = build(case, tmp_path, score=explode)
    done = wait(client, submit(client, {"model": "alphamissense"})["job_id"])
    assert done["state"] == "failed"
    assert "could not open its table" in done["error"]
    assert done["summary"] is None


def test_an_unknown_model_is_refused_before_a_job_is_created(case, tmp_path):
    client = build(case, tmp_path)
    reply = client.post(
        "/api/zoo/score", json={"model": "not-a-model"}, headers={"X-API-Key": TOKEN}
    )
    assert reply.status_code == 404
    assert "known:" in reply.json()["detail"]
    assert client.get("/api/zoo/jobs", headers={"X-API-Key": TOKEN}).json()["data"] == []


def test_the_mode_defaults_to_the_case_s_own(case, tmp_path):
    client = build(case, tmp_path)
    job = submit(client, {"model": "alphamissense"})
    assert job["params"]["mode"] == "catalogue-free"
    assert submit(client, {"model": "alphamissense", "mode": "aware"})["params"]["mode"] == "aware"


# ── the workflow job ─────────────────────────────────────────────────────────────────────


def test_a_run_job_returns_the_manifest_as_its_summary(case, tmp_path):
    client = build(case, tmp_path)
    job = submit(client, {"from_stage": "collect"}, path="/api/zoo/run")
    assert job["verb"] == "zoo-run"
    assert job["params"]["from_stage"] == "collect"
    done = wait(client, job["job_id"])
    assert done["summary"]["run_id"] == MANIFEST["run_id"]
    assert done["summary"]["outputs"] == MANIFEST["outputs"]
    assert not _coordinates(done)


def test_the_listing_shows_both_verbs_newest_first(case, tmp_path):
    client = build(case, tmp_path)
    first = submit(client, {"model": "alphamissense"})
    second = submit(client, {}, path="/api/zoo/run")
    wait(client, first["job_id"])
    wait(client, second["job_id"])
    listed = client.get("/api/zoo/jobs", headers={"X-API-Key": TOKEN}).json()["data"]
    assert [job["verb"] for job in listed] == ["zoo-run", "zoo-score"]


def test_an_unknown_job_id_is_a_404(case, tmp_path):
    client = build(case, tmp_path)
    for path in ("/api/zoo/jobs/nope", "/api/zoo/jobs/nope/wait"):
        reply = client.get(path, headers={"X-API-Key": TOKEN})
        assert reply.status_code == 404, path


def test_a_long_poll_timeout_is_capped_so_a_proxy_does_not_cut_it(case, tmp_path):
    client = build(case, tmp_path)
    job = submit(client, {"model": "alphamissense"})
    reply = client.get(
        f"/api/zoo/jobs/{job['job_id']}/wait",
        params={"timeout": 900},
        headers={"X-API-Key": TOKEN},
    )
    assert reply.status_code == 422


# ── registration ─────────────────────────────────────────────────────────────────────────


def test_the_routes_are_wired_into_the_real_application():
    """They have to be on the app the server serves, not only on a test's own router."""
    from mva.viz.app import create_app

    paths = set(create_app(token="").openapi()["paths"])
    assert {"/api/zoo/score", "/api/zoo/run", "/api/zoo/jobs", "/api/zoo/jobs/{job_id}"} <= paths


def _coordinates(payload: Any) -> list[str]:
    """Every key anywhere in a payload that would be a genomic position."""
    found: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                found.append(str(key))
            found.extend(_coordinates(value))
    elif isinstance(payload, list):
        for item in payload:
            found.extend(_coordinates(item))
    return found
