"""Tests for external cellular-abundance calibration (:mod:`mva.drugs.abundance_calibration`)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from mva.drugs.abundance_calibration import (
    CANDIDATE_ASSAYS,
    CHILD_BURIED_DDG,
    calibrate_at_ddg,
    fast_auroc,
    fast_bootstrap_auroc,
    fit_random_intercept,
    fit_weighted_logistic,
    transfer_to_bub1b,
)
from mva.drugs.variant_atlas_model import auroc


def test_fast_auroc_matches_pairwise_auroc() -> None:
    scores = [2.1, -0.4, 1.55, 0.9, 0.9, -1.2, 3.0, 0.1]
    labels = [1, 0, 1, 1, 0, 0, 1, 0]
    assert fast_auroc(scores, labels) == pytest.approx(auroc(scores, labels), abs=1e-12)


def test_fast_bootstrap_auroc_bounds() -> None:
    scores = [3.0, 2.5, 2.0, 1.5, -0.5, -1.0, -1.5, -2.0]
    labels = [1, 1, 1, 1, 0, 0, 0, 0]
    lo, hi = fast_bootstrap_auroc(scores, labels, n_draws=200, seed=42)
    assert lo == pytest.approx(1.0)
    assert hi == pytest.approx(1.0)


def test_weighted_logistic_and_calibration_monotone() -> None:
    rng = np.random.default_rng(7)
    blocks = []
    ids = []
    for k in range(5):
        ddg = rng.uniform(-1.0, 3.5, size=120)
        p = 1.0 / (1.0 + np.exp(-(-0.8 + 1.0 * ddg)))
        y = (rng.uniform(0.0, 1.0, size=120) < p).astype(int)
        blocks.append((ddg, y))
        ids.append(f"PROT_{k}")
    _b0, b1 = fit_weighted_logistic(blocks)
    assert b1 > 0.3
    cal = calibrate_at_ddg(blocks, ids, target_ddg=CHILD_BURIED_DDG, n_draws=200, seed=7)
    ci_lo, ci_hi = cal["cluster_bootstrap_ci95"]
    assert 0.50 < cal["p_low_abundance"] < 0.95
    assert ci_lo <= cal["p_low_abundance"] <= ci_hi
    assert len(cal["lopo_folds"]) == 5
    ri = fit_random_intercept(blocks, target_ddg=CHILD_BURIED_DDG)
    assert ri["beta1"] > 0.3
    assert len(ri["per_protein_p"]) == 5
    pred_lo, pred_hi = ri["new_protein_predictive_ci95"]
    assert pred_lo <= ri["empirical_iqr_p"][0] <= ri["empirical_iqr_p"][1] <= pred_hi


def test_transfer_to_bub1b_zero_refit() -> None:
    df = pl.DataFrame(
        {
            "change": ["I909T", "R727C", "R814H", "L844F", "L1012P", "Y155C", "R550Q", "Q921H"],
            "y": [1, 1, 1, 1, 1, 0, 0, 0],
            "ddg": [1.941, 0.911, 0.857, 1.513, 3.105, 2.225, 0.039, 0.976],
            "rsa": [0.023, 0.060, 0.165, 0.006, 0.006, 0.004, 0.801, 0.026],
            "plddt": [87.0, 88.5, 90.2, 85.9, 95.3, 96.3, 35.3, 83.2],
            "region": ["kinase"] * 5 + ["TPR", "disordered", "kinase"],
        }
    )
    out = transfer_to_bub1b(df, beta0=-0.7913, beta1=0.9146)
    assert out["n_alleles"] == 8
    assert out["auroc_all_8"] == pytest.approx(0.6000, abs=1e-4)
    assert out["post_hoc_auroc_without_y155c"] == pytest.approx(0.8000, abs=1e-4)
    assert 0.10 < out["external_brier_all_8"] < 0.35


def test_committed_abundance_calibration_artifacts() -> None:
    out_dir = Path("ressources/track2/it6/abundance_calibration")
    eval_path = out_dir / "evaluation.json"
    scores_path = out_dir / "scores.parquet"
    manifest_path = out_dir / "manifest.json"
    fig_path = Path("figures/it6/abundance-calibration.svg")

    assert eval_path.exists()
    assert scores_path.exists()
    assert manifest_path.exists()
    assert fig_path.exists()

    report = json.loads(eval_path.read_text())
    assert report["n_candidate_assays"] == len(CANDIDATE_ASSAYS) == 13
    assert report["n_surviving_proteins"] == 11
    assert report["n_total_buried_variants"] == 18825
    med_auc = report["summary_all_11_proteins"]["median_auroc_buried"]
    assert med_auc == pytest.approx(0.7588, abs=1e-4)
    assert report["calibration_at_1_55"]["p_low_abundance"] == pytest.approx(0.6517, abs=1e-4)
    assert report["calibration_at_1_55"]["lopo_median_p"] == pytest.approx(0.6456, abs=1e-4)
    # The pooled-curve CI excludes 0.5, but the protocol's new-protein interval does not.
    pred_lo, pred_hi = report["calibration_at_1_55"]["random_intercept"][
        "new_protein_predictive_ci95"
    ]
    assert pred_lo < 0.50 < pred_hi
    assert report["gate"]["gate"] == "B"
    assert report["gate"]["gate_a_informative"] is False

    r5 = report["decision_model_consequence"]["r5_hierarchy_calibrated"]
    assert r5["calibrated_point"]["best_action"] == "NMN"
    assert r5["calibrated_point"]["evpi"] == pytest.approx(0.1393, abs=1e-4)
    assert r5["calibrated_point"]["evsi_blot"] == pytest.approx(0.0846, abs=1e-4)
