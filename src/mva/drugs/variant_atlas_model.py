"""Small-n classification on a variant atlas: AUROC, a bootstrap interval, ridge logistic LOO.

Built for the case where a handful of published alleles carry a label (here: does the
substitution lower the protein's abundance, or leave it stable?) and the question is whether
a predicted score separates the two classes. Everything is transparent and pre-set:

* **AUROC** (area under the receiver-operating-characteristic curve) = the probability that
  a randomly chosen positive scores above a randomly chosen negative (ties count half). 0.5 =
  a coin, 1.0 = perfect separation. With 5 vs 3 alleles there are only 15 pairs, so the value
  moves in steps of 1/15 and its interval is wide — the bootstrap says how wide.
* **Ridge logistic regression** (a straight-line score squashed to a probability, with a
  penalty ``l2`` pulling coefficients toward zero so 8 points cannot be fitted perfectly),
  features standardised inside each training fold, Newton–Raphson (IRLS). ``l2 = 1`` is fixed
  in advance, never tuned.
* **Leave-one-out (LOO)**: each allele is scored by a model fitted without it — the only
  honest out-of-sample estimate at this size.

Pure numpy; no scikit-learn, no randomness except the seeded bootstrap.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

__all__ = [
    "Fit",
    "auroc",
    "bootstrap_auroc",
    "fit_logistic",
    "loo_probabilities",
    "percentile_rank",
    "roc_points",
]

#: The ridge penalty, fixed before any fit (E1 plan, entry 149). Not tuned.
L2 = 1.0


def auroc(scores: Sequence[float], labels: Sequence[int]) -> float:
    """P(score of a positive > score of a negative), ties = ½. ``labels`` are 1/0."""
    pos = [s for s, y in zip(scores, labels, strict=True) if y == 1]
    neg = [s for s, y in zip(scores, labels, strict=True) if y == 0]
    if not pos or not neg:
        raise ValueError("AUROC needs at least one allele of each class")
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return float(wins) / (len(pos) * len(neg))


def bootstrap_auroc(
    scores: Sequence[float], labels: Sequence[int], n: int = 2000, seed: int = 0
) -> tuple[float, float]:
    """Stratified bootstrap (resample within each class) → 95 % percentile interval."""
    rng = np.random.default_rng(seed)
    s, y = np.asarray(scores, dtype=float), np.asarray(labels, dtype=int)
    pos, neg = s[y == 1], s[y == 0]
    draws = []
    for _ in range(n):
        p = rng.choice(pos, len(pos), replace=True)
        q = rng.choice(neg, len(neg), replace=True)
        draws.append(((p[:, None] > q[None, :]) + 0.5 * (p[:, None] == q[None, :])).mean())
    low, high = np.percentile(draws, [2.5, 97.5])
    return float(low), float(high)


def roc_points(scores: Sequence[float], labels: Sequence[int]) -> list[tuple[float, float]]:
    """``(false-positive rate, true-positive rate)`` at every threshold, from (0,0) to (1,1)."""
    s, y = np.asarray(scores, dtype=float), np.asarray(labels, dtype=int)
    points = [(0.0, 0.0)]
    for cut in sorted(set(s.tolist()), reverse=True):
        called = s >= cut
        points.append(
            (float((called & (y == 0)).sum() / (y == 0).sum()),
             float((called & (y == 1)).sum() / (y == 1).sum()))
        )  # fmt: skip
    if points[-1] != (1.0, 1.0):
        points.append((1.0, 1.0))
    return points


@dataclass(frozen=True)
class Fit:
    """A fitted ridge logistic model, with the standardisation it was fitted under."""

    mean: np.ndarray
    scale: np.ndarray
    coef: np.ndarray  # intercept first
    features: tuple[str, ...]

    def probability(self, x: Sequence[float]) -> float:
        z = (np.asarray(x, dtype=float) - self.mean) / self.scale
        return float(1 / (1 + np.exp(-(self.coef[0] + z @ self.coef[1:]))))


def fit_logistic(
    rows: Sequence[Sequence[float]],
    labels: Sequence[int],
    features: Sequence[str],
    l2: float = L2,
    iterations: int = 100,
) -> Fit:
    """Ridge logistic regression by IRLS; the intercept is not penalised."""
    x = np.asarray(rows, dtype=float)
    y = np.asarray(labels, dtype=float)
    mean = x.mean(0)
    scale = x.std(0)
    scale[scale == 0] = 1.0
    design = np.column_stack([np.ones(len(x)), (x - mean) / scale])
    penalty = np.eye(design.shape[1]) * l2
    penalty[0, 0] = 0.0
    beta = np.zeros(design.shape[1])
    for _ in range(iterations):
        p = 1 / (1 + np.exp(-(design @ beta)))
        weight = p * (1 - p)
        gradient = design.T @ (y - p) - penalty @ beta
        hessian = design.T @ (design * weight[:, None]) + penalty
        step = np.linalg.solve(hessian, gradient)
        beta = beta + step
        if np.abs(step).max() < 1e-10:
            break
    return Fit(mean, scale, beta, tuple(features))


def loo_probabilities(
    rows: Sequence[Sequence[float]], labels: Sequence[int], features: Sequence[str],
    l2: float = L2,
) -> list[float]:  # fmt: skip
    """Each row's probability from a model fitted on every other row."""
    out = []
    for i in range(len(rows)):
        keep = [j for j in range(len(rows)) if j != i]
        fit = fit_logistic([rows[j] for j in keep], [labels[j] for j in keep], features, l2)
        out.append(fit.probability(rows[i]))
    return out


def percentile_rank(values: Sequence[float], x: float) -> float:
    """Mid-rank percentile of ``x`` in ``values``: % below plus half the % equal, 0–100."""
    v = np.asarray(values, dtype=float)
    return float(100 * ((v < x).mean() + 0.5 * (v == x).mean()))
