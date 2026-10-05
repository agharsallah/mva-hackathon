"""The HTTP application: CORS, auth, the cache, the routers, and one liveness probe.

Assembly only. Every route lives in its own module and every query lives below that.
That keeps this module the one place to look for "what is wired to what", and keeps it
short enough to be read in one go.

Three things are configured here rather than hard-coded, because a browser is involved:

* **CORS.** The React dev server is a different origin from this API, so the browser
  refuses to read the response unless the server says the origin is allowed. ``API_CORS``
  is the comma-separated list, defaulting to the Vite dev server on both spellings of
  loopback (``localhost`` and ``127.0.0.1`` are *different* origins to a browser, which
  is why both are there). Any loopback port is allowed on top of that list
  (:data:`LOOPBACK_ORIGIN`): Vite walks to 5174, 5175, … when 5173 is already taken, and
  a port-exact list turns that silent drift into a blocked fetch that the app can only
  report as "api down".
* **The cache directory.** ``API_CACHE``, under gitignored ``build/`` by default.
* **The shared token.** ``API_TOKEN``, empty by default, which leaves the API open — the
  only correct setting while it is bound to loopback. Set it and every ``/api/*`` route
  requires it as ``X-API-Key``; ``/health`` stays open for uptime probes. See
  :mod:`sepiq.viz.auth`. Set it whenever the service binds anything but loopback.

The router list is empty while the data layer for this challenge is being built: this is
the shell, and a route is added here as its module lands.
"""

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..settings import setting
from .auth import guard_dependencies, resolve_token
from .cache import Cache, default_directory

SERVICE = "api"

#: Any port on either spelling of loopback. The dev server's port is not stable — Vite
#: takes the next free one when 5173 is busy — and a developer's own machine is not a
#: cross-origin threat, so the port is not what makes this API safe. Deployed origins
#: are never loopback and still have to be named in ``API_CORS``.
LOOPBACK_ORIGIN = r"^http://(localhost|127\.0\.0\.1)(:\d+)?$"


def cors_origins(configured: str | None = None) -> list[str]:
    """The browser origins allowed to read from this API."""
    raw = configured if configured is not None else setting("API_CORS")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def create_app(
    cache: Cache | None = None,
    origins: list[str] | None = None,
    routers: list[APIRouter] | None = None,
    token: str | None = None,
) -> FastAPI:
    """Build the application. Tests inject the cache, the routers and the token.

    ``token=""`` forces an open API regardless of what the surrounding ``.env`` holds;
    ``token=None`` resolves ``API_TOKEN`` once, here, so no request parses a file.
    """
    cache = cache or Cache(default_directory())
    guarded = guard_dependencies(resolve_token(token))

    app = FastAPI(
        title=SERVICE,
        version="1.0.0",
        summary="The derived tables as JSON, for one React app.",
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
    app.state.cache = cache

    @app.get("/health", tags=["service"])
    def liveness() -> dict:
        """Liveness only — it touches no backend."""
        return {"ok": True, "service": SERVICE}

    # Every /api/* router carries the token guard; /health above stays open on purpose.
    for router in routers or []:
        app.include_router(router, dependencies=guarded)
    return app
