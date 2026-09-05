"""Shared doubles for the ``mva.drugs`` tests. No network, no sockets, no sleeps.

Two fakes:

``FakeFetcher``   stands in for :class:`mva.drugs.cache.Fetcher` at the adapter boundary.
                  Routes are matched on a substring of the url plus, for GraphQL POSTs, a
                  substring of the query body — which is how the two Open Targets queries
                  (search, target) are told apart when they share one endpoint.
``FakeClient``    stands in for ``httpx.Client`` *inside* a real ``Fetcher``, so the cache,
                  the retry ladder and the digest roll-up are exercised for real.

The recorded replies under ``tests/fixtures/track2/`` are trimmed real payloads, except
``card.json`` which is an invented second case — a test that passes against it cannot be
passing because the code hard-coded this repository's actual case.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).parent / "fixtures" / "track2"


def fixture(name: str) -> Any:
    """Load one recorded reply."""
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


class FakeFetcher:
    """A fetcher whose replies come from a routing table instead of the network."""

    def __init__(self, routes: list[tuple[str, str, Any]] | None = None) -> None:
        #: ``(url_fragment, body_fragment, payload)``. First match wins.
        self.routes: list[tuple[str, str, Any]] = list(routes or [])
        self.calls: list[tuple[str, str, Any]] = []
        self.replies: list[Any] = []
        self.live_calls = 0
        self.closed = False

    # ── the Fetcher surface the adapters use ────────────────────────────────────────

    def get_json(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        *,
        refresh: bool | None = None,
        allow_status: tuple[int, ...] = (),
    ) -> Any:
        self.calls.append(("GET", url, params))
        return self._match(url, json.dumps(params or {}))

    def post_json(
        self,
        url: str,
        json_body: dict[str, Any] | None = None,
        *,
        refresh: bool | None = None,
        allow_status: tuple[int, ...] = (),
        **kwargs: Any,
    ) -> Any:
        body = json_body if json_body is not None else kwargs.get("json") or {}
        self.calls.append(("POST", url, body))
        return self._match(url, json.dumps(body))

    def close(self) -> None:
        self.closed = True

    @property
    def digest(self) -> str:
        return "0" * 64

    @property
    def window(self) -> tuple[str, str]:
        return ("2026-01-01T00:00:00+00:00", "2026-01-01T00:01:00+00:00")

    # ── routing ─────────────────────────────────────────────────────────────────────

    def route(self, url_fragment: str, payload: Any, body_fragment: str = "") -> FakeFetcher:
        self.routes.append((url_fragment, body_fragment, payload))
        return self

    def _match(self, url: str, body: str) -> Any:
        for url_fragment, body_fragment, payload in self.routes:
            if url_fragment in url and (not body_fragment or body_fragment in body):
                return payload
        raise AssertionError(f"no fake route for {url} / {body[:120]}")

    def urls(self) -> list[str]:
        return [url for _method, url, _payload in self.calls]


class FakeReply:
    """The slice of an ``httpx.Response`` the cache reads."""

    def __init__(self, status_code: int, payload: Any, url: str = "https://example/x") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload) if payload is not None else ""
        self.request = type("Req", (), {"url": url})()

    def json(self) -> Any:
        if self._payload is None:
            raise ValueError("not JSON")
        return self._payload


class FakeClient:
    """An ``httpx.Client`` replacement: hands back a scripted queue of replies."""

    def __init__(self, replies: list[FakeReply]) -> None:
        self.queue = list(replies)
        self.requests: list[tuple[str, str]] = []
        self.closed = False

    def request(self, method: str, url: str, params: Any = None, json: Any = None) -> FakeReply:
        self.requests.append((method, url))
        if not self.queue:
            raise AssertionError(f"FakeClient ran out of replies at {method} {url}")
        return self.queue.pop(0)

    def close(self) -> None:
        self.closed = True
