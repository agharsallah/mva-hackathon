"""The viz API's shared-token guard, and the bind refusal that makes it non-optional.

Two behaviours are load-bearing and neither is obvious from reading `create_app`:

- ``/health`` is **outside** the guard, so an uptime probe never carries the secret;
- a non-loopback bind with no token **exits non-zero** rather than warning, because a
  warning printed into a systemd log is not a control.
"""

import pytest
from fastapi.testclient import TestClient

from mva.viz import queries, readstore, routes_warehouse
from mva.viz.app import create_app
from mva.viz.auth import resolve_token
from mva.viz.cache import Cache
from mva.viz.serve import main

TOKEN = "s3cret-token-value"


@pytest.fixture()
def guarded(tmp_path, monkeypatch):
    """The app with a token set. Queries are stubbed: this file tests the door, not the room."""
    monkeypatch.setattr(
        queries.access, "fetch", lambda settings, sql, params=None: [{"chrom": "1", "n_het": 1}]
    )
    monkeypatch.setattr(routes_warehouse, "overview", lambda settings: {"total_variants": 1})
    monkeypatch.setattr(readstore, "root", lambda: "s3://test/reads")
    with TestClient(
        create_app(settings=None, cache=Cache(tmp_path), origins=[], token=TOKEN)
    ) as running:
        yield running


class TestGuard:
    def test_health_needs_no_token(self, guarded):
        assert guarded.get("/health").status_code == 200

    def test_api_without_token_is_401(self, guarded):
        response = guarded.get("/api/overview")
        assert response.status_code == 401
        assert response.json()["detail"] == "missing or wrong X-API-Key"

    def test_api_with_wrong_token_is_401(self, guarded):
        response = guarded.get("/api/overview", headers={"X-API-Key": "not-it"})
        assert response.status_code == 401

    def test_api_with_the_token_passes(self, guarded):
        assert guarded.get("/api/overview", headers={"X-API-Key": TOKEN}).status_code == 200

    def test_empty_token_leaves_the_api_open(self, tmp_path, monkeypatch):
        monkeypatch.setattr(routes_warehouse, "overview", lambda settings: {"total_variants": 1})
        with TestClient(
            create_app(settings=None, cache=Cache(tmp_path), origins=[], token="")
        ) as open_api:
            assert open_api.get("/api/overview").status_code == 200


class TestResolveToken:
    def test_explicit_wins_over_the_environment(self, monkeypatch):
        monkeypatch.setenv("MVA_VIZ_TOKEN", "from-env")
        assert resolve_token("explicit") == "explicit"
        assert resolve_token("") == ""

    def test_none_reads_the_setting(self, monkeypatch):
        monkeypatch.setenv("MVA_VIZ_TOKEN", "from-env")
        assert resolve_token(None) == "from-env"

    def test_default_is_empty(self):
        assert resolve_token(None) == ""


class TestBindRefusal:
    """`main` is called with a host but never reaches uvicorn — it returns first."""

    def test_public_bind_without_a_token_refuses(self, capsys):
        assert main(["--host", "0.0.0.0"]) == 2
        assert "refusing to bind" in capsys.readouterr().out

    def test_insecure_flag_allows_it_with_a_warning(self, monkeypatch, capsys):
        """--insecure gets past the refusal; uvicorn.run is stubbed so nothing binds."""
        import uvicorn

        monkeypatch.setattr(uvicorn, "run", lambda *a, **k: None)
        monkeypatch.setattr("mva.viz.app.create_app", lambda: None)
        assert main(["--host", "0.0.0.0", "--insecure"]) == 0
        assert "--insecure" in capsys.readouterr().out
