"""The one response shape every ``/api/*`` endpoint returns.

``{data, cached_at, source}``, without exception. The uniformity is the point: a chart
component can show "computed from ``pg.results.stats_dp``, cached 3 minutes ago" for any
endpoint it is pointed at, with no per-endpoint knowledge. Two fields carry that:

* ``source`` — where the numbers came from, in the notation the rest of the repo uses
  (``pg.<schema>.<table>``, an ``s3://`` URL, or an upstream service URL).
* ``cached_at`` — the instant the payload was built, and ``null`` when the endpoint is
  cheap enough to be computed live on every request. A user looking at a stale number can
  therefore see that it is stale, which is the difference between a cache and a lie.
"""

from typing import Any

from pydantic import BaseModel, Field


class Envelope(BaseModel):
    """A payload with its provenance."""

    data: Any = Field(description="the endpoint's payload — a list of rows or an object")
    cached_at: str | None = Field(
        default=None,
        description="ISO-8601 instant the payload was built, or null when computed live")
    source: str = Field(description="where the numbers came from")


def live(data: Any, source: str) -> dict:
    """Envelope a payload that was computed during this request."""
    return {"data": data, "cached_at": None, "source": source}


def cached(entry, source: str) -> dict:
    """Envelope a :class:`~mva.viz.cache.Cached` payload, keeping its build instant."""
    return {"data": entry.data, "cached_at": entry.cached_at, "source": source}
