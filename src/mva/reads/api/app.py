"""The reads API — every ``mva-reads`` verb over HTTP, without shelling into the server.

Design in one paragraph: cheap questions answer inline; anything that touches the reads
(a scan is minutes, a convert is an hour) returns **202 with a job** instead of holding
the connection open through proxies and timeouts. Poll ``GET /jobs/{id}``, long-poll
``GET /jobs/{id}/wait``, or cancel with ``POST /jobs/{id}/cancel`` — cancel interrupts
the underlying DuckDB query, it does not merely hide the job. Finished jobs survive an
API restart; in-flight ones are marked ``lost`` rather than re-run.

Auth is one shared token: set ``MVA_API_TOKEN`` (``.env`` or environment) and every
request must carry it as ``X-API-Key``. An empty token leaves the API open — acceptable
only on localhost or behind an SSH tunnel.

Interactive documentation is generated from this module: ``/docs`` (Swagger UI, try
requests in the browser), ``/redoc``, and ``/openapi.json`` for client generation.
"""

from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from fastapi.security import APIKeyHeader

from ...warehouse.settings import setting
from . import runners
from .jobs import Manager, TERMINAL
from .models import (BenchRequest, ConvertRequest, JobOut, ProbeRequest,
                     ScanRequest, SqlRequest, VerifyRequest)

_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False,
                       description="the value of MVA_API_TOKEN on the server")


def token_guard(expected: str) -> Callable[[str | None], None]:
    """Build the auth dependency for one resolved token. Empty token means open.

    The expected value is bound here, at application construction, rather than read
    inside the request: resolving it per request meant a ``.env`` parse per HTTP call,
    and it made the API's behaviour depend on whichever ``.env`` happened to sit above
    the working directory — including a developer's own, in tests.
    """

    def require_token(provided: str | None = Depends(_HEADER)) -> None:
        if expected and provided != expected:
            raise HTTPException(status_code=401, detail="missing or wrong X-API-Key")

    return require_token


def default_jobs_dir() -> Path:
    return Path(setting("MVA_STAGING_DIR")).expanduser() / "api-jobs"


def create_app(manager: Manager | None = None, token: str | None = None) -> FastAPI:
    """Build the application.

    Both arguments are seams for tests: they inject their own :class:`Manager`, and pass
    ``token=""`` to get an open API regardless of what the surrounding environment holds.
    Left as ``None``, each is resolved from the settings loader once, here.
    """
    if manager is None:
        workers = int(setting("MVA_API_JOB_WORKERS") or "2")
        manager = Manager(directory=default_jobs_dir(), workers=workers)
    if token is None:
        token = setting("MVA_API_TOKEN")

    app = FastAPI(
        title="mva-reads API",
        version="1.0.0",
        summary="Query the 1.07-billion-read store over HTTP.",
        description=__doc__,
    )
    app.state.manager = manager
    # everything but /health requires the token; liveness probes carry no secrets
    api = APIRouter(dependencies=[Depends(token_guard(token))])

    def submitted(verb: str, params: dict, runner) -> JobOut:
        return JobOut(**manager.submit(verb, params, runner).snapshot())

    def known(job_id: str):
        job = manager.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"no job {job_id}")
        return job

    @app.get("/health", tags=["service"])
    def health() -> dict:
        """Liveness only — it does not touch the store."""
        return {"ok": True, "service": "mva-reads-api"}

    @api.get("/store/status", response_model=JobOut, status_code=202, tags=["store"])
    def store_status(root: str | None = None) -> JobOut:
        """What the store holds, from its manifest — shards, reads, GiB per lane."""
        return submitted("status", {"root": root}, runners.status_runner(root))

    @api.get("/store/qc", response_model=JobOut, status_code=202, tags=["store"])
    def store_qc(root: str | None = None) -> JobOut:
        """Per-lane read counts, filter rate and quality profile. Full scan — minutes."""
        return submitted("qc", {"root": root}, runners.qc_runner(root))

    @api.post("/scan", response_model=JobOut, status_code=202, tags=["query"])
    def scan(request: ScanRequest) -> JobOut:
        """K-mer strike: which reads carry each probe, either strand, one pass.

        One pass costs the same for one probe or five hundred — batch every candidate
        into a single request instead of looping.
        """
        return submitted("scan", request.model_dump(), runners.scan_runner(request))

    @api.post("/count", response_model=JobOut, status_code=202, tags=["query"])
    def count(request: ProbeRequest) -> JobOut:
        """Reads per probe with a triage verdict — decides whether an allele is real."""
        return submitted("count", request.model_dump(), runners.count_runner(request))

    @api.post("/sql", response_model=JobOut, status_code=202, tags=["query"])
    def sql(request: SqlRequest) -> JobOut:
        """Read-only SQL with the store bound as the ``reads`` view — the escape hatch."""
        return submitted("sql", request.model_dump(), runners.sql_runner(request))

    @api.post("/verify", response_model=JobOut, status_code=202, tags=["store"])
    def verify(request: VerifyRequest) -> JobOut:
        """Prove the store matches the delivery (deep checks need the source FASTQ)."""
        return submitted("verify", request.model_dump(),
                         runners.verify_runner(request))

    @api.post("/bench", response_model=JobOut, status_code=202, tags=["build"])
    def bench(request: BenchRequest) -> JobOut:
        """Race the conversion engines on a sample of the delivery."""
        return submitted("bench", request.model_dump(), runners.bench_runner(request))

    @api.post("/convert", response_model=JobOut, status_code=202, tags=["build"])
    def convert(request: ConvertRequest) -> JobOut:
        """Rebuild the whole store from the delivery — the hour-long verb.

        One at a time, enforced: two converts would race for the same staging
        directory and the same object keys, so a second submission while one is
        queued or running is refused with 409 rather than trusted to a docstring.
        """
        running = [job for job in manager.jobs(verb="convert")
                   if job.state not in TERMINAL]
        if running:
            raise HTTPException(status_code=409,
                                detail=f"convert {running[0].id} is already "
                                       f"{running[0].state} — cancel it or wait")
        return submitted("convert", request.model_dump(),
                         runners.convert_runner(request))

    @api.get("/jobs", response_model=list[JobOut], tags=["jobs"])
    def jobs(state: str | None = None, verb: str | None = None) -> list[JobOut]:
        """Every known job, newest first — including history from before a restart."""
        return [JobOut(**job.snapshot()) for job in manager.jobs(state, verb)]

    @api.get("/jobs/{job_id}", response_model=JobOut, tags=["jobs"])
    def job(job_id: str) -> JobOut:
        """One job. Poll this until ``state`` is terminal; ``result`` appears on done."""
        return JobOut(**known(job_id).snapshot())

    @api.get("/jobs/{job_id}/wait", response_model=JobOut, tags=["jobs"])
    def wait(job_id: str,
             timeout: float = Query(default=30, ge=0, le=290)) -> JobOut:
        """Long-poll: returns when the job finishes or after ``timeout`` seconds.

        The cap stays under common 300s proxy limits; on timeout you simply get the
        job still running — call wait again. One saturating pattern::

            while state not terminal: GET /jobs/{id}/wait?timeout=60
        """
        found = known(job_id)
        manager.wait(found, timeout)
        return JobOut(**found.snapshot())

    @api.post("/jobs/{job_id}/cancel", response_model=JobOut, tags=["jobs"])
    def cancel(job_id: str) -> JobOut:
        """Stop a queued or running job — interrupts the DuckDB query underneath."""
        found = known(job_id)
        if not manager.cancel(found):
            raise HTTPException(status_code=409,
                                detail=f"job {job_id} already {found.state}")
        return JobOut(**found.snapshot())

    @api.delete("/jobs/{job_id}", status_code=204, tags=["jobs"])
    def forget(job_id: str) -> None:
        """Drop a finished job from the listing and the on-disk history."""
        found = known(job_id)
        if found.state not in TERMINAL:
            raise HTTPException(status_code=409,
                                detail="cancel it first — the job is still running")
        manager.forget(job_id)

    app.include_router(api)
    return app
