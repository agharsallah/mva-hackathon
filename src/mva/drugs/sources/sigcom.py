"""SigCom LINCS (Ma'ayan lab), over its metadata and data APIs.

SigCom LINCS serves the LINCS L1000 2021 signatures: one **signature** (the expression change
one perturbation caused in one cell line at one dose and time) per record, grouped into
libraries — ``l1000_cp`` (chemicals), ``l1000_xpr`` (CRISPR knockouts), ``l1000_shRNA`` …
A query is an up-gene set and a down-gene set; the reply ranks every signature of a library
by how well its own ranked gene list agrees (**mimicker**) or disagrees (**reverser**).

**Schema notes (verified live 2026-09-25).**

* Two hosts. The metadata API is ``maayanlab.cloud/sigcom-lincs/metadata-api``. The data
  API's public path ``maayanlab.cloud/sigcom-lincs/data-api`` answers a POST with a 307 to
  ``data-api.sigcom-lincs.k8s.maayanlab.cloud``; clients that do not replay a POST across a
  redirect (``urllib``, ``httpx`` by default) must call the target host directly.
* Gene sets are sent as entity UUIDs, not symbols: ``entities/find`` maps one to the other.
* ``enrich/ranktwosided`` with ``limit=N`` returns the top N mimickers **and** the top N
  reversers. ``rank`` is 0-based over the whole library in mimicker order, so a reverser's
  own position is ``maxRank - 1 - rank``.
* ``signatures/find`` pages with LoopBack ``limit``/``skip``; ``fields`` trims the reply.

The cache (:class:`~mva.drugs.cache.Fetcher`) makes every reply replayable offline.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from typing import Any

from ..cache import Fetcher

__all__ = [
    "DATA",
    "METADATA",
    "crawl_library",
    "entity_ids",
    "library_ids",
    "rank_two_sided",
    "reverser_position",
    "signature_count",
]

METADATA = "https://maayanlab.cloud/sigcom-lincs/metadata-api"
#: The data API's redirect target (see the module docstring for why not the public path).
DATA = "https://data-api.sigcom-lincs.k8s.maayanlab.cloud/v1/api/v1"

#: Symbols per ``entities/find`` request: small enough for any proxy, large enough to be few.
ENTITY_BATCH = 250


def library_ids(fetcher: Fetcher, datasets: Sequence[str]) -> dict[str, str]:
    """``{"l1000_cp": "<library uuid>", …}`` for the named datasets SigCom holds."""
    payload = fetcher.post_json(
        f"{METADATA}/libraries/find",
        {"filter": {"where": {"dataset": {"inq": list(datasets)}}, "fields": ["id", "dataset"]}},
    )
    return {str(row["dataset"]): str(row["id"]) for row in payload or [] if row.get("id")}


def entity_ids(fetcher: Fetcher, symbols: Iterable[str]) -> dict[str, str]:
    """Gene symbol → SigCom entity UUID. A symbol SigCom does not know is simply absent."""
    wanted = sorted({s for s in symbols if s})
    out: dict[str, str] = {}
    for start in range(0, len(wanted), ENTITY_BATCH):
        chunk = wanted[start : start + ENTITY_BATCH]
        payload = fetcher.post_json(
            f"{METADATA}/entities/find",
            {
                "filter": {
                    "where": {"meta.symbol": {"inq": chunk}},
                    "fields": ["id", "meta.symbol"],
                }
            },
        )
        for row in payload or []:
            symbol = str((row.get("meta") or {}).get("symbol") or "")
            if symbol in chunk and row.get("id"):
                out.setdefault(symbol, str(row["id"]))
    return out


def crawl_library(
    fetcher: Fetcher,
    library: str,
    *,
    fields: Sequence[str] = ("id", "meta.pert_name", "meta.cell_line"),
    page: int = 20_000,
    expected: int | None = None,
) -> list[dict[str, Any]]:
    """Every signature record of one library, paged ``page`` at a time, ordered by id.

    Keyset paging (``id > last seen``), not ``skip``: a deep ``skip`` over the chemical
    library (700k rows) timed out with HTTP 504 on 2026-09-25, a keyset page does not.

    ``expected`` (from ``signatures/count``) is checked after the crawl: a short or
    duplicated crawl raises instead of silently shrinking the universe.
    """
    rows: list[dict[str, Any]] = []
    last = ""
    while True:
        where: dict[str, Any] = {"library": library}
        if last:
            where["id"] = {"gt": last}
        payload = fetcher.post_json(
            f"{METADATA}/signatures/find",
            {"filter": {"where": where, "fields": list(fields), "order": "id ASC", "limit": page}},
        )
        batch = list(payload or [])
        rows.extend(batch)
        if len(batch) < page:
            break
        last = str(batch[-1]["id"])
    unique = len({row.get("id") for row in rows})
    if unique != len(rows) or (expected is not None and unique != expected):
        raise ValueError(
            f"SigCom crawl of {library}: {len(rows)} rows, {unique} unique ids, expected {expected}"
        )
    return rows


def signature_count(fetcher: Fetcher, library: str) -> int:
    """How many signatures one library holds, from ``signatures/count``."""
    payload = fetcher.get_json(
        f"{METADATA}/signatures/count", {"where": json.dumps({"library": library})}
    )
    return int((payload or {}).get("count", 0))


def rank_two_sided(
    fetcher: Fetcher,
    up_ids: Sequence[str],
    down_ids: Sequence[str],
    *,
    database: str,
    limit: int,
) -> dict[str, Any]:
    """One two-sided rank enrichment: ``{"maxRank", "mimickers", "reversers", "results"}``."""
    payload = fetcher.post_json(
        f"{DATA}/enrich/ranktwosided",
        {
            "up_entities": sorted(up_ids),
            "down_entities": sorted(down_ids),
            "database": database,
            "limit": limit,
        },
    )
    if not isinstance(payload, dict) or "results" not in payload:
        raise ValueError(f"SigCom {database}: reply has no results ({str(payload)[:200]})")
    return payload


def reverser_position(result: dict[str, Any], max_rank: int) -> int:
    """1-based position of one result among reversers (1 = the strongest reverser)."""
    return max_rank - int(result["rank"])
