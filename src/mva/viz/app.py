"""The viz application: CORS, auth, the cache, the routers, and one liveness probe.

Assembly only. Every route lives in :mod:`~mva.viz.routes_warehouse` or
:mod:`~mva.viz.routes_reads`; every query lives below those. That keeps this module the
one place to look for "what is wired to what", and keeps it short enough to be read in
one go.

Two things are configured here rather than hard-coded, because a browser is involved:

* **CORS.** The React dev server is a different origin from this API, so the browser
  refuses to read the response unless the server says the origin is allowed.
  ``MVA_VIZ_CORS`` is the comma-separated list, defaulting to the Vite dev server on both
  spellings of loopback (``localhost`` and ``127.0.0.1`` are *different* origins to a
  browser, which is why both are there). Any loopback port is allowed on top of that
  list (:data:`LOOPBACK_ORIGIN`): Vite walks to 5174, 5175, … when 5173 is already taken,
  and a port-exact list turns that silent drift into a blocked fetch that the app can
  only report as "api down".
* **The cache directory.** ``MVA_VIZ_CACHE``, under gitignored ``build/`` by default. The
  locus cache holds real patient positions, so this must never point inside the tree git
  tracks.
* **The shared token.** ``MVA_VIZ_TOKEN``, empty by default, which leaves the API open —
  the only correct setting while it is bound to loopback. Set it and every ``/api/*``
  route requires it as ``X-API-Key``; ``/health`` stays open for uptime probes. See
  :mod:`mva.viz.auth`. Set it whenever the service binds anything but loopback.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..warehouse.objects import ObjectStore
from ..warehouse.settings import Postgres, object_store, setting
from . import api_zoo, api_zoo_jobs, health, probebuild, routes_reads, routes_warehouse
from .auth import guard_dependencies, resolve_token
from .cache import Cache, default_directory

SERVICE = "mva-viz-api"

#: Any port on either spelling of loopback. The dev server's port is not stable — Vite
#: takes the next free one when 5173 is busy — and a developer's own machine is not a
#: cross-origin threat, so the port is not what makes this API safe. Deployed origins
#: are never loopback and still have to be named in ``MVA_VIZ_CORS``.
LOOPBACK_ORIGIN = r"^http://(localhost|127\.0\.0\.1)(:\d+)?$"


def cors_origins(configured: str | None = None) -> list[str]:
    """The browser origins allowed to read from this API."""
    raw = configured if configured is not None else setting("MVA_VIZ_CORS")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def create_app(
    settings: Postgres | None = None,
    cache: Cache | None = None,
    origins: list[str] | None = None,
    upstream=None,
    store: ObjectStore | None = None,
    token: str | None = None,
) -> FastAPI:
    """Build the application. Tests inject settings, cache, a fake upstream and store.

    ``token=""`` forces an open API regardless of what the surrounding ``.env`` holds;
    ``token=None`` resolves ``MVA_VIZ_TOKEN`` once, here, so no request parses a file.
    """
    settings = settings or Postgres.from_env()
    cache = cache or Cache(default_directory())
    store = store or object_store()
    guarded = guard_dependencies(resolve_token(token))

    app = FastAPI(
        title=SERVICE,
        version="1.0.0",
        summary="The warehouse and the read store as JSON, for one React app.",
        description=__doc__,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins if origins is not None else cors_origins(),
        allow_origin_regex=LOOPBACK_ORIGIN,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    app.state.settings = settings
    app.state.cache = cache
    app.state.store = store

    @app.get("/health", tags=["service"])
    def liveness() -> dict:
        """Liveness only — it touches neither the database nor the object store.

        For "are the backends actually working", see ``GET /api/health/dependencies``
        (:mod:`mva.viz.health`).
        """
        return {"ok": True, "service": SERVICE}

    # Every /api/* router carries the token guard; /health above stays open on purpose.
    app.include_router(routes_warehouse.router(settings, cache), dependencies=guarded)
    app.include_router(routes_reads.router(cache, upstream), dependencies=guarded)
    app.include_router(health.router(settings, store, upstream), dependencies=guarded)
    # Reads nothing: the payload is the request, put through the pipeline's own rules.
    app.include_router(probebuild.router(), dependencies=guarded)
    # The model zoo. Its own router rather than a branch of the warehouse one: it resolves
    # its case from `src/mva/zoo/zoo.example.toml` (or `MVA_ZOO_CONFIG`) per request.
    app.include_router(api_zoo.router(settings, cache), dependencies=guarded)
    # The zoo's two write verbs (score, run) as background jobs. Same guard, plus their own
    # refusal when the token is empty: an open API may read the zoo, never spend the machine.
    app.include_router(api_zoo_jobs.router(settings, resolve_token(token)), dependencies=guarded)
    return app
