"""External cellular-abundance calibration for ThermoMPNN ΔΔG across ProteinGym DMS proteins.

Frozen protocol: ``ressources/track2/it6/abundance_calibration/protocol.md``.

* **Primary stratum.** Buried, high-confidence core residues (``RSA < 0.20``, ``pLDDT >= 90.0``),
  matching the child's buried pseudokinase substitution stratum.
* **Label.** ``y = 1`` if ``DMS_score_bin == 0`` (low abundance / destabilised expression under
  each ProteinGym assay's own cutoff); ``y = 0`` if ``DMS_score_bin == 1`` (WT-like).
* **Calibration.** Protein-equally-weighted two-parameter logistic regression
  ``logit P(y = 1 | ddg) = beta_0 + beta_1 * ddg``, evaluated at the child's buried pseudokinase
  value ``ddg = +1.55 kcal/mol`` with leave-one-protein-out (LOPO) cross-validation, a
  2,000-draw protein-cluster bootstrap 95 % confidence interval, and a random-intercept
  between-protein model.
* **Zero-refit transfer.** Evaluates the frozen external calibration curve on the eight primary
  published ``BUB1B`` alleles (PMID 20516114) without refitting.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import polars as pl
from scipy.optimize import minimize
from scipy.stats import spearmanr

from mva.drugs.abundance_assays import CANDIDATE_ASSAYS, AssaySpec
from mva.drugs.abundance_auroc import fast_auroc, fast_bootstrap_auroc

__all__ = [
    "BURIED_PLDDT_MIN",
    "BURIED_RSA_MAX",
    "CANDIDATE_ASSAYS",
    "CHILD_BURIED_DDG",
    "MIN_BURIED_VARIANTS",
    "AssaySpec",
    "calibrate_at_ddg",
    "evaluate_calibration",
    "fast_auroc",
    "fast_bootstrap_auroc",
    "fit_random_intercept",
    "fit_weighted_logistic",
    "transfer_to_bub1b",
]

BURIED_RSA_MAX = 0.20
BURIED_PLDDT_MIN = 90.0
MIN_BURIED_VARIANTS = 50
CHILD_BURIED_DDG = 1.55


def _sigmoid(z: float | np.ndarray) -> float | np.ndarray:
    return 1.0 / (1.0 + np.exp(-z))


def fit_weighted_logistic(
    protein_blocks: Sequence[tuple[np.ndarray, np.ndarray]],
) -> tuple[float, float]:
    """Fit ``logit P(y=1 | ddg) = b0 + b1 * ddg`` with equal total weight per protein."""
    xs = np.concatenate([b[0] for b in protein_blocks])
    ys = np.concatenate([b[1] for b in protein_blocks])
    ws = np.concatenate([np.full(len(b[0]), 1.0 / len(b[0])) for b in protein_blocks])

    def nll(theta: np.ndarray) -> float:
        z = theta[0] + theta[1] * xs
        return float(np.sum(ws * (np.logaddexp(0.0, z) - ys * z)))

    res = minimize(nll, np.array([0.0, 0.5], dtype=float), method="BFGS")
    return float(res.x[0]), float(res.x[1])


def fit_random_intercept(
    protein_blocks: Sequence[tuple[np.ndarray, np.ndarray]],
    target_ddg: float = CHILD_BURIED_DDG,
    n_draws: int = 2000,
    seed: int = 0,
) -> dict[str, Any]:
    """Fit protein-specific intercepts ``alpha_k + beta_1 * ddg`` in the buried stratum.

    The predictive interval is for a *new* protein (protocol step 4): each draw resamples the
    fitted intercepts (cluster bootstrap) to re-estimate ``mu`` and ``tau``, then draws one new
    intercept from ``N(mu, tau)``. The common slope is held at its estimate.
    """
    k_count = len(protein_blocks)

    def nll(theta: np.ndarray) -> float:
        alphas = theta[:k_count]
        beta1 = theta[k_count]
        total = 0.0
        for k, (bx, by) in enumerate(protein_blocks):
            z = alphas[k] + beta1 * bx
            w = 1.0 / len(bx)
            total += float(np.sum(w * (np.logaddexp(0.0, z) - by * z)))
        return total

    res = minimize(nll, np.zeros(k_count + 1, dtype=float), method="BFGS")
    alphas = res.x[:k_count]
    beta1 = float(res.x[k_count])
    mu_alpha = float(np.mean(alphas))
    tau_alpha = float(np.std(alphas, ddof=1))
    per_protein_p = [float(_sigmoid(float(a) + beta1 * target_ddg)) for a in alphas]
    q25, q50, q75 = np.percentile(per_protein_p, [25.0, 50.0, 75.0])
    rng = np.random.default_rng(seed)
    pred = np.empty(n_draws, dtype=float)
    for d in range(n_draws):
        a_d = rng.choice(alphas, k_count, replace=True)
        alpha_new = rng.normal(float(np.mean(a_d)), float(np.std(a_d, ddof=1)))
        pred[d] = float(_sigmoid(alpha_new + beta1 * target_ddg))
    pred_lo, pred_hi = np.percentile(pred, [2.5, 97.5])
    return {
        "beta1": round(beta1, 4),
        "mu_alpha": round(mu_alpha, 4),
        "tau_alpha": round(tau_alpha, 4),
        "population_median_p": round(float(_sigmoid(mu_alpha + beta1 * target_ddg)), 4),
        "empirical_median_p": round(float(q50), 4),
        "empirical_iqr_p": [round(float(q25), 4), round(float(q75), 4)],
        "empirical_range_p": [round(min(per_protein_p), 4), round(max(per_protein_p), 4)],
        "per_protein_p": [round(p, 4) for p in per_protein_p],
        "new_protein_predictive_ci95": [round(float(pred_lo), 4), round(float(pred_hi), 4)],
    }


def calibrate_at_ddg(
    protein_blocks: Sequence[tuple[np.ndarray, np.ndarray]],
    protein_ids: Sequence[str],
    target_ddg: float = CHILD_BURIED_DDG,
    n_draws: int = 2000,
    seed: int = 0,
) -> dict[str, Any]:
    """Cross-protein logistic calibration, LOPO validation, and cluster bootstrap CI."""
    b0, b1 = fit_weighted_logistic(protein_blocks)
    point_p = float(_sigmoid(b0 + b1 * target_ddg))

    lopo_folds: list[dict[str, Any]] = []
    for i, dms_id in enumerate(protein_ids):
        train = [b for j, b in enumerate(protein_blocks) if j != i]
        bx_test, by_test = protein_blocks[i]
        b0_i, b1_i = fit_weighted_logistic(train)
        p_target = float(_sigmoid(b0_i + b1_i * target_ddg))
        probs = np.asarray(_sigmoid(b0_i + b1_i * bx_test), dtype=float)
        brier = float(np.mean((probs - by_test) ** 2))
        lopo_folds.append(
            {
                "held_out_dms_id": dms_id,
                "beta0": round(b0_i, 4),
                "beta1": round(b1_i, 4),
                "p_low_at_target": round(p_target, 4),
                "brier_buried": round(brier, 4),
            }
        )

    lopo_ps = [f["p_low_at_target"] for f in lopo_folds]
    lopo_briers = [f["brier_buried"] for f in lopo_folds]

    rng = np.random.default_rng(seed)
    k_count = len(protein_blocks)
    boot_ps = np.empty(n_draws, dtype=float)
    for d in range(n_draws):
        idx = rng.choice(k_count, k_count, replace=True)
        b0_d, b1_d = fit_weighted_logistic([protein_blocks[j] for j in idx])
        boot_ps[d] = float(_sigmoid(b0_d + b1_d * target_ddg))
    ci_lo, ci_hi = np.percentile(boot_ps, [2.5, 97.5])

    return {
        "target_ddg_kcal_mol": target_ddg,
        "beta0": round(b0, 4),
        "beta1": round(b1, 4),
        "p_low_abundance": round(point_p, 4),
        "cluster_bootstrap_ci95": [round(float(ci_lo), 4), round(float(ci_hi), 4)],
        "lopo_median_p": round(float(np.median(lopo_ps)), 4),
        "lopo_range_p": [round(min(lopo_ps), 4), round(max(lopo_ps), 4)],
        "lopo_mean_brier": round(float(np.mean(lopo_briers)), 4),
        "lopo_median_brier": round(float(np.median(lopo_briers)), 4),
        "lopo_folds": lopo_folds,
        "random_intercept": fit_random_intercept(
            protein_blocks, target_ddg=target_ddg, n_draws=n_draws, seed=seed
        ),
    }


def transfer_to_bub1b(
    labelled_bub1b: pl.DataFrame,
    beta0: float,
    beta1: float,
) -> dict[str, Any]:
    """Zero-refit evaluation of the external calibration curve on published BUB1B alleles."""
    ddgs = labelled_bub1b["ddg"].to_list()
    ys = labelled_bub1b["y"].to_list()
    changes = labelled_bub1b["change"].to_list()
    rsas = labelled_bub1b["rsa"].to_list()
    plddts = labelled_bub1b["plddt"].to_list()
    regions = labelled_bub1b["region"].to_list()

    rows: list[dict[str, Any]] = []
    probs: list[float] = []
    for chg, y, ddg, rsa, plddt, reg in zip(changes, ys, ddgs, rsas, plddts, regions, strict=True):
        p = float(_sigmoid(beta0 + beta1 * float(ddg)))
        probs.append(p)
        rows.append(
            {
                "change": str(chg),
                "label": "abundance-lowering" if int(y) == 1 else "stable",
                "y": int(y),
                "ddg": round(float(ddg), 3),
                "rsa": round(float(rsa), 3),
                "plddt": round(float(plddt), 1),
                "region": str(reg),
                "external_p_low_abundance": round(p, 4),
            }
        )
    brier = float(np.mean((np.asarray(probs) - np.asarray(ys)) ** 2))
    kinase_rows = [r for r in rows if r["change"] != "Y155C"]
    kinase_y = [r["y"] for r in kinase_rows]
    kinase_ddg = [r["ddg"] for r in kinase_rows]
    return {
        "n_alleles": len(rows),
        "auroc_all_8": round(fast_auroc(ddgs, ys), 4),
        "post_hoc_auroc_without_y155c": round(fast_auroc(kinase_ddg, kinase_y), 4),
        "external_brier_all_8": round(brier, 4),
        "alleles": rows,
    }


def apply_gate(
    n_proteins: int, aucs_b: np.ndarray, ci_b: np.ndarray, cal: dict[str, Any]
) -> tuple[str, str]:
    """The frozen inclusion gate (protocol): returns ``(letter, verdict)``."""
    # Protocol gate: discrimination first, then the new-protein predictive interval (not the
    # cluster-bootstrap CI of the pooled curve, which measures the average protein only).
    discriminates = n_proteins >= 5 and float(np.median(aucs_b)) >= 0.70 and float(ci_b[0]) > 0.55
    pred_lo, pred_hi = cal["random_intercept"]["new_protein_predictive_ci95"]
    excludes_half = pred_lo > 0.50 or pred_hi < 0.50
    if discriminates and excludes_half:
        gate, verdict = (
            "A",
            (
                "Gate A (Informative): median buried AUROC >= 0.70 with CI lower bound > 0.55, "
                "and the new-protein predictive 95% interval at +1.55 kcal/mol excludes 0.50."
            ),
        )
    elif discriminates:
        gate, verdict = (
            "B",
            (
                "Gate B (Predictor works, patient uncertain): median buried AUROC >= 0.70 with CI "
                "lower bound > 0.55, but the new-protein predictive 95% interval at "
                f"+1.55 kcal/mol [{pred_lo:.2f}, {pred_hi:.2f}] includes 0.50. "
                "The 55/45 prior is kept; the CHX-chase blot decides."
            ),
        )
    else:
        gate, verdict = "C", "Gate C (Null / weak): AUROC criteria not met."
    return gate, verdict


def evaluate_calibration(
    scores_df: pl.DataFrame,
    labelled_bub1b: pl.DataFrame,
    n_draws: int = 2000,
    seed: int = 0,
) -> dict[str, Any]:
    """Compute per-protein AUROCs, across-protein summaries, calibration, and BUB1B transfer."""
    per_protein: list[dict[str, Any]] = []
    blocks_all: list[tuple[np.ndarray, np.ndarray]] = []
    ids_all: list[str] = []
    blocks_intra: list[tuple[np.ndarray, np.ndarray]] = []
    ids_intra: list[str] = []

    for spec in CANDIDATE_ASSAYS:
        sub = scores_df.filter(pl.col("dms_id") == spec.dms_id)
        if sub.height == 0:
            continue
        bur = sub.filter(pl.col("buried_high_conf"))
        if bur.height < MIN_BURIED_VARIANTS:
            continue
        bx = bur["ddg"].to_numpy()
        by = bur["y_low_abundance"].to_numpy()
        bs = bur["dms_score"].to_numpy()
        if int((by == 1).sum()) == 0 or int((by == 0).sum()) == 0:
            continue
        ax = sub["ddg"].to_numpy()
        ay = sub["y_low_abundance"].to_numpy()
        as_ = sub["dms_score"].to_numpy()

        auc_b = fast_auroc(bx, by)
        lo_b, hi_b = fast_bootstrap_auroc(bx, by, n_draws=n_draws, seed=seed)
        auc_a = fast_auroc(ax, ay)
        lo_a, hi_a = fast_bootstrap_auroc(ax, ay, n_draws=n_draws, seed=seed)
        rho_b = float(spearmanr(-bx, bs).statistic)
        rho_a = float(spearmanr(-ax, as_).statistic)
        b0_p, b1_p = fit_weighted_logistic([(bx, by)])
        p155_p = float(_sigmoid(b0_p + b1_p * CHILD_BURIED_DDG))

        per_protein.append(
            {
                "dms_id": spec.dms_id,
                "uniprot": spec.uniprot,
                "gene": spec.gene,
                "assay_kind": spec.assay_kind,
                "intracellular_abundance": spec.intracellular_abundance,
                "n_all": int(sub.height),
                "n_buried": int(bur.height),
                "n_buried_low": int((by == 1).sum()),
                "n_buried_wt": int((by == 0).sum()),
                "auroc_buried": round(auc_b, 4),
                "auroc_buried_ci95": [round(lo_b, 4), round(hi_b, 4)],
                "auroc_all": round(auc_a, 4),
                "auroc_all_ci95": [round(lo_a, 4), round(hi_a, 4)],
                "spearman_buried": round(rho_b, 4),
                "spearman_all": round(rho_a, 4),
                "single_protein_p_at_1_55": round(p155_p, 4),
            }
        )
        blocks_all.append((bx, by))
        ids_all.append(spec.dms_id)
        if spec.intracellular_abundance:
            blocks_intra.append((bx, by))
            ids_intra.append(spec.dms_id)

    rng = np.random.default_rng(seed)
    aucs_b = np.array([p["auroc_buried"] for p in per_protein], dtype=float)
    aucs_a = np.array([p["auroc_all"] for p in per_protein], dtype=float)
    n_p = len(aucs_b)
    boot_b = [float(np.median(rng.choice(aucs_b, n_p, replace=True))) for _ in range(n_draws)]
    boot_a = [float(np.median(rng.choice(aucs_a, n_p, replace=True))) for _ in range(n_draws)]
    ci_b = np.percentile(boot_b, [2.5, 97.5])
    ci_a = np.percentile(boot_a, [2.5, 97.5])

    aucs_intra = np.array(
        [p["auroc_buried"] for p in per_protein if p["intracellular_abundance"]], dtype=float
    )
    boot_intra = [
        float(np.median(rng.choice(aucs_intra, len(aucs_intra), replace=True)))
        for _ in range(n_draws)
    ]
    ci_intra = np.percentile(boot_intra, [2.5, 97.5])

    cal_all = calibrate_at_ddg(blocks_all, ids_all, CHILD_BURIED_DDG, n_draws=n_draws, seed=seed)
    cal_intra = calibrate_at_ddg(
        blocks_intra, ids_intra, CHILD_BURIED_DDG, n_draws=n_draws, seed=seed
    )
    bub1b_transfer = transfer_to_bub1b(labelled_bub1b, cal_all["beta0"], cal_all["beta1"])

    gate, verdict = apply_gate(len(per_protein), aucs_b, ci_b, cal_all)
    return {
        "n_candidate_assays": len(CANDIDATE_ASSAYS),
        "n_surviving_proteins": len(per_protein),
        "n_total_single_variants": int(sum(p["n_all"] for p in per_protein)),
        "n_total_buried_variants": int(sum(p["n_buried"] for p in per_protein)),
        "excluded_under_50_buried": ["ERBB2_HUMAN_Elazar_2016", "LYAM1_HUMAN_Elazar_2016"],
        "summary_all_11_proteins": {
            "median_auroc_buried": round(float(np.median(aucs_b)), 4),
            "median_auroc_buried_ci95": [round(float(ci_b[0]), 4), round(float(ci_b[1]), 4)],
            "mean_auroc_buried": round(float(np.mean(aucs_b)), 4),
            "min_auroc_buried": round(float(np.min(aucs_b)), 4),
            "max_auroc_buried": round(float(np.max(aucs_b)), 4),
            "median_auroc_all_residues": round(float(np.median(aucs_a)), 4),
            "median_auroc_all_residues_ci95": [round(float(ci_a[0]), 4), round(float(ci_a[1]), 4)],
        },
        "summary_intracellular_7_proteins": {
            "n_proteins": len(ids_intra),
            "median_auroc_buried": round(float(np.median(aucs_intra)), 4),
            "median_auroc_buried_ci95": [
                round(float(ci_intra[0]), 4),
                round(float(ci_intra[1]), 4),
            ],
            "calibration_at_1_55": cal_intra,
        },
        "calibration_at_1_55": cal_all,
        "per_protein": per_protein,
        "bub1b_zero_refit_transfer": bub1b_transfer,
        "gate": {
            "gate": gate,
            "gate_a_informative": gate == "A",
            "verdict": verdict,
        },
    }
