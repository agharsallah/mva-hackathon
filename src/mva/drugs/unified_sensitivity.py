"""Explicit Cartesian stress grid; coverage fractions are not confidence/probability.

Assay accuracies and utility factors are assumptions, not measured performance.
The canonical config is never mutated; route calibration precedes this sweep.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from itertools import product
from typing import Any

from mva.drugs.decision_config import with_param
from mva.drugs.decision_model import DecisionConfig, EvidenceRow, build_table
from mva.drugs.decision_sensitivity import flip_points
from mva.drugs.decision_voi import best_index, evpi, evsi, expected, test_likelihoods

GRID: dict[str, tuple[float, ...]] = {
    "prior:missense_class=unstable": tuple(i / 20 for i in range(6, 17)),
    "test:chx_chase_blot:sensitivity": (0.60, 0.75, 0.85, 0.95, 0.99),
    "test:chx_chase_blot:specificity": (0.60, 0.75, 0.85, 0.95, 0.99),
    "route:R2": (0.05, 0.25, 1.0),
    "safety:unassessed": (0.30, 0.60, 1.0),
    "applicability:missense_inactive:missense_class=unstable": (0.0, 0.25, 0.50),
}
RESULT_COLUMNS = (
    "best_action",
    "eu_baseline",
    "evpi",
    "evsi_blot",
    "evsi_share_of_evpi",
    "captures_half_evpi",
    "positive_p_unstable",
    "negative_p_unstable",
    "positive_action",
    "negative_action",
    "recommendation_changed_from_canonical",
    "assay_changes_recommendation",
    "evsi_readthrough",
)
SENSITIVITY_COLUMNS = (*GRID, *RESULT_COLUMNS)


def evaluate(
    config: DecisionConfig, rows: Sequence[EvidenceRow], safety: Mapping[str, str]
) -> dict[str, Any]:
    """Evaluate one scenario with canonical table/Bayes/VOI helpers, without rounding."""
    table = build_table(config, rows, safety)
    eus = expected(table.utility, table.probs)
    best = best_index(eus)
    perfect = evpi(table.utility, table.probs)
    tests = {test.name: test for test in config.tests}
    sample, outcomes = evsi(
        table.utility, table.probs, test_likelihoods(table.states, tests["chx_chase_blot"])
    )
    posteriors = [
        sum(
            p
            for state, p in zip(table.states, outcome.posterior, strict=True)
            if dict(state)["missense_class"] == "unstable"
        )
        for outcome in outcomes
    ]
    return {
        "best_action": table.actions[best],
        "eu_baseline": eus[best],
        "evpi": perfect,
        "evsi_blot": sample,
        "evsi_share_of_evpi": sample / perfect if perfect > 1e-12 else None,
        "captures_half_evpi": perfect > 1e-12 and sample >= 0.5 * perfect - 1e-12,
        "positive_p_unstable": posteriors[0],
        "negative_p_unstable": posteriors[1],
        "positive_action": table.actions[outcomes[0].best],
        "negative_action": table.actions[outcomes[1].best],
        "assay_changes_recommendation": any(
            outcome.probability > 0 and outcome.best != best for outcome in outcomes
        ),
        "evsi_readthrough": evsi(
            table.utility,
            table.probs,
            test_likelihoods(table.states, tests["readthrough_reporter"]),
        )[0],
    }


def build_sensitivity(
    config: DecisionConfig, rows: Sequence[EvidenceRow], safety: Mapping[str, str]
) -> dict[str, Any]:
    """Full 7,425-point joint grid including the unchanged calibrated baseline."""
    baseline = evaluate(config, rows, safety)
    scenarios: list[dict[str, Any]] = []
    thresholds: list[dict[str, Any]] = []
    utility_axes = tuple(GRID)[3:]
    for values in product(*(GRID[key] for key in utility_axes)):
        utility_config = config
        coefficients = dict(zip(utility_axes, values, strict=True))
        for key, value in coefficients.items():
            utility_config = with_param(utility_config, key, value)
        segments = flip_points(
            utility_config,
            lambda cfg: build_table(cfg, rows, safety),
            "missense_class",
            "unstable",
        )
        thresholds.append(
            {
                **coefficients,
                "segments": [
                    {"start": s.start, "end": s.end, "action": s.action} for s in segments
                ],
            }
        )
        for prior, sensitivity, specificity in product(*(GRID[key] for key in tuple(GRID)[:3])):
            coordinates = dict(zip(tuple(GRID)[:3], (prior, sensitivity, specificity), strict=True))
            varied = utility_config
            for key, value in coordinates.items():
                varied = with_param(varied, key, value)
            result = evaluate(varied, rows, safety)
            scenarios.append(
                {
                    **coordinates,
                    **coefficients,
                    **result,
                    "recommendation_changed_from_canonical": (
                        result["best_action"] != baseline["best_action"]
                    ),
                }
            )
    n = len(scenarios)
    eligible = [r for r in scenarios if r["evpi"] > 1e-12]
    captures = sum(r["captures_half_evpi"] for r in scenarios)
    numeric = (
        "eu_baseline",
        "evpi",
        "evsi_blot",
        "evsi_share_of_evpi",
        "positive_p_unstable",
        "negative_p_unstable",
        "evsi_readthrough",
    )
    return {
        "rows": scenarios,
        "summary": {
            "interpretation": (
                "Unweighted coverage of an explicitly specified Cartesian assumption grid; "
                "not probability, confidence, empirical assay validation or clinical benefit."
            ),
            "recommendation_definitions": {
                "recommendation_changed_from_canonical": (
                    "Scenario pre-test expected-utility maximizing action differs from "
                    "canonical pre-test NMN; not a state-branch comparison."
                ),
                "assay_changes_recommendation": (
                    "At least one positive-probability assay outcome selects a different "
                    "action from that same scenario's pre-test maximizing action."
                ),
            },
            "grid": GRID,
            "utility_rationale": {
                "route:R2": "strong discount, hierarchy calibration, and no discount",
                "safety:unassessed": "conservative, canonical, and no safety discount",
                "applicability:missense_inactive:missense_class=unstable": (
                    "canonical zero, 0.25, and 0.50 cross-state benefit for inactive-branch drugs"
                ),
            },
            "fixed": (
                "Other canonical coefficients, independent state priors, max evidence "
                "combination and readthrough prior remain unchanged; R1=R3=1."
            ),
            "canonical": baseline,
            "canonical_parameters": {
                "prior_unstable": config.variable("missense_class").weight("unstable"),
                "blot_sensitivity": next(
                    t.sensitivity for t in config.tests if t.name == "chx_chase_blot"
                ),
                "blot_specificity": next(
                    t.specificity for t in config.tests if t.name == "chx_chase_blot"
                ),
                "route_weights": dict(config.route_weights),
                "unassessed_safety": config.safety["unassessed"],
                "inactive_branch_unstable_applicability": config.applicability["missense_inactive"][
                    "missense_class"
                ]["unstable"],
            },
            "n_grid": n,
            "n_positive_evpi": len(eligible),
            "n_captures_half_evpi": captures,
            "fraction_grid_captures_half_evpi": captures / n,
            "fraction_positive_evpi_captures_half_evpi": captures / len(eligible),
            "n_recommendation_changed_from_canonical": sum(
                r["recommendation_changed_from_canonical"] for r in scenarios
            ),
            "fraction_grid_recommendation_changed_from_canonical": sum(
                r["recommendation_changed_from_canonical"] for r in scenarios
            )
            / n,
            "n_assay_changes_recommendation": sum(
                r["assay_changes_recommendation"] for r in scenarios
            ),
            "fraction_grid_assay_changes_recommendation": sum(
                r["assay_changes_recommendation"] for r in scenarios
            )
            / n,
            "best_action_counts": dict(Counter(r["best_action"] for r in scenarios)),
            "ranges": {
                key: [min(r[key] for r in eligible), max(r[key] for r in eligible)]
                for key in numeric
            },
            "exact_prior_recommendation_segments": thresholds,
            "prior_flip_threshold_range": [
                min(s["start"] for t in thresholds for s in t["segments"][1:]),
                max(s["start"] for t in thresholds for s in t["segments"][1:]),
            ],
            "structural_caveats": (
                "Zero readthrough EVSI follows the fixed derived feasibility prior and "
                "action structure, not empirical proof of assay uselessness. EVPI=0.18 "
                "is invariant only on the original route-only sweep, not this joint grid."
            ),
        },
    }
