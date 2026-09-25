"""Do independent generators name the same drugs more often than chance?

*Plain words.* Each generator (:mod:`mva.drugs.convergence_tables`) proposes a list of
approved drugs drawn from its own universe of drugs it could have proposed. The **statistic**
is the number of drugs named by at least ``k`` generators (``k = 2`` in step 10). The
**permutation null** asks what that count looks like when every list is replaced by a random
list of the same size drawn from the same universe - the generators keep their sizes and
their reach, and lose only whatever makes them agree. The one-sided p value is the share of
draws whose count reaches the observed one, with the standard ``+1`` correction so a p value
is never exactly zero::

    p = (1 + #{draws with count >= observed}) / (1 + draws)

An exclusion set (step 10: dasatinib, known before the join) is removed from every list *and*
every universe, so the "without" run is the same test on the smaller problem, not the same
null with one drug hidden.

Pure: numpy only, seeded, no I/O.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from .convergence_tables import GeneratorList

__all__ = [
    "ConvergenceResult",
    "converging",
    "membership",
    "null_counts",
    "pairwise",
    "run",
    "statistic",
]


def membership(lists: Sequence[GeneratorList], exclude: Iterable[str] = ()) -> dict[str, list[str]]:
    """``{drug: [generator ids that name it]}`` over approved rows, exclusions removed."""
    skip = set(exclude)
    out: dict[str, list[str]] = {}
    for item in lists:
        for drug in sorted(item.drugs - skip):
            out.setdefault(drug, []).append(item.generator)
    return out


def statistic(sets: Sequence[Iterable[str]], k: int = 2) -> int:
    """How many drugs appear in at least ``k`` of ``sets``."""
    counts: dict[str, int] = {}
    for items in sets:
        for drug in set(items):
            counts[drug] = counts.get(drug, 0) + 1
    return sum(1 for n in counts.values() if n >= k)


def converging(
    lists: Sequence[GeneratorList], k: int = 2, exclude: Iterable[str] = ()
) -> list[str]:
    """The drugs named by at least ``k`` generators, sorted by generator count then name."""
    named = membership(lists, exclude)
    hits = [d for d, gens in named.items() if len(gens) >= k]
    return sorted(hits, key=lambda d: (-len(named[d]), d))


def null_counts(
    sizes: Sequence[int],
    universes: Sequence[Sequence[str]],
    *,
    k: int = 2,
    draws: int = 10_000,
    seed: int = 0,
) -> np.ndarray:
    """The statistic under ``draws`` random re-draws, one list per universe.

    ``universes[i]`` is sampled without replacement to size ``sizes[i]``. Drugs are indexed
    over the union of the universes so a draw is a ``bincount``.
    """
    if len(sizes) != len(universes):
        raise ValueError("one size per universe")
    alphabet = sorted({d for u in universes for d in u})
    index = {d: i for i, d in enumerate(alphabet)}
    pools = [np.array(sorted(index[d] for d in set(u)), dtype=np.int64) for u in universes]
    for size, pool in zip(sizes, pools, strict=True):
        if size > len(pool):
            raise ValueError(f"a list of {size} cannot be drawn from a universe of {len(pool)}")
    rng = np.random.default_rng(seed)
    out = np.empty(draws, dtype=np.int64)
    for i in range(draws):
        picks = [
            rng.choice(pool, size=size, replace=False)
            for size, pool in zip(sizes, pools, strict=True)
            if size
        ]
        if not picks:
            out[i] = 0
            continue
        tally = np.bincount(np.concatenate(picks), minlength=len(alphabet))
        out[i] = int((tally >= k).sum())
    return out


@dataclass(frozen=True)
class ConvergenceResult:
    """One convergence test, everything a reader needs to re-derive its p value."""

    label: str
    k: int
    draws: int
    seed: int
    excluded: tuple[str, ...]
    sizes: dict[str, int]
    universe_sizes: dict[str, int]
    observed: int
    drugs: tuple[str, ...]
    null_mean: float
    null_p95: float
    null_max: int
    exceed: int
    p_value: float
    beats_p95: bool
    histogram: dict[int, int]

    def as_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["histogram"] = {str(n): c for n, c in sorted(self.histogram.items())}
        return out


def run(
    lists: Sequence[GeneratorList],
    *,
    label: str,
    k: int = 2,
    draws: int = 10_000,
    seed: int = 0,
    exclude: Iterable[str] = (),
) -> tuple[ConvergenceResult, np.ndarray]:
    """Observed count, its null and its one-sided p, with ``exclude`` removed everywhere."""
    skip = set(exclude)
    sets = [item.drugs - skip for item in lists]
    universes = [sorted(item.universe - skip) for item in lists]
    observed = statistic(sets, k)
    counts = null_counts([len(s) for s in sets], universes, k=k, draws=draws, seed=seed)
    exceed = int((counts >= observed).sum())
    p95 = float(np.percentile(counts, 95))
    values, freq = np.unique(counts, return_counts=True)
    result = ConvergenceResult(
        label=label,
        k=k,
        draws=draws,
        seed=seed,
        excluded=tuple(sorted(skip)),
        sizes={item.generator: len(s) for item, s in zip(lists, sets, strict=True)},
        universe_sizes={item.generator: len(u) for item, u in zip(lists, universes, strict=True)},
        observed=observed,
        drugs=tuple(converging(lists, k, skip)),
        null_mean=float(counts.mean()),
        null_p95=p95,
        null_max=int(counts.max()),
        exceed=exceed,
        p_value=(1 + exceed) / (1 + draws),
        beats_p95=observed > p95,
        histogram={int(v): int(c) for v, c in zip(values, freq, strict=True)},
    )
    return result, counts


def pairwise(lists: Sequence[GeneratorList], exclude: Iterable[str] = ()) -> Mapping[str, int]:
    """Shared approved drugs for every generator pair, ``"a|b"`` keyed (a diagnostic)."""
    skip = set(exclude)
    out: dict[str, int] = {}
    for i, a in enumerate(lists):
        for b in lists[i + 1 :]:
            out[f"{a.generator}|{b.generator}"] = len((a.drugs & b.drugs) - skip)
    return out
