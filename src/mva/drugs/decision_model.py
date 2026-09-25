"""The decision table: candidates x world-states -> a heuristic utility per cell.

A **world-state** is one assignment of every uncertain fact the drug choice depends on - for
example ``missense_class=unstable & readthrough_feasible=yes``. The engine does not know
which state the child is in; it holds a prior (a stated weight) for each, taken from a
config whose every number names its source.

The utility of drug ``d`` in state ``s`` is a product of stated weights, one per concern::

    u(d, s) = safety(d) x combine over d's evidence rows r of
              [ evidence_strength(r) x route_weight(r) x applicability(branch(r), s)
                x control(r) ]

* ``applicability`` - does the row's mechanism branch act in this state? A read-through drug
  (branch ``stop_allele``) does nothing if read-through is infeasible.
* ``control`` - did the route that produced the row pass its positive control? A failed
  control is penalised or the row excluded; that is a config choice. A row the route marks
  ``n/a`` (a published measurement, not an output of a controlled method) takes its own
  stated factor.
* ``safety`` - the per-child two-source flag (iteration 4, entries 152/155). A drug missing
  from the safety table is ``unassessed``, never ``safe``.
* ``combine`` - ``max`` (default: the best single argument; convergent routes are not
  assumed independent) or ``noisy_or`` (1 - product of 1 - u; rewards convergence).

**This is a triage heuristic, not a calibrated posterior** and not a clinical
recommendation: the weights are choices, and the sensitivity module shows where they matter.
The module is case-agnostic: branches, state variables and weights all come from the config.
No genomic position can appear here: rows carry drug names, route ids and weights.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from mva.drugs.names import base_name

__all__ = [
    "BRANCHES",
    "CONTROL_STATES",
    "HEURISTIC_NOTE",
    "SAFETY_CLASSES",
    "DecisionConfig",
    "DecisionTable",
    "Drug",
    "EvidenceRow",
    "NamedTest",
    "State",
    "StateVariable",
    "TornadoParam",
    "applicability",
    "build_table",
    "control_factor",
    "drug_key",
    "enumerate_states",
    "group_drugs",
    "state_label",
]

#: The pinned ``branch`` vocabulary of every route's candidate table (iteration-5 plan).
BRANCHES = ("stop_allele", "missense_unstable", "missense_inactive", "any")
#: ``positive_control_passed`` after normalisation.
CONTROL_STATES = ("passed", "failed", "unknown", "not_applicable")
#: Per-child safety classes: the first four mirror it4 ``candidate_safety.tsv``'s combined
#: flag; ``caution`` / ``avoid`` come from :mod:`mva.drugs.decision_avoid`.
SAFETY_CLASSES = (
    "unflagged",
    "genome_flag",
    "phenotype_flag",
    "both_flag",
    "unassessed",
    "caution",
    "avoid",
)
#: Printed on every output so no number is quoted as a probability of benefit.
HEURISTIC_NOTE = (
    "triage heuristic: each utility is a product of stated weights and each prior a stated "
    "weight; nothing here is a calibrated posterior, a probability of benefit, or advice for "
    "or against giving any drug to any patient"
)

#: One world-state: ``((variable, value), ...)`` in the config's variable order.
State = tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class StateVariable:
    """One uncertain fact, its values and their prior weights (summing to 1)."""

    name: str
    prior: tuple[tuple[str, float], ...]
    source: str
    todo: str | None = None

    @property
    def values(self) -> tuple[str, ...]:
        return tuple(value for value, _ in self.prior)

    def weight(self, value: str) -> float:
        return dict(self.prior)[value]


@dataclass(frozen=True)
class NamedTest:
    """A binary experiment on one variable: positive when the variable equals ``positive``."""

    name: str
    variable: str
    positive: str
    sensitivity: float
    specificity: float
    source: str
    todo: str | None = None


@dataclass(frozen=True)
class TornadoParam:
    """One parameter address (see :mod:`mva.drugs.decision_config`) and its swing range."""

    param: str
    low: float
    high: float


@dataclass(frozen=True)
class DecisionConfig:
    """Every weight the engine uses. Built by :func:`mva.drugs.decision_config.parse`."""

    variables: tuple[StateVariable, ...]
    applicability: Mapping[str, Mapping[str, Mapping[str, float]]]
    safety: Mapping[str, float]
    control_policy: str
    failed_factor: float
    unknown_factor: float
    na_factor: float
    combine: str
    baseline_name: str
    baseline_utility: float
    route_weights: Mapping[str, float] = field(default_factory=dict)
    tests: tuple[NamedTest, ...] = ()
    tornado: tuple[TornadoParam, ...] = ()

    def variable(self, name: str) -> StateVariable:
        for var in self.variables:
            if var.name == name:
                return var
        raise KeyError(f"no state variable {name!r} in the config")


@dataclass(frozen=True)
class EvidenceRow:
    """One row of a route's candidate table, validated."""

    drug_name: str
    route: str
    branch: str
    evidence_kind: str
    evidence_strength: float
    control: str
    source: str
    notes: str
    origin: str


@dataclass(frozen=True)
class Drug:
    """Every evidence row that names one molecule, across routes."""

    key: str
    rows: tuple[EvidenceRow, ...]

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted({row.drug_name for row in self.rows}))

    @property
    def routes(self) -> tuple[str, ...]:
        return tuple(sorted({row.route for row in self.rows}))

    @property
    def branches(self) -> tuple[str, ...]:
        return tuple(sorted({row.branch for row in self.rows}))


@dataclass(frozen=True)
class DecisionTable:
    """Actions x states. Action 0 is always the baseline ("defer"), so ties go to it."""

    actions: tuple[str, ...]
    states: tuple[State, ...]
    probs: tuple[float, ...]
    utility: tuple[tuple[float, ...], ...]
    drugs: tuple[Drug, ...]
    safety: Mapping[str, str]
    excluded: tuple[tuple[EvidenceRow, str], ...]


def drug_key(name: str) -> str:
    """The dedup key: :func:`mva.drugs.names.base_name` (salt words off, upper-cased)."""
    return base_name(" ".join(name.replace("_", " ").split()))


def state_label(state: State) -> str:
    """``missense_class=unstable & readthrough_feasible=yes``."""
    return " & ".join(f"{name}={value}" for name, value in state)


def enumerate_states(variables: Sequence[StateVariable]) -> list[tuple[State, float]]:
    """Every joint state and its prior weight. Variables are taken as independent."""
    states: list[tuple[State, float]] = []
    for combo in itertools.product(*(var.prior for var in variables)):
        state = tuple((var.name, value) for var, (value, _) in zip(variables, combo, strict=True))
        states.append((state, math.prod(weight for _, weight in combo)))
    return states


def applicability(config: DecisionConfig, branch: str, state: State) -> float:
    """Product over the variables the branch depends on; a variable not listed is 1."""
    rule = config.applicability[branch]
    factor = 1.0
    for name, value in state:
        if name in rule:
            factor *= rule[name].get(value, 0.0)
    return factor


def control_factor(config: DecisionConfig, control: str) -> float | None:
    """1 for a passed control; the stated penalty otherwise; ``None`` = row excluded."""
    if control == "passed":
        return 1.0
    if control == "not_applicable":
        return config.na_factor
    if control == "unknown":
        return config.unknown_factor
    if config.control_policy == "exclude":
        return None
    return config.failed_factor


def group_drugs(rows: Iterable[EvidenceRow]) -> list[Drug]:
    """Rows grouped by :func:`drug_key`, sorted by key (a stable action order)."""
    groups: dict[str, list[EvidenceRow]] = {}
    for row in rows:
        groups.setdefault(drug_key(row.drug_name), []).append(row)
    return [Drug(key, tuple(groups[key])) for key in sorted(groups)]


def _row_utility(config: DecisionConfig, row: EvidenceRow, state: State, ctrl: float) -> float:
    weight = config.route_weights.get(row.route, 1.0)
    return row.evidence_strength * weight * applicability(config, row.branch, state) * ctrl


def _combine(config: DecisionConfig, values: Sequence[float]) -> float:
    if not values:
        return 0.0
    if config.combine == "noisy_or":
        return 1.0 - math.prod(1.0 - min(1.0, v) for v in values)
    return max(values)


def build_table(
    config: DecisionConfig, rows: Sequence[EvidenceRow], safety: Mapping[str, str]
) -> DecisionTable:
    """The utility of every action in every state. ``safety`` maps drug key -> class."""
    kept: list[tuple[EvidenceRow, float]] = []
    excluded: list[tuple[EvidenceRow, str]] = []
    for row in rows:
        ctrl = control_factor(config, row.control)
        if ctrl is None:
            excluded.append((row, "route positive control failed; policy = exclude"))
        else:
            kept.append((row, ctrl))
    ctrl_of = {id(row): ctrl for row, ctrl in kept}
    drugs = group_drugs(row for row, _ in kept)
    states = enumerate_states(config.variables)
    classes = {drug.key: safety.get(drug.key, "unassessed") for drug in drugs}
    utility: list[tuple[float, ...]] = [tuple(config.baseline_utility for _ in states)]
    for drug in drugs:
        factor = config.safety[classes[drug.key]]
        utility.append(
            tuple(
                factor
                * _combine(
                    config,
                    [_row_utility(config, row, state, ctrl_of[id(row)]) for row in drug.rows],
                )
                for state, _ in states
            )
        )
    return DecisionTable(
        actions=(config.baseline_name, *(drug.key for drug in drugs)),
        states=tuple(state for state, _ in states),
        probs=tuple(prob for _, prob in states),
        utility=tuple(utility),
        drugs=tuple(drugs),
        safety=classes,
        excluded=tuple(excluded),
    )
