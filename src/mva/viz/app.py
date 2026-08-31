"""The viz application: CORS, the cache, the routers, and one liveness probe.

Assembly only. Every route lives in :mod:`~mva.viz.routes_warehouse` or
:mod:`~mva.viz.routes_reads`; every query lives below those. That keeps this module the
one place to look for "what is wired to what", and keeps it short enough to be read in
one go.

Two things are configured here rather than hard-coded, because a browser is involved:

* **CORS.** The React dev server is a different origin from this API, so the browser
  refuses to read the response unless the server says the origin is allowed.
  ``MVA_VIZ_CORS`` is the comma-separated list, defaulting to the Vite dev server on both
  spellings of loopback (``localhost`` and ``127.0.0.1`` are *different* origins to a
  browser, which is why both are there).
* **The cache directory.** ``MVA_VIZ_CACHE``, under gitignored ``build/`` by default. The
  locus cache holds real patient positions, so this must never point inside the tree git
  tracks.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..warehouse.settings import Postgres, setting
from . import routes_reads, routes_warehouse
from .cache import Cache, default_directory

SERVICE = "mva-viz-api"


def cors_origins(configured: str | None = None) -> list[str]:
    """The browser origins allowed to read from this API."""
    raw = configured if configured is not None else setting("MVA_VIZ_CORS")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def create_app(settings: Postgres | None = None, cache: Cache | None = None,
               origins: list[str] | None = None, upstream=None) -> FastAPI:
    """Build the application. Tests inject settings, cache and a fake upstream."""
    settings = settings or Postgres.from_env()
    cache = cache or Cache(default_directory())

    app = FastAPI(
        title=SERVICE,
        version="1.0.0",
        summary="The warehouse and the read store as JSON, for one React app.",
        description=__doc__,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins if origins is not None else cors_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    app.state.settings = settings
    app.state.cache = cache

    @app.get("/health", tags=["service"])
    def health() -> dict:
        """Liveness only — it touches neither the database nor the object store."""
        return {"ok": True, "service": SERVICE}

    app.include_router(routes_warehouse.router(settings, cache))
    app.include_router(routes_reads.router(cache, upstream))
    return app
