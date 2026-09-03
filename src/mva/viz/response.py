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
        description="ISO-8601 instant the payload was built, or null when computed live",
    )
    source: str = Field(description="where the numbers came from")


def live(data: Any, source: str) -> dict:
    """Envelope a payload that was computed during this request."""
    return {"data": data, "cached_at": None, "source": source}


def cached(entry, source: str, **extra: object) -> dict:
    """Envelope a :class:`~mva.viz.cache.Cached` payload, keeping its build instant.

    When the entry carries provenance (:class:`mva.viz.cache.Built`), it is appended to
    ``source``, so the line names *this* reply's upstreams rather than only the module's
    generic list of endpoints it could have called. ``extra`` is for facts the *route*
    knows and the builder does not — the disk-cache key being the one that matters, since
    it is the file a reader would have to delete to make the reply rebuild. See
    :func:`describe`.
    """
    return {
        "data": entry.data,
        "cached_at": entry.cached_at,
        "source": describe(source, getattr(entry, "provenance", None), **extra),
    }


def describe(source: str, provenance: dict | None, **extra: object) -> str:
    """``source`` followed by ``name=value`` for every concrete provenance fact.

    ``source`` alone is a *capability* statement — "this route reads Ensembl REST and
    AlphaFold DB". That is not enough to trace a figure back: two screenshots of the same
    route can be built from two Ensembl releases and two AlphaFold model versions. This
    appends what the reply was actually built from, in the same one-line notation the rest
    of the repository uses, because :class:`Envelope`'s ``source`` is a string and the
    client contracts that consume it are frozen.

    A ``None`` value is written as ``unknown`` rather than omitted: "we did not learn the
    Ensembl release" and "there is no Ensembl release" are different statements, and
    dropping the key would make them look the same.
    """
    facts = {**(provenance or {}), **extra}
    if not facts:
        return source
    rendered = ", ".join(
        f"{name}={'unknown' if value is None else value}" for name, value in facts.items()
    )
    return f"{source}; {rendered}"
