"""PubMed, over NCBI's E-utilities.

The literature table is the evidence layer under every repurposing direction: a direction
with no publication behind it is a guess, and the snapshot should say so by returning zero
rows rather than by omitting the query.

Two calls, the standard E-utilities pair: ``esearch`` turns a query into PMIDs,
``esummary`` turns PMIDs into citations. NCBI asks for **no more than 3 requests per
second** without an API key, which is the default ``min_interval_s`` the snapshot gives
this source's fetcher.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..cache import Fetcher

__all__ = ["BASE", "SUMMARY_BATCH", "search", "summaries"]

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

#: PMIDs per esummary call. NCBI's documented ceiling for a GET is 200.
SUMMARY_BATCH = 200


def search(fetcher: Fetcher, term: str, retmax: int = 50) -> list[str]:
    """PMIDs for one query, most recent first (E-utilities' default sort).

    A query that matches nothing returns an empty list. That is a result, not a failure:
    "no one has published on this" is exactly what a repurposing case needs to know.
    """
    if not term.strip():
        return []
    payload = fetcher.get_json(
        f"{BASE}/esearch.fcgi",
        {"db": "pubmed", "term": term, "retmax": retmax, "retmode": "json"},
    )
    result = (payload or {}).get("esearchresult") or {}
    return [str(pmid) for pmid in result.get("idlist") or []]


def count(fetcher: Fetcher, term: str) -> int:
    """How many records the query matches in total, independent of ``retmax``."""
    if not term.strip():
        return 0
    payload = fetcher.get_json(
        f"{BASE}/esearch.fcgi",
        {"db": "pubmed", "term": term, "retmax": 0, "retmode": "json"},
    )
    raw = ((payload or {}).get("esearchresult") or {}).get("count")
    try:
        return int(str(raw))
    except (TypeError, ValueError):
        return 0


def summaries(fetcher: Fetcher, pmids: Sequence[str]) -> list[dict[str, Any]]:
    """Citations for a list of PMIDs, in the order asked, as ``{pmid,title,journal,year,doi}``."""
    wanted = [str(p) for p in pmids if p]
    if not wanted:
        return []
    found: dict[str, dict[str, Any]] = {}
    for i in range(0, len(wanted), SUMMARY_BATCH):
        chunk = wanted[i : i + SUMMARY_BATCH]
        payload = fetcher.get_json(
            f"{BASE}/esummary.fcgi",
            {"db": "pubmed", "id": ",".join(chunk), "retmode": "json"},
        )
        result = (payload or {}).get("result") or {}
        for uid in result.get("uids") or []:
            record = result.get(str(uid))
            if isinstance(record, dict):
                found[str(uid)] = _row(record)
    return [found[p] for p in wanted if p in found]


def _row(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "pmid": str(record.get("uid") or ""),
        "title": str(record.get("title") or "").rstrip("."),
        "journal": str(record.get("source") or ""),
        "year": _year(record.get("pubdate")),
        "doi": _doi(record),
    }


def _year(pubdate: Any) -> str:
    """The four-digit year out of ``"2019 Jun"``; empty when there is none to take."""
    head = str(pubdate or "").strip().split(" ")[0]
    return head if head.isdigit() and len(head) == 4 else ""


def _doi(record: dict[str, Any]) -> str:
    for entry in record.get("articleids") or []:
        if entry.get("idtype") == "doi" and entry.get("value"):
            return str(entry["value"])
    return ""
