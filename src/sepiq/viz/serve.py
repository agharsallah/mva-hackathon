"""``sepiq-api`` — run the HTTP API under uvicorn.

Defaults to ``127.0.0.1:8900``: the only client is a React dev server on the same
machine, and with ``API_TOKEN`` empty this API has **no authentication**, which is
correct only while it is bound to loopback.

So binding a non-loopback address is gated: it needs ``API_TOKEN`` set, or an explicit
``--insecure`` that says the operator knows the port is open. A hosted deployment sets
the token and puts a TLS reverse proxy in front.
"""

import argparse
from pathlib import Path

from ..paths import anchor_cwd
from ..settings import setting

DEFAULT_PORT = 8900


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sepiq-api",
        description="serve the derived tables as JSON for the React app",
    )
    parser.add_argument("--host", default="127.0.0.1", help="bind address (default: %(default)s)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--reload", action="store_true", help="restart on source changes (development only)"
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="allow a non-loopback bind with no API_TOKEN (the port is then open)",
    )
    args = parser.parse_args(argv)

    # Every reference table, cache and docs path in this package is spelled relative to
    # the repository root (see `sepiq.paths`). A server started from `app/` answers 200 with
    # an empty list for each of them, which reads as a finding rather than as a
    # misconfiguration, so the process moves itself before anything reads a default.
    moved_from = anchor_cwd()
    if moved_from is not None:
        print(f"cwd:     {Path.cwd()} (moved from {moved_from} — relative paths are repo-rooted)")

    import uvicorn

    from .app import cors_origins, create_app
    from .auth import resolve_token
    from .cache import default_directory

    token = resolve_token()
    if args.host not in ("127.0.0.1", "localhost"):
        if not token and not args.insecure:
            print(
                f"refusing to bind {args.host} with no API_TOKEN: every /api/* route "
                f"would answer anyone who can reach the port.\n"
                f"Set API_TOKEN in .env (the proxy sends it as X-API-Key), "
                f"or pass --insecure if the port is genuinely private."
            )
            return 2
        if not token:
            print(f"warning: --insecure — {args.host} is open and unauthenticated")
    print(f"auth:    {'X-API-Key required' if token else 'open (API_TOKEN empty)'}")
    print(f"cache:   {default_directory()}")
    print(f"cors:    {', '.join(cors_origins()) or '(none — the browser will refuse)'}")
    print(f"upstream: {setting('UPSTREAM_URL') or '(none)'}")

    if args.reload:
        uvicorn.run(
            "sepiq.viz.app:create_app", factory=True, host=args.host, port=args.port, reload=True
        )
    else:
        uvicorn.run(create_app(), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
