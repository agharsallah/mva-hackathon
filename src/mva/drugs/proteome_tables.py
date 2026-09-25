"""Drug-perturbation proteomics, the tables: hits, controls, candidates, one TSV writer.

Rows are plain dicts so the driver can write them with :func:`write_tsv` and describe them
in a provenance manifest. The candidate rows follow the iteration-5 route contract
(``drug_name, route, branch, evidence_kind, evidence_strength, positive_control_passed,
source, notes``) and their strength comes from :func:`protein_strength`, whose rubric is
stated in its docstring and in the route's methodology entry.
"""

from __future__ import annotations

import csv
import math
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .proteome_run import DatasetResult

__all__ = [
    "CANDIDATE_COLUMNS",
    "control_rows",
    "hit_rows",
    "protein_strength",
    "write_tsv",
]

CANDIDATE_COLUMNS = (
    "drug_name",
    "route",
    "branch",
    "evidence_kind",
    "evidence_strength",
    "positive_control_passed",
    "source",
    "notes",
)

#: ≥ 25 % more protein, as log2 fold change.
EFFECT_LOG2 = math.log2(1.25)


def _r(value: float, digits: int = 4) -> float | str:
    return round(value, digits) if math.isfinite(value) else ""


def hit_rows(
    result: DatasetResult,
    compound_of: Callable[[str], str],
    canonical: Callable[[str], tuple[str, bool, str]],
    *,
    broad_share: float,
) -> list[dict[str, Any]]:
    """Every perturbation's target response, ranked; ``canonical`` → (name, approved, id)."""
    rows: list[dict[str, Any]] = []
    for r in result.responses:
        compound = compound_of(r.perturbation)
        name, approved, ident = canonical(compound)
        sens_rank, sens_z = result.sensitivity.get(r.perturbation, (0, math.nan))
        share = result.breadth.get(r.perturbation, math.nan)
        rows.append(
            {
                "dataset": result.name,
                "context": result.context,
                "perturbation": r.perturbation,
                "compound": compound,
                "canonical_name": name,
                "approved": approved,
                "chembl_id": ident,
                "target": result.fit["target"],
                "raw_log2fc": _r(r.raw),
                "proliferation_score": _r(r.score),
                "residual": _r(r.residual),
                "robust_z": _r(r.z, 3),
                "rank": r.rank,
                "hit": r.hit,
                "sensitivity_rank": sens_rank,
                "sensitivity_z": _r(sens_z, 3),
                "breadth": _r(share),
                "broad": bool(math.isfinite(share) and share > broad_share),
                "dataset_interpretable": result.interpretable,
            }
        )
    return rows


def control_rows(result: DatasetResult) -> list[dict[str, Any]]:
    """One row per (control, inducer): its rank among perturbations and the pass bit."""
    rows: list[dict[str, Any]] = []
    for spec, outcome in result.controls:
        rows.extend(
            [
                {
                    "dataset": result.name,
                    "context": result.context,
                    "protein": spec.protein,
                    "inducer": inducer,
                    "gates": spec.gates,
                    "rank": outcome.ranks.get(inducer) or "",
                    "robust_z": outcome.z.get(inducer)
                    if outcome.z.get(inducer) is not None
                    else "",
                    "universe": outcome.universe,
                    "cut_rank": outcome.cut_rank,
                    "z_min": outcome.z_min,
                    "control_passed": outcome.passed,
                    "why": spec.why,
                }
                for inducer in spec.inducers
            ]
        )
    return rows


def protein_strength(
    row: Mapping[str, Any], *, replicated: bool, z_min: float
) -> tuple[float, list[str]]:
    """Evidence strength in [0, 1] for one approved protein-raising hit, with its reasons.

    Rubric (fixed 2026-09-25 before the target was ranked):

    * 0.40 - a hit (robust z ≥ cut, raw change > 0) in a dataset whose gating control passed;
    * +0.15 - still z ≥ cut when the checkpoint/kinetochore module leaves the score;
    * +0.15 - not broad (lifts at most the declared share of all proteins);
    * +0.15 - raw effect ≥ 25 % more protein (log2 FC ≥ 0.32);
    * +0.15 - the same compound is a hit in an independent dataset.

    A row from a dataset whose control failed is capped at 0.10: the route could not show
    it finds a known induction, so its hit is a lead to look at, not evidence.
    """
    reasons: list[str] = []
    score = 0.0
    if row["hit"]:
        score += 0.40
        reasons.append("hit")
    sens = row["sensitivity_z"]
    if isinstance(sens, float) and sens >= z_min:
        score += 0.15
        reasons.append("survives SAC-excluded score")
    if not row["broad"]:
        score += 0.15
        reasons.append("not broad")
    raw = row["raw_log2fc"]
    if isinstance(raw, float) and raw >= EFFECT_LOG2:
        score += 0.15
        reasons.append("≥ 25 % raise")
    if replicated:
        score += 0.15
        reasons.append("replicated")
    if not row["dataset_interpretable"]:
        score = min(score, 0.10)
        reasons.append("control failed: capped")
    return round(min(score, 1.0), 2), reasons


def write_tsv(path: Path, rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> int:
    """Write ``rows`` under ``columns`` (tab-separated, header first). Returns the row count."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in columns})
    return len(rows)
