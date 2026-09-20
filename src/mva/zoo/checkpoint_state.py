"""What each workflow stage contributes to the run state, and how to put it back.

Split out of :mod:`mva.zoo.checkpoint` — that module is the marker's storage (digests, files,
lifetime), this one is the *content*: one ``capture`` and one ``restore`` per stage. The two
concerns change for different reasons, and together they were over the module-size limit.

A capture is JSON-able and complete: a restored state must let every later stage run exactly
as it would have. A restore returns ``False`` rather than raising when it cannot rebuild what
it was handed — a marker written by an older build, a lane file deleted by hand — and the
runner then simply runs the stage.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from .checkpoint import digest_of, directory, read_json
from .workflow_types import Config, RunState

__all__ = ["capture", "restore"]


def capture(config: Config, stage: str, state: RunState) -> dict[str, Any]:
    """The JSON-able slice of ``state`` that ``stage`` produced."""
    return _CAPTURE[stage](config, state)


def restore(config: Config, stage: str, state: RunState, payload: dict[str, Any]) -> bool:
    """Put a marker's slice back into ``state``. ``False`` when it cannot be — then re-run."""
    try:
        return _RESTORE[stage](config, state, payload)
    except (KeyError, TypeError, ValueError):
        return False


def _capture_normalize(_config: Config, state: RunState) -> dict[str, Any]:
    return {"records": [_as_json(record) for record in state.records]}


def _restore_normalize(_config: Config, state: RunState, payload: dict[str, Any]) -> bool:
    records = payload.get("records")
    if not isinstance(records, list):
        return False
    # Restored as plain dicts rather than `AlleleRecord`s on purpose: every downstream
    # reader goes through `workflow_stages._field` / `workflow_types.consequence_map`,
    # which accept a Mapping and an object alike, and a dict is what survives JSON.
    state.records = list(records)
    return True


def _capture_registry(_config: Config, state: RunState) -> dict[str, Any]:
    return {"cards": state.cards}


def _restore_registry(_config: Config, state: RunState, payload: dict[str, Any]) -> bool:
    cards = payload.get("cards")
    if not isinstance(cards, dict):
        return False
    state.cards = dict(cards)
    return True


def _capture_fan_out(_config: Config, state: RunState) -> dict[str, Any]:
    """Only each lane's digest: the scores themselves live in the per-model markers."""
    return {
        "models": {
            model: {
                "version": str(state.cards.get(model, {}).get("version", "")),
                "venue": state.venues.get(model, ""),
                "digest": digest_of(state.scores.get(model, {})),
            }
            for model in sorted(state.scores)
        }
    }


def _restore_fan_out(config: Config, state: RunState, payload: dict[str, Any]) -> bool:
    lanes = payload.get("models")
    if not isinstance(lanes, dict):
        return False
    for model, meta in lanes.items():
        stored = read_json(directory(config) / "fan_out" / f"{model}.json")
        if stored is None:
            return False  # the lane file was deleted; the stage has to run again
        scores = {str(key): float(value) for key, value in (stored.get("scores") or {}).items()}
        if digest_of(scores) != meta.get("digest"):
            return False  # the lane file no longer matches what the stage recorded
        state.scores[model] = scores
        state.venues[model] = str(meta.get("venue", "") or stored.get("venue", ""))
    return True


def _capture_collect(_config: Config, state: RunState) -> dict[str, Any]:
    return {"coverage": state.coverage}


def _restore_collect(_config: Config, state: RunState, payload: dict[str, Any]) -> bool:
    coverage = payload.get("coverage")
    if not isinstance(coverage, dict):
        return False
    state.coverage = dict(coverage)
    return True


def _capture_rank(_config: Config, state: RunState) -> dict[str, Any]:
    return {
        "pairs": [asdict(pair) for pair in state.pairs],
        "pair_build": dict(state.pair_build),
    }


def _restore_rank(_config: Config, state: RunState, payload: dict[str, Any]) -> bool:
    from . import rank as rank_module
    from .pairs import Pair

    rows = payload.get("pairs")
    if not isinstance(rows, list):
        return False
    state.pairs = [Pair(**row) for row in rows]
    state.pair_build = dict(payload.get("pair_build") or {})
    # The ranking itself is pure arithmetic over the pairs and the restored scores, so it is
    # re-derived rather than stored: a `ModelRank` is a nested dataclass tree and a JSON copy
    # of it would be a second spelling of the same numbers, free to drift.
    state.ranks = rank_module.rank_per_model(state.pairs, state.scores)
    return True


def _capture_reports(_config: Config, state: RunState) -> dict[str, Any]:
    return {"reports": state.reports}


def _restore_reports(_config: Config, state: RunState, payload: dict[str, Any]) -> bool:
    reports = payload.get("reports")
    if not isinstance(reports, list):
        return False
    state.reports = list(reports)
    return True


def _capture_merge(_config: Config, state: RunState) -> dict[str, Any]:
    return {"merged": state.merged}


def _restore_merge(_config: Config, state: RunState, payload: dict[str, Any]) -> bool:
    merged = payload.get("merged")
    if not isinstance(merged, dict):
        return False
    state.merged = dict(merged)
    return True


def _capture_render(config: Config, state: RunState) -> dict[str, Any]:
    return {"merged_report": str(config.merged_path), "method": state.method}


def _restore_render(config: Config, state: RunState, payload: dict[str, Any]) -> bool:
    """The render stage owns a file — but also the one fact the manifest reads back from it.

    ``method`` is what the *page* realised (``fusion+synthesis`` only when a synthesised
    section 5 is on it). A restored render must put it back, or a resumed run's manifest would
    quietly fall back to the configured method and claim a synthesis it never wrote.
    """
    if not Path(config.merged_path).is_file():
        return False
    state.method = str(payload.get("method") or "")
    return True


_CAPTURE: dict[str, Callable[[Config, RunState], dict[str, Any]]] = {
    "normalize": _capture_normalize,
    "registry_check": _capture_registry,
    "fan_out": _capture_fan_out,
    "collect": _capture_collect,
    "rank_per_model": _capture_rank,
    "report_per_model": _capture_reports,
    "merge": _capture_merge,
    "render": _capture_render,
}

_RESTORE: dict[str, Callable[[Config, RunState, dict[str, Any]], bool]] = {
    "normalize": _restore_normalize,
    "registry_check": _restore_registry,
    "fan_out": _restore_fan_out,
    "collect": _restore_collect,
    "rank_per_model": _restore_rank,
    "report_per_model": _restore_reports,
    "merge": _restore_merge,
    "render": _restore_render,
}


def _as_json(record: Any) -> Any:
    if is_dataclass(record) and not isinstance(record, type):
        return asdict(record)
    if isinstance(record, Mapping):
        return dict(record)
    return record
