"""Talk to a running ``mva-reads-api`` from a script, without re-learning its rules.

The job service is asynchronous on purpose: every verb that touches 1.07 billion reads
returns a job id and is polled. That contract is easy to get subtly wrong from a one-off
script, and two of the ways to get it wrong cost an hour each, so they are solved here
once:

**Poll in short waits, not one long hold.** A 280-second held connection is long enough
for an idle timeout somewhere between the client and the server to close it, and the job
keeps running while the client believes it failed. Many short polls cost nothing and
cannot be cut.

**A dropped connection is not a dead job.** The poller retries rather than raising, and
:func:`wait_for` attaches to a job that is already running instead of starting a second
one.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from typing import Any

#: Seconds per long-poll — short enough that nothing between here and the server times it
#: out mid-wait.
POLL_SECONDS = 25

#: Total polling budget, in rounds.
POLL_ROUNDS = 160

#: States a job never leaves.
TERMINAL = frozenset({"done", "failed", "cancelled", "lost"})


def _client(base: str, token: str):
    import httpx

    return httpx.Client(base_url=base.rstrip("/"), timeout=60.0, headers={"X-API-Key": token})


def wait_for(
    job_id: str,
    base: str,
    token: str,
    *,
    rounds: int = POLL_ROUNDS,
    report: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Poll one job to completion. Raises ``RuntimeError`` if it did not finish well."""
    import httpx

    with _client(base, token) as client:
        for round_number in range(rounds):
            try:
                reply = client.get(
                    f"/jobs/{job_id}/wait", params={"timeout": POLL_SECONDS}, timeout=60.0
                )
                reply.raise_for_status()
                job = reply.json()
            except httpx.HTTPError as dropped:
                # The job does not care that our connection did.
                report(f"  … poll {round_number} dropped ({type(dropped).__name__}); retrying")
                time.sleep(5)
                continue
            if job["state"] in TERMINAL:
                if job["state"] != "done":
                    raise RuntimeError(f"job {job_id} {job['state']}: {job.get('error')}")
                return dict(job["result"])
            if round_number % 4 == 0:
                report(f"  … still running ({int(job.get('elapsed_seconds') or 0)}s)")
    raise RuntimeError(f"job {job_id} did not finish within {rounds} polls")


def scan(
    probes: Sequence[tuple[str, str]],
    base: str,
    token: str,
    *,
    limit: int = 1000,
    report: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Run one k-mer strike and return its result."""
    body = {
        "probes": [{"name": name, "sequence": sequence} for name, sequence in probes],
        "limit": limit,
    }
    with _client(base, token) as client:
        started = client.post("/scan", json=body)
        started.raise_for_status()
        job_id = started.json()["id"]
    report(f"strike job {job_id}: {len(probes)} probes, one pass over the store")
    return wait_for(job_id, base, token, report=report)


def scan_batched(
    probes: Sequence[tuple[str, str]],
    base: str,
    token: str,
    *,
    chunk: int,
    limit: int = 1000,
    report: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Run a strike in batches of ``chunk`` probes and merge the hits.

    One pass over the store costs the same for 1 probe or 500 — that is the strike's whole
    design — so batching is normally wrong. It is right when the batch size is what decides
    whether the run finishes: at ~200 probes the survivor scan repeatedly saturated the
    shared job service mid-pass, while 20, the size step-0 entry 027 measured, has never
    failed. Correctness is identical; the cost is N/chunk passes instead of one, and it is
    stated rather than hidden.
    """
    merged: list[dict[str, Any]] = []
    batches = [list(probes[start : start + chunk]) for start in range(0, len(probes), chunk)]
    report(f"{len(probes)} probes in {len(batches)} batches of up to {chunk}")
    for index, batch in enumerate(batches, start=1):
        report(f"batch {index}/{len(batches)} …")
        result = scan(batch, base, token, limit=limit, report=report)
        merged.extend(result.get("hits", []))
        report(f"  {len(result.get('hits', [])):,} hits ({result.get('seconds')}s)")
    return {"hits": merged, "batches": len(batches)}
