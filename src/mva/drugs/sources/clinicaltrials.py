"""ClinicalTrials.gov, over the v2 REST API.

Two questions this answers, both of which a repurposing case must ask:

* **has anyone ever run a trial in this disease?** For an ultra-rare N-of-1 syndrome the
  honest answer is usually *no*, and an empty result set is the finding — it is the
  argument for repurposing rather than against it.
* **is this approved drug already in trials in the child's tumour context?** A drug with
  an existing paediatric sarcoma trial is a far shorter path than one without.

The v2 API nests everything under ``protocolSection``; this adapter flattens the eight
fields the contract fixes and drops the rest. Paging is by ``nextPageToken``.
"""

from __future__ import annotations

from typing import Any

from ..cache import Fetcher

__all__ = ["ENDPOINT", "PAGE_SIZE", "studies"]

ENDPOINT = "https://clinicaltrials.gov/api/v2/studies"

#: The API's own maximum page size. Fewer requests, same bytes.
PAGE_SIZE = 100


def studies(
    fetcher: Fetcher,
    cond: str | None = None,
    intr: str | None = None,
    page_size: int = PAGE_SIZE,
    max_pages: int = 3,
    extra: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Studies matching a condition and/or an intervention, flattened.

    ``max_pages`` bounds the walk: a broad condition can return thousands of studies and
    a snapshot does not need all of them to answer "is there any trial activity here".
    The bound is recorded in the manifest so a reader knows the table is a head, not a
    census, whenever a query hit it.

    ``extra`` is passed through verbatim - the v2 API's ``aggFilters`` (for instance
    ``ages:child``) is the one this repository uses, for the paediatric question.
    """
    params: dict[str, Any] = {"pageSize": page_size, "format": "json", **(extra or {})}
    if cond:
        params["query.cond"] = cond
    if intr:
        params["query.intr"] = intr
    if not cond and not intr:
        return []

    out: list[dict[str, Any]] = []
    token: str | None = None
    for _ in range(max(max_pages, 1)):
        page = dict(params)
        if token:
            page["pageToken"] = token
        payload = fetcher.get_json(ENDPOINT, page)
        if not isinstance(payload, dict):
            break
        for study in payload.get("studies") or []:
            row = _row(study)
            if row:
                out.append(row)
        token = payload.get("nextPageToken")
        if not token:
            break
    return out


def _row(study: dict[str, Any]) -> dict[str, Any] | None:
    protocol = study.get("protocolSection")
    if not isinstance(protocol, dict):
        return None
    ident = protocol.get("identificationModule") or {}
    status = protocol.get("statusModule") or {}
    design = protocol.get("designModule") or {}
    conditions = protocol.get("conditionsModule") or {}
    arms = protocol.get("armsInterventionsModule") or {}
    eligibility = protocol.get("eligibilityModule") or {}
    nct = str(ident.get("nctId") or "")
    if not nct:
        return None
    return {
        "nct_id": nct,
        "title": str(ident.get("briefTitle") or ident.get("officialTitle") or ""),
        "phase": "|".join(str(p) for p in design.get("phases") or []),
        "overall_status": str(status.get("overallStatus") or ""),
        "conditions": tuple(str(c) for c in conditions.get("conditions") or []),
        "interventions": tuple(
            str(i.get("name")) for i in arms.get("interventions") or [] if i.get("name")
        ),
        "start_date": str((status.get("startDateStruct") or {}).get("date") or ""),
        "study_type": str(design.get("studyType") or ""),
        # Eligibility, for the paediatric question. Empty when the registry states none.
        "min_age": str(eligibility.get("minimumAge") or ""),
        "max_age": str(eligibility.get("maximumAge") or ""),
        "std_ages": tuple(str(a) for a in eligibility.get("stdAges") or []),
    }
