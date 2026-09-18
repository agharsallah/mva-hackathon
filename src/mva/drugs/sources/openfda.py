"""openFDA drug labelling, over ``api.fda.gov``.

The challenge's eligibility rule is *market-approved drugs only*, and this is the second
of its two evidences: a drug with a current FDA Structured Product Label is on the US
market today, whatever ChEMBL's ``max_phase`` says. The two disagree in both directions —
ChEMBL carries phase 4 for drugs approved only outside the US, and openFDA carries labels
for generics ChEMBL never assigned a phase to — so a candidate row records both and lets a
reader see which evidence it rests on.

**A 404 is data, not an error.** openFDA answers ``404 NOT_FOUND`` when a search matches no
label, and that is exactly the answer "no US label for this name". It is returned as
``has_label: False``, never raised.
"""

from __future__ import annotations

from typing import Any

from ..cache import Fetcher

__all__ = ["ENDPOINT", "label"]

ENDPOINT = "https://api.fda.gov/drug/label.json"


def label(fetcher: Fetcher, generic_name: str) -> dict[str, Any]:
    """The first label matching a generic name, flattened; ``has_label`` says whether one exists.

    The name is matched against ``openfda.generic_name`` as a quoted phrase, so a
    multi-word name is one term rather than an OR over its words.
    """
    name = generic_name.strip()
    if not name:
        return _empty(generic_name)
    payload = fetcher.get_json(
        ENDPOINT,
        {"search": f'openfda.generic_name:"{name}"', "limit": 1},
        allow_status=(404,),
    )
    results = (payload or {}).get("results") if isinstance(payload, dict) else None
    if not results:
        return _empty(generic_name)
    entry = results[0].get("openfda") or {}
    return {
        # The label's own "8.4 Pediatric Use" section, present or absent. Present means the
        # label *discusses* children - it may say "safety not established" - so this is a
        # pointer to read, never a licence. Absent means the label carries no such section.
        "pediatric_use": bool(results[0].get("pediatric_use")),
        "generic_name": _first(entry.get("generic_name")) or generic_name,
        "brand_names": tuple(str(b) for b in entry.get("brand_name") or []),
        "application_numbers": tuple(str(a) for a in entry.get("application_number") or []),
        "routes": tuple(str(r) for r in entry.get("route") or []),
        "has_label": True,
    }


def _empty(generic_name: str) -> dict[str, Any]:
    return {
        "generic_name": generic_name,
        "brand_names": (),
        "application_numbers": (),
        "routes": (),
        "has_label": False,
        "pediatric_use": False,
    }


def _first(value: Any) -> str:
    return str(value[0]) if isinstance(value, list) and value else ""
