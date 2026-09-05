"""Open Targets Platform, over its v4 GraphQL endpoint.

Open Targets is the integrator: it already joins ChEMBL drugs, their mechanisms of action,
their clinical stage and the diseases they were tried in, per target. One query per gene
gives the whole known-drug table for that gene.

**Schema note (verified live 2026-09-06).** The v4 schema this repository was written
against has moved on:

* ``Target.knownDrugs`` no longer exists. The equivalent field is
  ``Target.drugAndClinicalCandidates`` (``clinicalTargets``), whose rows are
  ``ClinicalTargetFromTarget``.
* the clinical phase is no longer an integer ``phase`` but a string
  ``maxClinicalStage`` — ``"PHASE_1"``, ``"PHASE_2_3"``, ``"APPROVAL"``. :data:`STAGES`
  maps it back onto the integer phase the rest of this package uses, so the row shape the
  contract fixes is unchanged; ``"APPROVAL"`` is phase 4.
* ``Tractability`` fields are ``label``/``modality``/``value``, not ``id``.
* the disease attached to a row is a ``ClinicalDiseaseListItem``: a free-text
  ``diseaseFromSource`` plus an optional resolved ``disease {id name}``, which is ``null``
  when the source text never mapped to an ontology term.

``status`` comes from the row's clinical reports (``trialOverallStatus``), which is where
the old flat ``status`` field went.
"""

from __future__ import annotations

from typing import Any

from ..cache import Fetcher, SourceError

__all__ = [
    "ENDPOINT",
    "STAGES",
    "candidate_rows",
    "disease_known_drugs",
    "disease_search",
    "known_drugs",
    "stage_to_phase",
    "target_by_symbol",
]

ENDPOINT = "https://api.platform.opentargets.org/api/v4/graphql"

#: ``maxClinicalStage`` → the integer clinical phase. A combined stage takes its upper
#: bound (``PHASE_2_3`` is a phase-3 trial that enrolled from phase 2), and ``APPROVAL``
#: is phase 4 — the value the eligibility rule for this challenge keys on.
STAGES: dict[str, int] = {
    "PRECLINICAL": 0,
    "PHASE_1": 1,
    "PHASE_1_2": 2,
    "PHASE_2": 2,
    "PHASE_2_3": 3,
    "PHASE_3": 3,
    "PHASE_4": 4,
    "APPROVAL": 4,
    "APPROVED": 4,
}

_SEARCH = """
query($q: String!, $entity: String!) {
  search(queryString: $q, entityNames: [$entity]) { hits { id name entity } }
}
"""

_DRUG_ROWS = """
  count
  rows {
    maxClinicalStage
    drug {
      id name drugType maximumClinicalStage
      mechanismsOfAction { rows { mechanismOfAction actionType targets { approvedSymbol } } }
    }
    diseases { diseaseFromSource disease { id name } }
    clinicalReports { trialOverallStatus }
  }
"""

_TARGET = f"""
query($id: String!) {{
  target(ensemblId: $id) {{
    id approvedSymbol approvedName
    tractability {{ label modality value }}
    drugAndClinicalCandidates {{ {_DRUG_ROWS} }}
  }}
}}
"""

_DISEASE = f"""
query($id: String!) {{
  disease(efoId: $id) {{
    id name
    drugAndClinicalCandidates {{ {_DRUG_ROWS} }}
  }}
}}
"""


def _query(fetcher: Fetcher, query: str, variables: dict[str, Any]) -> dict[str, Any]:
    payload = fetcher.post_json(ENDPOINT, {"query": query, "variables": variables})
    if not isinstance(payload, dict):
        raise SourceError(ENDPOINT, "GraphQL reply was not an object")
    if payload.get("errors"):
        raise SourceError(ENDPOINT, f"GraphQL errors: {payload['errors']}")
    data = payload.get("data")
    return data if isinstance(data, dict) else {}


def stage_to_phase(stage: str | None) -> int | None:
    """``"PHASE_2_3"`` → ``3``; an unknown or absent stage → ``None``, never a guess."""
    return STAGES.get((stage or "").upper()) if stage else None


def target_by_symbol(fetcher: Fetcher, symbol: str) -> dict[str, Any] | None:
    """Resolve a gene symbol to its Open Targets target record, or ``None`` if unknown.

    Two calls: a search for the Ensembl gene id, then the target itself. The search is
    matched on ``name`` exactly (case-insensitively) rather than taken as the top hit —
    searching ``BUB1B`` also returns the readthrough gene ``BUB1B-PAK6``, and the top hit
    is not always the exact symbol.
    """
    hits = _query(fetcher, _SEARCH, {"q": symbol, "entity": "target"})
    matches = [
        hit
        for hit in (hits.get("search") or {}).get("hits", [])
        if str(hit.get("name", "")).upper() == symbol.upper()
    ]
    if not matches:
        return None
    data = _query(fetcher, _TARGET, {"id": matches[0]["id"]})
    target = data.get("target")
    if not isinstance(target, dict):
        return None
    return {
        "ensembl_id": target.get("id"),
        "approvedSymbol": target.get("approvedSymbol"),
        "approvedName": target.get("approvedName"),
        "tractability": [
            {"label": t.get("label"), "modality": t.get("modality"), "value": t.get("value")}
            for t in target.get("tractability") or []
            if t.get("value")
        ],
        "candidates_block": target.get("drugAndClinicalCandidates") or {},
    }


def known_drugs(fetcher: Fetcher, ensembl_id: str) -> list[dict[str, Any]]:
    """Every drug and clinical candidate Open Targets ties to one target."""
    data = _query(fetcher, _TARGET, {"id": ensembl_id})
    target = data.get("target")
    if not isinstance(target, dict):
        return []
    return candidate_rows(target.get("drugAndClinicalCandidates") or {})


def disease_search(fetcher: Fetcher, text: str) -> list[dict[str, str]]:
    """Free text → candidate disease terms, best match first, as ``{efo_id, name}``."""
    data = _query(fetcher, _SEARCH, {"q": text, "entity": "disease"})
    return [
        {"efo_id": str(hit.get("id", "")), "name": str(hit.get("name", ""))}
        for hit in (data.get("search") or {}).get("hits", [])
        if hit.get("id")
    ]


def disease_known_drugs(fetcher: Fetcher, efo_id: str) -> list[dict[str, Any]]:
    """Every drug and clinical candidate Open Targets ties to one disease term."""
    data = _query(fetcher, _DISEASE, {"id": efo_id})
    disease = data.get("disease")
    if not isinstance(disease, dict):
        return []
    return candidate_rows(disease.get("drugAndClinicalCandidates") or {})


def candidate_rows(block: dict[str, Any]) -> list[dict[str, Any]]:
    """One contract-shaped row per (candidate, disease) pair the API returns.

    A candidate tried in three diseases becomes three rows, which is the shape the old
    ``knownDrugs`` table had and the shape the candidate gatherer dedups over.
    """
    out: list[dict[str, Any]] = []
    for row in block.get("rows") or []:
        drug = row.get("drug") or {}
        phase = stage_to_phase(row.get("maxClinicalStage")) or stage_to_phase(
            drug.get("maximumClinicalStage")
        )
        moa, action, targets = _mechanism(drug)
        status = _status(row)
        diseases = row.get("diseases") or [{}]
        for entry in diseases:
            resolved = entry.get("disease") or {}
            out.append(
                {
                    "drug_id": drug.get("id"),
                    "drug_name": drug.get("name"),
                    "drug_type": drug.get("drugType"),
                    "mechanism_of_action": moa,
                    "action_type": action,
                    "mechanism_targets": targets,
                    "phase": phase,
                    "status": status,
                    "disease_id": resolved.get("id") or "",
                    "disease_name": resolved.get("name") or entry.get("diseaseFromSource") or "",
                    "approved": phase == 4,
                }
            )
    return out


def _mechanism(drug: dict[str, Any]) -> tuple[str, str, tuple[str, ...]]:
    """The first stated mechanism of action, its action type, and the symbols it names."""
    rows = ((drug.get("mechanismsOfAction") or {}).get("rows")) or []
    if not rows:
        return "", "", ()
    first = rows[0]
    symbols = tuple(
        str(t.get("approvedSymbol"))
        for row in rows
        for t in row.get("targets") or []
        if t.get("approvedSymbol")
    )
    return (
        str(first.get("mechanismOfAction") or ""),
        str(first.get("actionType") or ""),
        tuple(dict.fromkeys(symbols)),
    )


def _status(row: dict[str, Any]) -> str:
    """The first stated trial status among the row's clinical reports."""
    for report in row.get("clinicalReports") or []:
        value = report.get("trialOverallStatus")
        if value:
            return str(value)
    return ""
