"""The declared plan of a screen-wide sweep, and the input check that runs before it.

A :class:`SweepPlan` is every choice :func:`mva.drugs.screen_sweep_run.execute` makes, as
data, so the provenance manifest can record all of them and another lineage, annotation or
screen is a different configuration rather than a different script.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from mva.drugs import provenance
from mva.drugs.screen_replication_plan import SourceFile

__all__ = ["SweepPlan", "verify_inputs"]


@dataclass(frozen=True)
class SweepPlan:
    """Every choice the sweep makes, so the manifest can record all of them."""

    reused: tuple[SourceFile, ...]
    reused_dir: Path
    reused_manifest: Path
    """The manifest whose sha256 values the reused files must match (entry 151's)."""
    own: tuple[SourceFile, ...]
    own_dir: Path
    build_dir: Path
    out: Path
    generator_dir: Path
    generator: str
    entry: str
    in_group_codes: tuple[str, ...]
    annotation_column: str
    min_in_group: int
    min_arm: int
    alpha: float
    top_fraction: float
    hints: dict[str, str]
    control_exclude: tuple[str, ...]
    positive_control_drugs: tuple[str, ...]
    positive_control_lineage: str
    report_drugs: tuple[str, ...]
    """Named only to be *reported* (a retrospective fact); no rule reads this field."""
    seed: int = 20260924
    resamples: int = 2000
    negative_control_size: int = 200
    workers: int | None = None
    patient_data: str = "none; public data only"
    software: dict[str, str] = field(default_factory=dict)

    def path(self, role: str) -> Path:
        for source in self.own:
            if source.role == role:
                return self.own_dir / source.name
        return self.reused_dir / next(s.name for s in self.reused if s.role == role)


def verify_inputs(plan: SweepPlan) -> list[dict[str, Any]]:
    """Digest every input; refuse to run if a reused file differs from the fetching entry."""
    known = {i["name"]: i for i in json.loads(plan.reused_manifest.read_text())["inputs"]}
    rows = []
    for source in (*plan.reused, *plan.own):
        sha, size = provenance.digest(plan.path(source.role))
        if source in plan.reused and known[source.name]["sha256"] != sha:
            raise SystemExit(f"{source.name}: sha256 {sha[:16]} != {plan.reused_manifest}")
        rows.append({**asdict(source), "sha256": sha, "bytes": size})
    return rows
