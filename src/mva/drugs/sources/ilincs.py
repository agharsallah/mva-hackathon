"""iLINCS (University of Cincinnati), over its REST API.

A second, independently built connectivity engine over LINCS chemical signatures: its own
signature processing, its own library (``LIB_5``, the LINCS consensus chemical
signatures, ids ``LINCSCP_<n>``) and its own score — for an up/down query, a
**concordance** (a similarity in [-1, 1] between the query and each signature over the
query genes the signature measures). Negative = the compound pushes the genes the other
way: a reverser.

**Schema notes (verified live 2026-09-25).**

* ``POST /api/ilincsR/findConcordancesSC`` wants ``genesUp`` / ``genesDown`` as JSON
  **arrays**; a comma string gives HTTP 400.
* It scores only the L1000 **landmark** genes (the 978 genes the assay measures);
  ``NoOfGenes`` in the reply says how many query genes were used.
* It returns only signatures with ``pValue < 0.05`` — a truncated list, not the library.
* ``GET /api/SignatureMeta`` pages LoopBack-style with a JSON ``filter`` parameter.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from ..cache import Fetcher

__all__ = ["BASE", "CHEMICAL_LIBRARY", "concordance", "crawl_library", "signature_count"]

BASE = "https://www.ilincs.org/api"

#: LINCS chemical perturbation signatures, the library ``findConcordancesSC`` scores.
CHEMICAL_LIBRARY = "LIB_5"


def concordance(fetcher: Fetcher, up: Sequence[str], down: Sequence[str]) -> dict[str, Any]:
    """One UpDn query: ``{"genes_used", "rows"}``; rows keep the reply's own field names."""
    payload = fetcher.post_json(
        f"{BASE}/ilincsR/findConcordancesSC",
        {
            "mode": "UpDn",
            "metadata": True,
            "signatureProfile": {"genesUp": sorted(up), "genesDown": sorted(down)},
        },
    )
    if not isinstance(payload, dict) or "concordanceTable" not in payload:
        raise ValueError(f"iLINCS: reply has no concordanceTable ({str(payload)[:200]})")
    used = payload.get("NoOfGenes")
    genes_used = int(used[0]) if isinstance(used, list) and used else None
    return {"genes_used": genes_used, "rows": list(payload["concordanceTable"])}


def signature_count(fetcher: Fetcher, library: str = CHEMICAL_LIBRARY) -> int:
    payload = fetcher.get_json(
        f"{BASE}/SignatureMeta/count", {"where": json.dumps({"libraryid": library})}
    )
    return int((payload or {}).get("count", 0))


def crawl_library(
    fetcher: Fetcher,
    library: str = CHEMICAL_LIBRARY,
    *,
    fields: Sequence[str] = ("signatureid", "compound", "lincspertid", "pubChemID"),
    page: int = 20_000,
    expected: int | None = None,
) -> list[dict[str, Any]]:
    """Every signature record of one library, ordered by id; a short crawl raises."""
    rows: list[dict[str, Any]] = []
    skip = 0
    while True:
        batch = list(
            fetcher.get_json(
                f"{BASE}/SignatureMeta",
                {
                    "filter": json.dumps(
                        {
                            "where": {"libraryid": library},
                            "fields": list(fields),
                            "order": "signatureid ASC",
                            "limit": page,
                            "skip": skip,
                        }
                    )
                },
            )
            or []
        )
        rows.extend(batch)
        if len(batch) < page:
            break
        skip += page
    unique = len({row.get("signatureid") for row in rows})
    if unique != len(rows) or (expected is not None and unique != expected):
        raise ValueError(
            f"iLINCS crawl of {library}: {len(rows)} rows, {unique} unique ids, expected {expected}"
        )
    return rows
