"""Routes over the read store, and the proxy to ``mva-reads-api``.

Two halves with different cost models, deliberately kept in one module because the front
end sees them as one subject:

* **Aggregates** (``/api/reads/*``) run here, against Parquet in the object store. The
  two dimension tables are instant; anything that reads a shard is cached.
* **Passes over the reads** (``/api/probe/*``, ``/api/jobs/*``) are forwarded to
  ``mva-reads-api``, which owns the job registry. When it is not running, every one of
  those routes answers ``503`` with the URL it tried — see :mod:`mva.viz.proxy`.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from . import proxy, readstore
from .cache import Cache, safe_key
from .proxy import LONG_POLL_TIMEOUT, Upstream, forward
from .response import Envelope, cached, live


class Probe(BaseModel):
    """One candidate sequence to look for in the reads."""

    sequence: str = Field(description="DNA; validated upstream, not here")
    name: str | None = None


class ProbeRequest(BaseModel):
    """A batch of probes. One pass costs the same for one probe or five hundred."""

    probes: list[Probe]
    limit: int | None = Field(default=None, description="cap on hits returned (scan only)")


def router(cache: Cache, upstream: Upstream | None = None) -> APIRouter:
    """Build the read-store and proxy routes."""
    api = APIRouter(prefix="/api")
    reads = upstream or Upstream()

    @api.get("/reads/runs", response_model=Envelope, tags=["reads"])
    def runs() -> dict:
        """One row per delivered FASTQ: instrument, lane, read length, reads, bytes."""
        return live(readstore.runs(), f"{readstore.root()}/runs.parquet")

    @api.get("/reads/partitions", response_model=Envelope, tags=["reads"])
    def partitions() -> dict:
        """Shards, reads and GiB per ``(lane, read)`` partition, from the manifest."""
        return live(readstore.partitions(), f"{readstore.root()}/manifest.parquet")

    @api.get("/reads/flowcell", response_model=Envelope, tags=["reads"])
    def flowcell(
        lane: int = Query(ge=1, le=4),
        read: int = Query(ge=1, le=2),
        shard: int = Query(default=0, ge=0),
        refresh: bool = False,
    ) -> dict:
        """Read density across one shard's flowcell surface, binned 1000×1000.

        A column-pruned scan of ~4 M reads: three narrow integer columns out of a 240 MB
        shard, ~2.5 s live, then cached.
        """
        key = safe_key("flowcell", lane, read, shard)
        try:
            entry = cache.get_or_build(key, lambda: readstore.flowcell(lane, read, shard), refresh)
        except LookupError as missing:
            raise HTTPException(status_code=404, detail=str(missing)) from missing
        return cached(entry, f"{readstore.root()}/lane={lane}/read={read} shard {shard}")

    @api.get("/reads/cycle-quality", response_model=Envelope, tags=["reads"])
    def cycle_quality(refresh: bool = False) -> dict:
        """Mean Phred per cycle for each of the eight partitions — the decay curve.

        Sampled: 100k reads per partition. The first build reads the fat ``quality``
        column eight times and is slow; every later request is a cache hit.
        """
        entry = cache.get_or_build("cycle-quality", readstore.cycle_quality, refresh)
        return cached(
            entry, f"{readstore.root()} (sampled {readstore.SAMPLE_ROWS} reads per partition)"
        )

    @api.get("/reads/quality-levels", response_model=Envelope, tags=["reads"])
    def quality_levels(refresh: bool = False) -> dict:
        """Base counts per Phred value — four levels, because the NovaSeq quantises."""
        entry = cache.get_or_build("quality-levels", readstore.quality_levels, refresh)
        return cached(
            entry, f"{readstore.root()} (sampled {readstore.SAMPLE_ROWS} reads per partition)"
        )

    # ── proxy to mva-reads-api ───────────────────────────────────────────────────────

    @api.post("/probe/count", response_model=Envelope, tags=["probe"])
    async def probe_count(request: ProbeRequest) -> dict:
        """Reads per probe with a triage verdict. Returns a job — poll ``/api/jobs``."""
        return await _proxied(reads, "POST", "/count", json={"probes": _probes(request)})

    @api.post("/probe/scan", response_model=Envelope, tags=["probe"])
    async def probe_scan(request: ProbeRequest) -> dict:
        """Which reads carry each probe, either strand, one pass. Returns a job."""
        body: dict = {"probes": _probes(request)}
        if request.limit is not None:
            body["limit"] = request.limit
        return await _proxied(reads, "POST", "/scan", json=body)

    @api.get("/jobs", response_model=Envelope, tags=["probe"])
    async def jobs(state: str | None = None, verb: str | None = None) -> dict:
        """Every job the reads API knows, newest first."""
        return await _proxied(reads, "GET", "/jobs", params={"state": state, "verb": verb})

    @api.get("/jobs/{job_id}", response_model=Envelope, tags=["probe"])
    async def job(job_id: str) -> dict:
        """One job by id."""
        return await _proxied(reads, "GET", f"/jobs/{job_id}")

    @api.get("/jobs/{job_id}/wait", response_model=Envelope, tags=["probe"])
    async def job_wait(job_id: str, timeout: int = Query(default=30, ge=0, le=290)) -> dict:
        """Long-poll until the job is terminal or ``timeout`` seconds pass.

        Capped at 290 s upstream to stay under common 300 s proxy limits; on timeout the
        job comes back still ``running`` and the caller asks again.
        """
        return await _proxied(
            reads,
            "GET",
            f"/jobs/{job_id}/wait",
            params={"timeout": timeout},
            timeout=LONG_POLL_TIMEOUT,
        )

    @api.post("/jobs/{job_id}/cancel", response_model=Envelope, tags=["probe"])
    async def job_cancel(job_id: str) -> dict:
        """Interrupt the running query. A finished job is a 409."""
        return await _proxied(reads, "POST", f"/jobs/{job_id}/cancel")

    return api


def _probes(request: ProbeRequest) -> list[dict]:
    return [probe.model_dump(exclude_none=True) for probe in request.probes]


async def _proxied(upstream: Upstream, method: str, path: str, **kwargs) -> dict:
    """Forward, then envelope the upstream body so every ``/api/*`` route matches."""
    body = await forward(upstream, method, path, **kwargs)
    return live(body, f"{proxy.base_url()}{path}")
