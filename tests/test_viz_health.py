"""``GET /api/health/dependencies``: the seven probes, the overall rule, the never-5xx rule.

Two layers, in the style of `test_viz_units.py` and `test_viz_api.py`:

* Unit tests call `health_probes.probe_*` directly with a fake Postgres/ObjectStore/
  Upstream — no network, no database — to prove each probe's own up/degraded/down/
  skipped logic.
* Route tests go through `TestClient` with `health_probes.fetch` and the object-store /
  Ensembl / reads-API seams replaced, to prove the orchestration: concurrency, the
  overall rule, the envelope, and that nothing here can turn into a 5xx.

The password and access key below are fabricated strings assigned only so the
secret-leak tests have something real to look for; neither is a credential that works
anywhere.
"""

import asyncio

import httpx
from fastapi.testclient import TestClient

from mva.viz import health, health_probes, health_results
from mva.viz.app import create_app
from mva.viz.cache import Cache
from mva.viz.proxy import Reply, UnreachableError, Upstream
from mva.warehouse.objects import ObjectStore, diagnose
from mva.warehouse.objects import UnreachableError as StoreUnreachableError
from mva.warehouse.postgres import Result
from mva.warehouse.settings import Postgres

#: A fully configured warehouse, distinct from `Postgres()`'s empty defaults so the
#: "missing settings" remedy path is never accidentally exercised by these tests.
SETTINGS = Postgres(
    host="db.example",
    port="5432",
    database="mva",
    user="mva",
    password="s3cret-pg-password",
    schema="warehouse",
    result_schema="results",
)

#: A fully configured object store, likewise distinct from the all-blank default.
STORE = ObjectStore(
    endpoint="minio.example:9012",
    access_key="AKIAEXAMPLE",
    secret_key="s3cret-access-key",
    bucket="mva",
    use_ssl=False,
)

#: Row counts the "everything is healthy" fixture reports for the two reference tables.
REFERENCE_COUNTS = {"gnomad_constraint": 18314, "clinvar_panel": 4468152}


def healthy_fetch(settings, sql, params=None):
    """Answers every SQL the health checks issue when the warehouse is fully healthy."""
    if sql.strip() == "SELECT 1":
        return []
    if "information_schema.schemata" in sql:
        return [{"schema_name": settings.schema}, {"schema_name": settings.result_schema}]
    if "information_schema.tables" in sql:
        return [{"table_name": "gnomad_constraint"}, {"table_name": "clinvar_panel"}]
    for table, count in REFERENCE_COUNTS.items():
        if table in sql:
            return [{"n": count}]
    raise AssertionError(f"unexpected SQL: {sql}")


class FakeResponse:
    def __init__(self, status_code=200, text='{"ping":1}'):
        self.status_code = status_code
        self.text = text


class FakeHttpx:
    """A stand-in for the `httpx` module: only what `probe_ensembl` uses."""

    HTTPError = httpx.HTTPError

    def get(self, url, timeout=None):
        return FakeResponse()


class RaisingHttpx:
    HTTPError = httpx.HTTPError

    def get(self, url, timeout=None):
        raise httpx.ConnectError("boom")


class Fake(Upstream):
    """A reads API that always answers ``status``/``body`` without a network call."""

    def __init__(self, status=200, body=None):
        self.status, self.body = status, body or {}

    async def request(self, method, path, *, params=None, json=None, timeout=30.0):  # noqa: ASYNC109
        return Reply(self.status, self.body)


class Down(Upstream):
    """A reads API that is simply not running — `mva-reads-api`'s current state."""

    async def request(self, *args, **kwargs):
        raise UnreachableError("http://127.0.0.1:8765")


def _raise(*args, **kwargs):
    raise RuntimeError("boom")


def client(
    tmp_path,
    monkeypatch,
    *,
    upstream: Upstream | None = None,
    store: ObjectStore = STORE,
    settings: Postgres = SETTINGS,
    fetch=healthy_fetch,
) -> TestClient:
    """A running app with every dependency seam replaced by a healthy fake by default."""
    monkeypatch.setattr(health_probes, "fetch", fetch)
    monkeypatch.setattr(health_probes, "httpx", FakeHttpx())
    monkeypatch.setattr(health_probes.objects_mod, "listing", lambda store, prefix="": ["a", "b"])
    monkeypatch.setattr(
        health_probes.objects_mod, "query", lambda store, sql: Result(("n",), [(8,)])
    )
    return TestClient(
        create_app(
            settings=settings,
            cache=Cache(tmp_path),
            origins=[],
            upstream=upstream or Fake(200, {"ok": True}),
            store=store,
        )
    )


def dependencies(running: TestClient) -> dict:
    response = running.get("/api/health/dependencies")
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"data", "cached_at", "source"}
    assert body["cached_at"] is None  # the contract's fixed envelope shape for this route
    assert body["source"] == "live dependency probes"
    return body["data"]


def by_id(data: dict) -> dict:
    return {check["id"]: check for check in data["checks"]}


# ── everything healthy ───────────────────────────────────────────────────────────────


def test_every_check_is_up_and_overall_is_up(tmp_path, monkeypatch):
    data = dependencies(client(tmp_path, monkeypatch))
    checks = by_id(data)
    assert set(checks) == {
        "viz-api",
        "warehouse",
        "object-store",
        "parquet",
        "reads-api",
        "ensembl",
        "reference-snapshots",
    }
    for check_id, check in checks.items():
        assert check["status"] == "up", (check_id, check)
        assert check["remedy"] is None
        assert isinstance(check["latency_ms"], int) and check["latency_ms"] >= 0
    assert data["overall"] == "up"
    assert data["checked_at"]


def test_the_seven_checks_come_back_in_the_contracts_order(tmp_path, monkeypatch):
    data = dependencies(client(tmp_path, monkeypatch))
    assert [c["id"] for c in data["checks"]] == [
        "viz-api",
        "warehouse",
        "object-store",
        "parquet",
        "reads-api",
        "ensembl",
        "reference-snapshots",
    ]


def test_every_check_names_the_pages_it_powers(tmp_path, monkeypatch):
    checks = by_id(dependencies(client(tmp_path, monkeypatch)))
    assert checks["reads-api"]["powers"] == ["Probes"]
    assert checks["ensembl"]["powers"] == ["Panel"]
    assert "Panel" in checks["reference-snapshots"]["powers"]
    assert checks["viz-api"]["kind"] == "internal"
    assert checks["ensembl"]["kind"] == "third-party"
    assert checks["reference-snapshots"]["kind"] == "snapshot"


# ── one check down (or skipped) at a time ────────────────────────────────────────────


def test_viz_api_is_always_up():
    result = health_probes.probe_viz_api("mva-viz-api", "1.0.0")
    assert result["status"] == "up"
    assert "mva-viz-api" in result["detail"]


def test_warehouse_down_when_select_1_fails(monkeypatch):
    monkeypatch.setattr(health_probes, "fetch", _raise)
    result = health_probes.probe_warehouse(SETTINGS)
    assert result["status"] == "down"
    assert result["detail"] == "boom"
    assert result["remedy"]


def test_warehouse_degraded_when_a_schema_is_missing(monkeypatch):
    def missing_result_schema(settings, sql, params=None):
        if sql.strip() == "SELECT 1":
            return []
        return [{"schema_name": settings.schema}]  # result_schema absent

    monkeypatch.setattr(health_probes, "fetch", missing_result_schema)
    result = health_probes.probe_warehouse(SETTINGS)
    assert result["status"] == "degraded"
    assert "results" in result["detail"]


def test_object_store_down_when_listing_is_unreachable(monkeypatch):
    def boom(store, prefix=""):
        raise StoreUnreachableError(diagnose(store, ConnectionError("refused")))

    monkeypatch.setattr(health_probes.objects_mod, "listing", boom)
    result = health_probes.probe_object_store(STORE)
    assert result["status"] == "down"
    assert "cannot reach the object store" in result["remedy"]


def test_object_store_skipped_when_unconfigured():
    result = health_probes.probe_object_store(ObjectStore())
    assert result["status"] == "skipped"
    assert result["remedy"] is not None


def test_parquet_down_when_the_read_fails(monkeypatch):
    monkeypatch.setattr(health_probes.objects_mod, "query", _raise)
    result = health_probes.probe_parquet(STORE)
    assert result["status"] == "down"
    assert result["remedy"]


def test_parquet_skipped_when_unconfigured():
    result = health_probes.probe_parquet(ObjectStore())
    assert result["status"] == "skipped"
    assert result["remedy"] is not None


def test_reads_api_down_when_unreachable():
    result = asyncio.run(health_probes.probe_reads_api(Down()))
    assert result["status"] == "down"
    assert "unreachable" in result["detail"]


def test_reads_api_down_on_an_unhealthy_status():
    result = asyncio.run(health_probes.probe_reads_api(Fake(503, {"detail": "starting up"})))
    assert result["status"] == "down"
    assert "503" in result["detail"]


def test_ensembl_down_when_the_request_fails(monkeypatch):
    monkeypatch.setattr(health_probes, "httpx", RaisingHttpx())
    result = health_probes.probe_ensembl()
    assert result["status"] == "down"
    assert result["remedy"]


def test_reference_snapshots_degraded_when_a_table_is_missing(monkeypatch):
    def one_table_only(settings, sql, params=None):
        if sql.strip() == "SELECT 1":
            return []
        if "information_schema.tables" in sql:
            return [{"table_name": "gnomad_constraint"}]  # clinvar_panel missing
        return [{"n": 1}]

    monkeypatch.setattr(health_probes, "fetch", one_table_only)
    result = health_probes.probe_reference_snapshots(SETTINGS)
    assert result["status"] == "degraded"
    assert "clinvar_panel" in result["detail"]


def test_reference_snapshots_degraded_when_a_table_is_empty(monkeypatch):
    def empty_clinvar(settings, sql, params=None):
        if sql.strip() == "SELECT 1":
            return []
        if "information_schema.tables" in sql:
            return [{"table_name": "gnomad_constraint"}, {"table_name": "clinvar_panel"}]
        if "clinvar_panel" in sql:
            return [{"n": 0}]
        return [{"n": 18314}]

    monkeypatch.setattr(health_probes, "fetch", empty_clinvar)
    result = health_probes.probe_reference_snapshots(SETTINGS)
    assert result["status"] == "degraded"
    assert "empty" in result["detail"]


def test_reference_snapshots_names_the_release_when_healthy(monkeypatch):
    monkeypatch.setattr(health_probes, "fetch", healthy_fetch)
    result = health_probes.probe_reference_snapshots(SETTINGS)
    assert result["status"] == "up"
    assert "gnomAD" in result["detail"]
    assert "ClinVar" in result["detail"]


# ── overall, computed per the contract's rules ───────────────────────────────────────


def test_overall_is_down_when_an_internal_check_is_down(tmp_path, monkeypatch):
    data = dependencies(client(tmp_path, monkeypatch, fetch=_raise))
    checks = by_id(data)
    assert checks["warehouse"]["status"] == "down"
    assert checks["warehouse"]["kind"] == "internal"
    assert data["overall"] == "down"


def test_overall_is_degraded_not_down_when_only_upstream_is_down(tmp_path, monkeypatch):
    data = dependencies(client(tmp_path, monkeypatch, upstream=Down()))
    checks = by_id(data)
    assert checks["reads-api"]["status"] == "down"
    assert checks["reads-api"]["kind"] == "upstream"
    assert data["overall"] == "degraded"


def test_overall_is_degraded_not_down_when_only_ensembl_is_down(tmp_path, monkeypatch):
    running = client(tmp_path, monkeypatch)
    monkeypatch.setattr(
        health_probes,
        "probe_ensembl",
        lambda timeout=2.0: health_probes.down("unreachable", "retry later"),
    )
    data = dependencies(running)
    assert by_id(data)["ensembl"]["status"] == "down"
    assert by_id(data)["ensembl"]["kind"] == "third-party"
    assert data["overall"] == "degraded"


def test_skipped_never_degrades_overall(tmp_path, monkeypatch):
    """An unconfigured object store is a valid deployment, not a failure."""
    data = dependencies(client(tmp_path, monkeypatch, store=ObjectStore()))
    checks = by_id(data)
    assert checks["object-store"]["status"] == "skipped"
    assert checks["object-store"]["latency_ms"] is None
    assert checks["parquet"]["status"] == "skipped"
    assert checks["parquet"]["latency_ms"] is None
    assert data["overall"] == "up"


# ── the endpoint can never 5xx ───────────────────────────────────────────────────────


def test_every_check_down_still_answers_200(tmp_path, monkeypatch):
    running = client(tmp_path, monkeypatch, upstream=Down(), fetch=_raise)
    monkeypatch.setattr(health_probes.objects_mod, "listing", _raise)
    monkeypatch.setattr(health_probes.objects_mod, "query", _raise)
    monkeypatch.setattr(health_probes, "httpx", RaisingHttpx())

    response = running.get("/api/health/dependencies")
    assert response.status_code == 200
    data = response.json()["data"]
    for check in data["checks"]:
        if check["id"] == "viz-api":
            continue  # this process answering the request is itself proof it is up
        assert check["status"] in ("down", "degraded", "skipped"), check
    assert data["overall"] == "down"


def test_a_probe_that_raises_something_unexpected_still_becomes_down(tmp_path, monkeypatch):
    """`run_check`'s own safety net: a bug in a probe must not 5xx the endpoint."""
    running = client(tmp_path, monkeypatch)

    def boom(service, version):
        raise ValueError("a bug nobody caught")

    monkeypatch.setattr(health_probes, "probe_viz_api", boom)
    data = dependencies(running)
    assert by_id(data)["viz-api"]["status"] == "down"
    assert "a bug nobody caught" in by_id(data)["viz-api"]["detail"]


# ── a timeout still says where it was probing ────────────────────────────────────────


#: Short enough that the timeout test does not slow the suite; the budget under test is
#: passed in explicitly, so the production numbers stay out of this.
TEST_BUDGET = 0.05


async def _never_returns():
    await asyncio.sleep(TEST_BUDGET + 5)
    return health_probes.up("should never get here")  # pragma: no cover


def test_a_timeout_still_reports_the_endpoint_it_was_probing():
    """`run_check`'s own safety net never reaches the probe's code that sets `endpoint`."""
    result = asyncio.run(
        health.run_check(
            "warehouse",
            _never_returns(),
            "db.example:5432/mva (password: set)",
            budget=TEST_BUDGET,
        )
    )
    assert result["status"] == "down"
    assert result["detail"] == f"timed out after {TEST_BUDGET:.0f}s"
    assert result["endpoint"] == "db.example:5432/mva (password: set)"
    assert result["timeout_ms"] == round(TEST_BUDGET * 1000)


def test_a_timeouts_remedy_names_the_knob_that_raises_the_budget():
    """A slow-but-alive dependency must not send a developer hunting a phantom outage."""
    result = asyncio.run(health.run_check("warehouse", _never_returns(), None, TEST_BUDGET))
    assert "MVA_HEALTH_TIMEOUTS=warehouse=" in result["remedy"]


def test_static_endpoint_is_null_only_for_this_process_itself():
    store, settings = ObjectStore(), Postgres()
    for check_id in health_results.REGISTRY:
        endpoint = health_probes.static_endpoint(check_id, settings, store)
        if check_id == "viz-api":
            assert endpoint is None
        else:
            assert endpoint, check_id


# ── no secret ever reaches the response ──────────────────────────────────────────────


def test_no_password_or_access_key_in_the_response_body(tmp_path, monkeypatch):
    response = client(tmp_path, monkeypatch).get("/api/health/dependencies")
    text = response.text
    assert SETTINGS.password not in text
    assert STORE.secret_key not in text
    assert STORE.access_key not in text


def test_the_password_is_redacted_even_out_of_a_failing_drivers_own_message(tmp_path, monkeypatch):
    """A connection library could echo its DSN back on failure; this proves it is scrubbed."""

    def leaky(settings, sql, params=None):
        raise RuntimeError(f"auth failed, tried password={settings.password}")

    response = client(tmp_path, monkeypatch, fetch=leaky).get("/api/health/dependencies")
    assert response.status_code == 200
    assert SETTINGS.password not in response.text
    assert "[redacted]" in response.text


def test_the_access_key_is_redacted_even_out_of_a_failing_drivers_own_message(
    tmp_path, monkeypatch
):
    def leaky(store, prefix=""):
        raise StoreUnreachableError(
            f"S3 rejected access_key={store.access_key} secret={store.secret_key}"
        )

    running = client(tmp_path, monkeypatch)
    monkeypatch.setattr(health_probes.objects_mod, "listing", leaky)
    response = running.get("/api/health/dependencies")
    assert response.status_code == 200
    assert STORE.access_key not in response.text
    assert STORE.secret_key not in response.text
