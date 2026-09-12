"""Small exact statistics, written out rather than imported.

One function so far: Fisher's exact test on a 2x2 table, one-sided. Step 2 compares how
often a target gene carries a biallelic candidate against how often a decoy does, and the
counts are single digits — the regime where a chi-square approximation is wrong and where
an exact test is a dozen lines of integer arithmetic.

**Why not SciPy.** It is not a declared dependency of this project; it arrives transitively
and could leave the same way. A number that appears in a figure and in a verdict should not
depend on a package nobody chose. :func:`math.comb` is exact and in the standard library.
"""

from __future__ import annotations

from math import comb

__all__ = ["fisher_exact_greater"]


def fisher_exact_greater(a: int, b: int, c: int, d: int) -> float:
    """One-sided p for the table ``[[a, b], [c, d]]``, testing ``a`` larger than chance.

    ``a`` successes out of ``a + b`` in the first group, ``c`` out of ``c + d`` in the
    second. The p returned is the probability, under the hypergeometric null with both
    margins fixed, of seeing ``a`` **or more** successes in the first group.

    >>> round(fisher_exact_greater(4, 392, 2, 394), 3)
    0.343
    >>> round(fisher_exact_greater(10, 386, 10, 386), 3)
    0.589
    """
    if min(a, b, c, d) < 0:
        raise ValueError("a 2x2 table has no negative cells")
    row_one, successes, total = a + b, a + c, a + b + c + d
    if total == 0:
        return 1.0
    ways = comb(total, row_one)
    if ways == 0:
        return 1.0
    upper = min(row_one, successes)
    tail = sum(
        comb(successes, k) * comb(total - successes, row_one - k) for k in range(a, upper + 1)
    )
    return tail / ways
