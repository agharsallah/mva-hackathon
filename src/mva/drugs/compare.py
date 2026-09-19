"""Side-by-side counts for both controls: the decoy per direction, and the transfer per case.

Two questions, one module, because both are "the same pipeline, run again, compared".

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

**The transfer comparison** (:mod:`mva.drugs.transfer` builds the card) asks the other
question: not *is this direction specific* but *does this pipeline run at all for a case it
was never written for*. Its unit is the **case**, not the direction: one row for the real
card and one per transfer case, each carrying what the same code produced and what it cost.
The same boundary applies and for the same reason - a transfer card has no ``evidence.tsv``,
so ``curated_rows`` is printed beside every count rather than folded into the rung numbers.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from .ladder import PATHWAY_DIRECTION, _context_drugs, _split, _truthy
from .mechanism import MechanismCard
from .names import base_name

__all__ = [
    "CaseRun",
    "approved_by_direction",
    "approved_set",
    "compare",
    "comparison_row",
    "comparison_rows",
    "request_totals",
]


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


@dataclass(frozen=True)
class CaseRun:
    """One case's outputs: the snapshot index, the enrichment analysis, the wall clock."""

    label: str
    role: str
    snapshot: dict[str, Any]
    analysis: dict[str, Any]
    curated_rows: int = 0
    #: Wall clock of the pass the counts above come from - the one that filled the cache.
    wall_seconds: float | None = None
    #: Wall clock of a second pass over the warm cache, when one was run. The pair is the
    #: honest cost statement: what a new case costs once, and what re-deriving it costs.
    warm_seconds: float | None = None


def request_totals(*blocks: dict[str, Any] | None) -> tuple[int, int]:
    """``(live, cached)`` summed over every ``requests`` block given.

    Both ``snapshot.json`` and ``analysis.json`` record ``{source: {replies, live}}``.
    ``replies`` counts every answer the stage used and ``live`` the subset that went to the
    network, so ``replies - live`` is the number served from the on-disk cache. Summing the
    two files is what makes a cold run and a warm re-run comparable in one number.
    """
    live = cached = 0
    for block in blocks:
        for entry in (block or {}).values():
            if not isinstance(entry, dict):
                continue
            made = int(entry.get("live") or 0)
            replies = int(entry.get("replies") or 0)
            live += made
            cached += max(replies - made, 0)
    return live, cached


def _by_rung(analysis: dict[str, Any]) -> dict[str, int]:
    found = analysis.get("ladder_drugs_by_max_rung") or {}
    return {str(rung): int(found.get(str(rung), 0)) for rung in range(1, 6)}


def comparison_row(run: CaseRun) -> dict[str, Any]:
    """One case as one row of :data:`mva.drugs.tables.TRANSFER_COMPARISON_COLUMNS`.

    Pure: everything is read out of the two JSON payloads the run already wrote. A number
    the payload does not carry comes back as ``None`` and prints as an empty cell, which
    the manifest states means *not recorded*, never zero.
    """
    card = run.snapshot.get("card") or {}
    rows = run.analysis.get("rows") or {}
    rungs = _by_rung(run.analysis)
    live, cached = request_totals(run.snapshot.get("requests"), run.analysis.get("requests"))
    return {
        "case": run.label,
        "role": run.role,
        "gene": card.get("gene"),
        "disease": card.get("disease"),
        "tumour_context": card.get("tumour_context"),
        "card_version": card.get("version"),
        "targets": (run.snapshot.get("targets") or {}).get("total"),
        "candidate_rows": (run.snapshot.get("rows") or {}).get("drug_candidates"),
        "approved_drugs": (run.snapshot.get("candidates") or {}).get("distinct_approved_drugs"),
        "drugs_rung_5": rungs["5"],
        "drugs_rung_4": rungs["4"],
        "drugs_rung_3": rungs["3"],
        "drugs_rung_2": rungs["2"],
        "drugs_rung_1": rungs["1"],
        "shortlist": rows.get("shortlist"),
        "do_not": rows.get("do_not"),
        "curated_rows": run.curated_rows,
        "live_requests": live,
        "cached_replies": cached,
        "wall_seconds": None if run.wall_seconds is None else round(run.wall_seconds, 1),
        "warm_seconds": None if run.warm_seconds is None else round(run.warm_seconds, 1),
    }


def comparison_rows(runs: Sequence[CaseRun] | Iterable[CaseRun]) -> list[dict[str, Any]]:
    """Every case, in the order given: the real card first, then each transfer case."""
    return [comparison_row(run) for run in runs]
