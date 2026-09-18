"""The real card against its decoys: which directions nominate the same drugs for any gene?

A decoy card (:mod:`mva.drugs.decoy`) keeps the child and swaps the gene. After the same
snapshot has run on both, this module asks one question per direction: **how much of the
direction's approved drug set also came out for the decoy?** Jaccard over base names, with
the shared drugs listed so the overlap can be read, not just measured.

An overlap is not a failure of the direction - a statin is a statin whatever the decoy - but
it is a failure of *specificity*: the automated stage would have nominated it for a child
with a different gene, so it cannot count as evidence *for this mechanism*. The report labels
such a direction non-specific and leans on the curated rung instead.

Only the automated flags are compared. The decoy has no hand-read literature, so a curated
rung has no counterpart on the decoy side, and comparing it would be comparing a number to
its absence.
"""

from __future__ import annotations

from typing import Any

from .ladder import PATHWAY_DIRECTION, _context_drugs, _split, _truthy
from .mechanism import MechanismCard
from .names import base_name

__all__ = ["approved_by_direction", "approved_set", "compare"]


def approved_set(candidates: list[dict[str, Any]]) -> set[str]:
    """Base names of every approved drug in a candidate table."""
    return {base_name(str(r["drug_name"])) for r in candidates if _truthy(r.get("approved"))}


def approved_by_direction(candidates: list[dict[str, Any]]) -> dict[str, set[str]]:
    """Base names of approved drugs per direction id; ``pathway`` for pathway-only rows."""
    out: dict[str, set[str]] = {}
    for row in candidates:
        if not _truthy(row.get("approved")):
            continue
        name = base_name(str(row["drug_name"]))
        directions = _split(row.get("direction_ids")) or (PATHWAY_DIRECTION,)
        for direction in directions:
            out.setdefault(direction, set()).add(name)
    return out


def _labelled(candidates: list[dict[str, Any]]) -> set[str]:
    return {
        base_name(str(r["drug_name"]))
        for r in candidates
        if _truthy(r.get("approved")) and _truthy(r.get("fda_label"))
    }


def compare(
    card: MechanismCard,
    real_candidates: list[dict[str, Any]],
    decoy_name: str,
    decoy_candidates: list[dict[str, Any]],
    decoy_trials: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """One row per real direction (plus ``all``) against one decoy's approved set."""
    decoy_set = approved_set(decoy_candidates)
    decoy_context = _context_drugs(decoy_trials, card.tumour_context) & decoy_set
    decoy_labelled = _labelled(decoy_candidates)
    per_direction = approved_by_direction(real_candidates)
    per_direction["all"] = approved_set(real_candidates)
    rows = []
    for direction in sorted(per_direction, key=lambda d: (d == "all", d)):
        real = per_direction[direction]
        shared = real & decoy_set
        union = real | decoy_set
        rows.append(
            {
                "decoy": decoy_name,
                "direction_id": direction,
                "direction_approved": len(real),
                "decoy_approved": len(decoy_set),
                "shared": len(shared),
                "jaccard": round(len(shared) / len(union), 4) if union else 0.0,
                "shared_drugs": tuple(sorted(shared)),
                "decoy_with_context_trial": len(decoy_context),
                "decoy_with_fda_label": len(decoy_labelled),
            }
        )
    return rows
