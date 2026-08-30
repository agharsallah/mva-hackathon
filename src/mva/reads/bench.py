"""The engine bake-off: same sample, same machine, measured not argued.

Cuts one sample of N reads from the head of a real FASTQ, recompresses it so every engine
pays the same decompression bill, then runs the full conversion (parse, project, encode,
shard) per engine and reports reads/second, output size, and peak memory.

**Peak memory is not a footnote here.** An engine that materialises the file instead of
streaming it looks fast on a one-million-read sample and dies on an eleven-gigabyte one,
so the bake-off is meant to be run at two sample sizes: memory that grows with the sample
means the engine buffers, and it is disqualified for the full set no matter how fast it
looked. :func:`streams` does that comparison.

The sample is written to a scratch directory and deleted with it — read payloads are
patient data and never land in the repository.
"""

import multiprocessing
import resource
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from . import engines, schema
from .convert import as_source, convert_file


def peak_rss_bytes() -> int:
    """Peak resident memory of this process, in bytes.

    ``ru_maxrss`` is kilobytes on Linux and bytes on macOS — normalise so the number
    means the same thing in a methodology entry written on either. It is a high-water
    mark that never falls, which is why each engine is measured in its own process:
    inside one process the second engine measured would inherit the first one's peak.
    """
    scale = 1 if sys.platform == "darwin" else 1024
    return scale * resource.getrusage(resource.RUSAGE_SELF).ru_maxrss


@dataclass(frozen=True)
class Timing:
    """One engine's result on the shared sample."""

    engine: str
    reads: int
    rows: int
    seconds: float
    parquet_bytes: int
    peak_rss: int = 0
    error: str = ""

    @property
    def reads_per_second(self) -> float:
        return self.rows / self.seconds if self.seconds else 0.0

    @property
    def ok(self) -> bool:
        return bool(self.rows) and not self.error


def cut_sample(fastq, reads: int, scratch: Path) -> Path:
    """The first ``reads`` records of ``fastq``, as a fresh gzip in ``scratch``.

    Written to disk on purpose: every engine must race the same bytes, and one of them
    can only read a path. A remote object is streamed through the same pipeline.
    """
    source = as_source(fastq)
    decompressor = engines.find_decompressor()
    scratch.mkdir(parents=True, exist_ok=True)
    sample = scratch / source.name  # keep the name: lane/read parse must still work
    local = "" if source.path is None else f" {engines.shlex_quote(source.path)}"
    command = (f"{engines.shlex_quote(decompressor)} -dc{local} "
               f"| head -n {int(reads) * 4} | gzip -1 > {engines.shlex_quote(sample)}")
    if source.path is not None:
        subprocess.run(command, shell=True, check=True)
    else:
        process = subprocess.Popen(command, shell=True, stdin=subprocess.PIPE)
        with source.open_stream() as stream:
            try:
                shutil.copyfileobj(stream, process.stdin, length=8 * 1024 * 1024)
            except BrokenPipeError:
                pass  # `head` closed the pipe once it had enough — expected
            finally:
                try:
                    process.stdin.close()
                except BrokenPipeError:
                    pass
        process.wait()
    if not sample.exists() or sample.stat().st_size == 0:
        raise RuntimeError(f"could not cut a sample from {source.name}")
    return sample


def _run_one(engine: str, sample: str, out_dir: str, memory_limit: str, queue) -> None:
    """One engine's conversion, in a process of its own so its memory is its own."""
    baseline = peak_rss_bytes()
    started = time.perf_counter()
    try:
        done = convert_file(Path(sample), Path(out_dir), engine=engine,
                            memory_limit=memory_limit)
        queue.put(Timing(engine, 0, done.rows, done.seconds, done.parquet_bytes,
                         peak_rss=max(0, peak_rss_bytes() - baseline)))
    except Exception as error:  # a losing engine is a result, not a crash
        queue.put(Timing(engine, 0, 0, time.perf_counter() - started, 0,
                         error=f"{type(error).__name__}: {error}"))


def race(fastq, reads: int = 1_000_000,
         contenders: tuple[str, ...] = (),
         jobs: int = 1, memory_limit: str | None = None,
         report=print) -> list[Timing]:
    """Run every available engine over the same sample; never fake a missing one.

    Each engine runs in a fresh spawned process: peak memory is then attributable to
    that engine alone, and a segfaulting reader cannot take the benchmark down with it.

    **The memory limit is part of the measurement.** Left unset, DuckDB claims most of
    the machine for its buffer pool, so peak memory reflects what was available rather
    than what is needed, and an engine can look like it hoards when it is only being
    allowed to. The default is the share one job would get in a real ``jobs``-way run
    (:func:`mva.reads.store.machine_share`), so a bench result predicts the conversion.
    """
    from .store import machine_share

    contenders = contenders or tuple(engines.ENGINES)
    memory_limit = memory_limit or machine_share(jobs)[1]
    report(f"budget per engine: {memory_limit} DuckDB memory "
           f"(the share of a {jobs}-job run)")
    context = multiprocessing.get_context("spawn")
    scratch = Path(tempfile.mkdtemp(prefix="mva-bench-"))
    timings: list[Timing] = []
    if reads < schema.ROW_GROUP_SIZE:
        report(f"note: {reads:,} reads is under one {schema.ROW_GROUP_SIZE:,}-row "
               f"row group — timings are valid, memory comparisons are not")
    try:
        report(f"cutting {reads:,}-read sample from {as_source(fastq).name} …")
        sample = cut_sample(fastq, reads, scratch)
        for engine in contenders:
            if not engines.available(engine):
                timings.append(Timing(engine, reads, 0, 0.0, 0, error="not installed"))
                report(f"  {engine}: not installed, skipped")
                continue
            queue = context.Queue()
            worker = context.Process(target=_run_one, args=(
                engine, str(sample), str(scratch / f"out-{engine}"), memory_limit, queue))
            worker.start()
            worker.join()
            result = queue.get() if not queue.empty() else Timing(
                engine, reads, 0, 0.0, 0,
                error=f"worker died with exit code {worker.exitcode}")
            timing = Timing(engine, reads, result.rows, result.seconds,
                            result.parquet_bytes, result.peak_rss, result.error)
            timings.append(timing)
            if timing.ok:
                report(f"  {engine}: {timing.rows:,} reads in {timing.seconds:.1f}s "
                       f"= {timing.reads_per_second:,.0f} reads/s, "
                       f"{timing.parquet_bytes / 2**20:.1f} MiB parquet, "
                       f"{timing.peak_rss / 2**20:.0f} MiB peak RSS")
            else:
                report(f"  {engine}: FAILED — {timing.error}")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return timings


def streams(small: Timing, large: Timing, tolerance: float = 0.5) -> bool:
    """Did memory stay flat while the sample grew? ``False`` means it buffers.

    A streaming engine holds a bounded number of batches, so memory barely moves; a
    buffering one grows with the input. ``tolerance`` is the share of proportional growth
    allowed before the engine is called a buffer.

    **Both samples must exceed one Parquet row group** (:data:`~mva.reads.schema.
    ROW_GROUP_SIZE`), or this measures the wrong thing: DuckDB accumulates a full row
    group before flushing it, so below that size memory grows with the sample for every
    engine — that growth is the writer filling its buffer, not the reader hoarding the
    file. :func:`race` warns when a sample is too small for the comparison to mean
    anything.

    Read the verdict together with the memory limit :func:`race` reports. An engine that
    *fails* under the budget says so as an error; this only compares the survivors, and
    what it answers is "does the need grow with the input", not "did it fit this time".
    """
    if not (small.ok and large.ok and small.peak_rss):
        return False
    growth = large.peak_rss / small.peak_rss
    proportional = large.rows / small.rows
    return growth < 1 + tolerance * (proportional - 1)


def winner(timings: list[Timing]) -> Timing:
    """Fastest engine that actually finished."""
    finished = [timing for timing in timings if timing.ok]
    if not finished:
        raise RuntimeError("no engine completed the benchmark")
    return max(finished, key=lambda timing: timing.reads_per_second)
