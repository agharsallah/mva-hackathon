"""Cell-cycle-corrected expression signatures: read, correct, compare. Pure numpy, no network.

Entry 153 queried LINCS with a BUB1B-knockout signature whose strongest genes were a
proliferation drop and a p53/p21 arrest - the response most essential-gene knockouts share.
Its positive control (does BUB1B loss look like loss of the other checkpoint genes?) failed.
This module removes the shared cell-cycle component and asks the same question again.

A **consensus matrix** here is rows = perturbations (one knockout, or one compound), columns
= measured genes, values = LINCS characteristic-direction coefficients (signed change).

The correction is the one single-cell tools use (Seurat's ``vars.to.regress``), turned on
its side: every perturbation gets an **S score** and a **G2/M score** (mean coefficient over
the Tirosh 2016 lists, :mod:`.proteome_sets`), and each gene's column is regressed on the two
scores across all perturbations::

    coef[p, g] = a_g + b_g * S[p] + c_g * G2M[p] + residual[p, g]

The residual matrix is the **cell-cycle-corrected** signature set. A sensitivity variant
removes the top ``k`` principal components instead (the dominant shared axes, whatever
they are). Two perturbations are then compared by the Pearson correlation of their rows.

Nothing here names BUB1B, LINCS or a drug: every label comes from the caller.
"""

from __future__ import annotations

import gzip
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

__all__ = [
    "Consensus",
    "ControlResult",
    "cc_residuals",
    "pc_residuals",
    "read_consensus",
    "row_scores",
    "sibling_control",
    "similarity",
]


@dataclass(frozen=True)
class Consensus:
    """``values[i, j]`` = coefficient of gene ``columns[j]`` under perturbation ``rows[i]``."""

    rows: tuple[str, ...]
    columns: tuple[str, ...]
    values: np.ndarray

    def col(self, names: Sequence[str]) -> np.ndarray:
        where = {c: j for j, c in enumerate(self.columns)}
        return self.values[:, [where[n] for n in names]]

    def row_index(self) -> dict[str, int]:
        return {r: i for i, r in enumerate(self.rows)}


@dataclass(frozen=True)
class ControlResult:
    """Where named sibling perturbations land among all others, by similarity to the query."""

    query: str
    siblings_named: tuple[str, ...]
    siblings_present: tuple[str, ...]
    ranks: dict[str, int]
    percentiles: dict[str, float]
    universe: int
    cut: float
    any_in_cut: bool
    mean_percentile: float
    permutation_p: float
    draws: int
    passed: bool


def read_consensus(
    path: Path,
    columns: Collection[str],
    *,
    keep_row: Callable[[str], bool] = lambda _label: True,
    progress: Callable[[int], None] = lambda _n: None,
) -> Consensus:
    """Stream a gzipped rows x genes TSV, keeping only ``columns`` (and rows ``keep_row`` accepts).

    The first header cell is the (empty) row-label header. Columns the file lacks are
    skipped, so the returned ``columns`` may be a subset; the caller checks what it needs.
    """
    with gzip.open(path, "rt") as handle:
        header = handle.readline().rstrip("\n").split("\t")[1:]
        wanted = set(columns)
        idx = [j for j, g in enumerate(header) if g in wanted]
        take = np.array(idx, dtype=np.int64)
        labels: list[str] = []
        blocks: list[np.ndarray] = []
        for n, line in enumerate(handle, start=1):
            label, _, rest = line.rstrip("\n").partition("\t")
            if not keep_row(label):
                continue
            values = np.array(rest.split("\t"), dtype=object)[take]
            blocks.append(np.array(values, dtype=np.float32))
            labels.append(label)
            if n % 2000 == 0:
                progress(n)
    matrix = np.vstack(blocks) if blocks else np.zeros((0, len(idx)), dtype=np.float32)
    return Consensus(tuple(labels), tuple(header[j] for j in idx), matrix)


def row_scores(consensus: Consensus, members: Sequence[str]) -> np.ndarray:
    """Mean coefficient over ``members`` per row (members the matrix lacks are ignored)."""
    present = [m for m in members if m in set(consensus.columns)]
    if not present:
        raise ValueError("no score member present in the matrix")
    return np.asarray(np.nanmean(consensus.col(present), axis=1), dtype=float)


def cc_residuals(y: np.ndarray, covariates: Sequence[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    """Regress every column of ``y`` on ``[1, *covariates]`` across rows; ``(residual, r2)``.

    NaN cells are set to the column mean before the fit (LINCS consensus rows have none;
    the guard keeps a stray NaN from poisoning a whole column).
    """
    y = np.asarray(y, dtype=float)
    col_mean = np.nanmean(y, axis=0)
    y = np.where(np.isnan(y), col_mean, y)
    design = np.column_stack([np.ones(y.shape[0]), *covariates])
    coef, *_ = np.linalg.lstsq(design, y, rcond=None)
    residual = y - design @ coef
    ss_tot = np.sum((y - y.mean(axis=0)) ** 2, axis=0)
    with np.errstate(all="ignore"):
        r2 = np.where(ss_tot > 0, 1 - np.sum(residual**2, axis=0) / ss_tot, 0.0)
    return residual, r2


def pc_residuals(y: np.ndarray, k: int) -> np.ndarray:
    """Remove the top ``k`` principal components of column-centred ``y`` (sensitivity)."""
    centred = np.asarray(y, dtype=float) - np.nanmean(y, axis=0)
    centred = np.asarray(np.nan_to_num(centred), dtype=float)
    if k <= 0:
        return centred
    u, s, vt = np.linalg.svd(centred, full_matrices=False)
    return np.asarray(centred - (u[:, :k] * s[:k]) @ vt[:k], dtype=float)


def similarity(matrix: np.ndarray, query: np.ndarray) -> np.ndarray:
    """Pearson r of ``query`` with every row of ``matrix`` (NaN for a constant row)."""
    m = matrix - matrix.mean(axis=1, keepdims=True)
    q = query - query.mean()
    denom = np.linalg.norm(m, axis=1) * np.linalg.norm(q)
    with np.errstate(all="ignore"):
        return np.where(denom > 0, (m @ q) / denom, np.nan)


def sibling_control(
    labels: Sequence[str],
    sims: np.ndarray,
    query: str,
    siblings: Sequence[str],
    *,
    cut: float,
    draws: int,
    seed: int,
    alpha: float = 0.05,
) -> ControlResult:
    """Rank every other perturbation by similarity (1 = most alike) and test the siblings.

    Pass needs both: (i) any present sibling inside the top ``cut`` share (entry 153's
    rule), and (ii) the siblings' mean percentile beats ``draws`` random same-size sets drawn
    from the same universe at ``p < alpha``. Rule (i) alone passes by chance ~1-(1-cut)^n of
    the time; (ii) is the calibrated part.
    """
    others = [(lab, float(s)) for lab, s in zip(labels, sims, strict=True) if lab != query]
    others = [(lab, s) for lab, s in others if np.isfinite(s)]
    others.sort(key=lambda item: -item[1])
    universe = len(others)
    rank = {lab: i for i, (lab, _) in enumerate(others, start=1)}
    present = tuple(s for s in siblings if s in rank)
    pct = {s: rank[s] / universe for s in present}
    any_in = any(v <= cut for v in pct.values())
    if not present:
        return ControlResult(query, tuple(siblings), (), {}, {}, universe, cut, False,
                             float("nan"), float("nan"), draws, False)  # fmt: skip
    observed = float(np.mean(list(pct.values())))
    rng = np.random.default_rng(seed)
    ranks = np.arange(1, universe + 1) / universe
    null = np.array(
        [np.mean(rng.choice(ranks, size=len(present), replace=False)) for _ in range(draws)]
    )
    p = float((np.sum(null <= observed) + 1) / (draws + 1))
    return ControlResult(
        query=query,
        siblings_named=tuple(siblings),
        siblings_present=present,
        ranks={s: rank[s] for s in present},
        percentiles={s: round(v * 100, 2) for s, v in pct.items()},
        universe=universe,
        cut=cut,
        any_in_cut=any_in,
        mean_percentile=round(observed * 100, 2),
        permutation_p=round(p, 5),
        draws=draws,
        passed=any_in and p < alpha,
    )
