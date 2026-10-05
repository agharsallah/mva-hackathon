"""Forwarding the job-shaped verbs to the upstream service instead of reimplementing them.

The browser must talk to one origin, but a long-running computation may already have a
service of its own, with a job registry, cancellation and restart-safe history.
Re-hosting that logic here would give the front end two answers to "what is the state of
my job". So these routes are a thin pass-through.

Three properties are the reason this is a module and not four lines of ``httpx``:

* **Down is a 503, never a hang.** A connection error, a DNS failure or a timeout becomes
  ``503 {"detail": "upstream unreachable at <url>"}``. A chart can render that; a
  30-second white screen it cannot.
* **The secret stays server-side.** ``API_TOKEN`` is attached here as ``X-API-Key``,
  so the token never reaches the browser.
* **The upstream's own errors survive.** A 404 for an unknown job, or a 422 for a
  malformed request, is forwarded with its status and body intact rather than flattened
  into a generic failure.
"""

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException

from ..settings import setting

#: Long enough for the upstream's own capped long-poll (290 s) plus its overhead.
LONG_POLL_TIMEOUT = 300.0

#: Everything else upstream answers inline.
DEFAULT_TIMEOUT = 30.0


def base_url() -> str:
    """Where the upstream service is, without a trailing slash."""
    return (setting("UPSTREAM_URL") or "http://127.0.0.1:8765").rstrip("/")


def headers() -> dict[str, str]:
    """Auth for the upstream, when a token is configured."""
    token = setting("API_TOKEN")
    return {"X-API-Key": token} if token else {}


@dataclass(frozen=True)
class Reply:
    """One upstream response: its status and its decoded body."""

    status: int
    body: Any


class Upstream:
    """The upstream service as a callable. Swapped for a fake by a caller that needs one."""

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json: Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,  # noqa: ASYNC109 - forwarded to httpx's own timeout
    ) -> Reply:
        import httpx

        url = f"{base_url()}{path}"
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(
                    method, url, params=_clean(params), json=json, headers=headers()
                )
        except Exception as failure:
            raise UnreachableError(base_url()) from failure
        return Reply(response.status_code, _decode(response))


class UnreachableError(RuntimeError):
    """The upstream could not be reached at all — distinct from it returning an error."""

    def __init__(self, url: str) -> None:
        super().__init__(f"upstream unreachable at {url}")
        self.url = url


async def forward(
    upstream: Upstream,
    method: str,
    path: str,
    *,
    params: dict | None = None,
    json: Any | None = None,
    timeout: float = DEFAULT_TIMEOUT,  # noqa: ASYNC109 - forwarded straight to httpx's own timeout
) -> Any:
    """Forward one call and return the upstream body, or raise the right HTTP error."""
    try:
        reply = await upstream.request(method, path, params=params, json=json, timeout=timeout)
    except UnreachableError as down:
        raise HTTPException(status_code=503, detail=str(down)) from down
    if reply.status >= 400:
        detail = reply.body
        if isinstance(detail, dict) and "detail" in detail:
            detail = detail["detail"]
        raise HTTPException(status_code=reply.status, detail=detail)
    return reply.body


def _clean(params: dict | None) -> dict | None:
    """Drop unset query parameters so the upstream sees absence, not an empty string."""
    if not params:
        return None
    return {key: value for key, value in params.items() if value not in (None, "")}


def _decode(response) -> Any:
    try:
        return response.json()
    except ValueError:
        return {"detail": response.text[:2000]}
