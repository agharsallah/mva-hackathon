"""Is a protein's amount cell-cycle-bound at baseline, and how long does it live?

Two descriptive numbers that belong beside any drug-perturbation result for a cell-cycle
gene, and neither of which depends on a drug:

* **how tightly the protein tracks the mitotic program** across untreated cell lines — the
  correlation of its amount with a proliferation score over the CCLE proteome, reported with
  its percentile among all quantified proteins, so "it follows the cell cycle" is a measured
  statement rather than an assertion;
* **its half-life**, when the published turnover atlas quantifies it, with the percentile
  among proteins. A protein the atlas does not hold gets an empty block, never a guess.

Case-agnostic: the target is a parameter and no gene is named here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from mva.drugs.proteome import score_correlations, set_score
from mva.drugs.proteome_sets import TIROSH_G2M, members
from mva.drugs.proteome_sources import read_ccle_protein, read_half_lives

__all__ = ["baseline"]


def baseline(target: str, *, ccle_path: Path, half_life_path: Path) -> dict[str, Any]:
    """The descriptive block: correlation with the G2/M score, and the protein's half-life."""
    ccle = read_ccle_protein(ccle_path)
    genes = members(TIROSH_G2M, set(ccle.genes), {target})
    score, used = set_score(ccle, genes, min_members=10)
    r = score_correlations(ccle, score)
    at = ccle.index()[target]
    finite = r[np.isfinite(r)]
    halves = read_half_lives(half_life_path)
    hl: dict[str, Any] = {}
    for column, value in halves.get(target, {}).items():
        pool = np.array([v[column] for v in halves.values() if column in v])
        hl[column] = {
            "hours": round(value, 2),
            "percentile_among_proteins": round(float(np.mean(pool <= value)) * 100, 1),
            "proteins": int(pool.size),
        }
    return {
        "ccle_lines": len(ccle.perturbations),
        "ccle_score_members": len(used),
        "ccle_r_target_vs_g2m": round(float(r[at]), 4),
        "ccle_percentile_of_r": round(float(np.mean(finite <= r[at])) * 100, 1),
        "ccle_proteins_with_r": int(finite.size),
        "half_life": hl,
    }
