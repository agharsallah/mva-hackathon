"""``GET /api/health/dependencies``: which of this API's backends actually work.

``/health`` (:mod:`mva.viz.app`) is a liveness probe — it touches nothing and answers in
microseconds, which is exactly right for a container orchestrator asking "should I
restart this process". It cannot answer a different, harder question the React app
needs answered: "is Postgres up, is the object store reachable, can I actually read a
Parquet file through it, is the reads API alive, is Ensembl up, do the ingested
reference tables exist?" That is what this module adds.

Design, in order of how surprising each choice might look:

* **Seven checks, run concurrently, each capped at its own budget** from
  :mod:`mva.viz.health_budget`. A dead dependency must cost this endpoint one wait, not
  seven — see :func:`assemble`. The budgets differ per check because the probes do
  wildly different amounts of work, and a probe cut off mid-handshake is reported as
  `down` when it was only slow; that module owns the numbers and the reasoning.
* **Never raises** on a dependency failure. Every probe in :mod:`mva.viz.health_probes`
  already turns its own failure into a `down` result; :func:`run_check` adds a second net
  (a timeout, or an exception a probe forgot to catch) so this endpoint truly cannot 5xx.
  A malformed *request* — an unknown check id in ``only`` — is a 400, which is a
  different thing: the caller is wrong, not the platform.
* **Cached per check for** :data:`CACHE_TTL` **seconds, in memory, per app instance.** Not
  :mod:`mva.viz.cache`'s disk cache: that one exists so an expensive answer survives a
  process restart, and a dependency probe is the opposite on both counts — its only
  value is "right now", and writing it to disk would be pure overhead for something
  that goes stale in ten seconds. :class:`CheckCache` is built fresh by every
  :func:`router` call so one test's probes can never leak into another's.
* **The cache is per check, not per payload**, because of ``only``: re-probing one
  service has to leave the other six rows exactly as they were last measured, and each
  row therefore carries its own ``checked_at`` rather than borrowing the payload's.
* **The envelope's own ``cached_at`` is always ``null``**, per the contract: this route
  answers from :class:`CheckCache` or freshly from the probes, and either way each row
  carries its own ``checked_at`` — the contract's chosen way to show staleness for *this*
  endpoint, rather than the envelope's usual field.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from ..warehouse.objects import ObjectStore
from ..warehouse.settings import Postgres
from . import health_probes as probes
from .cache import now as timestamp
from .health_budget import DEFAULT_TIMEOUT, budgets, inner_timeout, timeout_for
from .health_results import REGISTRY, down, failed
from .proxy import Upstream
from .response import Envelope, live

#: Mirrors ``app.py``'s own constants. Duplicated rather than imported so this leaf
#: module never depends on the FastAPI assembly that in turn imports it.
SERVICE = "mva-viz-api"
VERSION = "1.0.0"

#: How long one probed result is served again before the next request re-probes.
CACHE_TTL = 10.0

SOURCE = "live dependency probes"


@dataclass
class CheckCache:
    """The last result for each check id, each stamped with when it was measured.

    ``fresh`` is what serves a page reload cheaply; ``last`` is what makes ``only`` work —
    a per-service re-probe returns the whole board, so the six rows nobody asked to
    re-probe come back as last measured, however long ago that was. Their own
    ``checked_at`` says so, which is why staleness never has to be hidden.
    """

    ttl: float = CACHE_TTL
    _rows: dict[str, tuple[float, dict]] = field(default_factory=dict, init=False, repr=False)

    def fresh(self, check_id: str) -> dict | None:
        """The row for ``check_id`` if it was measured within :data:`ttl` seconds."""
        entry = self._rows.get(check_id)
        if entry is None:
            return None
        measured_at, row = entry
        return row if time.monotonic() - measured_at <= self.ttl else None

    def last(self, check_id: str) -> dict | None:
        """The row for ``check_id`` however old it is — ``None`` only if never probed."""
        entry = self._rows.get(check_id)
        return None if entry is None else entry[1]

    def put(self, row: dict) -> None:
        self._rows[row["id"]] = (time.monotonic(), row)


async def run_check(
    check_id: str,
    awaitable,
    fallback_endpoint: str | None = None,
    budget: float = DEFAULT_TIMEOUT,
) -> dict:
    """Run one check's coroutine under its own budget and merge in its static facts.

    Two safety nets on top of what the probe itself already catches: a timeout becomes
    `down`, and any exception a probe forgot to catch becomes `down` too. Either way this
    coroutine returns a result — it is the reason the endpoint as a whole never 5xxs.

    ``fallback_endpoint`` — from :func:`health_probes.static_endpoint` — fills in
    ``endpoint`` when neither safety net reached the probe's own code far enough to set
    one, so a timeout still says *where* nothing answered.

    ``timeout_ms`` goes back in the row so the board can say what the budget was: a
    "timed out after 12s" card is only actionable next to the number it blew through.

    The parameter is ``budget`` rather than ``timeout`` because it is not forwarded to a
    client as a deadline — it is the wall this coroutine stops waiting at.
    """
    meta = REGISTRY[check_id]
    start = time.perf_counter()
    try:
        result = await asyncio.wait_for(awaitable, timeout=budget)
    except TimeoutError:
        result = down(
            f"timed out after {budget:.0f}s",
            "The dependency did not answer within this check's budget; probe it directly "
            "to see whether it is slow or fully down, and raise the budget with "
            f"MVA_HEALTH_TIMEOUTS={check_id}=<seconds> if it is merely slow.",
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
        "timeout_ms": round(budget * 1000),
        "checked_at": timestamp(),
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


def resolve_targets(only: list[str] | None) -> list[str]:
    """Which checks this request asked to (re-)probe, in the contract's order.

    ``only`` absent means every check — the board's normal load. Naming ids restricts the
    probing to those, which is what the per-card "re-probe" button uses: one button must
    not cost a round trip to Postgres, MinIO, the reads API *and* Ensembl.
    """
    if not only:
        return list(REGISTRY)
    requested = [part.strip() for token in only for part in token.split(",") if part.strip()]
    unknown = [check_id for check_id in requested if check_id not in REGISTRY]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=(
                f"unknown check id(s): {', '.join(unknown)} — valid ids: {', '.join(REGISTRY)}"
            ),
        )
    return [check_id for check_id in REGISTRY if check_id in set(requested)]


def _factories(
    settings: Postgres, store: ObjectStore, upstream: Upstream, budget: dict[str, float]
) -> dict[str, Callable[[], Awaitable[dict]]]:
    """One coroutine *factory* per check id, in the contract's declared order.

    Factories rather than coroutines because a request may run a subset: a coroutine built
    for a check this request serves from cache would never be awaited.

    The two probes that speak HTTP get their *own* client timeout from the same budget
    (minus :data:`~mva.viz.health_budget.INNER_SLACK`) so a raised budget actually gives
    them longer, and so their specific remedy beats the orchestrator's generic timeout
    message. The thread-backed probes have no timeout knob to pass — ``asyncio.wait_for``
    stops waiting on them but cannot cancel the thread, which is why their budgets are
    generous rather than tight.
    """
    return {
        "viz-api": lambda: asyncio.to_thread(probes.probe_viz_api, SERVICE, VERSION),
        "warehouse": lambda: asyncio.to_thread(probes.probe_warehouse, settings),
        "object-store": lambda: asyncio.to_thread(probes.probe_object_store, store),
        "parquet": lambda: asyncio.to_thread(probes.probe_parquet, store),
        "reads-api": lambda: probes.probe_reads_api(
            upstream, timeout=inner_timeout(timeout_for("reads-api", budget))
        ),
        "ensembl": lambda: asyncio.to_thread(
            probes.probe_ensembl, inner_timeout(timeout_for("ensembl", budget))
        ),
        "reference-snapshots": lambda: asyncio.to_thread(
            probes.probe_reference_snapshots, settings
        ),
    }


def _to_probe(cache: CheckCache, targets: list[str], refresh: bool) -> list[str]:
    """The checks this request must actually run, in the contract's order.

    Two reasons a check runs: it was asked for and has no fresh row (or ``refresh``
    bypasses freshness), or it was *not* asked for and has never been probed at all — the
    board must render every check even when the very first request names ``only``.
    """
    asked = set(targets)
    return [
        check_id
        for check_id in REGISTRY
        if (check_id in asked and (refresh or cache.fresh(check_id) is None))
        or (check_id not in asked and cache.last(check_id) is None)
    ]


async def assemble(
    settings: Postgres,
    store: ObjectStore,
    upstream: Upstream,
    cache: CheckCache,
    budget: dict[str, float],
    *,
    targets: list[str] | None = None,
    refresh: bool = False,
) -> dict:
    """Probe what needs probing, concurrently, and assemble the contract's ``data`` object.

    Always returns every check in the registry: the ones probed on this request, plus the
    ones served from :class:`CheckCache`, each carrying its own ``checked_at``.
    """
    selected = list(REGISTRY) if targets is None else targets
    running = _to_probe(cache, selected, refresh)
    if running:
        factories = _factories(settings, store, upstream, budget)
        for row in await asyncio.gather(
            *(
                run_check(
                    check_id,
                    factories[check_id](),
                    probes.static_endpoint(check_id, settings, store),
                    timeout_for(check_id, budget),
                )
                for check_id in running
            )
        ):
            cache.put(row)
    measured = (cache.last(check_id) for check_id in REGISTRY)
    checks = [row for row in measured if row is not None]
    return {"checked_at": timestamp(), "overall": overall(checks), "checks": checks}


async def probe_all(settings: Postgres, store: ObjectStore, upstream: Upstream) -> dict:
    """Every check, freshly probed with the configured budgets — no cache involved."""
    return await assemble(settings, store, upstream, CheckCache(), budgets(), refresh=True)


def router(settings: Postgres, store: ObjectStore, upstream: Upstream | None = None) -> APIRouter:
    """Build the one route this module owns."""
    api = APIRouter(prefix="/api")
    reads = upstream or Upstream()
    cache = CheckCache()
    budget = budgets()

    @api.get("/health/dependencies", response_model=Envelope, tags=["health"])
    async def dependencies(
        refresh: Annotated[bool, Query()] = False,
        only: Annotated[list[str] | None, Query()] = None,
    ) -> dict:
        """Seven dependency checks, run concurrently, each row cached ~10 s.

        ``refresh=true`` bypasses the cache; ``only=<id>`` (repeatable, or comma-separated)
        restricts probing to those checks and serves the rest from cache. Together they
        are the per-service re-probe button on the Status page.

        See ``docs/step-0/methodology/053-dependency-health.md`` for the contract this
        implements field by field, and ``065-health-controls.md`` for the per-check
        budgets, the per-check cache and ``only``.
        """
        data = await assemble(
            settings,
            store,
            reads,
            cache,
            budget,
            targets=resolve_targets(only),
            refresh=refresh,
        )
        return live(data, SOURCE)

    return api
