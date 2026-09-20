"""``/api/zoo/score``, ``/api/zoo/run`` and ``/api/zoo/jobs/*`` — the zoo's write verbs.

:mod:`mva.viz.api_zoo` is the read-only window onto what the zoo produced. This module is the
other half: the two verbs that make it produce something. Scoring 39,000 alleles and running
the eight-stage DAG both take minutes, and an HTTP request should not, so both are **jobs** —
submitted, given an id, run on a worker thread, polled or long-polled until terminal. That is
the pattern ``mva-reads-api`` already uses for a k-mer scan, and this module reuses its
:class:`~mva.reads.api.jobs.Manager` rather than growing a second one: one lifecycle
(``queued → running → done | failed | cancelled | lost``), one snapshot shape, one place where
"finished answers survive a restart" is implemented.

**The job body is the CLI's body.** ``POST /api/zoo/score`` runs the same four calls
``mva-zoo score`` runs — build the adapter, measure coverage, write the rows to
``warehouse.allele_scores``, append the ``data_lineage`` edge — so a score written through the
API is indistinguishable from one written at the terminal, cache key and lineage row included.
A re-submission of the same alleles inserts **0** rows: the cache is keyed on
``(model, version, allele_id)`` and skips what it already holds.

**Compute needs a token.** Every route here is under the same ``X-API-Key`` guard as the rest
of ``/api/*``, and the two ``POST``s additionally **refuse outright when ``MVA_VIZ_TOKEN`` is
empty**, saying so in the reply. An open API is the correct setting for a loopback read
service; it is not a correct setting for a route that spends a machine's CPU for an hour and
appends to the warehouse. The ``GET``s stay open on an open deployment because they can only
report on jobs that were never allowed to start.

**Coordinate-free, like every other zoo route.** A reply carries ``allele_id`` hashes, model
keys, versions, scores and venues. ``aux`` is a model's own extra output, so it is filtered
(:data:`FORBIDDEN_AUX`) before it leaves: a lane that decided to echo a position into its aux
JSON must not be able to publish one through this route.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..reads.api.jobs import Job, Manager
from ..warehouse.settings import Postgres
from ..zoo import cache as zoo_cache
from ..zoo import registry
from ..zoo.types import MODES, ScoreRow
from .api_zoo_case import Case, case_config
from .cache import default_directory
from .response import Envelope, live

__all__ = ["FORBIDDEN_AUX", "MAX_ROWS", "Runners", "router"]

#: How many score rows a reply may inline before the caller is told to read them back through
#: ``GET /api/zoo/scores``. A job that scored the whole callset answers with its summary only.
MAX_ROWS = 500

#: Keys an ``aux`` payload may not carry out of the API. A model's aux is free-form JSON, so
#: it is the one field on this route that is not coordinate-free *by construction*.
FORBIDDEN_AUX = frozenset(
    {"pos", "position", "chrom", "chromosome", "start", "end", "ref", "alt", "locus"}
)

SOURCE = "mva.zoo.adapters + warehouse.allele_scores (written by this request)"


class ScoreRequest(BaseModel):
    """Score one lane over some alleles — or, with ``allele_ids`` omitted, over all of them."""

    model: str = Field(min_length=1, max_length=64, description="the model card's key")
    allele_ids: list[str] | None = Field(
        default=None,
        max_length=50_000,
        description="the coordinate-free allele keys; null or omitted means the whole record set",
    )
    mode: str | None = Field(
        default=None,
        description=f"one of {', '.join(MODES)}; omitted, the case config's own mode is used",
    )
    config: str | None = Field(
        default=None, description="a case TOML to run against; omitted, the server's own case"
    )


class RunRequest(BaseModel):
    """Run the whole DAG. The manifest comes back as the job's result, coordinate-free."""

    config: str | None = Field(default=None, description="a case TOML; omitted, the server's case")
    from_stage: str | None = Field(
        default=None, max_length=32, description="re-run from this stage; earlier ones are restored"
    )
    force: bool = Field(default=False, description="drop the checkpoints and recompute every stage")


class Runners:
    """The two job bodies, as one injectable object.

    Production uses the defaults, which open the warehouse and call :mod:`mva.zoo`. A test
    hands in its own two callables and exercises the routes, the manager and the payload
    shaping without a database — the seam is here rather than inside the routes so that what
    a test replaces is exactly one function per verb.
    """

    def __init__(
        self,
        score: Callable[[Postgres, Case, ScoreRequest], dict[str, Any]] | None = None,
        run: Callable[[Case, RunRequest], dict[str, Any]] | None = None,
    ):
        self.score = score or _score_job
        self.run = run or _run_job


def router(
    settings: Postgres,
    token: str,
    *,
    case: Case | None = None,
    manager: Manager | None = None,
    runners: Runners | None = None,
) -> APIRouter:
    """Build the job routes. ``token`` is the resolved ``MVA_VIZ_TOKEN``; empty refuses writes."""
    api = APIRouter(prefix="/api/zoo", tags=["zoo"])
    jobs = manager if manager is not None else Manager(default_directory() / "zoo-jobs", workers=1)
    bodies = runners or Runners()

    def resolve(path: str | None) -> Case:
        return _case(case, path)

    @api.post("/score", response_model=Envelope, summary="score one lane — returns a job id")
    def zoo_score(request: ScoreRequest) -> dict:
        """Submit a scoring job: adapter → coverage → cache write → lineage edge.

        Idempotent by cache key: re-submitting the same alleles for the same
        ``(model, version)`` inserts 0 rows and reports them as ``skipped``. 403 when the
        server has no ``MVA_VIZ_TOKEN`` — an open API does not get to spend the machine.
        """
        _require_token(token, "POST /api/zoo/score")
        current = resolve(request.config)
        _known_model(request.model)
        job = jobs.submit(
            "zoo-score",
            {
                "model": request.model,
                "alleles": len(request.allele_ids) if request.allele_ids else None,
                "mode": request.mode or current.config.mode,
            },
            lambda _job: bodies.score(settings, current, request),
        )
        return live(_snapshot(job, current), SOURCE)

    @api.post("/run", response_model=Envelope, summary="run the whole DAG — returns a job id")
    def zoo_run(request: RunRequest) -> dict:
        """Submit a workflow job. Its result is the run manifest's coordinate-free copy."""
        _require_token(token, "POST /api/zoo/run")
        current = resolve(request.config)
        job = jobs.submit(
            "zoo-run",
            {"config": str(current.config.path), "from_stage": request.from_stage},
            lambda _job: bodies.run(current, request),
        )
        return live(_snapshot(job, current), SOURCE)

    @api.get("/jobs", response_model=Envelope, summary="every zoo job, newest first")
    def zoo_jobs(state: str | None = None) -> dict:
        found = [job for job in jobs.jobs(state=state) if job.verb.startswith("zoo-")]
        return live([_snapshot(job, resolve(None)) for job in found], SOURCE)

    @api.get("/jobs/{job_id}", response_model=Envelope, summary="one job's state and summary")
    def zoo_job(job_id: str) -> dict:
        return live(_snapshot(_find(jobs, job_id), resolve(None)), SOURCE)

    @api.get("/jobs/{job_id}/wait", response_model=Envelope, summary="long-poll until terminal")
    def zoo_job_wait(
        job_id: str,
        timeout: int = Query(default=30, ge=0, le=290),
    ) -> dict:
        """Block until the job is terminal or ``timeout`` seconds pass, then answer either way.

        Capped at 290 s to stay under the usual 300 s proxy limit; on a timeout the job comes
        back still ``running`` and the caller asks again.
        """
        job = _find(jobs, job_id)
        jobs.wait(job, float(timeout))
        return live(_snapshot(job, resolve(None)), SOURCE)

    return api


# ---------------------------------------------------------------------------------------
# The two job bodies
# ---------------------------------------------------------------------------------------


def _score_job(settings: Postgres, case: Case, request: ScoreRequest) -> dict[str, Any]:
    """What ``mva-zoo score`` does, in this process: adapter, coverage, cache, lineage.

    Deliberately the same four calls rather than a shell-out: a subprocess would need its own
    warehouse connection and its own ``.env``, and its failure would arrive as an exit code
    instead of an exception this job can report.
    """
    import time

    from ..warehouse.postgres import attached
    from ..zoo.adapters import build as build_adapter
    from ..zoo.adapters import coverage_of, records_from_parquet

    config = case.config
    mode = request.mode or config.mode
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}; expected one of {', '.join(MODES)}")
    card = _known_model(request.model)
    parquet = Path(config.out_dir) / "records.parquet"
    began = time.perf_counter()

    with attached(replace(settings, schema=config.warehouse_schema)) as connection:
        records = records_from_parquet(parquet, allele_ids=request.allele_ids)
        if not records:
            raise ValueError(f"{parquet} holds no record for the requested alleles")
        records = [record.masked() for record in records] if mode == "catalogue-free" else records
        adapter = build_adapter(card, connection=connection, records_parquet=parquet)
        coverage = coverage_of(adapter, records)
        run_id = zoo_cache.run_id()
        written = zoo_cache.write(
            connection,
            config.warehouse_schema,
            _stamped(adapter.score(records), mode=mode),
            run_id=run_id,
        )
        zoo_cache.lineage_row(
            connection,
            config.warehouse_schema,
            model=card.key,
            version=str(card.version),
            run_id=run_id,
            rows=written.inserted,
            digest=str(getattr(adapter, "digest", "") or ""),
            source_ref=str(getattr(adapter, "source_ref", "") or card.source),
        )
        rows = _rows(connection, case, request, card.key)

    return {
        "model": card.key,
        "version": str(card.version),
        "mode": mode,
        "run_id": run_id,
        "requested": len(records),
        "inserted": written.inserted,
        "skipped": written.skipped,
        "coverage": {
            "scored": coverage.scored,
            "total": coverage.total,
            "fraction": round(coverage.fraction, 6),
        },
        "incomplete": str(getattr(adapter, "incomplete", "") or ""),
        "wall_clock_seconds": round(time.perf_counter() - began, 3),
        "rows": rows,
    }


def _run_job(case: Case, request: RunRequest) -> dict[str, Any]:
    """Run the DAG in this process and hand back the manifest's coordinate-free copy."""
    from ..zoo import workflow

    manifest = workflow.run(case.config.path, from_stage=request.from_stage, force=request.force)
    return manifest.public()


def _rows(connection: Any, case: Case, request: ScoreRequest, model: str) -> list[dict[str, Any]]:
    """The cached rows for the alleles that were asked for, when there are few enough."""
    ids = request.allele_ids
    if not ids or len(ids) > MAX_ROWS:
        return []
    found = zoo_cache.read(connection, case.config.warehouse_schema, model=model, allele_ids=ids)
    return [
        {
            "allele_id": row.allele_id,
            "model": row.model,
            "version": row.version,
            "score": row.score,
            "aux": _safe_aux(row.aux),
            "venue": row.venue,
            # `null`, not "", when the cache reader did not bring a timestamp back:
            # `mva.zoo.cache.read` does not select `ts`, and an empty string would read
            # as "written at the epoch" rather than as "not asked for".
            "ts": getattr(row, "ts", None) or None,
        }
        for row in sorted(found, key=lambda item: item.allele_id)
    ]


def _stamped(rows: Iterator[ScoreRow], *, mode: str) -> Iterator[ScoreRow]:
    """Record which catalogue mode produced each row — the CLI stamps the same field."""
    for row in rows:
        yield replace(row, aux={**row.aux, "mode": mode})


# ---------------------------------------------------------------------------------------
# Shaping and guards
# ---------------------------------------------------------------------------------------


def _snapshot(job: Job, case: Case) -> dict[str, Any]:
    """One job as the API serves it: state, summary or error, and the case it belongs to."""
    raw = job.snapshot()
    result = raw.get("result")
    payload: dict[str, Any] = {
        "job_id": raw["id"],
        "verb": raw["verb"],
        "state": raw["state"],
        "params": raw["params"],
        "submitted_at": raw["submitted_at"],
        "elapsed_seconds": raw["elapsed_seconds"],
        "error": raw["error"],
        "case": case.config.case_json(),
        "summary": None,
        "rows": [],
    }
    if isinstance(result, Mapping):
        payload["summary"] = {key: value for key, value in result.items() if key != "rows"}
        # Rows are inlined only when the caller named the alleles and there were few enough of
        # them. The count is read back off the job's own params, so a later GET applies the
        # same rule as the POST that created it. `aux` is sanitised here as well as in the
        # job body: this is the boundary the guarantee is about, whoever produced the rows.
        asked = raw["params"].get("alleles") if isinstance(raw["params"], Mapping) else None
        if isinstance(asked, int) and asked <= MAX_ROWS:
            rows = result.get("rows") or []
            payload["rows"] = [{**row, "aux": _safe_aux(row.get("aux"))} for row in rows]
    elif result is not None:
        payload["summary"] = result
    return payload


def _safe_aux(aux: Any) -> dict[str, Any]:
    """A model's own extra output, minus anything shaped like a position."""
    if not isinstance(aux, Mapping):
        return {}
    return {key: value for key, value in aux.items() if str(key).lower() not in FORBIDDEN_AUX}


def _case(pinned: Case | None, path: str | None) -> Case:
    """The case this request runs against: the pinned one, the named one, or the server's."""
    if pinned is not None:
        return pinned
    if not path:
        return case_config()
    from ..zoo.case_config import Config
    from .api_zoo_reads import Tables

    try:
        config = Config.load(path)
    except (OSError, ValueError) as error:
        raise HTTPException(
            status_code=400, detail=f"cannot read case config {path!r}: {error}"
        ) from error
    return Case(config=config, tables=Tables.of(config))


def _known_model(key: str) -> Any:
    """The model card, or a 404 naming the keys that do exist."""
    cards = registry.load()
    if key not in cards:
        raise HTTPException(
            status_code=404, detail=f"no model {key!r}; known: {', '.join(sorted(cards))}"
        )
    return cards[key]


def _find(jobs: Manager, job_id: str) -> Job:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"no job {job_id!r}")
    return job


def _require_token(token: str, verb: str) -> None:
    """Refuse a compute verb on an API that has no shared secret, and say why."""
    if not token:
        raise HTTPException(
            status_code=403,
            detail=(
                f"{verb} is disabled: MVA_VIZ_TOKEN is empty, so this API is open. "
                "A route that spends the machine's CPU and appends to the warehouse needs "
                "the shared token set (the read routes do not)."
            ),
        )
