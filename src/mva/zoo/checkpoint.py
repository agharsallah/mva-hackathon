"""Checkpoint markers: what each stage finished, from what, and how to rehydrate it.

A *checkpoint* here is one JSON file per stage under
``<out_dir>/checkpoints/<run_id>/<stage>.json``. It holds four things a resume needs and
nothing else:

``inputs_digest``
    a hash of **everything the stage consumed** — the config digest chained through every
    earlier stage's content. This is what makes the resume content-addressed rather than
    name-addressed: change the config, change a record, change a model version, and every
    marker downstream of the change stops matching and its stage re-runs. A marker whose
    name matches but whose digest does not is ignored, never trusted.
``rows`` / ``note`` / ``finished_at``
    the stage's own receipt, so ``build/<case>/checkpoints/`` reads as a log of what a
    killed run got through.
``state``
    the stage's contribution to :class:`~mva.zoo.workflow_types.RunState`, as JSON, so the
    next run can skip the stage *and still have what it produced*. Without this a "skip"
    would leave the downstream stages with nothing to read.

**The chain.** The runner keeps a rolling digest: ``chain₀ = config.digest`` and
``chainₖ₊₁ = H(chainₖ, H(stateₖ))``. Stage *k* is skipped only when its marker's
``inputs_digest`` equals ``chainₖ``. Two runs of the same configuration over the same data
therefore produce the same chain and skip everything; a run whose first stage reads one
extra record produces a different ``chain₁`` and re-runs all eight.

**Fan-out is resumable inside itself.** ``fan_out`` writes one extra marker per model under
``checkpoints/<run_id>/fan_out/<model>.json``, keyed by ``(chain, model, version)``, holding
that lane's scores. A run killed after the second of four lanes restarts having to score two.
The stage-level marker keeps only each lane's *digest*, so the scores live in exactly one
file and a changed score still moves the chain.

**What a restore is not.** Restoring is rehydration from the stage's own output, never a
recomputation of it: the point of the resume is that nothing outside the process is asked
again (no warehouse read, no registry read, no adapter, no callset scan). The one exception
is named where it happens — ``rank_per_model`` re-derives its ranking arithmetic from the
restored pairs and scores rather than storing a nested dataclass tree, which is pure
in-process arithmetic over data the checkpoint already holds.

What each stage captures and how it is rehydrated lives next door in
:mod:`mva.zoo.checkpoint_state`; this module is the marker's storage and its digests.

Written for :mod:`mva.zoo.workflow`; nothing else should need it. Claim ``P4-5``.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .workflow_types import STAGES, Config

__all__ = [
    "Marker",
    "ModelMarker",
    "advance",
    "clear",
    "digest_of",
    "directory",
    "load",
    "load_model",
    "read_json",
    "save",
    "save_model",
    "seed",
]


def directory(config: Config) -> Path:
    """Where this run's markers live. Under ``out_dir``, so never inside the git tree."""
    return Path(config.out_dir) / "checkpoints" / config.run_id


def seed(config: Config) -> str:
    """The chain's first link: the **effective** configuration, overrides included.

    Not ``config.digest`` alone. That is the hash of the TOML's bytes, and every
    command-line override (``--case-gene``, ``--iteration``) leaves it — and therefore the
    run id — untouched. Two runs of the same file with different overrides would otherwise
    share a checkpoint directory and restore each other's work.
    """
    return digest_of(
        config.digest,
        config.case_json(),
        config.mode,
        sorted(config.models),
        config.method,
        config.rrf_k,
        str(config.schema),
        str(config.warehouse_schema),
    )


def digest_of(*parts: Any) -> str:
    """A short, stable content hash of any JSON-able parts. Order matters; keys do not."""
    hasher = hashlib.sha256()
    for part in parts:
        hasher.update(json.dumps(part, sort_keys=True, default=str).encode("utf-8"))
        hasher.update(b"\x00")
    return hasher.hexdigest()[:16]


@dataclass(frozen=True)
class Marker:
    """One finished stage, on disk."""

    stage: str
    run_id: str
    inputs_digest: str
    rows: int = 0
    note: str = ""
    finished_at: str = ""
    state: dict[str, Any] = field(default_factory=dict)

    @property
    def content_digest(self) -> str:
        """The hash of what the stage produced — the link this stage adds to the chain."""
        return digest_of(self.state)

    def to_json(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "run_id": self.run_id,
            "inputs_digest": self.inputs_digest,
            "rows": self.rows,
            "note": self.note,
            "finished_at": self.finished_at,
            "state": self.state,
        }


@dataclass(frozen=True)
class ModelMarker:
    """One lane's slice of ``fan_out``: its scores, its venue, and what it was keyed by."""

    model: str
    version: str
    venue: str
    inputs_digest: str
    scores: dict[str, float] = field(default_factory=dict)
    finished_at: str = ""

    @property
    def content_digest(self) -> str:
        return digest_of(self.version, self.scores)


def load(config: Config, stage: str) -> Marker | None:
    """This run's marker for ``stage``, or ``None`` when there is none or it is unreadable."""
    payload = read_json(directory(config) / f"{stage}.json")
    if payload is None or payload.get("stage") != stage:
        return None
    return Marker(
        stage=stage,
        run_id=str(payload.get("run_id", "")),
        inputs_digest=str(payload.get("inputs_digest", "")),
        rows=int(payload.get("rows", 0) or 0),
        note=str(payload.get("note", "")),
        finished_at=str(payload.get("finished_at", "")),
        state=dict(payload.get("state") or {}),
    )


def save(
    config: Config, stage: str, *, inputs_digest: str, rows: int, note: str, state: dict[str, Any]
) -> Marker:
    """Write the marker for a stage that has just finished (after its table and lineage)."""
    marker = Marker(
        stage=stage,
        run_id=config.run_id,
        inputs_digest=inputs_digest,
        rows=rows,
        note=note,
        finished_at=datetime.now(UTC).isoformat(timespec="seconds"),
        state=state,
    )
    _write(directory(config) / f"{stage}.json", marker.to_json())
    return marker


def load_model(config: Config, model: str, inputs_digest: str) -> ModelMarker | None:
    """One lane's fan-out marker, only if it was written for exactly these inputs."""
    payload = read_json(directory(config) / "fan_out" / f"{model}.json")
    if payload is None or payload.get("inputs_digest") != inputs_digest:
        return None
    scores = payload.get("scores") or {}
    if not isinstance(scores, Mapping):
        return None
    return ModelMarker(
        model=model,
        version=str(payload.get("version", "")),
        venue=str(payload.get("venue", "")),
        inputs_digest=inputs_digest,
        scores={str(key): float(value) for key, value in scores.items()},
        finished_at=str(payload.get("finished_at", "")),
    )


def save_model(
    config: Config,
    model: str,
    *,
    version: str,
    venue: str,
    inputs_digest: str,
    scores: Mapping[str, float],
) -> ModelMarker:
    """Write one lane's fan-out marker the moment that lane comes back."""
    marker = ModelMarker(
        model=model,
        version=version,
        venue=venue,
        inputs_digest=inputs_digest,
        scores=dict(scores),
        finished_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )
    _write(
        directory(config) / "fan_out" / f"{model}.json",
        {
            "model": marker.model,
            "version": marker.version,
            "venue": marker.venue,
            "inputs_digest": marker.inputs_digest,
            "finished_at": marker.finished_at,
            "scores": marker.scores,
        },
    )
    return marker


def clear(config: Config, *, from_stage: str | None = None) -> int:
    """Delete this run's markers from ``from_stage`` on (all of them when it is ``None``).

    Returns how many files were removed, which is what ``--force`` prints.
    """
    base = directory(config)
    if not base.is_dir():
        return 0
    wanted = STAGES[STAGES.index(from_stage) :] if from_stage else STAGES
    removed = 0
    for stage in wanted:
        path = base / f"{stage}.json"
        if path.is_file():
            path.unlink()
            removed += 1
        if stage == "fan_out":
            for lane in sorted((base / "fan_out").glob("*.json")):
                lane.unlink()
                removed += 1
    return removed


def advance(chain: str, marker: Marker) -> str:
    """The next link: the chain so far plus what this stage produced."""
    return digest_of(chain, marker.content_digest)


def read_json(path: Path) -> dict[str, Any] | None:
    """A marker, or ``None`` for absent, truncated or unreadable — never an exception.

    A half-written marker from a process that was killed mid-write is exactly the case this
    module exists for, and it must read as "not done" rather than take the next run down.
    """
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _write(path: Path, payload: dict[str, Any]) -> None:
    """Write a marker atomically: a crash mid-write must not leave a half-valid marker."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
