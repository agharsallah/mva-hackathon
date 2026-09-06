"""``mva-viz-api`` — run the viz API under uvicorn.

Defaults to ``127.0.0.1:8900``: the only client is a React dev server on the same
machine, and with ``MVA_VIZ_TOKEN`` empty this API has **no authentication** because it
holds no write verb and no secret the browser could not already reach. That is only true
while it is bound to loopback — ``--host 0.0.0.0`` publishes patient positions from
``/api/panel/locus`` to anyone who can reach the port.

So binding a non-loopback address is gated: it needs ``MVA_VIZ_TOKEN`` set, or an
explicit ``--insecure`` that says the operator knows the port is open. The hosted
deployment sets the token and puts a TLS reverse proxy in front — see
``docs/step-0/infrastructure.md``.
"""

import argparse

from ..warehouse.settings import setting

DEFAULT_PORT = 8900


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mva-viz-api",
        description="serve the warehouse and the read store as JSON for the viz app",
    )
    parser.add_argument("--host", default="127.0.0.1", help="bind address (default: %(default)s)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--reload", action="store_true", help="restart on source changes (development only)"
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="allow a non-loopback bind with no MVA_VIZ_TOKEN (publishes patient positions)",
    )
    args = parser.parse_args(argv)

    import uvicorn

    from .app import cors_origins, create_app
    from .auth import resolve_token
    from .cache import default_directory

    token = resolve_token()
    if args.host not in ("127.0.0.1", "localhost"):
        if not token and not args.insecure:
            print(
                f"refusing to bind {args.host} with no MVA_VIZ_TOKEN: /api/panel/locus "
                f"serves real patient positions to anyone who can reach the port.\n"
                f"Set MVA_VIZ_TOKEN in .env (the Vercel proxy sends it as X-API-Key), "
                f"or pass --insecure if the port is genuinely private."
            )
            return 2
        if not token:
            print(f"warning: --insecure — {args.host} is open, patient positions included")
    print(f"auth:    {'X-API-Key required' if token else 'open (MVA_VIZ_TOKEN empty)'}")
    print(f"cache:   {default_directory()}")
    print(f"cors:    {', '.join(cors_origins()) or '(none — the browser will refuse)'}")
    print(f"upstream reads API: {setting('MVA_READS_API_URL')}")

    if args.reload:
        uvicorn.run(
            "mva.viz.app:create_app", factory=True, host=args.host, port=args.port, reload=True
        )
    else:
        uvicorn.run(create_app(), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
