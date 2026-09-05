"""One polite, cached HTTP client, shared by every source adapter.

Seven public APIs, a few thousand requests per snapshot, and a run that must be repeatable
without hammering anyone. So every reply is written to disk keyed by
``sha256(method + url + canonical body)`` and a second run of the same query reads the file
instead of the socket. That gives three things at once:

* **Reproducibility.** The snapshot can be rebuilt offline from the cache, and the digest
  of each cached body is what the provenance manifest records — so a manifest names the
  exact bytes an adapter parsed, not "whatever the API said that day".
* **Politeness.** A minimum interval between *live* calls (cache hits do not sleep), plus
  three retries with exponential backoff on 429 and 5xx.
* **Cheap iteration.** ``--refresh`` bypasses the cache for one run; without it, fixing a
  parser costs no requests at all.

The cache holds only public API replies — no patient data ever reaches it — but it lives
under ``build/`` (gitignored) because it is a rebuildable artefact, not a source file.

Errors are never swallowed here. A request that cannot be satisfied raises
:class:`SourceError` naming the url; an adapter that *expects* a 404 to mean "no such
record" (openFDA does) says so by catching it explicitly.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = ["DEFAULT_CACHE_DIR", "Fetcher", "Reply", "SourceError"]

#: Gitignored via ``build/``. Rebuildable, so never committed.
DEFAULT_CACHE_DIR = Path("build/track2-cache")

#: Sent on every request. Public APIs ask for a contactable agent string; NCBI requires it.
USER_AGENT = "mva-hackathon-track2/0.1 (https://github.com/; research use)"

#: Statuses worth trying again: rate limit, and the five server-side failures.
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})

#: Attempts per live request, and the first backoff in seconds (doubled each attempt).
ATTEMPTS = 3
BACKOFF = 1.5


class SourceError(RuntimeError):
    """A public API could not be read. Carries the url so the failure names its source."""

    def __init__(self, url: str, detail: str) -> None:
        super().__init__(f"{url}: {detail}")
        self.url = url
        self.detail = detail


@dataclass(frozen=True)
class Reply:
    """One cached reply, as it sits on disk plus the digest of its body."""

    url: str
    method: str
    params: Any
    retrieved_at: str
    status: int
    body: Any
    sha256: str
    from_cache: bool


@dataclass
class Fetcher:
    """A cached, rate-limited JSON client for one source.

    ``source`` names the API and becomes the cache sub-directory, so the provenance
    roll-up can attribute every cached body to the API it came from without re-parsing it.
    """

    source: str = "generic"
    cache_dir: Path = DEFAULT_CACHE_DIR
    min_interval_s: float = 0.34
    user_agent: str = USER_AGENT
    refresh: bool = False
    timeout: float = 60.0
    replies: list[Reply] = field(default_factory=list)
    _last_call: float = 0.0
    _client: Any = None

    # ── the two verbs ───────────────────────────────────────────────────────────────

    def get_json(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        *,
        refresh: bool | None = None,
        allow_status: tuple[int, ...] = (),
    ) -> Any:
        """GET and decode JSON. ``allow_status`` returns the body instead of raising."""
        return self._fetch("GET", url, params, None, refresh, allow_status)

    def post_json(
        self,
        url: str,
        json: dict[str, Any],
        *,
        refresh: bool | None = None,
        allow_status: tuple[int, ...] = (),
    ) -> Any:
        """POST a JSON body and decode the JSON reply."""
        return self._fetch("POST", url, None, json, refresh, allow_status)

    # ── caching ─────────────────────────────────────────────────────────────────────

    def key(self, method: str, url: str, payload: Any) -> str:
        """The cache key: a digest over the method, the url and the canonical payload."""
        canonical = _canonical(payload)
        return hashlib.sha256(f"{method}\n{url}\n{canonical}".encode()).hexdigest()

    def path_for(self, method: str, url: str, payload: Any) -> Path:
        return (
            self.cache_dir / self.source / f"{method.lower()}-{self.key(method, url, payload)}.json"
        )

    def _fetch(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None,
        body: dict[str, Any] | None,
        refresh: bool | None,
        allow_status: tuple[int, ...],
    ) -> Any:
        payload = body if method == "POST" else params
        path = self.path_for(method, url, payload)
        wants_live = self.refresh if refresh is None else refresh
        if not wants_live:
            cached = _read(path)
            if cached is not None:
                self.replies.append(_reply(cached, from_cache=True))
                return _unwrap(cached, url, allow_status)

        record = self._live(method, url, params, body, allow_status)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, indent=1, sort_keys=True), encoding="utf-8")
        self.replies.append(_reply(record, from_cache=False))
        return _unwrap(record, url, allow_status)

    # ── the socket ──────────────────────────────────────────────────────────────────

    def _live(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None,
        body: dict[str, Any] | None,
        allow_status: tuple[int, ...],
    ) -> dict[str, Any]:
        import httpx  # deferred: a cache-only run must not need the dependency loaded

        if self._client is None:
            self._client = httpx.Client(
                timeout=self.timeout, headers={"User-Agent": self.user_agent}
            )
        detail = "no attempt was made"
        for attempt in range(ATTEMPTS):
            self._wait()
            try:
                reply = self._client.request(method, url, params=params, json=body)
            except httpx.HTTPError as error:
                detail = f"{type(error).__name__}: {error}"
            else:
                if reply.status_code in RETRY_STATUSES:
                    detail = f"HTTP {reply.status_code}"
                else:
                    return self._record(method, url, params, body, reply, allow_status)
            time.sleep(BACKOFF * (2**attempt))
        raise SourceError(url, f"{ATTEMPTS} attempts failed ({detail})")

    def _record(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None,
        body: dict[str, Any] | None,
        reply: Any,
        allow_status: tuple[int, ...],
    ) -> dict[str, Any]:
        payload = body if method == "POST" else params
        if reply.status_code >= 400 and reply.status_code not in allow_status:
            raise SourceError(url, f"HTTP {reply.status_code}: {reply.text[:200]}")
        try:
            decoded = reply.json()
        except ValueError as error:
            raise SourceError(url, f"reply was not JSON ({error})") from error
        return {
            "url": str(reply.request.url),
            "method": method,
            "params": payload,
            "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "status": reply.status_code,
            "body": decoded,
        }

    def _wait(self) -> None:
        """Sleep out the remainder of the polite interval since the last *live* call."""
        gap = time.monotonic() - self._last_call
        if self._last_call and gap < self.min_interval_s:
            time.sleep(self.min_interval_s - gap)
        self._last_call = time.monotonic()

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    # ── provenance ──────────────────────────────────────────────────────────────────

    @property
    def digest(self) -> str:
        """One digest over every body this fetcher returned, sorted so it is order-free.

        A manifest cannot list a thousand cached files, so it lists one roll-up per source
        instead: the sha256 of the sorted per-reply digests. Same replies in, same value
        out, whatever order the adapters asked in.
        """
        joined = "\n".join(sorted(reply.sha256 for reply in self.replies))
        return hashlib.sha256(joined.encode()).hexdigest()

    @property
    def window(self) -> tuple[str, str] | None:
        """``(first, last)`` ``retrieved_at`` over every reply used, or ``None``."""
        stamps = sorted(reply.retrieved_at for reply in self.replies if reply.retrieved_at)
        return (stamps[0], stamps[-1]) if stamps else None

    @property
    def live_calls(self) -> int:
        return sum(1 for reply in self.replies if not reply.from_cache)


def _canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _read(path: Path) -> dict[str, Any] | None:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return loaded if isinstance(loaded, dict) and "body" in loaded else None


def _reply(record: dict[str, Any], *, from_cache: bool) -> Reply:
    return Reply(
        url=str(record.get("url", "")),
        method=str(record.get("method", "")),
        params=record.get("params"),
        retrieved_at=str(record.get("retrieved_at", "")),
        status=int(record.get("status", 0)),
        body=record.get("body"),
        sha256=hashlib.sha256(_canonical(record.get("body")).encode()).hexdigest(),
        from_cache=from_cache,
    )


def _unwrap(record: dict[str, Any], url: str, allow_status: tuple[int, ...]) -> Any:
    status = int(record.get("status", 0))
    if status >= 400 and status not in allow_status:
        raise SourceError(url, f"HTTP {status} (cached)")
    return record.get("body")
