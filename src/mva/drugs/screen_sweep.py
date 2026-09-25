"""Screen-wide: run the same rank contrast over *every* eligible compound, not a shortlist.

:mod:`mva.drugs.screen_replication` asks whether a named list of drugs hits a group of cell
lines harder than the rest. A sweep asks the unbiased version of that question: over every
compound a screen measured well enough, which ones does the contrast single out, once the
multiplicity of testing all of them is paid for? Nothing here is new statistics — every
number comes from :func:`~mva.drugs.screen_replication.contrast_item` (one-sided
Mann-Whitney U, Cliff's delta, percentile bootstrap CI) and
:func:`~mva.drugs.screen_replication.with_adjusted` (Benjamini-Hochberg), unchanged. What
this module adds is the bookkeeping a sweep needs:

* **eligibility** — a compound enters only if it was measured on at least ``min_in`` lines
  inside *and* ``min_out`` outside every contrast (fixed before the run, per contrast);
* **one drug, one test** — a drug with several copies (batches, sub-screens) contributes
  exactly one *representative* copy to the family, chosen by entry 151's rule (the copy
  measured on most in-group lines), so duplicates never inflate ``m``;
* **rank and percentile** — rank by one-sided p (ties by larger delta, then id) and the
  delta percentile among the family, the two views a reader needs to place one drug.

Software-engineer's reading: a sweep is a ``map`` of a pure function over the rows of a
matrix, followed by a ``group_by(drug)`` that keeps one row per group and a vectorised BH
over what is left. It is deterministic given ``seed``: each copy's bootstrap seed is
``seed + its index in the sorted eligible list``, so the answer does not depend on how many
worker processes ran it.
"""

from __future__ import annotations

import math
import os
from collections.abc import Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace

import numpy as np
from scipy import stats

from mva.drugs.screen_replication import (
    MIN_GROUP,
    Group,
    ItemResult,
    contrast_item,
    run_contrast,
    with_adjusted,
)
from mva.drugs.screen_replication_report import Screen, representative

__all__ = [
    "Eligibility",
    "FamilyRow",
    "eligible_items",
    "family",
    "measured_counts",
    "opposite_p",
    "sweep_contrast",
    "top_k",
]


@dataclass(frozen=True)
class Eligibility:
    """The minimum number of measured lines on each side of one contrast."""

    group: Group
    min_in: int
    min_out: int


@dataclass(frozen=True)
class FamilyRow:
    """One copy of one drug in one contrast, with its family bookkeeping."""

    result: ItemResult
    drug: str
    representative: bool
    rank: int | None
    """1 = smallest one-sided p among the representatives; ``None`` for other copies."""
    percentile: float | None
    """Share of representatives (x100) whose delta is <= this copy's delta."""


def measured_counts(screen: Screen, group: Group) -> tuple[np.ndarray, np.ndarray]:
    """``(inside, outside)`` finite-value counts for every item, vectorised over the matrix."""
    lines = np.asarray(screen.lines)
    finite = np.isfinite(screen.matrix)
    inside = finite[:, np.isin(lines, sorted(group.inside))].sum(axis=1)
    outside = finite[:, np.isin(lines, sorted(group.outside))].sum(axis=1)
    return inside, outside


def eligible_items(
    screen: Screen, candidates: Sequence[str], rules: Sequence[Eligibility]
) -> list[str]:
    """The candidates that meet **every** rule, sorted by id (which fixes the seeds)."""
    wanted = set(candidates)
    keep = np.isin(np.asarray(screen.item_ids), sorted(wanted))
    for rule in rules:
        inside, outside = measured_counts(screen, rule.group)
        keep &= (inside >= rule.min_in) & (outside >= rule.min_out)
    return sorted(i for i, k in zip(screen.item_ids, keep, strict=True) if k)


def _one(job: tuple[str, str, list[str], np.ndarray, Group, int, int]) -> ItemResult:
    item_id, name, lines, row, group, resamples, seed = job
    values = dict(zip(lines, (float(v) for v in row), strict=True))
    if resamples == 0:  # entry 151's no-bootstrap path: p and point delta only
        return run_contrast({item_id: values}, group, names={item_id: name}, resamples=0)[0]
    return contrast_item(item_id, name, values, group, resamples=resamples, seed=seed)


def sweep_contrast(
    screen: Screen,
    group: Group,
    items: Sequence[str],
    names: Mapping[str, str],
    *,
    seed: int,
    resamples: int,
    workers: int | None = None,
) -> list[ItemResult]:
    """:func:`contrast_item` for every item, in the order given, seed ``seed + index``.

    ``workers > 1`` fans the rows out over processes; results are identical to a serial
    run because each row's seed is fixed by its position, never by scheduling.
    """
    index = {item: i for i, item in enumerate(screen.item_ids)}
    jobs = [
        (
            item,
            names.get(item, item),
            screen.lines,
            screen.matrix[index[item]],
            group,
            resamples,
            seed + i,
        )
        for i, item in enumerate(items)
    ]
    workers = workers if workers is not None else max(1, (os.cpu_count() or 2) - 1)
    if workers <= 1 or len(jobs) < 50:
        return [_one(job) for job in jobs]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_one, jobs, chunksize=16))


def family(
    screen: Screen,
    group: Group,
    results: Sequence[ItemResult],
    drug_of: Mapping[str, str],
) -> list[FamilyRow]:
    """Representative per drug (entry 151's rule), BH over the representatives, rank, percentile.

    The family is exactly the representatives of the drugs passed in: every eligible drug
    counts once, whatever its p value, and the family is declared by the eligibility rule,
    not by the results.
    """
    by_drug: dict[str, list[str]] = {}
    for r in results:
        by_drug.setdefault(drug_of[r.item_id], []).append(r.item_id)
    reps = {rep for ids in by_drug.values() if (rep := representative(screen, ids, group))}
    tested = [r for r in results if r.item_id in reps and r.p_raw is not None]
    adjusted = {r.item_id: r for r in with_adjusted(tested)}
    order = sorted(
        tested, key=lambda r: (r.p_raw, -(r.delta if r.delta is not None else -2.0), r.item_id)
    )
    rank = {r.item_id: i for i, r in enumerate(order, start=1)}
    deltas = np.asarray([r.delta for r in tested if r.delta is not None], dtype=float)
    out: list[FamilyRow] = []
    for r in results:
        final = adjusted.get(r.item_id, r)
        pct = (
            float((deltas <= r.delta).mean() * 100) if r.delta is not None and deltas.size else None
        )
        out.append(
            FamilyRow(
                result=replace(r, p_adjusted=final.p_adjusted),
                drug=drug_of[r.item_id],
                representative=r.item_id in reps,
                rank=rank.get(r.item_id),
                percentile=pct,
            )
        )
    return out


def opposite_p(
    screen: Screen, group: Group, items: Sequence[str], *, lower_is_sensitive: bool = True
) -> dict[str, float | None]:
    """One-sided p for the **other** direction ("the in-group is less sensitive") per item.

    The registered test is one-sided, so a drug pointing the wrong way only shows as p near
    1; a contrary-direction check needs its own p. Same orientation, same rank test.
    """
    sign = -1.0 if lower_is_sensitive else 1.0
    index = {item: i for i, item in enumerate(screen.item_ids)}
    out: dict[str, float | None] = {}
    for item in items:
        values = {
            line: sign * float(v)
            for line, v in zip(screen.lines, screen.matrix[index[item]], strict=True)
            if np.isfinite(v)
        }
        inside, outside = group.split(values)
        if len(inside) < MIN_GROUP or len(outside) < MIN_GROUP:
            out[item] = None
            continue
        out[item] = float(stats.mannwhitneyu(inside, outside, alternative="less").pvalue)
    return out


def top_k(n: int, fraction: float) -> int:
    """How many drugs "the top ``fraction``" of ``n`` is: ``ceil(fraction * n)``, at least 1."""
    return max(1, math.ceil(fraction * n)) if n else 0
