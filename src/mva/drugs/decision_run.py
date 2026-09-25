"""One decision analysis end to end: table -> expected utility -> VOI -> sensitivity -> files.

:func:`analyse` returns a JSON-ready report; :func:`write` lays it out as the ``decision_*``
TSVs plus one ``.provenance.json`` manifest each (the shape of iteration 4's
``candidate_safety.provenance.json``) and a ``decision_summary.json`` the figure script
reads. Nothing is computed in :func:`write`; it only formats what :func:`analyse` returned.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from mva.drugs import provenance
from mva.drugs.decision_model import (
    HEURISTIC_NOTE,
    DecisionConfig,
    DecisionTable,
    EvidenceRow,
    build_table,
    state_label,
)
from mva.drugs.decision_sensitivity import flip_points, sweep, tornado
from mva.drugs.decision_voi import best_index, evpi, evppi, evsi, expected, test_likelihoods
from mva.drugs.tables import write_tsv

__all__ = ["analyse", "write"]


def _utility_rows(table: DecisionTable, eus: Sequence[float]) -> list[dict[str, Any]]:
    labels = [state_label(s) for s in table.states]
    best_per_state = [best_index([row[s] for row in table.utility]) for s in range(len(labels))]
    drugs = {drug.key: drug for drug in table.drugs}
    order = sorted(range(len(table.actions)), key=lambda i: (-eus[i], i))
    rows = []
    for rank, i in enumerate(order, start=1):
        key = table.actions[i]
        drug = drugs.get(key)
        rows.append(
            {
                "rank": rank,
                "action": key,
                "names": drug.names if drug else ("baseline",),
                "routes": drug.routes if drug else (),
                "branches": drug.branches if drug else (),
                "n_rows": len(drug.rows) if drug else 0,
                "controls": sorted({r.control for r in drug.rows}) if drug else (),
                "safety_class": table.safety.get(key, "n/a (baseline)"),
                "expected_utility": round(eus[i], 6),
                "best_in_states": [labels[s] for s, b in enumerate(best_per_state) if b == i],
                **{f"u[{label}]": round(table.utility[i][s], 6) for s, label in enumerate(labels)},
            }
        )
    return rows


def analyse(
    config: DecisionConfig,
    rows: Sequence[EvidenceRow],
    safety: Mapping[str, str],
    *,
    tornado_metric: str | None = None,
    steps: int = 101,
) -> dict[str, Any]:
    """Everything the decision engine concludes from ``rows``, ``safety`` and ``config``."""

    def build(cfg: DecisionConfig) -> DecisionTable:
        return build_table(cfg, rows, safety)

    table = build(config)
    eus = expected(table.utility, table.probs)
    best = best_index(eus)
    labels = [state_label(s) for s in table.states]
    states = []
    for s, label in enumerate(labels):
        column = [row[s] for row in table.utility]
        i = best_index(column)
        states.append(
            {
                "state": label,
                "prior": table.probs[s],
                "best": table.actions[i],
                "utility": column[i],
            }
        )
    voi: list[dict[str, Any]] = [
        {"kind": "evpi", "target": "all variables", "value": evpi(table.utility, table.probs)}
    ]
    for var in config.variables:
        groups = [dict(state)[var.name] for state in table.states]
        voi.append(
            {
                "kind": "evppi",
                "target": var.name,
                "value": evppi(table.utility, table.probs, groups),
            }
        )
    for test in config.tests:
        gain, outcomes = evsi(table.utility, table.probs, test_likelihoods(table.states, test))
        voi.append(
            {
                "kind": "evsi",
                "target": test.name,
                "variable": test.variable,
                "sensitivity": test.sensitivity,
                "specificity": test.specificity,
                "value": gain,
                "outcomes": [
                    {
                        "result": o.result,
                        "probability": o.probability,
                        "best": table.actions[o.best],
                        "eu": o.value,
                        "posterior": dict(zip(labels, o.posterior, strict=True)),
                    }
                    for o in outcomes
                ],
            }
        )
    flips: list[dict[str, Any]] = []
    sweeps: list[dict[str, Any]] = []
    for var in config.variables:
        value = var.values[0]
        flips.extend(
            {
                "variable": var.name,
                "value": value,
                "start": seg.start,
                "end": seg.end,
                "action": seg.action,
            }
            for seg in flip_points(config, build, var.name, value)
        )
        sweeps.extend(
            {"variable": var.name, "value": value, **point}
            for point in sweep(config, build, var.name, value, steps)
        )
    metric = tornado_metric or (f"evsi:{config.tests[0].name}" if config.tests else "eu_best")
    torn = [
        {
            "param": r.param,
            "low": r.low,
            "high": r.high,
            "metric": metric,
            "metric_low": r.metric_low,
            "metric_high": r.metric_high,
            "swing": r.swing,
            "best_low": r.best_low,
            "best_high": r.best_high,
            "flips": r.flips,
        }
        for r in tornado(config, build, metric)
    ]
    return {
        "note": HEURISTIC_NOTE,
        "priors": {v.name: dict(v.prior) for v in config.variables},
        "best": {"action": table.actions[best], "expected_utility": eus[best]},
        "baseline": config.baseline_name,
        "states": states,
        "utilities": _utility_rows(table, eus),
        "voi": voi,
        "flips": flips,
        "sweep": sweeps,
        "tornado": torn,
        "excluded": [
            {"drug_name": row.drug_name, "route": row.route, "reason": why, "origin": row.origin}
            for row, why in table.excluded
        ],
        "n_rows": len(rows),
        "n_drugs": len(table.drugs),
    }


#: Output table name -> (report key, what its columns mean).
_TABLES: dict[str, tuple[str, str]] = {
    "utilities": (
        "utilities",
        (
            "one action per row, ranked by expected utility; u[<state>] "
            "is the heuristic utility in that world-state; baseline = defer"
        ),
    ),
    "states": ("states", "one world-state per row: prior weight, the best action there"),
    "voi": ("voi", "EVPI, EVPPI per variable, EVSI per named test (utility units)"),
    "flips": ("flips", "the best action on each [start, end] of one prior; ends are exact"),
    "sweep": ("sweep", "best action, EVPI and EVSI on a grid of one prior"),
    "tornado": ("tornado", "each parameter at its low/high end, the rest held"),
}


def _manifest(
    name: str, notes: str, out: Path, rows: int, meta: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "assumptions": meta["assumptions"],
        "clinical_framing": (
            "research exercise; no row advises for or against giving any drug to any patient"
        ),
        "columns": notes,
        "entry": meta["entry"],
        "generated_at": provenance.now(),
        "code_version": provenance.code_version(),
        "inputs": meta["inputs"],
        "limitations": meta["limitations"],
        "parameters": meta["parameters"],
        "rows": rows,
        "output": provenance.output(out, rows),
        "sources": meta["sources"],
        "tool": meta["tool"],
        "validation": meta["validation"],
        "wording": HEURISTIC_NOTE,
        "table": name,
    }


def _cell(value: Any) -> Any:
    """Six decimals for floats (float noise off the page), JSON for nested objects."""
    if isinstance(value, float):
        return _rounded(value)
    if isinstance(value, dict | list):
        return json.dumps(_rounded(value), sort_keys=True)
    return value


def _rounded(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 6) + 0.0
    if isinstance(value, dict):
        return {k: _rounded(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_rounded(v) for v in value]
    return value


def write(report: Mapping[str, Any], out_dir: Path, meta: Mapping[str, Any]) -> list[Path]:
    """``decision_<table>.tsv`` + ``.provenance.json`` per table, and the summary JSON."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, (key, notes) in _TABLES.items():
        records = [{k: _cell(v) for k, v in r.items()} for r in report[key]]
        columns: list[str] = list(dict.fromkeys(k for r in records for k in r))
        path = out_dir / f"decision_{name}.tsv"
        rows = write_tsv(path, columns, records)
        manifest = _manifest(name, notes, path, rows, meta)
        written += [path, provenance.write(manifest, path.with_suffix(".provenance.json"))]
    summary = out_dir / "decision_summary.json"
    summary.write_text(json.dumps(_rounded({**report, "meta": dict(meta)}), indent=2) + "\n")
    return [*written, summary]
