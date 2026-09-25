"""Signature reversal, the table part: compound rows, the generator list, the verdict inputs.

Pure functions over the rankings :mod:`mva.drugs.signature_reversal` produced and the
approval records of :mod:`mva.drugs.signature_reversal_approval`. No I/O except
:func:`write_tsv`. The registered test (H092 / P4-27) is spelled out in
:func:`verdict_inputs`, so the verdict a run suggests is reproducible from the table.
"""

from __future__ import annotations

import csv
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .names import base_name
from .signature_reversal import Ranked, percentile
from .signature_reversal_approval import Approval

__all__ = [
    "COMPOUND_COLUMNS",
    "GENERATOR_COLUMNS",
    "JOIN_RULE",
    "ControlResult",
    "compound_rows",
    "control_result",
    "engine_overlap",
    "generator_rows",
    "join_key",
    "verdict_inputs",
    "write_tsv",
]

COMPOUND_COLUMNS = (
    "drug",
    "sigcom_label",
    "ilincs_label",
    "in_sigcom",
    "in_ilincs",
    "sigcom_rank",
    "sigcom_best_signature_position",
    "sigcom_z_sum",
    "sigcom_signatures_in_depth",
    "sigcom_best_context",
    "ilincs_rank",
    "ilincs_best_signature_position",
    "ilincs_similarity",
    "ilincs_signatures_in_depth",
    "ilincs_best_context",
    "top_both",
    "approved",
    "approval_evidence",
    "decoy_top_hits",
    "decoys",
    "specific",
    "listed",
)

#: The step-10 generator table contract (docs/iteration4/step-10/README.md).
GENERATOR_COLUMNS = (
    "generator",
    "rank",
    "drug",
    "drug_label",
    "approved",
    "approval_evidence",
    "score",
    "score_name",
    "direction_hint",
    "evidence",
    "source_ids",
)


@dataclass(frozen=True)
class ControlResult:
    """The positive control in one genetic library."""

    database: str
    universe: int
    ranks: Mapping[str, int | None]
    """Control gene → gene-level mimicker rank (``None`` = beyond the retrieved depth)."""
    depth_genes: int
    cut: float

    @property
    def passed(self) -> bool:
        return any(
            rank is not None and percentile(rank, self.universe) <= self.cut
            for rank in self.ranks.values()
        )


def control_result(
    database: str,
    ranked: Sequence[Ranked],
    controls: Collection[str],
    *,
    universe: int,
    cut: float,
) -> ControlResult:
    """Where each control gene lands among the library's genes, by best mimicker signature."""
    by_key = {item.key: item.rank for item in ranked}
    return ControlResult(
        database=database,
        universe=universe,
        ranks={gene: by_key.get(gene) for gene in sorted(controls)},
        depth_genes=len(ranked),
        cut=cut,
    )


def compound_rows(
    sigcom: Sequence[Ranked],
    ilincs: Sequence[Ranked],
    *,
    sigcom_universe: Collection[str],
    ilincs_universe: Collection[str],
    approvals: Mapping[str, Approval],
    decoy_tops: Sequence[Collection[str]],
    top_n: int,
    decoy_max_hits: int,
) -> list[dict[str, Any]]:
    """One row per compound seen as a reverser by either engine, best combined rank first."""
    s_by = {item.key: item for item in sigcom}
    i_by = {item.key: item for item in ilincs}
    rows: list[dict[str, Any]] = []
    for key in sorted(set(s_by) | set(i_by)):
        s, i = s_by.get(key), i_by.get(key)
        top_both = bool(s and i and s.rank <= top_n and i.rank <= top_n)
        hits = sum(1 for top in decoy_tops if key in top)
        approval = approvals.get(key, Approval(approved=False, evidence=""))
        specific = hits <= decoy_max_hits
        rows.append(
            {
                "drug": key,
                "sigcom_label": s.label if s else "",
                "ilincs_label": i.label if i else "",
                "in_sigcom": key in sigcom_universe,
                "in_ilincs": key in ilincs_universe,
                "sigcom_rank": s.rank if s else None,
                "sigcom_best_signature_position": s.best_position if s else None,
                "sigcom_z_sum": round(s.best_score, 4) if s else None,
                "sigcom_signatures_in_depth": s.signatures if s else 0,
                "sigcom_best_context": s.context if s else "",
                "ilincs_rank": i.rank if i else None,
                "ilincs_best_signature_position": i.best_position if i else None,
                "ilincs_similarity": round(i.best_score, 4) if i else None,
                "ilincs_signatures_in_depth": i.signatures if i else 0,
                "ilincs_best_context": i.context if i else "",
                "top_both": top_both,
                "approved": approval.approved,
                "approval_evidence": approval.evidence,
                "decoy_top_hits": hits,
                "decoys": len(decoy_tops),
                "specific": specific,
                "listed": top_both and approval.approved,
            }
        )
    return sorted(rows, key=_combined_order)


def _combined_order(row: Mapping[str, Any]) -> tuple[int, int, str]:
    big = 1 << 30
    s = row["sigcom_rank"] if row["sigcom_rank"] is not None else big
    i = row["ilincs_rank"] if row["ilincs_rank"] is not None else big
    return (max(s, i), min(s, i), str(row["drug"]))


def join_key(name: str) -> str:
    """Step 10's cross-generator join key: hyphens folded to spaces, then ``base_name``."""
    return base_name(name.replace("-", " "))


JOIN_RULE = (
    "drug = mva.drugs.names.base_name(name.replace('-', ' ')): hyphens folded to spaces first"
)


def generator_rows(rows: Sequence[Mapping[str, Any]], *, entry: str) -> list[dict[str, Any]]:
    """G4 ``lincs``: approved drugs in both engines' top reversers, ranked by the worse rank.

    The list rule is step 10's; the decoy count is carried in ``evidence`` so step 10 can
    see specificity without the list silently shrinking.
    """
    listed = [row for row in rows if row["listed"]]
    out: list[dict[str, Any]] = []
    for rank, row in enumerate(listed, start=1):
        worse = max(int(row["sigcom_rank"]), int(row["ilincs_rank"]))
        out.append(
            {
                "generator": "lincs",
                "rank": rank,
                "drug": join_key(str(row["drug"])),
                "drug_label": row["sigcom_label"] or row["ilincs_label"],
                "approved": "true",
                "approval_evidence": row["approval_evidence"],
                "score": worse,
                "score_name": "worse of the two engines' compound reverser ranks (1 = best)",
                # Reversal is mechanism-agnostic: it says the drug pushes the expression
                # state the other way, not how. So the source argues no direction.
                "direction_hint": "none",
                "evidence": (
                    f"reverses the BUB1B-loss signature (CRISPR-knockout consensus): SigCom rank "
                    f"{row['sigcom_rank']}, iLINCS rank {row['ilincs_rank']}; in the top "
                    f"reversers of {row['decoy_top_hits']} of {row['decoys']} random decoys"
                ),
                "source_ids": f"entry:{entry}",
            }
        )
    return out


def verdict_inputs(
    rows: Sequence[Mapping[str, Any]],
    controls: Sequence[ControlResult],
    *,
    decoy_max_hits: int,
) -> dict[str, Any]:
    """The registered test's three clauses, counted, and the status they imply.

    Supported: the positive control passes and one approved drug is in both engines' top
    reversers and in at most ``decoy_max_hits`` decoys' top reversers. Refuted: the control
    passes and no approved drug qualifies (none in both tops, or every such drug is in
    more decoys' tops). Uninterpretable: the control fails.
    """
    both = [row for row in rows if row["top_both"]]
    listed = [row for row in both if row["approved"]]
    specific = [row for row in listed if int(row["decoy_top_hits"]) <= decoy_max_hits]
    control_passed = any(control.passed for control in controls)
    if not control_passed:
        status = "uninterpretable"
    elif specific:
        status = "supported"
    else:
        status = "refuted"
    return {
        "top_both": len(both),
        "top_both_approved": len(listed),
        "top_both_approved_specific": len(specific),
        "specific_drugs": [row["drug"] for row in specific],
        "listed_drugs": [row["drug"] for row in listed],
        "control_passed": control_passed,
        "controls": {
            control.database: {
                "passed": control.passed,
                "universe_genes": control.universe,
                "genes_in_depth": control.depth_genes,
                "ranks": dict(control.ranks),
                "cut": control.cut,
            }
            for control in controls
        },
        "status": status,
    }


def write_tsv(path: Path, rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> Path:
    """Tab-separated, header always written (an empty list is a valid result)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _cell(row.get(column)) for column in columns})
    return path


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def engine_overlap(
    sigcom_tops: Sequence[Collection[str]],
    ilincs_top: Collection[str],
    universe: Collection[str],
) -> list[int]:
    """How many keys each SigCom top list shares with the iLINCS top, inside ``universe``.

    Element 0 is the real signature; the rest are decoys. A descriptive null for "the two
    engines agree": a decoy's SigCom top meeting the real iLINCS top counts the compounds
    both engines would rank highly whatever the query (frequent reversers).
    """
    inside = set(universe)
    real = set(ilincs_top) & inside
    return [len(set(top) & real) for top in sigcom_tops]
