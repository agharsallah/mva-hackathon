"""The reads API: job lifecycle, validation at the edge, auth, and restart history.

No store and no DuckDB: the runners' access layer is monkeypatched, so these tests
exercise exactly what the API adds — everything below it is covered elsewhere.
"""

import threading

import pytest
from fastapi.testclient import TestClient

from mva.reads.api import runners
from mva.reads.api.app import create_app
from mva.reads.api.jobs import DONE, LOST, Manager
from mva.reads.scan import Hit


class FakeConnection:
    description = [("lane",), ("n",)]

    def interrupt(self):
        pass

    def execute(self, query):
        return self

    def fetchall(self):
        return [(1, 2)]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("MVA_API_TOKEN", raising=False)
    monkeypatch.setattr(runners.access, "resolve_root",
                        lambda root=None: root or "s3://test/reads")
    monkeypatch.setattr(runners.access, "connection",
                        lambda root: FakeConnection())
    manager = Manager(directory=tmp_path / "jobs", workers=1)
    with TestClient(create_app(manager)) as running:
        yield running


def finished(client, response) -> dict:
    assert response.status_code == 202, response.text
    job_id = response.json()["id"]
    done = client.get(f"/jobs/{job_id}/wait", params={"timeout": 10}).json()
    return done


def test_scan_runs_as_a_job_and_returns_hits(client, monkeypatch):
    hit = Hit(probe="brca", lane=1, read_num=1, tile=1101, x=5, y=7,
              position=12, strand="+", sequence="ACGT")
    monkeypatch.setattr(runners.scan, "kmers",
                        lambda conn, root, probes, limit, names: [hit])
    job = finished(client, client.post("/scan", json={
        "probes": [{"sequence": "acgt", "name": "brca"}], "limit": 5}))
    assert job["state"] == DONE
    assert job["result"]["hits"][0]["probe"] == "brca"
    assert job["result"]["root"] == "s3://test/reads"


def test_count_attaches_a_verdict_per_probe(client, monkeypatch):
    monkeypatch.setattr(runners.scan, "counts",
                        lambda conn, root, probes, names: [("real", 20, 15, 35, 4)])
    job = finished(client, client.post("/count", json={
        "probes": [{"sequence": "ACGT", "name": "real"},
                   {"sequence": "TTTT", "name": "missing"}]}))
    by_name = {row["probe"]: row for row in job["result"]["counts"]}
    assert by_name["real"]["verdict"] == "present"
    assert by_name["missing"] == {"probe": "missing", "forward": 0, "reverse": 0,
                                  "total": 0, "lanes": 0, "verdict": "absent"}


def test_a_probe_that_is_not_dna_is_refused_before_any_job(client):
    response = client.post("/scan", json={"probes": [{"sequence": "HELLO"}]})
    assert response.status_code == 422
    assert client.get("/jobs").json() == []


def test_sql_rejects_writes_and_multiple_statements(client):
    for query in ("DROP TABLE reads", "SELECT 1; SELECT 2"):
        assert client.post("/sql", json={"query": query}).status_code == 422


def test_sql_returns_columns_and_rows(client, monkeypatch):
    monkeypatch.setattr(runners.scan, "sql",
                        lambda conn, root, query: [(1, 2)])
    job = finished(client, client.post("/sql", json={
        "query": "SELECT lane, count(*) AS n FROM reads GROUP BY lane"}))
    assert job["result"] == {"root": "s3://test/reads",
                             "seconds": job["result"]["seconds"],
                             "columns": ["lane", "n"], "row_count": 1,
                             "truncated": False, "rows": [[1, 2]]}


def test_a_failing_runner_becomes_a_failed_job_with_the_reason(client, monkeypatch):
    def boom(conn, root, probes, limit, names):
        raise RuntimeError("shard missing")
    monkeypatch.setattr(runners.scan, "kmers", boom)
    job = finished(client, client.post("/scan",
                                       json={"probes": [{"sequence": "ACGT"}]}))
    assert job["state"] == "failed"
    assert "shard missing" in job["error"]


def test_cancel_interrupts_a_running_job(client, monkeypatch):
    release = threading.Event()

    def slow(conn, root, probes, limit, names):
        release.wait(10)
        raise RuntimeError("interrupted")

    monkeypatch.setattr(runners.scan, "kmers", slow)
    job_id = client.post("/scan",
                         json={"probes": [{"sequence": "ACGT"}]}).json()["id"]
    cancelled = client.post(f"/jobs/{job_id}/cancel")
    assert cancelled.status_code == 200
    release.set()
    assert client.get(f"/jobs/{job_id}/wait",
                      params={"timeout": 10}).json()["state"] == "cancelled"


def test_cancel_after_the_job_finished_is_a_conflict(client, monkeypatch):
    monkeypatch.setattr(runners.scan, "kmers", lambda *a, **k: [])
    job = finished(client, client.post("/scan",
                                       json={"probes": [{"sequence": "ACGT"}]}))
    assert client.post(f"/jobs/{job['id']}/cancel").status_code == 409


def test_unknown_job_is_404(client):
    assert client.get("/jobs/deadbeef").status_code == 404


def test_history_survives_a_restart_and_inflight_jobs_are_lost(tmp_path):
    directory = tmp_path / "jobs"
    first = Manager(directory=directory, workers=1)
    done = first.submit("scan", {"probes": 1}, lambda job: {"hits": []})
    stuck = first.submit("scan", {"probes": 1}, lambda job: {"hits": []})
    first.wait(done, 5)
    first.wait(stuck, 5)
    # forge a crash: rewrite one record as still running, then reload
    record = directory / f"{stuck.id}.json"
    record.write_text(record.read_text().replace('"done"', '"running"'))
    second = Manager(directory=directory, workers=1)
    assert second.get(done.id).state == DONE
    assert second.get(done.id).result == {"hits": []}
    assert second.get(stuck.id).state == LOST


def test_token_required_when_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("MVA_API_TOKEN", "sesame")
    with TestClient(create_app(Manager(directory=None, workers=1))) as client:
        assert client.get("/health").status_code == 200  # liveness needs no secret
        assert client.get("/jobs").status_code == 401
        assert client.get("/jobs", headers={"X-API-Key": "wrong"}).status_code == 401
        assert client.get("/jobs",
                          headers={"X-API-Key": "sesame"}).status_code == 200
