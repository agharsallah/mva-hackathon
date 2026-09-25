"""Drug-perturbation proteomics, the run: controls first, then the target, per dataset.

A :class:`ProteomePlan` names one target protein, the textbook inductions that must come out
on top before the target may be read (:class:`ControlSpec`), the proliferation gene set and
the cuts. :func:`run_dataset` applies it to one :class:`~.proteome.ProteomeMatrix` and
returns plain rows; the driver decides where they are written.

Order inside a dataset, and why:

1. **Score** every perturbation on the declared set, the target removed (primary), and on
   the set minus the checkpoint/kinetochore module (sensitivity).
2. **Controls** on the primary score. A gating control that fails marks the dataset
   ``uninterpretable`` and its target rows are still written, flagged, never promoted.
3. **Target**: one OLS on the score, every perturbation ranked by robust z.
4. **Breadth**: the same model over every protein, so a hit that lifts a large share of the
   proteome is labelled broad (a proteasome inhibitor is not a BubR1-specific lead).

Case-agnostic: the target, the controls and every threshold come from the plan.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .proteome import (
    ControlOutcome,
    ProteomeMatrix,
    Response,
    breadth,
    control_outcome,
    fit_corrected,
    rank_responses,
    set_score,
    z_matrix,
)
from .proteome_sets import SAC_MODULE, members

__all__ = ["ControlSpec", "DatasetResult", "ProteomePlan", "run_dataset"]


@dataclass(frozen=True)
class ControlSpec:
    """A known induction: every ``inducers`` label must be a top hit for ``protein``."""

    protein: str
    inducers: tuple[str, ...]
    gates: bool
    why: str


@dataclass(frozen=True)
class ProteomePlan:
    """Everything the run needs to know about the question, nothing about the files."""

    target: str
    score_set: tuple[str, ...]
    z_min: float
    top_fraction: float
    broad_share: float
    min_members: int = 10
    sensitivity_exclude: frozenset[str] = SAC_MODULE


@dataclass
class DatasetResult:
    """One dataset's controls, target ranking and descriptive numbers."""

    name: str
    context: str
    controls: list[tuple[ControlSpec, ControlOutcome]]
    responses: list[Response]
    sensitivity: dict[str, tuple[int, float]]
    breadth: dict[str, float]
    fit: dict[str, Any]
    score_members: tuple[str, ...]
    interpretable: bool
    notes: list[str] = field(default_factory=list)


def _score(
    matrix: ProteomeMatrix, plan: ProteomePlan, exclude: Collection[str]
) -> tuple[np.ndarray, tuple[str, ...]]:
    genes = members(plan.score_set, set(matrix.genes), exclude)
    return set_score(matrix, genes, min_members=plan.min_members)


def _control(
    matrix: ProteomeMatrix,
    spec: ControlSpec,
    score: np.ndarray,
    z_min: float,
    top_fraction: float,
) -> ControlOutcome:
    if spec.protein not in set(matrix.genes):
        return ControlOutcome(spec.protein, spec.inducers, {}, {}, 0, 0, z_min, False)
    fit = fit_corrected(spec.protein, matrix.row(spec.protein), score)
    responses = rank_responses(matrix, fit, score, z_min=z_min)
    return control_outcome(
        spec.protein, spec.inducers, responses, top_fraction=top_fraction, z_min=z_min
    )


def run_dataset(
    name: str,
    context: str,
    matrix: ProteomeMatrix,
    plan: ProteomePlan,
    controls: Sequence[ControlSpec],
    *,
    z_min: float | None = None,
    top_fraction: float | None = None,
    with_breadth: bool = True,
    progress: Callable[[str], None] = lambda _msg: None,
) -> DatasetResult:
    """Controls, then the target, on one matrix. ``z_min``/``top_fraction`` override the plan
    for a small dataset (stated by the caller, never tuned after seeing the target)."""
    z_cut = plan.z_min if z_min is None else z_min
    top = plan.top_fraction if top_fraction is None else top_fraction
    score, used = _score(matrix, plan, {plan.target})
    outcomes = [(spec, _control(matrix, spec, score, z_cut, top)) for spec in controls]
    gating = [o.passed for s, o in outcomes if s.gates]
    interpretable = bool(gating) and all(gating)
    progress(f"{name}: controls {[(s.protein, o.passed) for s, o in outcomes]}")

    target_row = matrix.row(plan.target)
    fit = fit_corrected(plan.target, target_row, score)
    responses = rank_responses(matrix, fit, score, z_min=z_cut)
    finite = np.isfinite(target_row) & np.isfinite(score)
    pearson = float(np.corrcoef(target_row[finite], score[finite])[0, 1])

    sens_score, sens_used = _score(matrix, plan, set(plan.sensitivity_exclude) | {plan.target})
    sens_fit = fit_corrected(plan.target, target_row, sens_score)
    sens_rank = rank_responses(matrix, sens_fit, sens_score, z_min=z_cut)
    sensitivity = {r.perturbation: (r.rank, r.z) for r in sens_rank}

    shares: dict[str, float] = {}
    if with_breadth:
        progress(f"{name}: breadth over {len(matrix.genes)} proteins")
        share = breadth(z_matrix(matrix, score), matrix.values, z_min=z_cut)
        shares = {p: float(s) for p, s in zip(matrix.perturbations, share, strict=True)}

    return DatasetResult(
        name=name,
        context=context,
        controls=outcomes,
        responses=responses,
        sensitivity=sensitivity,
        breadth=shares,
        fit={
            "target": plan.target,
            "perturbations": len(matrix.perturbations),
            "proteins": len(matrix.genes),
            "fit_n": fit.n,
            "slope_on_score": round(fit.slope, 4),
            "r2": round(fit.r2, 4),
            "pearson_target_vs_score": round(pearson, 4),
            "score_members": len(used),
            "sensitivity_score_members": len(sens_used),
            "sensitivity_slope": round(sens_fit.slope, 4),
            "sensitivity_r2": round(sens_fit.r2, 4),
            "z_min": z_cut,
            "top_fraction": top,
        },
        score_members=used,
        interpretable=interpretable,
    )
