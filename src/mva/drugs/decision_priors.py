"""Priors computed from another route's table, never typed into the config.

A state variable in the config may carry ``derive`` instead of (or beside) a typed ``prior``.
:func:`resolve` computes it, writes the value into a copy of the config, and returns a record
of the rule, the rows it read and the arithmetic, so the manifest can show how the number
was made.

One method so far, ``threshold_crossing``, over a dosage table (one row per scenario):

* the **threshold** is read from the table: the value of ``threshold.column`` in the first
  row whose ``threshold.where_column`` contains ``threshold.where_contains``;
* the **starting states** are the untreated rows (``start.drug_column == start.drug_value``,
  ``start.scenario_column`` starting with ``start.scenario_prefix``) that sit *below* it;
* the **gains** are the ``gain_column`` of every row whose scenario contains one of
  ``gains.<mode>`` (``strict``: real doses only; ``lenient``: also the stated upper bounds);
* ``P(yes)`` = share of (start, gain) pairs with ``start + gain >= threshold``, equal weights.

A string ``"derived:<variable>:<mode>"`` anywhere in ``tornado`` is replaced by that value, so
a sweep range can end at the lenient reading without the number being retyped.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from mva.drugs.decision_io import read_tsv
from mva.drugs.provenance import digest, repo_relative

__all__ = ["resolve", "threshold_crossing"]


def threshold_crossing(spec: dict[str, Any]) -> dict[str, Any]:
    """Both readings (``strict``, ``lenient``) and every input the rule used."""
    path = Path(spec["table"])
    rows = read_tsv(path)
    thr = spec["threshold"]
    anchor = next(r for r in rows if thr["where_contains"] in r[thr["where_column"]])
    threshold = float(anchor[thr["column"]])
    start = spec["start"]
    total, gain_col, scen = spec["total_column"], spec["gain_column"], start["scenario_column"]
    starts = [
        (r[scen], float(r[total]))
        for r in rows
        if r[start["drug_column"]] == start["drug_value"]
        and r[scen].startswith(start["scenario_prefix"])
        and float(r[total]) < threshold
    ]
    out: dict[str, Any] = {
        "method": "threshold_crossing",
        "table": repo_relative(path),
        "sha256": digest(path)[0],
        "threshold": threshold,
        "threshold_row": anchor[thr["where_column"]],
        "starts": dict(starts),
    }
    for mode, words in spec["gains"].items():
        gains = [(r[scen], float(r[gain_col])) for r in rows if any(w in r[scen] for w in words)]
        pairs = [(s, g, t + v >= threshold) for s, t in starts for g, v in gains]
        crossing = sum(1 for *_, ok in pairs if ok)
        out[mode] = {
            "gains": dict(gains),
            "pairs": len(pairs),
            "crossing": crossing,
            "prior_yes": crossing / len(pairs) if pairs else 0.0,
            "crossing_pairs": [f"{s} + {g}" for s, g, ok in pairs if ok],
        }
    return out


def _substitute(node: Any, values: dict[str, float]) -> Any:
    if isinstance(node, str) and node.startswith("derived:"):
        return values[node]
    if isinstance(node, dict):
        return {k: _substitute(v, values) for k, v in node.items()}
    if isinstance(node, list):
        return [_substitute(v, values) for v in node]
    return node


def resolve(raw: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """``(config with derived priors filled, {variable: derivation record})``."""
    out = copy.deepcopy(raw)
    records: dict[str, Any] = {}
    values: dict[str, float] = {}
    for name, var in out["state_variables"].items():
        spec = var.get("derive")
        if not spec:
            continue
        if spec["method"] != "threshold_crossing":
            raise ValueError(f"unknown derive method {spec['method']!r} for {name}")
        record = threshold_crossing(spec)
        yes, no = spec["values"]
        p = record[spec["use"]]["prior_yes"]
        var["prior"] = {yes: p, no: 1.0 - p}
        records[name] = record
        for mode in spec["gains"]:
            values[f"derived:{name}:{mode}"] = record[mode]["prior_yes"]
    out["tornado"] = _substitute(out.get("tornado", []), values)
    return out, records
