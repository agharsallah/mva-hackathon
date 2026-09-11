"""What each API verb actually executes, inside a job's worker thread.

Every runner follows the same contract: build its own DuckDB connection (they are not
shared across threads), hand ``connection.interrupt`` to the job so cancel is real,
do exactly what the CLI verb does, and return a JSON-safe dict. The CLI prints; these
return — the measuring code underneath (:mod:`..scan`, :mod:`..verify`,
:mod:`..store`, :mod:`..bench`) is the same.
"""

import time
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from ...warehouse.settings import object_store, setting
from .. import access, baitjob, bench, scan, store, triage, verify
from .jobs import Job


def _named(probes) -> tuple[list[str], list[str]]:
    names = [probe.name or f"kmer{index}" for index, probe in enumerate(probes, start=1)]
    return names, [probe.sequence for probe in probes]


def _open(job: Job, root: str | None):
    """Resolve the root and open an interruptible connection for this job."""
    resolved = access.resolve_root(root)
    connection = access.connection(resolved)
    job.attach_interrupt(connection.interrupt)
    return resolved, connection


def scan_runner(request) -> Callable[[Job], dict]:
    def run(job: Job) -> dict:
        root, connection = _open(job, request.root)
        names, probes = _named(request.probes)
        started = time.perf_counter()
        hits = scan.kmers(connection, root, probes, limit=request.limit, names=names)
        return {
            "root": root,
            "probes": len(probes),
            "seconds": round(time.perf_counter() - started, 1),
            "hits": [asdict(hit) for hit in hits],
        }

    return run


def count_runner(request) -> Callable[[Job], dict]:
    def run(job: Job) -> dict:
        root, connection = _open(job, request.root)
        names, probes = _named(request.probes)
        started = time.perf_counter()
        found = {row[0]: row for row in scan.counts(connection, root, probes, names=names)}
        counts = []
        for name in names:
            _, forward, reverse, total, lanes = found.get(name, (name, 0, 0, 0, 0))
            counts.append(
                {
                    "probe": name,
                    "forward": forward,
                    "reverse": reverse,
                    "total": total,
                    "lanes": lanes,
                    "verdict": triage.verdict(total, lanes),
                }
            )
        return {
            "root": root,
            "seconds": round(time.perf_counter() - started, 1),
            "expected": triage.EXPECTED_HINT,
            "counts": counts,
        }

    return run


def bait_runner(request) -> Callable[[Job], dict]:
    """Sweep the store against a whole baited region and publish what it recovered.

    Unlike every other verb here this one *writes* — one Parquet object at the key the
    caller named — because its result is ~15 million reads and an HTTP response is not the
    place for them. It is still read-only with respect to the store itself: nothing under
    ``reads/`` is touched.

    The bait is fetched from the object store rather than posted, so the request stays a
    few hundred bytes for a 40-million-k-mer bait. There is no interrupt to attach: the
    pass is NumPy over Arrow batches, not one long DuckDB statement, so cancelling means
    letting the current shard finish.
    """

    def run(job: Job) -> dict:
        root = access.resolve_root(request.root)
        staging = Path(setting("MVA_STAGING_DIR") or ".").expanduser() / "bait"
        bait = baitjob.fetch_bait(
            request.bait_key, staging / Path(request.bait_key).name, k=request.k
        )
        _, result = baitjob.run_bait(
            root,
            bait,
            stride=request.stride,
            out_key=request.out_key,
            shard_limit=request.shard_limit,
            collect_mates=request.collect_mates,
            staging=staging,
        )
        return {"root": root, "bait_key": request.bait_key, **result.as_dict()}

    return run


def qc_runner(root_override: str | None) -> Callable[[Job], dict]:
    def run(job: Job) -> dict:
        root, connection = _open(job, root_override)
        rows = scan.qc(connection, root)
        return {
            "root": root,
            "lanes": [
                {
                    "lane": lane,
                    "read": read,
                    "reads": reads,
                    "filtered_pct": filtered,
                    "below_q37_pct": below,
                }
                for lane, read, reads, filtered, below in rows
            ],
        }

    return run


def sql_runner(request) -> Callable[[Job], dict]:
    def run(job: Job) -> dict:
        root, connection = _open(job, request.root)
        started = time.perf_counter()
        # The cap is pushed into the engine: fetching everything and truncating in
        # Python would materialise an unbounded result to throw most of it away.
        # One extra row is asked for so "truncated" is a fact, not a guess.
        capped = f"SELECT * FROM ({request.query}) LIMIT {int(request.limit) + 1}"
        rows = scan.sql(connection, root, capped)
        columns = [name for name, *_ in connection.description or []]
        return {
            "root": root,
            "seconds": round(time.perf_counter() - started, 1),
            "columns": columns,
            "row_count": min(len(rows), request.limit),
            "truncated": len(rows) > request.limit,
            "rows": [list(row) for row in rows[: request.limit]],
        }

    return run


def status_runner(root_override: str | None) -> Callable[[Job], dict]:
    def run(job: Job) -> dict:
        root, connection = _open(job, root_override)
        rows = connection.execute(f"""
            SELECT lane, read_num, count(*) AS shards, sum(rows) AS reads,
                   round(sum(bytes) / 2.0**30, 2) AS gib
            FROM '{root}/manifest.parquet' GROUP BY lane, read_num
            ORDER BY lane, read_num""").fetchall()
        partitions = [
            {"lane": lane, "read": read, "shards": shards, "reads": reads, "gib": gib}
            for lane, read, shards, reads, gib in rows
        ]
        return {
            "root": root,
            "partitions": partitions,
            "total_reads": sum(p["reads"] for p in partitions),
            "total_shards": sum(p["shards"] for p in partitions),
        }

    return run


def verify_runner(request) -> Callable[[Job], dict]:
    def run(job: Job) -> dict:
        root, connection = _open(job, request.root)
        sources = (
            [] if request.shallow else store.discover(request.source or setting("MVA_SOURCE_DIR"))
        )
        report = verify.run(
            root,
            sources,
            expected_total=request.expected_total,
            deep=not request.shallow,
            connection=connection,
        )
        return {
            "root": root,
            "ok": report.ok,
            "shards": report.shards,
            "total_rows": report.total_rows,
            "notes": report.notes,
            "failures": report.failures,
        }

    return run


def bench_runner(request) -> Callable[[Job], dict]:
    def run(job: Job) -> dict:
        fastqs = store.discover(request.source or setting("MVA_SOURCE_DIR"))
        timings = bench.race(
            fastqs[0],
            reads=request.reads,
            contenders=tuple(request.engines),
            jobs=request.jobs,
            memory_limit=request.memory_limit,
        )
        completed = [timing for timing in timings if timing.ok]
        best = bench.winner(completed) if completed else None
        return {
            "reads": request.reads,
            "timings": [asdict(timing) for timing in timings],
            "winner": best.engine if best else None,
        }

    return run


def convert_runner(request) -> Callable[[Job], dict]:
    def run(job: Job) -> dict:
        fastqs = store.discover(request.source or setting("MVA_SOURCE_DIR"))
        staging = Path(request.staging or setting("MVA_STAGING_DIR")).expanduser()
        room = store.check_room(staging, fastqs)  # NotEnoughRoomError -> a failed job
        started = time.perf_counter()
        results = store.convert_all(
            fastqs, staging, engine=request.engine, jobs=request.jobs, threads=request.threads
        )
        runs_path, manifest_path = store.write_tables(staging, results)
        summary = {
            "engine": request.engine,
            "files": len(results),
            "disk": room,
            "rows": sum(result.rows for result in results),
            "parquet_bytes": sum(result.parquet_bytes for result in results),
            "minutes": round((time.perf_counter() - started) / 60, 1),
            "runs_table": str(runs_path),
            "manifest_table": str(manifest_path),
            "uploaded_objects": 0,
        }
        if request.upload:
            cfg = object_store()
            summary["uploaded_objects"] = store.upload(cfg, staging, results)
            summary["root"] = access.s3_root(cfg)
        return summary

    return run
