"""Has this approved drug ever been given to children in a registered study?

The evidence ladder's top rung asks for paediatric use, and the snapshot's trial stage cannot
answer it: it asks about the drug in the *tumour context*, which for an ultra-rare paediatric
syndrome is usually nothing. This asks the wider question - any indication, any phase, as long
as the study admits children - through the v2 API's own age aggregate (``aggFilters=ages:child``).

A hit is a pointer, not a licence: a study that *admits* children may have enrolled none, and a
study registered is not a study completed. The row keeps the registry's eligibility fields
(minimum and maximum age, the age groups) so a reader can judge, and the ladder prints the
count beside the label's own paediatric section rather than merging the two.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from .sources import clinicaltrials

__all__ = ["CHILD_FILTER", "MAX_CONDITIONS", "studies_for", "survey"]

#: ClinicalTrials.gov v2's aggregate filter for studies whose age groups include children.
CHILD_FILTER = {"aggFilters": "ages:child"}

#: Basket studies list hundreds of conditions; the row keeps this many and says how many
#: more there were. The question here is "does it admit children", not "what does it treat".
MAX_CONDITIONS = 12

#: One registry record carries a 240,000-character title (a pasted document). A title longer
#: than this is cut and marked, so one bad record cannot make the table unreadable.
MAX_TITLE = 300


def studies_for(fetcher: Any, drug_name: str, *, max_pages: int = 1) -> list[dict[str, Any]]:
    """Studies of ``drug_name`` that admit children, one page (the API's 100) by default."""
    found = clinicaltrials.studies(
        fetcher, intr=drug_name, max_pages=max_pages, extra=dict(CHILD_FILTER)
    )
    query = f"intr={drug_name} aggFilters=ages:child"
    return [{"drug_name": drug_name, **_trim(row), "query": query} for row in found]


def _trim(row: dict[str, Any]) -> dict[str, Any]:
    conditions = tuple(row.get("conditions") or ())
    if len(conditions) > MAX_CONDITIONS:
        extra = len(conditions) - MAX_CONDITIONS
        conditions = (*conditions[:MAX_CONDITIONS], f"...(+{extra} more)")
    title = str(row.get("title") or "")
    if len(title) > MAX_TITLE:
        title = title[:MAX_TITLE] + " ...(cut)"
    return {**row, "conditions": conditions, "title": title}


def survey(
    fetcher: Any,
    drug_names: Iterable[str],
    *,
    max_pages: int = 1,
    progress: Callable[[str], None] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Every drug once. Returns ``(rows, log)``; the log carries the hit count per drug."""
    say = progress or (lambda _line: None)
    names = list(dict.fromkeys(drug_names))
    rows: list[dict[str, Any]] = []
    log: list[dict[str, Any]] = []
    for index, name in enumerate(names, start=1):
        found = studies_for(fetcher, name, max_pages=max_pages)
        rows.extend(found)
        log.append({"drug_name": name, "hits": len(found), "pages": max_pages})
        if index % 25 == 0 or index == len(names):
            say(f"  paediatric trials {index}/{len(names)} drugs  rows {len(rows)}")
    return rows, log
