"""Load, validate and perturb the decision engine's config.

The config is JSON (see ``ressources/track2/it5/decision_config.json``). Every prior and
every weight carries a ``source`` string; a value still awaiting another route's numbers
carries a ``todo`` string, and :func:`todos` lists them so a run can print what is still a
placeholder. Validation is strict: a prior that does not sum to 1, a weight outside [0, 1],
a branch without an applicability rule or a test on an unknown value is an error, not a
silent default.

**Parameter addresses** (used by the tornado and by ``--set`` on the driver)::

    prior:<variable>=<value>          the prior weight of one value (others rescale)
    safety:<class>                    one safety factor
    control:failed_factor | control:unknown_factor | control:na_factor
    test:<name>:sensitivity | test:<name>:specificity
    applicability:<branch>:<variable>=<value>
    route:<route>                     one route's weight (default 1)
    baseline                          the baseline action's utility
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

from mva.drugs.decision_model import (
    BRANCHES,
    SAFETY_CLASSES,
    DecisionConfig,
    NamedTest,
    StateVariable,
    TornadoParam,
)
from mva.drugs.decision_priors import resolve

__all__ = ["load", "parse", "todos", "with_param", "with_prior"]

TOL = 1e-9


def _unit(value: Any, what: str) -> float:
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{what} = {number} is outside [0, 1]")
    return number


def _variable(name: str, spec: dict[str, Any]) -> StateVariable:
    prior = tuple((str(k), _unit(v, f"prior {name}={k}")) for k, v in spec["prior"].items())
    if len(prior) < 2:
        raise ValueError(f"state variable {name!r} needs at least two values")
    total = sum(weight for _, weight in prior)
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"prior of {name!r} sums to {total}, not 1")
    return StateVariable(name, prior, str(spec.get("source", "")), spec.get("todo"))


def parse(raw: dict[str, Any]) -> DecisionConfig:
    """A validated :class:`DecisionConfig` from the config's JSON object."""
    variables = tuple(_variable(n, s) for n, s in raw["state_variables"].items())
    values = {var.name: set(var.values) for var in variables}
    applic: dict[str, dict[str, dict[str, float]]] = {}
    for branch, rule in raw["applicability"].items():
        if branch.startswith("_"):
            continue
        applic[branch] = {}
        for var, factors in rule.items():
            if var.startswith("_"):
                continue
            if var not in values or not set(factors) <= values[var]:
                raise ValueError(f"applicability[{branch}] names unknown {var}/{set(factors)}")
            applic[branch][var] = {
                v: _unit(f, f"applicability {branch}") for v, f in factors.items()
            }
    missing = set(BRANCHES) - set(applic)
    if missing:
        raise ValueError(f"no applicability rule for pinned branch(es) {sorted(missing)}")
    safety = {k: _unit(v, f"safety {k}") for k, v in raw["safety"]["factors"].items()}
    if set(SAFETY_CLASSES) - set(safety):
        raise ValueError(f"safety factors missing {sorted(set(SAFETY_CLASSES) - set(safety))}")
    control = raw["control"]
    if control["policy"] not in ("penalty", "exclude"):
        raise ValueError("control.policy must be 'penalty' or 'exclude'")
    combine = raw.get("combine", "max")
    if combine not in ("max", "noisy_or"):
        raise ValueError("combine must be 'max' or 'noisy_or'")
    tests = []
    for spec in raw.get("tests", []):
        if spec["variable"] not in values or spec["positive"] not in values[spec["variable"]]:
            raise ValueError(f"test {spec['name']!r} targets an unknown variable or value")
        tests.append(
            NamedTest(
                name=spec["name"],
                variable=spec["variable"],
                positive=spec["positive"],
                sensitivity=_unit(spec["sensitivity"], "sensitivity"),
                specificity=_unit(spec["specificity"], "specificity"),
                source=str(spec.get("source", "")),
                todo=spec.get("todo"),
            )
        )
    return DecisionConfig(
        variables=variables,
        applicability=applic,
        safety=safety,
        control_policy=control["policy"],
        failed_factor=_unit(control["failed_factor"], "control.failed_factor"),
        unknown_factor=_unit(control["unknown_factor"], "control.unknown_factor"),
        na_factor=_unit(control.get("na_factor", 1.0), "control.na_factor"),
        combine=combine,
        baseline_name=raw["baseline"]["name"],
        baseline_utility=_unit(raw["baseline"]["utility"], "baseline.utility"),
        route_weights={k: float(v) for k, v in raw.get("route_weights", {}).items()},
        tests=tuple(tests),
        tornado=tuple(
            TornadoParam(t["param"], float(t["low"]), float(t["high"]))
            for t in raw.get("tornado", [])
        ),
    )


def load(path: Path) -> tuple[DecisionConfig, dict[str, Any]]:
    """``(config, raw JSON)`` with derived priors computed (:mod:`mva.drugs.decision_priors`).

    The raw object is kept for the provenance manifest; its ``_derived`` key holds each
    derivation's rule, inputs and arithmetic.
    """
    raw, derived = resolve(json.loads(path.read_text(encoding="utf-8")))
    raw["_derived"] = derived
    return parse(raw), raw


def todos(raw: dict[str, Any]) -> list[str]:
    """Every ``todo`` marker in the config, as ``<where>: <text>``."""
    found: list[str] = []

    def walk(node: Any, where: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key.endswith("todo") and value:
                    label = where if key == "todo" else f"{where}.{key}".lstrip(".")
                    found.append(f"{label}: {value}")
                else:
                    walk(value, f"{where}.{key}" if where else key)
        elif isinstance(node, list):
            for i, item in enumerate(node):
                walk(item, f"{where}[{i}]")

    walk(raw, "")
    return found


def with_prior(config: DecisionConfig, variable: str, value: str, p: float) -> DecisionConfig:
    """Set ``P(variable=value) = p``; the other values share ``1 - p`` in their old ratio."""
    var = config.variable(variable)
    rest = [(v, w) for v, w in var.prior if v != value]
    total = sum(w for _, w in rest)
    share = {v: (1.0 - p) * (w / total if total > TOL else 1.0 / len(rest)) for v, w in rest}
    prior = tuple((v, p if v == value else share[v]) for v, _ in var.prior)
    new = dataclasses.replace(var, prior=prior)
    return dataclasses.replace(
        config, variables=tuple(new if v.name == variable else v for v in config.variables)
    )


def _replace_test(config: DecisionConfig, name: str, field: str, value: float) -> DecisionConfig:
    if name not in {t.name for t in config.tests}:
        raise KeyError(f"no test {name!r}")

    def change(test: NamedTest) -> NamedTest:
        if field == "sensitivity":
            return dataclasses.replace(test, sensitivity=value)
        return dataclasses.replace(test, specificity=value)

    tests = tuple(change(t) if t.name == name else t for t in config.tests)
    return dataclasses.replace(config, tests=tests)


def with_param(config: DecisionConfig, param: str, value: float) -> DecisionConfig:
    """``config`` with one addressed parameter set to ``value`` (see the module docstring)."""
    kind, _, rest = param.partition(":")
    if kind == "prior":
        variable, _, val = rest.partition("=")
        return with_prior(config, variable, val, value)
    if kind == "safety":
        if rest not in config.safety:
            raise KeyError(f"no safety class {rest!r}")
        return dataclasses.replace(config, safety={**config.safety, rest: value})
    if kind == "control" and rest == "failed_factor":
        return dataclasses.replace(config, failed_factor=value)
    if kind == "control" and rest == "unknown_factor":
        return dataclasses.replace(config, unknown_factor=value)
    if kind == "control" and rest == "na_factor":
        return dataclasses.replace(config, na_factor=value)
    if kind == "test":
        name, _, field = rest.rpartition(":")
        if field not in ("sensitivity", "specificity"):
            raise KeyError(f"bad test field in {param!r}")
        return _replace_test(config, name, field, value)
    if kind == "applicability":
        branch, _, cell = rest.partition(":")
        variable, _, val = cell.partition("=")
        rule = {k: dict(v) for k, v in config.applicability[branch].items()}
        rule.setdefault(variable, {})[val] = value
        return dataclasses.replace(config, applicability={**config.applicability, branch: rule})
    if kind == "route":
        return dataclasses.replace(config, route_weights={**config.route_weights, rest: value})
    if kind == "baseline":
        return dataclasses.replace(config, baseline_utility=value)
    raise KeyError(f"unknown parameter address {param!r}")
