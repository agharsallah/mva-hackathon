"""Target set → candidate drug table, three sources merged and deduped.

Three sources, on purpose, because they fail differently:

* **Open Targets** integrates deeply for well-studied targets and states a clinical stage.
* **ChEMBL** is the primary mechanism-of-action record and the primary approval record.
* **DGIdb** aggregates ~40 curated resources and covers breadth Open Targets has no
  clinical row for.

A candidate is keyed on ``(drug_name.lower(), target_symbol)``: the same drug against two
different targets is two candidates (they are two different arguments), the same drug
against the same target from three sources is one row whose ``source`` names all three.

``approved`` is the challenge's eligibility flag and is a **disjunction over independent
evidences**: ChEMBL ``max_phase == 4``, or an Open Targets clinical stage of 4
(``APPROVAL``), or DGIdb's own approved flag. ``fda_label`` is then checked only for the
approved ones — it is one request per drug and there is no reason to spend it on a
phase-1 compound. ``fda_label`` is ``None`` for a row that was never checked, which is a
different statement from ``False`` ("checked; openFDA has no label under that name").
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from .pathway import TargetRow
from .sources import chembl as chembl_api
from .sources import dgidb as dgidb_api
from .sources import opentargets as ot_api

__all__ = ["Candidate", "Sources", "gather", "key_of"]


@dataclass
class Sources:
    """Which fetcher to use per source. ``openfda`` may be ``None`` to skip label checks."""

    opentargets: Any = None
    chembl: Any = None
    dgidb: Any = None
    openfda: Any = None


@dataclass(frozen=True)
class Candidate:
    """One drug–target pair, with every fact the eligibility rule reads."""

    drug_name: str
    drug_id: str
    target_symbol: str
    target_role: str
    direction_ids: tuple[str, ...] = ()
    source: tuple[str, ...] = ()
    interaction_or_moa: str = ""
    action_type: str = ""
    max_phase: int | None = None
    approved: bool = False
    fda_label: bool | None = None
    pmids: tuple[str, ...] = ()
    first_approval: str = ""
    atc: tuple[str, ...] = ()


def key_of(drug_name: str, target_symbol: str) -> tuple[str, str]:
    """The dedup key: drug name case-folded, target symbol as written."""
    return (drug_name.strip().lower(), target_symbol)


@dataclass
class _Merge:
    """Accumulator for one dedup key across sources."""

    row: Candidate
    ids: dict[str, None] = field(default_factory=dict)

    def absorb(self, other: Candidate) -> None:
        merged = self.row
        sources = dict.fromkeys((*merged.source, *other.source))
        pmids = dict.fromkeys((*merged.pmids, *other.pmids))
        directions = dict.fromkeys((*merged.direction_ids, *other.direction_ids))
        self.row = replace(
            merged,
            source=tuple(sources),
            pmids=tuple(pmids),
            direction_ids=tuple(directions),
            drug_id=merged.drug_id or other.drug_id,
            interaction_or_moa=merged.interaction_or_moa or other.interaction_or_moa,
            action_type=merged.action_type or other.action_type,
            max_phase=_max(merged.max_phase, other.max_phase),
            approved=merged.approved or other.approved,
            atc=merged.atc or other.atc,
            first_approval=merged.first_approval or other.first_approval,
        )


def gather(
    targets: Sequence[TargetRow],
    sources: Sources,
    *,
    progress: Callable[[str], None] | None = None,
) -> list[Candidate]:
    """Every candidate drug for every target, merged, enriched and flagged.

    Four passes, in this order because each one's cost depends on the last:

    1. Open Targets and ChEMBL, per target (two to three requests each).
    2. DGIdb, once for the whole symbol list.
    3. ChEMBL molecule facts, batched over every ChEMBL id any source produced — this is
       what settles ``max_phase``, ``first_approval`` and ``atc`` uniformly.
    4. openFDA, only for the rows that came out approved.
    """
    say = progress or (lambda _line: None)
    merged: dict[tuple[str, str], _Merge] = {}

    for index, target in enumerate(targets, start=1):
        for row in _opentargets_rows(sources.opentargets, target):
            _add(merged, row)
        for row in _chembl_rows(sources.chembl, target):
            _add(merged, row)
        if index % 10 == 0 or index == len(targets):
            say(f"  targets {index}/{len(targets)}  candidates {len(merged)}")

    for row in _dgidb_rows(sources.dgidb, targets):
        _add(merged, row)
    say(f"  after dgidb: {len(merged)} candidates")

    enriched = _enrich(sources.chembl, [entry.row for entry in merged.values()], say)
    return _label(sources.openfda, enriched, say)


# ── per-source collection ───────────────────────────────────────────────────────────


def _opentargets_rows(fetcher: Any, target: TargetRow) -> list[Candidate]:
    if fetcher is None:
        return []
    record = ot_api.target_by_symbol(fetcher, target.symbol)
    if record is None:
        return []
    out: list[Candidate] = []
    for row in ot_api.candidate_rows(record.get("candidates_block") or {}):
        name = str(row.get("drug_name") or "")
        if not name:
            continue
        phase = row.get("phase")
        out.append(
            Candidate(
                drug_name=name,
                drug_id=str(row.get("drug_id") or ""),
                target_symbol=target.symbol,
                target_role=target.role,
                direction_ids=target.direction_ids,
                source=("opentargets",),
                interaction_or_moa=str(row.get("mechanism_of_action") or ""),
                action_type=str(row.get("action_type") or ""),
                max_phase=phase if isinstance(phase, int) else None,
                approved=bool(row.get("approved")),
            )
        )
    return out


def _chembl_rows(fetcher: Any, target: TargetRow) -> list[Candidate]:
    if fetcher is None:
        return []
    out: list[Candidate] = []
    for entry in chembl_api.targets_for_gene(fetcher, target.symbol):
        target_id = entry.get("target_chembl_id")
        if not target_id:
            continue
        for mechanism in chembl_api.mechanisms_for_target(fetcher, str(target_id)):
            molecule_id = mechanism["molecule_chembl_id"]
            out.append(
                Candidate(
                    drug_name=molecule_id,  # replaced by pref_name in the enrichment pass
                    drug_id=molecule_id,
                    target_symbol=target.symbol,
                    target_role=target.role,
                    direction_ids=target.direction_ids,
                    source=("chembl",),
                    interaction_or_moa=mechanism["mechanism_of_action"],
                    action_type=mechanism["action_type"],
                    max_phase=mechanism["max_phase"],
                    approved=mechanism["max_phase"] == 4,
                    pmids=mechanism["pmids"],
                )
            )
    return out


def _dgidb_rows(fetcher: Any, targets: Sequence[TargetRow]) -> list[Candidate]:
    if fetcher is None:
        return []
    by_symbol = {t.symbol: t for t in targets}
    edges = dgidb_api.interactions(fetcher, list(by_symbol))
    out: list[Candidate] = []
    for edge in edges:
        target = by_symbol.get(edge["gene"])
        name = edge["drug_name"]
        if target is None or not name:
            continue
        out.append(
            Candidate(
                drug_name=name,
                drug_id=edge["drug_concept_id"],
                target_symbol=target.symbol,
                target_role=target.role,
                direction_ids=target.direction_ids,
                source=("dgidb",),
                interaction_or_moa="|".join(edge["interaction_types"]),
                action_type="|".join(edge["interaction_types"]),
                approved=bool(edge["approved"]),
                pmids=edge["pmids"],
            )
        )
    return out


# ── the two enrichment passes ───────────────────────────────────────────────────────


def _enrich(fetcher: Any, rows: list[Candidate], say: Callable[[str], None]) -> list[Candidate]:
    """Fill phase, first approval, ATC and the preferred name from ChEMBL, in batches."""
    if fetcher is None:
        return rows
    wanted = {cid for row in rows if (cid := _chembl_id(row))}
    facts = chembl_api.molecules(fetcher, wanted)
    say(f"  chembl molecule facts: {len(facts)}/{len(wanted)} ids resolved")
    out: list[Candidate] = []
    for row in rows:
        fact = facts.get(_chembl_id(row) or "")
        if fact is None:
            out.append(row)
            continue
        phase = fact["max_phase"]
        out.append(
            replace(
                row,
                drug_name=str(fact["pref_name"] or row.drug_name),
                max_phase=_max(row.max_phase, phase),
                approved=row.approved or phase == 4,
                first_approval=str(fact["first_approval"] or ""),
                atc=fact["atc_classifications"] or row.atc,
            )
        )
    return _redup(out)


def _label(fetcher: Any, rows: list[Candidate], say: Callable[[str], None]) -> list[Candidate]:
    """Check openFDA for the approved rows only. ``None`` elsewhere means 'not checked'."""
    if fetcher is None:
        return rows
    from .sources import openfda as openfda_api

    names = sorted({row.drug_name for row in rows if row.approved and row.drug_name})
    say(f"  openfda: checking {len(names)} approved drug names")
    seen: dict[str, bool] = {}
    for name in names:
        seen[name] = bool(openfda_api.label(fetcher, name)["has_label"])
    labelled = sum(1 for v in seen.values() if v)
    say(f"  openfda: {labelled}/{len(names)} have a current US label")
    return [
        replace(row, fda_label=seen.get(row.drug_name)) if row.approved else row for row in rows
    ]


# ── merge plumbing ──────────────────────────────────────────────────────────────────


def _add(merged: dict[tuple[str, str], _Merge], row: Candidate) -> None:
    key = key_of(row.drug_name, row.target_symbol)
    existing = merged.get(key)
    if existing is None:
        merged[key] = _Merge(row=row)
    else:
        existing.absorb(row)


def _redup(rows: Iterable[Candidate]) -> list[Candidate]:
    """Re-run the dedup after enrichment renamed ChEMBL ids to preferred names."""
    merged: dict[tuple[str, str], _Merge] = {}
    for row in rows:
        _add(merged, row)
    return [entry.row for entry in merged.values()]


def _chembl_id(row: Candidate) -> str | None:
    """The ChEMBL molecule id behind a row, from any source's id spelling.

    Open Targets and ChEMBL write a bare ``CHEMBL123``; DGIdb writes a *namespaced*
    ``chembl:CHEMBL123``. The namespace is stripped first and the bare form is only tried
    after, because ``"chembl:CHEMBL123".upper()`` also starts with ``CHEMBL`` — testing
    the bare form first silently turned every DGIdb id into ``CHEMBL:CHEMBL123``, which
    ChEMBL resolves to nothing.
    """
    value = row.drug_id.strip()
    if ":" in value:
        namespaced = dgidb_api.chembl_id(value)
        return namespaced.upper() if namespaced else None
    return value.upper() if value.upper().startswith("CHEMBL") else None


def _max(left: int | None, right: int | None) -> int | None:
    if left is None:
        return right
    if right is None:
        return left
    return max(left, right)
