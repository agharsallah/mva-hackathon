"""DGIdb (the Drug–Gene Interaction Database), over its GraphQL endpoint.

DGIdb is the *union* source: it aggregates 40-odd curated resources (ChEMBL, TTD,
GuideToPharmacology, MyCancerGenome, NCI, DrugBank's open subset…) into one gene → drug
edge list, each edge carrying which resources asserted it and how confident their union
is. Where Open Targets integrates deeply for a handful of well-studied targets, DGIdb
covers breadth — it will name a drug for a gene that Open Targets has no clinical row for.

One request answers a whole gene list, so the whole target set costs a single call.

**Schema note (verified live 2026-09-06).** The field is ``interactionScore``, not
``score``; ``publications`` carry ``pmid``; ``sources`` carry ``sourceDbName``. The
contract's row shape is preserved by renaming at the edge of this adapter, so nothing
downstream sees DGIdb's spelling.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..cache import Fetcher, SourceError

__all__ = ["ENDPOINT", "interactions"]

ENDPOINT = "https://dgidb.org/api/graphql"

_QUERY = """
query($names: [String!]) {
  genes(names: $names) {
    nodes {
      name
      interactions {
        drug { name conceptId approved }
        interactionScore
        interactionTypes { type directionality }
        publications { pmid }
        sources { sourceDbName }
      }
    }
  }
}
"""


def interactions(fetcher: Fetcher, gene_symbols: Sequence[str]) -> list[dict[str, Any]]:
    """Every drug–gene edge DGIdb holds for the given symbols, one row per edge.

    Symbols DGIdb does not know simply return no rows — that is "no curated interaction",
    not an error, and it is not distinguishable in the reply from "gene not in DGIdb".
    Both are the same statement for our purpose: nothing to add.
    """
    wanted = [str(s) for s in gene_symbols if s]
    if not wanted:
        return []
    payload = fetcher.post_json(ENDPOINT, {"query": _QUERY, "variables": {"names": wanted}})
    if not isinstance(payload, dict):
        raise SourceError(ENDPOINT, "GraphQL reply was not an object")
    if payload.get("errors"):
        raise SourceError(ENDPOINT, f"GraphQL errors: {payload['errors']}")
    nodes = ((payload.get("data") or {}).get("genes") or {}).get("nodes") or []
    out: list[dict[str, Any]] = []
    for node in nodes:
        gene = str(node.get("name") or "")
        for edge in node.get("interactions") or []:
            drug = edge.get("drug") or {}
            out.append(
                {
                    "gene": gene,
                    "drug_name": str(drug.get("name") or ""),
                    "drug_concept_id": str(drug.get("conceptId") or ""),
                    "approved": bool(drug.get("approved")),
                    "interaction_types": tuple(
                        dict.fromkeys(
                            str(t.get("type"))
                            for t in edge.get("interactionTypes") or []
                            if t.get("type")
                        )
                    ),
                    "sources": tuple(
                        dict.fromkeys(
                            str(s.get("sourceDbName"))
                            for s in edge.get("sources") or []
                            if s.get("sourceDbName")
                        )
                    ),
                    "pmids": tuple(
                        dict.fromkeys(
                            str(p.get("pmid"))
                            for p in edge.get("publications") or []
                            if p.get("pmid")
                        )
                    ),
                    "score": edge.get("interactionScore"),
                }
            )
    return out


def chembl_id(concept_id: str) -> str | None:
    """``"chembl:CHEMBL3586573"`` → ``"CHEMBL3586573"``; any other namespace → ``None``.

    DGIdb's concept ids are namespaced (``chembl:``, ``ncit:``, ``rxcui:``…). Only the
    ChEMBL ones can be enriched with approval facts from ChEMBL, so the rest stay as they
    are rather than being coerced into an id that would not resolve.
    """
    if not concept_id:
        return None
    namespace, _, rest = concept_id.partition(":")
    return rest or None if namespace.lower() == "chembl" else None
