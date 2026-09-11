"""Run an external genomics tool, and record enough to believe the result later.

Every tool in this package is a black box we did not write and cannot fix: an aligner, two
variant callers, two structural-variant callers, a depth counter, a phaser. The value of
running them comes entirely from the published benchmarks attached to *specific versions*,
so a result whose version was not recorded is a result with no benchmark behind it.

So every invocation goes through :func:`run`, and every stage writes a
:class:`Provenance` manifest beside its output: the exact argv, the tool's own version
string as it reported it, the wall time, and the sha256 of every input and output. That is
the difference between "we called variants with freebayes" and a claim someone else can
check.

Adapters in this package never touch the warehouse. They take paths, run a process, parse
its output into rows, and stop; putting the rows anywhere is the loader's job.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import IO


class ToolMissingError(RuntimeError):
    """A required executable is not on PATH — raised before anything is written."""


@dataclass(frozen=True)
class Invocation:
    """One process run: what was asked, what came back, how long it took."""

    tool: str
    version: str
    argv: tuple[str, ...]
    seconds: float
    returncode: int
    stderr_tail: str = ""


@dataclass
class Provenance:
    """The manifest one stage writes beside its outputs."""

    stage: str
    started_at: str
    inputs: dict[str, str] = field(default_factory=dict)
    outputs: dict[str, str] = field(default_factory=dict)
    invocations: list[Invocation] = field(default_factory=list)
    parameters: dict[str, object] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "stage": self.stage,
            "started_at": self.started_at,
            "finished_at": datetime.now(UTC).isoformat(),
            "inputs": self.inputs,
            "outputs": self.outputs,
            "parameters": self.parameters,
            "invocations": [asdict(item) for item in self.invocations],
            "notes": self.notes,
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path


def sha256(path: Path, *, limit: int | None = None) -> str:
    """Digest of a file. ``limit`` caps the bytes read — a 3 GB BAM does not need all of
    them to catch the mistakes a digest is here to catch, and says so in the manifest."""
    digest = hashlib.sha256()
    read = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 22), b""):
            digest.update(chunk)
            read += len(chunk)
            if limit is not None and read >= limit:
                return f"{digest.hexdigest()}:first{limit}"
    return digest.hexdigest()


def require(*executables: str) -> None:
    """Fail before doing any work if a tool is missing, naming all of them at once."""
    missing = [name for name in executables if shutil.which(name) is None]
    if missing:
        raise ToolMissingError(
            f"not on PATH: {', '.join(missing)} — install them before running this stage"
        )


def version_of(executable: str, *args: str) -> str:
    """Whatever the tool prints when asked, first line, verbatim.

    Deliberately not parsed into a structured version: the string a tool prints about
    itself is the thing a reader can compare against a paper, and normalising it would
    lose exactly the build and revision detail that distinguishes two releases.
    """
    for probe in args or ("--version",):
        try:
            result = subprocess.run(
                [executable, probe], capture_output=True, text=True, check=False, timeout=60
            )
        except (OSError, subprocess.TimeoutExpired):  # pragma: no cover - environment
            continue
        text = (result.stdout or result.stderr).strip()
        if text:
            return text.splitlines()[0].strip()
    return "unknown"


def run(
    argv: list[str],
    *,
    tool: str | None = None,
    version: str | None = None,
    stdout: Path | None = None,
    check: bool = True,
) -> Invocation:
    """Run one process, timed, with its stderr tail kept.

    ``stdout`` redirects to a file rather than through a pipe, because several of these
    tools emit gigabytes there and a pipe would hold it in memory.
    """
    name = tool or argv[0]
    require(name)
    started = time.perf_counter()
    if stdout is not None:
        stdout.parent.mkdir(parents=True, exist_ok=True)
        with stdout.open("wb") as sink:
            raw = subprocess.run(argv, stdout=sink, stderr=subprocess.PIPE, check=False)
        returncode, err = raw.returncode, raw.stderr.decode("utf-8", errors="replace")
    else:
        completed = subprocess.run(argv, capture_output=True, text=True, check=False)
        returncode, err = completed.returncode, completed.stderr
    seconds = time.perf_counter() - started
    invocation = Invocation(
        tool=name,
        version=version or version_of(name),
        argv=tuple(argv),
        seconds=round(seconds, 2),
        returncode=returncode,
        stderr_tail="\n".join(err.strip().splitlines()[-5:]),
    )
    if check and returncode != 0:
        raise RuntimeError(
            f"{name} exited {returncode}\n  argv: {' '.join(argv)}\n"
            f"  stderr: {invocation.stderr_tail}"
        )
    return invocation


def capture(argv: list[str], *, check: bool = True) -> str:
    """Run a process for its stdout — for the small, structured outputs (`flagstat -O json`,
    `samtools idxstats`) whose whole purpose is to be parsed."""
    require(argv[0])
    result = subprocess.run(argv, capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        raise RuntimeError(
            f"{argv[0]} exited {result.returncode}\n  argv: {' '.join(argv)}\n"
            f"  stderr: {result.stderr.strip().splitlines()[-1] if result.stderr else ''}"
        )
    return result.stdout


def pipe(stages: list[list[str]], *, stdout: Path, check: bool = True) -> list[Invocation]:
    """Run processes connected by pipes, as a shell would, with each one recorded.

    Used where the tools themselves expect it — ``bcftools mpileup | bcftools call`` is
    one logical step, and materialising the pileup between them would write tens of
    gigabytes for nothing.
    """
    for stage in stages:
        require(stage[0])
    stdout.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    processes: list[subprocess.Popen[bytes]] = []
    previous: IO[bytes] | None = None
    with stdout.open("wb") as sink:
        for index, stage in enumerate(stages):
            last = index == len(stages) - 1
            process = subprocess.Popen(
                stage,
                stdin=previous,
                stdout=sink if last else subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if previous is not None:
                # The downstream process now owns the read end; closing ours is what lets
                # the upstream see EOF when it finishes.
                previous.close()
            previous = process.stdout
            processes.append(process)
        errors = [process.communicate()[1] for process in processes]
    seconds = time.perf_counter() - started
    invocations = []
    for process, stage, err in zip(processes, stages, errors, strict=True):
        text = (err or b"").decode("utf-8", errors="replace")
        invocations.append(
            Invocation(
                tool=stage[0],
                version=version_of(stage[0]),
                argv=tuple(stage),
                seconds=round(seconds, 2),
                returncode=process.returncode,
                stderr_tail="\n".join(text.strip().splitlines()[-5:]),
            )
        )
        if check and process.returncode != 0:
            raise RuntimeError(
                f"{stage[0]} exited {process.returncode} in a pipeline\n"
                f"  argv: {' '.join(stage)}\n  stderr: {invocations[-1].stderr_tail}"
            )
    return invocations


def started_now(stage: str) -> Provenance:
    return Provenance(stage=stage, started_at=datetime.now(UTC).isoformat())
