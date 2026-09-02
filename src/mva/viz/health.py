"""``GET /api/health/dependencies``: which of this API's backends actually work.

``/health`` (:mod:`mva.viz.app`) is a liveness probe — it touches nothing and answers in
microseconds, which is exactly right for a container orchestrator asking "should I
restart this process". It cannot answer a different, harder question the React app
needs answered: "is Postgres up, is the object store reachable, can I actually read a
Parquet file through it, is the reads API alive, is Ensembl up, do the ingested
reference tables exist?" That is what this module adds.

Design, in order of how surprising each choice might look:

* **Seven checks, run concurrently, each capped at** :data:`CHECK_TIMEOUT`. A dead
  dependency must cost this endpoint 2 seconds, not 2 seconds times seven — see
  :func:`probe_all`.
* **Never raises.** Every probe in :mod:`mva.viz.health_probes` already turns its own
  failure into a `down` result; :func:`run_check` adds a second net (a timeout, or an
  exception a probe forgot to catch) so this endpoint truly cannot 5xx.
* **Cached for** :data:`CACHE_TTL` **seconds, in memory, per app instance.** Not
  :mod:`mva.viz.cache`'s disk cache: that one exists so an expensive answer survives a
  process restart, and a dependency probe is the opposite on both counts — its only
  value is "right now", and writing it to disk would be pure overhead for something
  that goes stale in ten seconds. :class:`TTLCache` is a single (data, instant) pair,
  good for one process's lifetime, and built fresh by every :func:`router` call so one
  test's probes can never leak into another's.
* **The envelope's own ``cached_at`` is always ``null``**, per the contract: this route
  answers instantly from :class:`TTLCache` or freshly from the seven probes, and either
  way the payload carries its own ``checked_at`` — the contract's chosen way to show
  staleness for *this* endpoint, rather than the envelope's usual field.
"""

import asyncio
import time
from dataclasses import dataclass, field

from fastapi import APIRouter, Query

from ..warehouse.objects import ObjectStore
from ..warehouse.settings import Postgres
from . import health_probes as probes
from .cache import now as timestamp
from .health_results import REGISTRY, down, failed
from .proxy import Upstream
from .response import Envelope, live

#: Mirrors ``app.py``'s own constants. Duplicated rather than imported so this leaf
#: module never depends on the FastAPI assembly that in turn imports it.
SERVICE = "mva-viz-api"
VERSION = "1.0.0"

#: Per-check budget. The whole response must return in ~3 s even when every dependency
#: is dead — seven checks at up to 2 s each, run concurrently, cost one 2 s wait.
CHECK_TIMEOUT = 2.0

#: How long one probed result is served again before the next request re-probes.
CACHE_TTL = 10.0

SOURCE = "live dependency probes"


@dataclass
class TTLCache:
    """One payload, valid for :data:`CACHE_TTL` seconds. See the module docstring."""

    ttl: float = CACHE_TTL
    _built_at: float | None = field(default=None, init=False, repr=False)
    _data: dict | None = field(default=None, init=False, repr=False)

    def get(self) -> dict | None:
        if self._data is None or self._built_at is None:
            return None
        if time.monotonic() - self._built_at > self.ttl:
            return None
        return self._data

    def set(self, data: dict) -> dict:
        self._data, self._built_at = data, time.monotonic()
        return data


async def run_check(check_id: str, awaitable, fallback_endpoint: str | None = None) -> dict:
    """Run one check's coroutine under the shared timeout and merge in its static facts.

    Two safety nets on top of what the probe itself already catches: a timeout becomes
    `down`, and any exception a probe forgot to catch becomes `down` too. Either way this
    coroutine returns a result — it is the reason the endpoint as a whole never 5xxs.

    ``fallback_endpoint`` — from :func:`health_probes.static_endpoint` — fills in
    ``endpoint`` when neither safety net reached the probe's own code far enough to set
    one, so a timeout still says *where* nothing answered.
    """
    meta = REGISTRY[check_id]
    start = time.perf_counter()
    try:
        result = await asyncio.wait_for(awaitable, timeout=CHECK_TIMEOUT)
    except TimeoutError:
        result = down(
            f"timed out after {CHECK_TIMEOUT:.0f}s",
            "The dependency did not answer within the health check's budget; probe it "
            "directly to see whether it is slow or fully down.",
        )
    except Exception as error:
        result = failed(error, "Unexpected failure running this probe; check server logs.")
    latency_ms = (
        None if result["status"] == "skipped" else round((time.perf_counter() - start) * 1000)
    )
    return {
        "id": check_id,
        "name": meta.name,
        "kind": meta.kind,
        "status": result["status"],
        "latency_ms": latency_ms,
        "detail": result["detail"],
        "remedy": result["remedy"],
        "powers": list(meta.powers),
        "endpoint": result["endpoint"] or fallback_endpoint,
    }


def overall(checks: list[dict]) -> str:
    """``down`` if any ``internal`` check is down; else ``degraded`` if any check is
    down or degraded; else ``up``. ``skipped`` never degrades the overall status.
    """
    if any(check["status"] == "down" and check["kind"] == "internal" for check in checks):
        return "down"
    if any(check["status"] in ("down", "degraded") for check in checks):
        return "degraded"
    return "up"


def _awaitables(settings: Postgres, store: ObjectStore, upstream: Upstream) -> dict:
    """One coroutine per check id, in the contract's declared order."""
    return {
        "viz-api": asyncio.to_thread(probes.probe_viz_api, SERVICE, VERSION),
        "warehouse": asyncio.to_thread(probes.probe_warehouse, settings),
        "object-store": asyncio.to_thread(probes.probe_object_store, store),
        "parquet": asyncio.to_thread(probes.probe_parquet, store),
        "reads-api": probes.probe_reads_api(upstream),
        "ensembl": asyncio.to_thread(probes.probe_ensembl),
        "reference-snapshots": asyncio.to_thread(probes.probe_reference_snapshots, settings),
    }


async def probe_all(settings: Postgres, store: ObjectStore, upstream: Upstream) -> dict:
    """Run all seven checks concurrently and assemble the contract's ``data`` object."""
    awaitables = _awaitables(settings, store, upstream)
    checks = await asyncio.gather(
        *(
            run_check(check_id, awaitable, probes.static_endpoint(check_id, settings, store))
            for check_id, awaitable in awaitables.items()
        )
    )
    return {"checked_at": timestamp(), "overall": overall(checks), "checks": list(checks)}


def router(settings: Postgres, store: ObjectStore, upstream: Upstream | None = None) -> APIRouter:
    """Build the one route this module owns."""
    api = APIRouter(prefix="/api")
    reads = upstream or Upstream()
    cache = TTLCache()

    @api.get("/health/dependencies", response_model=Envelope, tags=["health"])
    async def dependencies(refresh: bool = Query(default=False)) -> dict:
        """Seven dependency checks, run concurrently, cached ~10 s.

        See ``docs/step-0/methodology/053-dependency-health.md`` for the contract this
        implements field by field, and why each check is probed the way it is.
        """
        hit = None if refresh else cache.get()
        if hit is not None:
            return live(hit, SOURCE)
        return live(cache.set(await probe_all(settings, store, reads)), SOURCE)

    return api
