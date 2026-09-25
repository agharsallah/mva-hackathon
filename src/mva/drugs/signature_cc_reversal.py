"""Cell-cycle-corrected reversal: which compound's corrected signature points the other way?

Runs only after :func:`.signature_cc.sibling_control` passed for the query. The compound
matrix is corrected with its **own** S and G2/M scores (a compound library has its own
proliferation axis, fitted on compounds, not borrowed from knockouts); the query is the
corrected knockout row. A **reverser** is a compound whose corrected row correlates most
negatively with the query.

Specificity follows entry 153: the same ranking is run for decoy queries (corrected rows of
randomly drawn other knockouts); a compound in the top ``n`` of two or more decoys reverses
"any knockout", not this one.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from .signature_cc import similarity

__all__ = ["Reverser", "decoy_counts", "rank_reversers", "top_labels"]


@dataclass(frozen=True)
class Reverser:
    """One compound row: its Pearson r with the query (negative = reverses) and rank."""

    label: str
    r: float
    rank: int


def rank_reversers(
    labels: Sequence[str], compounds: np.ndarray, query: np.ndarray
) -> list[Reverser]:
    """Every compound, most negative r first (rank 1); NaN rows last with rank 0."""
    sims = similarity(compounds, query)
    order = sorted(range(len(labels)), key=lambda i: (not np.isfinite(sims[i]), sims[i]))
    out: list[Reverser] = []
    for position, i in enumerate(order, start=1):
        finite = bool(np.isfinite(sims[i]))
        out.append(Reverser(labels[i], float(sims[i]), position if finite else 0))
    return out


def top_labels(ranked: Sequence[Reverser], n: int) -> set[str]:
    return {r.label for r in ranked if 0 < r.rank <= n}


def decoy_counts(
    labels: Sequence[str], compounds: np.ndarray, decoys: Sequence[np.ndarray], n: int
) -> dict[str, int]:
    """For each compound, in how many decoy queries' top ``n`` reversers it sits."""
    counts = dict.fromkeys(labels, 0)
    for decoy in decoys:
        for label in top_labels(rank_reversers(labels, compounds, decoy), n):
            counts[label] += 1
    return counts
