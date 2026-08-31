"""``mva-reads-api`` — run the reads API under uvicorn.

One process on purpose: the job registry lives in memory (results also on disk), so a
multi-worker uvicorn would split it. The job pool inside the process provides the
concurrency that matters — the queries themselves.
"""

import argparse

from ...warehouse.settings import setting


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mva-reads-api",
                                     description="serve the read store over HTTP")
    parser.add_argument("--host", default="127.0.0.1",
                        help="bind address; 0.0.0.0 exposes it — set MVA_API_TOKEN "
                             "first (default: %(default)s)")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--job-workers", type=int,
                        default=int(setting("MVA_API_JOB_WORKERS") or "2"),
                        help="store queries running at once; a scan saturates I/O, so "
                             "keep this small (default: %(default)s)")
    args = parser.parse_args(argv)

    import uvicorn

    from .app import create_app, default_jobs_dir
    from .jobs import Manager

    if not setting("MVA_API_TOKEN"):
        print("warning: MVA_API_TOKEN is empty — the API is open to anyone who can "
              "reach it")
    manager = Manager(directory=default_jobs_dir(), workers=args.job_workers)
    uvicorn.run(create_app(manager), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
