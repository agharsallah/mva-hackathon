"""Drug-perturbation proteomics, the pure part: which perturbation raises a protein?

Input is a **perturbation proteome matrix**: rows are proteins (by gene symbol), columns are
perturbations (a compound at one dose, or one replicate), values are log2 fold change
against the vehicle (DMSO) control. Think of it as a ``dict[gene, vector over drugs]``.

The question for one target protein is not "which drug raises it most" - a drug that stops
cells dividing lowers every mitotic protein, and one that piles cells up in mitosis raises
them all. So each perturbation gets a **proliferation score** (median change over a declared
gene set, :mod:`.proteome_sets`), and the target's change is regressed on that score across
perturbations with ordinary least squares::

    target[d] = a + b * score[d] + residual[d]

``residual`` is the **proliferation-corrected response**; dividing it by a robust spread
(1.4826 x the median absolute deviation, which equals the standard deviation for normal
data but ignores a few huge outliers) gives a **robust z**. A **hit** is a perturbation
whose robust z clears a cut *and* whose raw change is positive: the protein actually went up,
not merely "fell less than expected".

The same model run over every protein gives each perturbation a **breadth**: the share of
all proteins that are hits under it. A drug that raises a quarter of the proteome (a
proteasome inhibitor) is not a specific lead for one protein, and breadth says so.

No I/O, no network, no gene or drug name is built in: every name comes from the caller.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

import numpy as np

__all__ = [
    "MAD_TO_SD",
    "ControlOutcome",
    "Fit",
    "ProteomeMatrix",
    "Response",
    "breadth",
    "control_outcome",
    "fit_corrected",
    "rank_responses",
    "robust_z",
    "score_correlations",
    "set_score",
    "z_matrix",
]

#: Scales a median absolute deviation to a standard deviation under normality.
MAD_TO_SD = 1.4826


@dataclass(frozen=True)
class ProteomeMatrix:
    """``values[i, j]`` = log2 fold change of ``genes[i]`` under ``perturbations[j]``."""

    genes: tuple[str, ...]
    perturbations: tuple[str, ...]
    values: np.ndarray
    source: str

    def __post_init__(self) -> None:
        if self.values.shape != (len(self.genes), len(self.perturbations)):
            raise ValueError("values must be genes x perturbations")
        if len(set(self.genes)) != len(self.genes):
            raise ValueError("gene symbols must be unique; collapse duplicates first")

    def index(self) -> dict[str, int]:
        return {g: i for i, g in enumerate(self.genes)}

    def row(self, gene: str) -> np.ndarray:
        return np.asarray(self.values[self.index()[gene]], dtype=float)

    def select(self, perturbations: Sequence[str]) -> ProteomeMatrix:
        where = {p: j for j, p in enumerate(self.perturbations)}
        cols = [where[p] for p in perturbations]
        return ProteomeMatrix(self.genes, tuple(perturbations), self.values[:, cols], self.source)


@dataclass(frozen=True)
class Fit:
    """One target's OLS fit on the proliferation score across perturbations."""

    target: str
    intercept: float
    slope: float
    r2: float
    n: int
    residual: np.ndarray
    z: np.ndarray


@dataclass(frozen=True)
class Response:
    """One perturbation's response of one target, raw and corrected."""

    perturbation: str
    raw: float
    score: float
    residual: float
    z: float
    rank: int
    hit: bool


@dataclass(frozen=True)
class ControlOutcome:
    """Did a textbook induction come out on top, for every named inducer?"""

    protein: str
    inducers: tuple[str, ...]
    ranks: dict[str, int | None]
    z: dict[str, float | None]
    universe: int
    cut_rank: int
    z_min: float
    passed: bool


def set_score(
    matrix: ProteomeMatrix, genes: Collection[str], *, min_members: int = 10
) -> tuple[np.ndarray, tuple[str, ...]]:
    """Median change over the set members the matrix holds, per perturbation.

    Returns ``(score, members used)``. A perturbation where fewer than ``min_members`` set
    proteins were quantified scores NaN rather than a number resting on two proteins.
    """
    index = matrix.index()
    used = tuple(g for g in genes if g in index)
    if len(used) < min_members:
        raise ValueError(f"only {len(used)} set members quantified (< {min_members})")
    block = matrix.values[[index[g] for g in used], :].astype(float)
    counts = np.sum(~np.isnan(block), axis=0)
    with np.errstate(all="ignore"):
        score = np.nanmedian(block, axis=0) if block.size else np.full(block.shape[1], np.nan)
    score = np.where(counts >= min_members, score, np.nan)
    return score, used


def robust_z(residual: np.ndarray) -> np.ndarray:
    """``residual / (1.4826 x MAD)``, NaN-aware; a zero spread gives NaN, never infinity."""
    finite = residual[np.isfinite(residual)]
    if finite.size == 0:
        return np.full_like(residual, np.nan)
    spread = MAD_TO_SD * float(np.median(np.abs(finite - np.median(finite))))
    if spread == 0:
        return np.full_like(residual, np.nan)
    return (residual - float(np.median(finite))) / spread


def fit_corrected(target: str, y: np.ndarray, score: np.ndarray) -> Fit:
    """OLS of ``y`` on ``score`` over perturbations where both are finite.

    Perturbations missing either value keep a NaN residual; they are not imputed.
    """
    ok = np.isfinite(y) & np.isfinite(score)
    n = int(ok.sum())
    if n < 3:
        raise ValueError(f"{target}: fewer than 3 perturbations with a value and a score")
    x = score[ok]
    design = np.column_stack([np.ones(n), x])
    coef, *_ = np.linalg.lstsq(design, y[ok], rcond=None)
    fitted = design @ coef
    ss_res = float(np.sum((y[ok] - fitted) ** 2))
    ss_tot = float(np.sum((y[ok] - y[ok].mean()) ** 2))
    residual = np.full_like(y, np.nan, dtype=float)
    residual[ok] = y[ok] - fitted
    return Fit(
        target=target,
        intercept=float(coef[0]),
        slope=float(coef[1]),
        r2=1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0,
        n=n,
        residual=residual,
        z=robust_z(residual),
    )


def rank_responses(
    matrix: ProteomeMatrix, fit: Fit, score: np.ndarray, *, z_min: float
) -> list[Response]:
    """Every perturbation for ``fit.target``, best corrected response first (rank 1).

    Perturbations with no residual are listed last with rank 0 and never a hit.
    """
    raw = matrix.row(fit.target)
    order = sorted(
        range(len(matrix.perturbations)),
        key=lambda j: (not np.isfinite(fit.z[j]), -(fit.z[j] if np.isfinite(fit.z[j]) else 0.0)),
    )
    out: list[Response] = []
    for position, j in enumerate(order, start=1):
        finite = bool(np.isfinite(fit.z[j]))
        out.append(
            Response(
                perturbation=matrix.perturbations[j],
                raw=float(raw[j]),
                score=float(score[j]),
                residual=float(fit.residual[j]),
                z=float(fit.z[j]),
                rank=position if finite else 0,
                hit=finite and fit.z[j] >= z_min and raw[j] > 0,
            )
        )
    return out


def z_matrix(matrix: ProteomeMatrix, score: np.ndarray, *, min_n: int = 10) -> np.ndarray:
    """The robust z of every protein under every perturbation (one OLS per protein).

    Vectorised per missingness pattern would be faster; a plain loop over ~10,000 proteins
    is a few seconds and easier to trust. Proteins with fewer than ``min_n`` usable
    perturbations are NaN throughout.
    """
    out = np.full(matrix.values.shape, np.nan)
    for i, gene in enumerate(matrix.genes):
        y = np.asarray(matrix.values[i], dtype=float)
        if int(np.sum(np.isfinite(y) & np.isfinite(score))) < min_n:
            continue
        out[i] = fit_corrected(gene, y, score).z
    return out


def breadth(zmat: np.ndarray, raw: np.ndarray, *, z_min: float) -> np.ndarray:
    """Per perturbation: the share of quantified proteins that are hits under it."""
    hits = (zmat >= z_min) & (raw > 0)
    quantified = np.sum(np.isfinite(zmat), axis=0)
    with np.errstate(all="ignore"):
        share = np.sum(hits, axis=0) / quantified
    return np.where(quantified > 0, share, np.nan)


def control_outcome(
    protein: str,
    inducers: Sequence[str],
    responses: Sequence[Response],
    *,
    top_fraction: float,
    z_min: float,
) -> ControlOutcome:
    """Pass when **every** named inducer is a hit inside the top ``top_fraction`` of ranks.

    An inducer the dataset does not hold, or holds without a value, fails the control:
    absence is never read as a pass.
    """
    ranked = [r for r in responses if r.rank > 0]
    universe = len(ranked)
    cut = max(1, int(np.floor(top_fraction * universe)))
    by_name: Mapping[str, Response] = {r.perturbation: r for r in ranked}
    ranks: dict[str, int | None] = {}
    zs: dict[str, float | None] = {}
    ok = bool(inducers)
    for name in inducers:
        hit = by_name.get(name)
        ranks[name] = hit.rank if hit else None
        zs[name] = round(hit.z, 3) if hit else None
        ok = ok and bool(hit and hit.hit and hit.rank <= cut)
    return ControlOutcome(protein, tuple(inducers), ranks, zs, universe, cut, z_min, ok)


def score_correlations(matrix: ProteomeMatrix, score: np.ndarray, *, min_n: int = 10) -> np.ndarray:
    """Pearson r of every protein with the score across perturbations (NaN when < ``min_n``).

    Descriptive: it places one target among all proteins ("how cell-cycle-bound is it?").
    """
    out = np.full(len(matrix.genes), np.nan)
    for i in range(len(matrix.genes)):
        y = np.asarray(matrix.values[i], dtype=float)
        ok = np.isfinite(y) & np.isfinite(score)
        if int(ok.sum()) >= min_n and float(np.std(y[ok])) > 0:
            out[i] = float(np.corrcoef(y[ok], score[ok])[0, 1])
    return out
