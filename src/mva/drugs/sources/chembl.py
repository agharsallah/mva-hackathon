"""ChEMBL, over the EBI REST API.

ChEMBL is the primary record this challenge's eligibility rule keys on: *market-approved
drugs only*, evidenced by ``max_phase == 4`` or an FDA label. It is also the source of the
mechanism-of-action statements Open Targets re-serves, so querying it directly gives rows
Open Targets may not have integrated yet.

**Schema note (verified live 2026-09-06).** ``max_phase`` is served as a *string*
(``"4.0"``), not the integer the older API returned; :func:`phase` parses it back and
answers ``None`` rather than guessing when the field is absent or unparseable.

Three calls, in the order a caller needs them:

``targets_for_gene``  gene symbol → the human ChEMBL target(s) for that protein
``mechanisms_for_target``  a target → every molecule with a stated mechanism against it
``molecules``  a batch of molecule ids → phase, first approval, ATC class, warnings
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from ..cache import Fetcher

__all__ = [
    "BASE",
    "BATCH",
    "mechanisms_for_target",
    "molecule",
    "molecules",
    "phase",
    "targets_for_gene",
]

BASE = "https://www.ebi.ac.uk/chembl/api/data"

#: Molecule ids per bulk request. ChEMBL accepts ``__in`` filters; 50 keeps the URL short
#: enough for every proxy in the path and the reply small enough to cache comfortably.
BATCH = 50

#: The only organism whose targets are kept. A mouse or rat orthologue is a different
#: protein and its drugs are not evidence about this child.
HUMAN = "Homo sapiens"


def phase(value: Any) -> int | None:
    """``"4.0"`` → ``4``; ``None``/``""``/nonsense → ``None``. Never a guessed zero."""
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def targets_for_gene(fetcher: Fetcher, symbol: str) -> list[dict[str, Any]]:
    """Human ChEMBL targets whose components name ``symbol`` as a gene symbol.

    The free-text search is deliberately *not* trusted on its own: searching a symbol
    returns fuzzy hits, so a hit is kept only when one of its target components carries
    that exact symbol as a ``GENE_SYMBOL`` synonym. That makes the mapping exact and
    case-agnostic in one step.
    """
    payload = fetcher.get_json(
        f"{BASE}/target/search.json", {"q": symbol, "limit": 20, "format": "json"}
    )
    out: list[dict[str, Any]] = []
    for target in (payload or {}).get("targets", []):
        if target.get("organism") != HUMAN or not _names(target, symbol):
            continue
        out.append(
            {
                "target_chembl_id": target.get("target_chembl_id"),
                "pref_name": target.get("pref_name"),
                "organism": target.get("organism"),
                "target_type": target.get("target_type"),
                "accessions": tuple(
                    str(c.get("accession"))
                    for c in target.get("target_components") or []
                    if c.get("accession")
                ),
            }
        )
    return out


def _names(target: dict[str, Any], symbol: str) -> bool:
    """Does any component of this target declare ``symbol`` as its gene symbol?"""
    wanted = symbol.upper()
    for component in target.get("target_components") or []:
        for synonym in component.get("target_component_synonyms") or []:
            if str(synonym.get("syn_type", "")).startswith("GENE_SYMBOL") and (
                str(synonym.get("component_synonym", "")).upper() == wanted
            ):
                return True
    return False


def mechanisms_for_target(fetcher: Fetcher, target_chembl_id: str) -> list[dict[str, Any]]:
    """Every molecule ChEMBL records a mechanism of action against for one target."""
    payload = fetcher.get_json(
        f"{BASE}/mechanism.json",
        {"target_chembl_id": target_chembl_id, "limit": 1000, "format": "json"},
    )
    out: list[dict[str, Any]] = []
    for row in (payload or {}).get("mechanisms", []):
        if not row.get("molecule_chembl_id"):
            continue
        out.append(
            {
                "molecule_chembl_id": str(row["molecule_chembl_id"]),
                "mechanism_of_action": str(row.get("mechanism_of_action") or ""),
                "action_type": str(row.get("action_type") or ""),
                "max_phase": phase(row.get("max_phase")),
                "pmids": tuple(
                    str(ref.get("ref_id"))
                    for ref in row.get("mechanism_refs") or []
                    if ref.get("ref_type") == "PubMed" and ref.get("ref_id")
                ),
            }
        )
    return out


def molecule(fetcher: Fetcher, molecule_chembl_id: str) -> dict[str, Any] | None:
    """One molecule's approval facts, or ``None`` when ChEMBL does not hold the id."""
    found = molecules(fetcher, [molecule_chembl_id])
    return found.get(molecule_chembl_id)


def molecules(fetcher: Fetcher, ids: Iterable[str]) -> dict[str, dict[str, Any]]:
    """Approval facts for many molecules, batched ``BATCH`` at a time.

    Returned as a mapping so a caller can look one up without scanning; ids ChEMBL does
    not know are simply absent from it, which is a different statement from "phase 0".
    """
    wanted = sorted({str(i) for i in ids if i})
    out: dict[str, dict[str, Any]] = {}
    for chunk in _chunks(wanted, BATCH):
        payload = fetcher.get_json(
            f"{BASE}/molecule.json",
            {"molecule_chembl_id__in": ",".join(chunk), "limit": BATCH, "format": "json"},
        )
        for row in (payload or {}).get("molecules", []):
            key = str(row.get("molecule_chembl_id") or "")
            if not key:
                continue
            out[key] = {
                "molecule_chembl_id": key,
                "pref_name": row.get("pref_name"),
                "max_phase": phase(row.get("max_phase")),
                "first_approval": row.get("first_approval"),
                "molecule_type": row.get("molecule_type"),
                "atc_classifications": tuple(str(a) for a in row.get("atc_classifications") or []),
                "black_box_warning": bool(row.get("black_box_warning")),
                "withdrawn_flag": bool(row.get("withdrawn_flag")),
            }
    return out


def _chunks(items: Sequence[str], size: int) -> list[list[str]]:
    return [list(items[i : i + size]) for i in range(0, len(items), size)]
