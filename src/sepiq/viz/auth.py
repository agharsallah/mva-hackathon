"""One shared token, for the day this stops being a loopback service.

The API was written for one client on one machine, so it had no authentication: nothing
it serves is reachable by a browser that could not already reach the data. That stops
being true the moment it binds a public interface.

* ``API_TOKEN`` empty  → the API is open. The only correct setting for loopback.
* ``API_TOKEN`` set    → every ``/api/*`` request must carry it as ``X-API-Key``.

``/health`` is deliberately outside the guard: an uptime probe carries no secret and the
response is a constant. Nothing else is exempt.

The comparison is :func:`secrets.compare_digest`, not ``!=``. A plain comparison returns
as soon as two bytes differ, so the time it takes leaks how much of a guessed token was
right — enough, over many requests, to recover it a character at a time.
"""

import secrets
from collections.abc import Callable

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader

from ..settings import setting

#: The header clients send. ``auto_error=False`` so a missing header reaches the guard
#: as ``None`` and an open API (empty token) still answers it.
HEADER = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description="the value of API_TOKEN on the server; not needed when it is empty",
)


def resolve_token(token: str | None = None) -> str:
    """The expected token, resolved once at application construction.

    Passed explicitly it wins — that is the seam tests use to get an open API regardless
    of the ``.env`` sitting above the working directory. ``None`` reads the setting.
    """
    return setting("API_TOKEN") if token is None else token


def token_guard(expected: str) -> Callable[[str | None], None]:
    """Build the auth dependency for one resolved token. Empty token means open."""

    def require_token(provided: str | None = Depends(HEADER)) -> None:
        if not expected:
            return
        if provided is None or not secrets.compare_digest(provided, expected):
            raise HTTPException(status_code=401, detail="missing or wrong X-API-Key")

    return require_token


def guard_dependencies(expected: str) -> list:
    """The ``dependencies=`` list for a protected router — empty when the API is open.

    An empty list rather than a no-op dependency keeps the OpenAPI schema honest: an
    open deployment does not advertise a security scheme nobody has to satisfy.
    """
    return [Depends(token_guard(expected))] if expected else []
