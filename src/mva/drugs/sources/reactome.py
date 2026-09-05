"""Reactome, over its ContentService REST API.

Reactome supplies the *pathway neighbourhood*: given the affected protein, which curated
reactions and pathways it participates in, and which other proteins participate in those.
That turns a short seed list into a mechanism-shaped target set — a drug that hits a
different member of the same checkpoint is a candidate the seed list alone would miss.

**Schema note (verified live 2026-09-06).** ``/data/pathways/low/entity/{id}`` takes a
*Reactome* identifier (a stable id or dbId) and answers ``404 NOT_FOUND`` for a UniProt
accession. The endpoint that maps an external accession to pathways is
``/data/mapping/UniProt/{accession}/pathways``, which this module uses instead; the
function keeps the contracted name and signature.

``/data/participants/{stId}/referenceEntities`` returns whole UniProt records — a few
hundred kB per pathway, most of it free-text comments. Only ``geneName[0]`` of each human
``ReferenceGeneProduct`` is kept.
"""

from __future__ import annotations

from typing import Any

from ..cache import Fetcher

__all__ = ["BASE", "SPECIES", "participants", "pathways_for_uniprot", "search_pathway"]

BASE = "https://reactome.org/ContentService"

#: NCBI taxon id for human. A pathway inferred into another species is a different object.
SPECIES = "9606"

#: The species name Reactome's search endpoint expects (it takes a name, not a taxon id).
SPECIES_NAME = "Homo sapiens"

#: The class of participant that maps back to a gene. Small molecules, complexes and
#: sets also participate in a pathway; none of them names a gene.
GENE_PRODUCT = "ReferenceGeneProduct"


def pathways_for_uniprot(fetcher: Fetcher, uniprot: str) -> list[dict[str, str]]:
    """Lower-level pathways containing one UniProt accession, as ``{stId, displayName}``.

    An accession Reactome does not annotate answers ``404``; that is "not curated here",
    not a failure, so the empty list is returned rather than raising.
    """
    url = f"{BASE}/data/mapping/UniProt/{uniprot}/pathways"
    payload = fetcher.get_json(url, {"species": SPECIES}, allow_status=(404,))
    if not isinstance(payload, list):
        return []
    return [
        {"stId": str(row.get("stId")), "displayName": str(row.get("displayName") or "")}
        for row in payload
        if row.get("stId") and row.get("speciesName") in (SPECIES_NAME, None)
    ]


def participants(fetcher: Fetcher, st_id: str) -> list[str]:
    """The gene symbols of every human protein participating in one pathway.

    First-seen order, deduped. A participant with no ``geneName`` — an unnamed isoform, a
    non-protein entity — contributes nothing rather than a placeholder symbol.
    """
    payload = fetcher.get_json(
        f"{BASE}/data/participants/{st_id}/referenceEntities", allow_status=(404,)
    )
    if not isinstance(payload, list):
        return []
    seen: dict[str, None] = {}
    for entity in payload:
        if not isinstance(entity, dict) or entity.get("className") != GENE_PRODUCT:
            continue
        names = entity.get("geneName") or []
        if names:
            seen.setdefault(str(names[0]), None)
    return list(seen)


def search_pathway(fetcher: Fetcher, text: str) -> list[dict[str, str]]:
    """Free text → human Reactome pathways, best match first, as ``{stId, name}``.

    The search service marks matched words with ``<span class="highlighting">`` inside the
    returned name; the markup is stripped here so a name written to a table is plain text.
    """
    payload = fetcher.get_json(
        f"{BASE}/search/query",
        {
            "query": text,
            "species": SPECIES_NAME,
            "types": "Pathway",
            "cluster": "true",
        },
        allow_status=(404,),
    )
    out: list[dict[str, str]] = []
    for group in _results(payload):
        out.extend(
            {"stId": str(entry["stId"]), "name": _plain(entry.get("name"))}
            for entry in group.get("entries") or []
            if entry.get("stId")
        )
    return out


def _results(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    results = payload.get("results")
    return [r for r in results if isinstance(r, dict)] if isinstance(results, list) else []


def _plain(value: Any) -> str:
    """Drop the search service's highlight markup from a returned name."""
    text = str(value or "")
    for token in ('<span class="highlighting" >', "<span class='highlighting' >", "</span>"):
        text = text.replace(token, "")
    return text.strip()
