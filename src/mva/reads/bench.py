"""The engine bake-off: same sample, same machine, measured not argued.

Cuts one sample of N reads from the head of a real FASTQ, recompresses it so every engine
pays the same decompression bill, then runs the full conversion (parse, project, encode,
shard) per engine and reports reads/second and output size. The winner converts the
1.08-billion-read set; the numbers go in a methodology entry.

The sample is written to a scratch directory and deleted with it — read payloads are
patient data and never land in the repository.
"""

import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from . import engines
from .convert import convert_file


@dataclass(frozen=True)
class Timing:
    """One engine's result on the shared sample."""

    engine: str
    rows: int
    seconds: float
    parquet_bytes: int
    error: str = ""

    @property
    def reads_per_second(self) -> float:
        return self.rows / self.seconds if self.seconds else 0.0


def cut_sample(fastq: Path, reads: int, scratch: Path) -> Path:
    """The first ``reads`` records of ``fastq``, as a fresh gzip in ``scratch``."""
    decompressor = engines.find_decompressor()
    sample = scratch / fastq.name  # keep the name: lane/read parse must still work
    subprocess.run(
        f"{engines.shlex_quote(decompressor)} -dc {engines.shlex_quote(fastq)} "
        f"| head -n {int(reads) * 4} | gzip -1 > {engines.shlex_quote(sample)}",
        shell=True, check=True)
    return sample


def race(fastq: Path, reads: int = 1_000_000,
         contenders: tuple[str, ...] = ("pipe", "biobear"),
         report=print) -> list[Timing]:
    """Run every available engine over the same sample; never fake a missing one."""
    scratch = Path(tempfile.mkdtemp(prefix="mva-bench-"))
    timings: list[Timing] = []
    try:
        report(f"cutting {reads:,}-read sample from {fastq.name} …")
        sample = cut_sample(fastq, reads, scratch)
        for engine in contenders:
            if engine == "biobear" and not engines.biobear_available():
                timings.append(Timing(engine, 0, 0.0, 0, error="not installed"))
                report(f"  {engine}: not installed, skipped")
                continue
            out = scratch / f"out-{engine}"
            started = time.perf_counter()
            try:
                done = convert_file(sample, out, engine=engine)
            except Exception as error:  # a losing engine is a result, not a crash
                timings.append(Timing(engine, 0, time.perf_counter() - started, 0,
                                      error=str(error)))
                report(f"  {engine}: FAILED — {error}")
                continue
            timings.append(Timing(engine, done.rows, done.seconds, done.parquet_bytes))
            report(f"  {engine}: {done.rows:,} reads in {done.seconds:.1f}s "
                   f"= {done.reads_per_second:,.0f} reads/s, "
                   f"{done.parquet_bytes / 2**20:.1f} MiB parquet")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return timings


def winner(timings: list[Timing]) -> Timing:
    """Fastest engine that actually finished."""
    finished = [t for t in timings if t.rows and not t.error]
    if not finished:
        raise RuntimeError("no engine completed the benchmark")
    return max(finished, key=lambda t: t.reads_per_second)
