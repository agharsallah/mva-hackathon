"""Sweep results as tables: the wide per-compound table, the controls, the generator list.

Three artifacts, all case-agnostic (a contrast is a short tag such as ``rms`` plus the
:class:`~mva.drugs.screen_sweep.FamilyRow` list it produced):

* :func:`sweep_table` — one row per eligible compound copy, every contrast side by side,
  with the drug-level q of each contrast repeated on every copy so a reader can filter on
  it without re-deriving the representative.
* :func:`calibration` — how the family behaved: raw p < 0.05 rate (about 5 % under the
  null), how many drugs reach q < alpha, and the p a drug would need at rank 1.
* :func:`generator_rows` — the step-10 table contract (``generator``, ``rank``, ``drug`` …):
  the union of each contrast's top fraction, ranked, with the direction the contrast
  argues. The universe is every drug in the family.

No genomic position can appear: the identifiers are drug names, BRD ids and line counts.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import polars as pl

from mva.drugs.screen_sweep import FamilyRow, top_k

__all__ = ["calibration", "drug_level", "generator_rows", "sweep_table", "universe_rows"]


def _rank(row: FamilyRow) -> int:
    return row.rank if row.rank is not None else 1 << 30


def drug_level(rows: Sequence[FamilyRow]) -> dict[str, FamilyRow]:
    """``{drug: its representative row}`` for one contrast."""
    return {r.drug: r for r in rows if r.representative}


def sweep_table(
    contrasts: Mapping[str, Sequence[FamilyRow]],
    annotation: Mapping[str, Mapping[str, Any]],
    *,
    alpha: float,
    extra: Mapping[tuple[str, str], Mapping[str, Any]] | None = None,
) -> pl.DataFrame:
    """Long format: one row per compound copy x contrast.

    ``annotation[item_id]`` supplies name, MOA, target, ...; ``extra[(item_id, contrast)]``
    adds per-contrast columns (``p_opposite``, a sensitivity result). ``q``, ``rank`` are
    set on the representative copy only; ``drug_q`` repeats the representative's q on every
    copy, and ``hit_both`` is true when the drug's q is below ``alpha`` in **every**
    contrast — the H093 question.
    """
    reps = {tag: drug_level(rows) for tag, rows in contrasts.items()}

    def drug_q(tag: str, drug: str) -> float | None:
        rep = reps[tag].get(drug)
        return rep.result.p_adjusted if rep is not None else None

    out = []
    for tag, rows in contrasts.items():
        for row in rows:
            r = row.result
            qs = [drug_q(t, row.drug) for t in contrasts]
            out.append(
                {
                    "item_id": r.item_id,
                    "drug": row.drug,
                    **annotation.get(r.item_id, {}),
                    "contrast": tag,
                    "n_in": r.n_in,
                    "n_out": r.n_out,
                    "median_in": r.median_in,
                    "median_out": r.median_out,
                    "cliffs_delta": r.delta,
                    "ci_low": r.ci_low,
                    "ci_high": r.ci_high,
                    "p_raw": r.p_raw,
                    "q": r.p_adjusted if row.representative else None,
                    "rank": row.rank,
                    "percentile": row.percentile,
                    "representative": row.representative,
                    "drug_q": drug_q(tag, row.drug),
                    "hit_both": all(q is not None and q < alpha for q in qs),
                    **(extra or {}).get((r.item_id, tag), {}),
                }
            )
    return pl.DataFrame(out, infer_schema_length=None).sort("contrast", "item_id")


def calibration(rows: Sequence[FamilyRow], *, alpha: float) -> dict[str, Any]:
    """How one contrast's family behaved — the numbers a reader checks before any hit."""
    reps = [r for r in rows if r.representative and r.result.p_raw is not None]
    p = np.asarray([r.result.p_raw for r in reps], dtype=float)
    q = np.asarray([r.result.p_adjusted for r in reps], dtype=float)
    d = np.asarray([r.result.delta for r in reps], dtype=float)
    passing = p[q < alpha]
    return {
        "family_size": len(reps),
        "fraction_p_below_0.05": float((p < 0.05).mean()) if p.size else None,
        "expected_under_null": 0.05,
        "drugs_q_below_alpha": int((q < alpha).sum()),
        "alpha": alpha,
        "min_q": float(q.min()) if q.size else None,
        "min_p": float(p.min()) if p.size else None,
        "p_needed_at_rank_1": alpha / len(reps) if reps else None,
        "largest_p_passing": float(passing.max()) if passing.size else None,
        "median_delta": float(np.median(d)) if d.size else None,
        "delta_2.5pct": float(np.percentile(d, 2.5)) if d.size else None,
        "delta_97.5pct": float(np.percentile(d, 97.5)) if d.size else None,
    }


def generator_rows(
    contrasts: Mapping[str, Sequence[FamilyRow]],
    hints: Mapping[str, str],
    labels: Mapping[str, str],
    source_ids: Mapping[str, Sequence[str]],
    moa: Mapping[str, str],
    *,
    generator: str,
    fraction: float,
    approval_evidence: str,
) -> pl.DataFrame:
    """The union of each contrast's top ``fraction`` of drugs, in the step-10 contract.

    Within a contrast, drugs are ordered by the family ``rank`` (one-sided p, ties by the
    larger delta). The union is ranked by the best within-contrast rank, then the smaller
    p. ``score`` is ``-log10`` of that best p. ``hints[tag]`` is the direction a hit on
    that contrast argues; a drug listed by several contrasts carries them all, ``|``-joined.
    """
    reps = {tag: drug_level(rows) for tag, rows in contrasts.items()}
    chosen: dict[str, list[tuple[str, FamilyRow]]] = {}
    for tag, by_drug in reps.items():
        ranked = sorted((r for r in by_drug.values() if r.rank is not None), key=_rank)
        for row in ranked[: top_k(len(ranked), fraction)]:
            chosen.setdefault(row.drug, []).append((tag, row))
    ordered = sorted(
        chosen.items(),
        key=lambda kv: (
            min(r.rank for _, r in kv[1] if r.rank is not None),
            min(r.result.p_raw for _, r in kv[1] if r.result.p_raw is not None),
            kv[0],
        ),
    )
    out = []
    for i, (drug, picks) in enumerate(ordered, start=1):
        best_tag, best = min(picks, key=lambda tr: (_rank(tr[1]), tr[1].result.p_raw or 1.0))
        parts = []
        for tag in contrasts:
            r = reps[tag].get(drug)
            if r is None or r.result.delta is None:
                continue
            parts.append(
                f"{tag}: delta {r.result.delta:+.3f} (n {r.result.n_in}/{r.result.n_out}), "
                f"p {r.result.p_raw:.2g}, q {r.result.p_adjusted:.2g}, rank {r.rank}"
            )
        out.append(
            {
                "generator": generator,
                "rank": i,
                "drug": drug,
                "drug_label": labels.get(best.result.item_id, drug),
                "approved": True,
                "approval_evidence": approval_evidence,
                "score": -math.log10(max(best.result.p_raw or 1.0, 1e-300)),
                "score_name": f"-log10 one-sided Mann-Whitney p, best contrast ({best_tag})",
                "direction_hint": "|".join(hints[t] for t in contrasts if t in dict(picks)),
                "evidence": (
                    f"PRISM 24Q2 top {fraction:.1%} on {'+'.join(t for t, _ in picks)}; "
                    + "; ".join(parts)
                    + f"; MOA {moa.get(best.result.item_id) or 'not annotated'}"
                ),
                "source_ids": "|".join(sorted(source_ids.get(drug, []))),
            }
        )
    return pl.DataFrame(out)


def universe_rows(contrasts: Mapping[str, Sequence[FamilyRow]]) -> pl.DataFrame:
    """Every drug in any contrast's family, ``approved`` true by the Launched filter."""
    drugs = sorted({r.drug for rows in contrasts.values() for r in rows if r.representative})
    return pl.DataFrame({"drug": drugs, "approved": [True] * len(drugs)})
