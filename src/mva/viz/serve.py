"""``mva-viz-api`` — run the viz API under uvicorn.

Defaults to ``127.0.0.1:8900``: the only client is a React dev server on the same
machine, and this API has **no authentication** because it holds no write verb and no
secret the browser could not already reach. That is only true while it is bound to
loopback — ``--host 0.0.0.0`` publishes patient positions from ``/api/panel/locus`` to
anyone who can reach the port, so it warns.
"""

import argparse

from ..warehouse.settings import setting

DEFAULT_PORT = 8900


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mva-viz-api",
        description="serve the warehouse and the read store as JSON for the viz app")
    parser.add_argument("--host", default="127.0.0.1",
                        help="bind address (default: %(default)s)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--reload", action="store_true",
                        help="restart on source changes (development only)")
    args = parser.parse_args(argv)

    import uvicorn

    from .app import cors_origins, create_app
    from .cache import default_directory

    if args.host not in ("127.0.0.1", "localhost"):
        print(f"warning: binding {args.host} — /api/panel/locus serves real patient "
              f"positions and this API has no authentication")
    print(f"cache:   {default_directory()}")
    print(f"cors:    {', '.join(cors_origins()) or '(none — the browser will refuse)'}")
    print(f"upstream reads API: {setting('MVA_READS_API_URL')}")

    if args.reload:
        uvicorn.run("mva.viz.app:create_app", factory=True, host=args.host,
                    port=args.port, reload=True)
    else:
        uvicorn.run(create_app(), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
