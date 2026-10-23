"""Exact AUROC and its stratified bootstrap interval for the abundance calibration."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from scipy.stats import rankdata

__all__ = ["fast_auroc", "fast_bootstrap_auroc"]


def fast_auroc(scores: Sequence[float] | np.ndarray, labels: Sequence[int] | np.ndarray) -> float:
    """Exact Mann-Whitney AUROC in O(N log N) via average ranks (ties = 0.5)."""
    s = np.asarray(scores, dtype=float)
    y = np.asarray(labels, dtype=int)
    n1 = int((y == 1).sum())
    n0 = int((y == 0).sum())
    if n1 == 0 or n0 == 0:
        raise ValueError("AUROC requires at least one positive and one negative observation")
    ranks = rankdata(s, method="average")
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def fast_bootstrap_auroc(
    scores: Sequence[float] | np.ndarray,
    labels: Sequence[int] | np.ndarray,
    n_draws: int = 2000,
    seed: int = 0,
) -> tuple[float, float]:
    """Stratified bootstrap 95 % percentile interval for AUROC."""
    rng = np.random.default_rng(seed)
    s = np.asarray(scores, dtype=float)
    y = np.asarray(labels, dtype=int)
    pos, neg = s[y == 1], s[y == 0]
    n1, n0 = len(pos), len(neg)
    yy = np.concatenate([np.ones(n1, dtype=int), np.zeros(n0, dtype=int)])
    draws = np.empty(n_draws, dtype=float)
    for i in range(n_draws):
        p = rng.choice(pos, n1, replace=True)
        q = rng.choice(neg, n0, replace=True)
        draws[i] = fast_auroc(np.concatenate([p, q]), yy)
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return float(lo), float(hi)
