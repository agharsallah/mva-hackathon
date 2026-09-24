"""Does a drug hypothesis survive a large screen nobody curated for this case?

The shape of the question is case-agnostic. Somebody hands you

* a **response matrix** — one number per (compound, cell line); lower usually means the
  drug killed that line harder,
* a **line annotation** — which lines belong to the group the hypothesis is about (a
  tumour lineage, a genotype, a score above a threshold), and
* a **drug list** — the candidates the hypothesis names.

and asks whether the candidates hit the group harder than everything else. That is one
rank test per drug, an effect size with a confidence interval, a multiplicity correction
over the drugs tested, and controls that show the pipeline is not manufacturing
selectivity. None of it knows about BUB1B, rhabdomyosarcoma or PRISM: the PRISM-specific
readers live in :mod:`mva.drugs.screen_replication_prism`, and the group is any
``set[str]`` of line ids the caller builds.

Software-engineer's reading: a response matrix is a sparse two-key table
``(item, line) -> float``; a contrast is a pure function from that table plus a membership
predicate to one row per item; everything here is deterministic given ``seed``.

Conventions fixed once, so a sign never has to be re-derived at a call site:

* ``lower_is_sensitive`` says which end of the metric means "the drug worked". Values are
  flipped once on the way in, so downstream every statistic is oriented **sensitivity-up**.
* :func:`cliffs_delta` is then always "in-group more sensitive is positive", and the
  one-sided p is always "in-group more sensitive".

Assumptions and limits that belong next to every number this module produces:

* Mann-Whitney tests a **stochastic ordering**, not a difference of means; with a handful
  of in-group lines it has little power, and a non-significant p is not evidence of no
  effect.
* The bootstrap CI is percentile over resampled groups. With n below ~10 it is wide and
  its coverage is approximate; report it, never round it away.
* Benjamini-Hochberg controls the false discovery rate over the family the caller passes.
  The family must be declared before the run, not chosen after seeing the p values.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Literal

import numpy as np
from scipy import stats

__all__ = [
    "Group",
    "ItemResult",
    "benjamini_hochberg",
    "bootstrap_delta_ci",
    "cliffs_delta",
    "contrast_item",
    "median_split",
    "negative_control_sample",
    "run_contrast",
    "with_adjusted",
]

#: Rows with fewer than this many lines on either side are reported, never tested: a
#: rank test on two observations is arithmetic, not evidence.
MIN_GROUP = 3


@dataclass(frozen=True)
class Group:
    """One contrast: which lines are inside, which are the comparison, and its name."""

    name: str
    inside: frozenset[str]
    outside: frozenset[str]
    in_label: str
    out_label: str
    definition: str
    """How membership was decided, in one sentence, for the provenance manifest."""

    def split(self, values: Mapping[str, float]) -> tuple[np.ndarray, np.ndarray]:
        """``(inside values, outside values)`` for the lines this item was measured on."""
        ins = [v for line, v in values.items() if line in self.inside]
        out = [v for line, v in values.items() if line in self.outside]
        return np.asarray(ins, dtype=float), np.asarray(out, dtype=float)


@dataclass(frozen=True)
class ItemResult:
    """One drug in one contrast. Every field is oriented sensitivity-up."""

    item_id: str
    item_name: str
    contrast: str
    n_in: int
    n_out: int
    median_in: float | None
    median_out: float | None
    delta: float | None
    """Cliff's delta, positive = the in-group was more sensitive. ``None`` if untested."""
    ci_low: float | None
    ci_high: float | None
    p_raw: float | None
    p_adjusted: float | None = None
    status: str = "tested"
    """``tested``, ``too-few-lines`` or ``absent`` — an unmeasured drug is a result."""


def cliffs_delta(inside: np.ndarray, outside: np.ndarray) -> float:
    """``P(in > out) - P(in < out)`` on sensitivity-up values; ties count as neither.

    +1 means every in-group line was more sensitive than every comparison line, -1 the
    reverse, 0 no ordering. Computed from the Mann-Whitney statistic so the effect size
    and the p value can never disagree about direction.
    """
    n_in, n_out = len(inside), len(outside)
    if n_in == 0 or n_out == 0:
        return float("nan")
    u = float(stats.mannwhitneyu(inside, outside, alternative="two-sided").statistic)
    return 2.0 * u / (n_in * n_out) - 1.0


def bootstrap_delta_ci(
    inside: np.ndarray,
    outside: np.ndarray,
    *,
    resamples: int = 2000,
    alpha: float = 0.05,
    seed: int = 0,
) -> tuple[float, float]:
    """Percentile bootstrap interval for :func:`cliffs_delta`, resampling both groups."""
    rng = np.random.default_rng(seed)
    n_in, n_out = len(inside), len(outside)
    draws = np.empty(resamples, dtype=float)
    for i in range(resamples):
        a = inside[rng.integers(0, n_in, n_in)]
        b = outside[rng.integers(0, n_out, n_out)]
        draws[i] = cliffs_delta(a, b)
    lo, hi = np.nanpercentile(draws, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi)


def contrast_item(
    item_id: str,
    item_name: str,
    values: Mapping[str, float],
    group: Group,
    *,
    lower_is_sensitive: bool = True,
    resamples: int = 2000,
    seed: int = 0,
    min_group: int = MIN_GROUP,
) -> ItemResult:
    """One drug against one contrast: medians, Cliff's delta with CI, one-sided p.

    The one-sided alternative is always "the in-group is more sensitive"; refutation of a
    hypothesis that predicts that direction therefore shows up as ``p`` near 1 together
    with a negative ``delta``, which is what the caller should report, not hide.
    """
    sign = -1.0 if lower_is_sensitive else 1.0
    oriented = {line: sign * value for line, value in values.items() if np.isfinite(value)}
    inside, outside = group.split(oriented)
    if len(inside) < min_group or len(outside) < min_group:
        return ItemResult(
            item_id=item_id,
            item_name=item_name,
            contrast=group.name,
            n_in=len(inside),
            n_out=len(outside),
            median_in=None,
            median_out=None,
            delta=None,
            ci_low=None,
            ci_high=None,
            p_raw=None,
            status="too-few-lines",
        )
    p = float(stats.mannwhitneyu(inside, outside, alternative="greater").pvalue)
    delta = cliffs_delta(inside, outside)
    lo, hi = bootstrap_delta_ci(inside, outside, resamples=resamples, seed=seed)
    return ItemResult(
        item_id=item_id,
        item_name=item_name,
        contrast=group.name,
        n_in=len(inside),
        n_out=len(outside),
        # Reported on the original scale the caller passed in, not the flipped one.
        median_in=float(sign * np.median(inside)),
        median_out=float(sign * np.median(outside)),
        delta=delta,
        ci_low=lo,
        ci_high=hi,
        p_raw=p,
    )


def run_contrast(
    responses: Mapping[str, Mapping[str, float]],
    group: Group,
    *,
    names: Mapping[str, str] | None = None,
    lower_is_sensitive: bool = True,
    resamples: int = 2000,
    seed: int = 0,
) -> list[ItemResult]:
    """:func:`contrast_item` over every item of ``responses``, in the order given.

    ``resamples = 0`` skips the bootstrap — used for the background sweep over thousands
    of drugs, where only the p value and the point effect size are wanted.
    """
    names = names or {}
    out: list[ItemResult] = []
    for i, (item_id, values) in enumerate(responses.items()):
        if resamples == 0:
            sign = -1.0 if lower_is_sensitive else 1.0
            oriented = {k: sign * v for k, v in values.items() if np.isfinite(v)}
            inside, outside = group.split(oriented)
            if len(inside) < MIN_GROUP or len(outside) < MIN_GROUP:
                out.append(
                    ItemResult(
                        item_id,
                        names.get(item_id, item_id),
                        group.name,
                        len(inside),
                        len(outside),
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        status="too-few-lines",
                    )
                )
                continue
            out.append(
                ItemResult(
                    item_id=item_id,
                    item_name=names.get(item_id, item_id),
                    contrast=group.name,
                    n_in=len(inside),
                    n_out=len(outside),
                    median_in=float(sign * np.median(inside)),
                    median_out=float(sign * np.median(outside)),
                    delta=cliffs_delta(inside, outside),
                    ci_low=None,
                    ci_high=None,
                    p_raw=float(stats.mannwhitneyu(inside, outside, alternative="greater").pvalue),
                )
            )
            continue
        out.append(
            contrast_item(
                item_id,
                names.get(item_id, item_id),
                values,
                group,
                lower_is_sensitive=lower_is_sensitive,
                resamples=resamples,
                seed=seed + i,
            )
        )
    return out


def benjamini_hochberg(p_values: Sequence[float]) -> list[float]:
    """Benjamini-Hochberg adjusted p values (q), monotone, clipped at 1.

    Step-up over the sorted p values: ``q_(i) = min_{j>=i} ( m * p_(j) / j , 1 )``.
    """
    m = len(p_values)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: p_values[i])
    adjusted = [0.0] * m
    running = 1.0
    for rank, idx in reversed(list(enumerate(order, start=1))):
        running = min(running, m * p_values[idx] / rank)
        adjusted[idx] = min(running, 1.0)
    return adjusted


def with_adjusted(results: Sequence[ItemResult]) -> list[ItemResult]:
    """Fill ``p_adjusted`` by BH **over exactly the results passed in**.

    The family is the caller's declaration, which is why this takes a list rather than
    scanning a table: a family chosen after seeing the p values is not a correction.
    Untested rows keep ``p_adjusted = None`` and are not counted in ``m``.
    """
    tested = [r for r in results if r.p_raw is not None]
    q = benjamini_hochberg([r.p_raw for r in tested if r.p_raw is not None])
    by_key = {(r.item_id, r.contrast): v for r, v in zip(tested, q, strict=True)}
    return [replace(r, p_adjusted=by_key.get((r.item_id, r.contrast))) for r in results]


def median_split(
    scores: Mapping[str, float],
    *,
    name: str,
    high_label: str = "high",
    low_label: str = "low",
    exclude_ties: bool = True,
    quantiles: tuple[float, float] | None = None,
) -> Group:
    """Split lines on a continuous annotation into an in-group (high) and a comparison.

    ``quantiles=None`` is the median split; lines exactly at the median are dropped when
    ``exclude_ties`` (the honest default for an integer score with many ties). Passing
    e.g. ``(1 / 3, 2 / 3)`` gives a tertile contrast and drops the middle band.
    """
    finite = {line: v for line, v in scores.items() if np.isfinite(v)}
    values = np.asarray(list(finite.values()), dtype=float)
    if quantiles is None:
        cut = float(np.median(values))
        inside = {line for line, v in finite.items() if v > cut}
        outside = {
            line for line, v in finite.items() if (v < cut or (v == cut and not exclude_ties))
        }
        definition = (
            f"median split at {cut:g} over the {len(finite)} annotated lines; "
            f"{'ties at the median dropped' if exclude_ties else 'ties assigned low'}"
        )
    else:
        lo_cut, hi_cut = (float(np.quantile(values, q)) for q in quantiles)
        inside = {line for line, v in finite.items() if v >= hi_cut}
        outside = {line for line, v in finite.items() if v <= lo_cut}
        definition = (
            f"quantile split over the {len(finite)} annotated lines: "
            f">= {hi_cut:g} vs <= {lo_cut:g} (middle band dropped)"
        )
    return Group(
        name=name,
        inside=frozenset(inside),
        outside=frozenset(outside),
        in_label=high_label,
        out_label=low_label,
        definition=definition,
    )


def negative_control_sample(
    universe: Iterable[str],
    *,
    exclude: Iterable[str],
    size: int,
    seed: int,
) -> list[str]:
    """A seeded random draw of items, for the "does this pipeline find hits anywhere?" band.

    The point of the band is calibration: if a pipeline reports 5 % of unrelated drugs
    below a one-sided 0.05, the test is behaving; far more means the contrast itself, not
    the drug, is producing the signal.
    """
    blocked = set(exclude)
    pool = sorted({item for item in universe if item not in blocked})
    rng = np.random.default_rng(seed)
    take = min(size, len(pool))
    picked = rng.choice(len(pool), size=take, replace=False)
    return [pool[int(i)] for i in sorted(picked)]


Alternative = Literal["in-group more sensitive"]
"""The only alternative this module tests; the orientation is handled by the sign flip."""
