"""Run long store queries in the background and remember what they returned.

A k-mer scan walks ~46 GiB of sequence and takes minutes; an HTTP request should not.
Every expensive verb is therefore a **job**: submitted, given an id, run on a small
worker pool, and polled (or long-polled) until done. Two decisions shape the module:

**Cancellation is real, not cosmetic.** A runner hands its DuckDB connection's
``interrupt`` to the job; cancel invokes it, so a mistaken full scan stops burning the
machine instead of merely being hidden from the listing.

**Finished answers survive a restart.** Each state change writes the job as JSON into a
directory. On startup the history is reloaded; jobs that were still queued or running in
the dead process are marked ``lost`` — never silently re-run, because a convert is not
idempotent and a re-scan should be an explicit choice.
"""

import json
import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Every state a job can be in. Terminal states are the last four.
QUEUED, RUNNING = "queued", "running"
DONE, FAILED, CANCELLED, LOST = "done", "failed", "cancelled", "lost"
TERMINAL = (DONE, FAILED, CANCELLED, LOST)


@dataclass
class Job:
    """One submitted verb: its inputs, its lifecycle, and eventually its answer."""

    id: str
    verb: str
    params: dict
    state: str = QUEUED
    submitted_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    result: Any = None
    error: str | None = None
    _completed: threading.Event = field(default_factory=threading.Event, repr=False)
    _interrupt: Callable[[], None] | None = field(default=None, repr=False)
    _cancel_requested: bool = field(default=False, repr=False)

    def attach_interrupt(self, interrupt: Callable[[], None]) -> None:
        """Give cancel something to pull — typically ``connection.interrupt``.

        If cancel already arrived while the runner was setting up, fire immediately:
        the race between "cancel requested" and "connection created" must not leave a
        query running.
        """
        self._interrupt = interrupt
        if self._cancel_requested:
            interrupt()

    def snapshot(self) -> dict:
        """The job as a JSON-safe dict — the one shape the API and the disk share."""
        elapsed = (self.finished_at or time.time()) - self.started_at if self.started_at else None
        return {
            "id": self.id,
            "verb": self.verb,
            "state": self.state,
            "params": self.params,
            "submitted_at": self.submitted_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "elapsed_seconds": round(elapsed, 3) if elapsed is not None else None,
            "result": self.result,
            "error": self.error,
        }


class Manager:
    """The pool, the registry, and the on-disk history."""

    def __init__(self, directory: Path | None = None, workers: int = 2):
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="reads-api")
        self._directory = directory
        if directory is not None:
            directory.mkdir(parents=True, exist_ok=True)
            self._load_history(directory)

    def submit(self, verb: str, params: dict, runner: Callable[[Job], Any]) -> Job:
        """Register and enqueue one job; returns immediately with it still queued."""
        job = Job(id=uuid.uuid4().hex[:12], verb=verb, params=params)
        with self._lock:
            self._jobs[job.id] = job
        self._persist(job)
        self._pool.submit(self._run, job, runner)
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def jobs(self, state: str | None = None, verb: str | None = None) -> list[Job]:
        """All known jobs, newest first, optionally filtered."""
        with self._lock:
            found = list(self._jobs.values())
        found.sort(key=lambda job: job.submitted_at, reverse=True)
        return [
            job
            for job in found
            if (state is None or job.state == state) and (verb is None or job.verb == verb)
        ]

    def wait(self, job: Job, timeout: float) -> bool:
        """Block up to ``timeout`` seconds; True when the job reached a terminal state."""
        return job._completed.wait(timeout)

    def cancel(self, job: Job) -> bool:
        """Ask a queued or running job to stop. False when it already finished.

        A queued job is marked and will be dropped the moment the pool picks it up. A
        running one gets its attached interrupt pulled; the runner's exception then
        lands as ``cancelled`` rather than ``failed``.
        """
        if job.state in TERMINAL:
            return False
        job._cancel_requested = True
        if job._interrupt is not None:
            try:
                job._interrupt()
            except Exception:  # the query may have just finished — that is fine
                pass
        return True

    def forget(self, job_id: str) -> bool:
        """Drop a terminal job from the registry and the disk history."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.state not in TERMINAL:
                return False
            del self._jobs[job_id]
        if self._directory is not None:
            (self._directory / f"{job_id}.json").unlink(missing_ok=True)
        return True

    def _run(self, job: Job, runner: Callable[[Job], Any]) -> None:
        if job._cancel_requested:
            self._finish(job, CANCELLED, error="cancelled before it started")
            return
        job.state, job.started_at = RUNNING, time.time()
        self._persist(job)
        try:
            result = runner(job)
        except Exception as error:
            state = CANCELLED if job._cancel_requested else FAILED
            self._finish(job, state, error=f"{type(error).__name__}: {error}")
        else:
            self._finish(job, DONE, result=result)

    def _finish(self, job: Job, state: str, result: Any = None, error: str | None = None) -> None:
        job.state, job.result, job.error = state, result, error
        job.finished_at = time.time()
        self._persist(job)
        job._completed.set()

    def _persist(self, job: Job) -> None:
        if self._directory is None:
            return
        path = self._directory / f"{job.id}.json"
        try:
            path.write_text(json.dumps(job.snapshot(), default=str), encoding="utf-8")
        except OSError:  # a full disk must not take the query down with it
            pass

    def _load_history(self, directory: Path) -> None:
        for path in sorted(directory.glob("*.json")):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
                job = Job(
                    id=record["id"],
                    verb=record["verb"],
                    params=record.get("params") or {},
                    state=record.get("state", LOST),
                    submitted_at=record.get("submitted_at") or 0.0,
                    started_at=record.get("started_at"),
                    finished_at=record.get("finished_at"),
                    result=record.get("result"),
                    error=record.get("error"),
                )
            except (json.JSONDecodeError, KeyError, TypeError):
                continue  # a truncated record is history we can live without
            if job.state not in TERMINAL:
                job.state = LOST
                job.error = "the API restarted while this job was in flight"
                self._persist(job)
            job._completed.set()
            self._jobs[job.id] = job
