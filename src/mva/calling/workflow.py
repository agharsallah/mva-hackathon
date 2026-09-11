"""The whole read-to-allele chain as one function, so the order cannot drift.

Six stages have to happen in one order and each depends on the last: align, index, measure
depth, call twice, normalise both, phase. Written out in a script that order is a comment;
written here it is the control flow, and the manifest each stage produced is collected into
one place a report can read.

**Every stage is optional and every stage is recorded.** A run without a phaser installed
should produce alignments, coverage and calls, and *say* that phasing did not run — not
fail at the end and leave five hours of work unattributed. So each stage records its
outcome, and a missing tool is a note rather than an exception.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar

from . import align as align_module
from . import coverage as coverage_module
from . import phase as phase_module
from . import smallvars, sv
from .tools import ToolMissingError

T = TypeVar("T")


@dataclass
class Stage:
    """One stage's outcome — ran, skipped, or failed, and why."""

    name: str
    status: str
    seconds: float = 0.0
    detail: dict[str, object] = field(default_factory=dict)
    note: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "ran"


@dataclass
class Workflow:
    """Everything the chain produced, and the record of how far it got."""

    out_dir: Path
    stages: list[Stage] = field(default_factory=list)
    alignment: align_module.Alignment | None = None
    depth: coverage_module.Coverage | None = None
    callsets: dict[str, smallvars.Callset] = field(default_factory=dict)
    sv_callsets: dict[str, sv.SvCallset] = field(default_factory=dict)
    phasing: phase_module.Phasing | None = None

    def record(self, stage: Stage) -> Stage:
        self.stages.append(stage)
        return stage

    def summary(self) -> dict[str, object]:
        return {
            "stages": [
                {
                    "name": stage.name,
                    "status": stage.status,
                    "seconds": round(stage.seconds, 1),
                    "note": stage.note,
                    **stage.detail,
                }
                for stage in self.stages
            ],
            "alignment": (
                {
                    "bam": str(self.alignment.bam),
                    "reads": self.alignment.reads,
                    "mapped": self.alignment.mapped,
                    "mapped_fraction": round(self.alignment.mapped_fraction, 6),
                    "properly_paired": self.alignment.properly_paired,
                    "duplicates": self.alignment.duplicates,
                }
                if self.alignment
                else None
            ),
            "coverage": (coverage_module.summarise(self.depth) if self.depth else None),
            "callsets": {
                name: {"vcf": str(call.vcf), "records": call.records}
                for name, call in self.callsets.items()
            },
            "sv_callsets": {
                name: {
                    "vcf": str(call.vcf),
                    "records": call.records,
                    "method_class": call.method_class,
                }
                for name, call in self.sv_callsets.items()
            },
            "phase_blocks": len(self.phasing.blocks) if self.phasing else None,
        }

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.summary(), indent=2, sort_keys=True), encoding="utf-8")
        return path


def _timed(
    workflow: Workflow,
    name: str,
    action: Callable[[], T],
    *,
    detail: Callable[[T], dict[str, object]] | None = None,
) -> T | None:
    """Run one stage, record it, and turn a missing tool into a note rather than a stop."""
    import time

    started = time.perf_counter()
    try:
        result = action()
    except ToolMissingError as missing:
        workflow.record(Stage(name=name, status="skipped", note=str(missing)))
        return None
    except RuntimeError as failure:
        workflow.record(
            Stage(
                name=name,
                status="failed",
                seconds=time.perf_counter() - started,
                note=str(failure).splitlines()[0],
            )
        )
        return None
    workflow.record(
        Stage(
            name=name,
            status="ran",
            seconds=time.perf_counter() - started,
            detail=detail(result) if detail else {},
        )
    )
    return result


def run_all(
    reference: Path,
    r1: Path,
    r2: Path,
    regions: Path,
    out_dir: Path,
    *,
    stem: str = "baited",
    threads: int = 4,
    depth_floor: float = 10.0,
    with_sv: bool = True,
    with_phase: bool = True,
) -> Workflow:
    """Align the recovered reads and take them to normalised, phased calls.

    ``regions`` is the BED of baited intervals: the aligner sees the whole genome so a
    read that belongs elsewhere goes elsewhere, and then every measurement and every
    caller is restricted to where the bait actually was.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    workflow = Workflow(out_dir=out_dir)

    workflow.alignment = _timed(
        workflow,
        "align",
        lambda: align_module.align(reference, r1, r2, out_dir, threads=threads, stem=stem),
        detail=lambda result: {
            "reads": result.reads,
            "mapped_fraction": round(result.mapped_fraction, 6),
            "duplicates": result.duplicates,
        },
    )
    if workflow.alignment is None:
        return workflow
    bam = workflow.alignment.bam

    workflow.depth = _timed(
        workflow,
        "coverage",
        lambda: coverage_module.per_region(bam, regions, out_dir, stem=stem, threads=threads),
        detail=lambda result: {
            "regions": len(result.regions),
            "below_floor": len(result.below(depth_floor)),
        },
    )

    callers: tuple[tuple[str, Callable[[], smallvars.Callset]], ...] = (
        ("freebayes", lambda: smallvars.freebayes(reference, bam, regions, out_dir, stem=stem)),
        ("bcftools", lambda: smallvars.bcftools(reference, bam, regions, out_dir, stem=stem)),
    )
    for name, call_small in callers:
        raw = _timed(
            workflow,
            f"call:{name}",
            call_small,
            detail=lambda result: {"records": result.records},
        )
        if raw is None:
            continue
        called_raw = raw

        def _normalise(source: smallvars.Callset = called_raw) -> smallvars.Callset:
            return smallvars.normalise(reference, source, out_dir)

        normalised = _timed(
            workflow,
            f"normalise:{name}",
            _normalise,
            detail=lambda result: {"records": result.records},
        )
        workflow.callsets[name] = normalised or raw

    if with_sv:
        sv_callers: tuple[tuple[str, Callable[[], sv.SvCallset]], ...] = (
            ("delly", lambda: sv.delly(reference, bam, out_dir, stem=stem)),
            ("dysgu", lambda: sv.dysgu(reference, bam, out_dir, stem=stem, threads=threads)),
        )
        for name, call_sv in sv_callers:
            called = _timed(
                workflow,
                f"sv:{name}",
                call_sv,
                detail=lambda result: {
                    "records": result.records,
                    "method_class": result.method_class,
                },
            )
            if called is not None:
                workflow.sv_callsets[name] = called

    if with_phase and workflow.callsets:
        source = workflow.callsets.get("freebayes") or next(iter(workflow.callsets.values()))
        workflow.phasing = _timed(
            workflow,
            "phase",
            lambda: phase_module.whatshap(reference, bam, source.vcf, out_dir, stem=stem),
            detail=lambda result: {"blocks": len(result.blocks)},
        )

    return workflow
