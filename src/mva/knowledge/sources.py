"""The three public literature APIs step 5 reads, one thin adapter each.

Same contract as every adapter under :mod:`mva.drugs.sources`: the first argument is a
:class:`~mva.drugs.cache.Fetcher`, the function holds no state, and the caching, the
politeness interval and the provenance digest all belong to the fetcher rather than to
this module. Swap the fetcher and the same call runs offline from the cache.

**Three sources, three different questions, and they are not interchangeable:**

``LitVar 2.0``
    keyed on a dbSNP identifier. *Has anyone published about this exact variant?* It is
    the only one of the three that can answer at allele resolution, which is why step 5
    asks it about the child's own alleles rather than about genes.
``PubTator 3.0``
    a full-text search over PubMed and PMC with entities already annotated. *Which papers
    mention this gene together with this clinical feature?* Used once per (gene, term)
    pair, so a paper's matched-term count falls out of the queries themselves.
``PubMed (E-utilities)``
    reached through the existing :mod:`mva.drugs.sources.pubmed` client, not re-written
    here. It supplies the **citation-volume baseline** — how many papers mention the gene
    at all — which is the null the knowledge ranking has to beat to be worth anything.

Every function returns plain rows and raises :class:`~mva.drugs.cache.SourceError` rather
than returning a sentinel: a source that cannot be read is a recorded fact in the
methodology entry, never a silent zero.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from urllib.parse import quote

from ..drugs.cache import Fetcher, SourceError

__all__ = [
    "LITVAR",
    "NOT_FOUND",
    "PUBTATOR",
    "gene_query",
    "litvar_id",
    "litvar_path",
    "publications_for_rsid",
    "search_papers",
    "unique_pmids",
    "variants_for_gene",
]

#: LitVar 2.0, NCBI. Public, no key, same 3-requests-per-second courtesy as E-utilities.
LITVAR = "https://www.ncbi.nlm.nih.gov/research/litvar2-api"

#: PubTator 3.0, NCBI. Wei 2024, PMID 38572754.
PUBTATOR = "https://www.ncbi.nlm.nih.gov/research/pubtator3-api"

#: Papers per PubTator page. The count and the best-scoring page are all step 5 reads, so
#: one page is enough and asking for more would only slow the pass.
PAGE = 10


def litvar_id(rsid: str) -> str:
    """LitVar's own identifier for a dbSNP variant: ``litvar@rs1801376##``."""
    return f"litvar@{rsid}##"


def litvar_path(rsid: str) -> str:
    """The identifier as it must appear **inside a url path**: ``litvar%40rs1801376%23%23``.

    This is not decoration. The trailing ``##`` is part of LitVar's identifier, but ``#``
    in a url starts a fragment, so an HTTP client sends everything before it and drops the
    rest — and LitVar answers the truncated identifier with *Variant not found*. Left
    unencoded, this module reports "nobody has published about this variant" for **every**
    variant, which is a wrong headline rather than a failed request. Measured 2026-09-18:
    ``rs1801376`` returns 0 publications unencoded and 66 encoded.
    """
    return quote(litvar_id(rsid), safe="")


#: LitVar answers a variant it holds no entry for with **HTTP 400 and this phrase**, not
#: with 404 and not with an empty list. Measured live 2026-09-18 on ``rs12952117``. It is
#: the same statement as "no publication mentions this variant", so it is allowed through
#: and turned into an empty list; any other 400 is a real failure and still raises.
NOT_FOUND = "Variant not found"


def publications_for_rsid(fetcher: Fetcher, rsid: str) -> list[str]:
    """Every PMID LitVar holds for one dbSNP variant, newest first as LitVar orders them.

    An empty list is a *result*: "nobody has written about this exact variant", which is
    the common case and is exactly the number step 5 needs in its denominator. It is
    reached two ways — LitVar holds the variant with no publications, or LitVar holds no
    entry at all (see :data:`NOT_FOUND`) — and both mean the same thing here.

    A caller that needs "was this allele askable at all" must not use this function's zero
    for it: that question is answered by whether the allele has a dbSNP identifier, and
    :mod:`mva.knowledge.catalogue` keeps the two apart.
    """
    if not rsid.strip():
        return []
    payload = fetcher.get_json(
        f"{LITVAR}/variant/get/{litvar_path(rsid.strip())}/publications",
        allow_status=(400, 404),
    )
    if not isinstance(payload, dict):
        return []
    detail = str(payload.get("detail") or "")
    if detail:
        if NOT_FOUND.lower() in detail.lower():
            return []
        raise SourceError(f"{LITVAR}/variant/get/{litvar_path(rsid)}/publications", detail)
    return [str(pmid) for pmid in payload.get("pmids") or []]


def variants_for_gene(fetcher: Fetcher, gene: str) -> list[dict[str, Any]]:
    """The published variants LitVar surfaces for a gene symbol, most-cited first.

    **This endpoint is an autocomplete and returns only its top few matches.** It is used
    for colour — the best-known alleles of a gene — and never as a denominator; the
    denominator comes from :func:`publications_for_rsid` over the child's own alleles,
    which is complete by construction.
    """
    if not gene.strip():
        return []
    payload = fetcher.get_json(
        f"{LITVAR}/variant/autocomplete/", {"query": gene.strip()}, allow_status=(404,)
    )
    if not isinstance(payload, list):
        return []
    rows = []
    for entry in payload:
        if not isinstance(entry, dict) or gene not in (entry.get("gene") or []):
            continue
        rows.append(
            {
                "rsid": str(entry.get("rsid") or ""),
                "hgvs": str(entry.get("hgvs") or entry.get("name") or ""),
                "pmid_count": int(entry.get("pmids_count") or 0),
                "clin_sig": ";".join(entry.get("data_clinical_significance") or []),
            }
        )
    return rows


def search_papers(fetcher: Fetcher, text: str, *, page: int = 1) -> dict[str, Any]:
    """One PubTator 3.0 free-text search: ``{"count": int, "papers": [...]}``.

    ``count`` is the total across every page and is what a match decision is made on;
    ``papers`` is the first page, kept so a match can be shown with a citation rather
    than only as a number. A query matching nothing returns ``count = 0`` and no papers.
    """
    if not text.strip():
        return {"count": 0, "papers": []}
    payload = fetcher.get_json(
        f"{PUBTATOR}/search/", {"text": text.strip(), "page": page}, allow_status=(404,)
    )
    if not isinstance(payload, dict):
        return {"count": 0, "papers": []}
    papers = []
    for entry in (payload.get("results") or [])[:PAGE]:
        if not isinstance(entry, dict):
            continue
        papers.append(
            {
                "pmid": str(entry.get("pmid") or entry.get("_id") or ""),
                "title": str(entry.get("title") or ""),
                "journal": str(entry.get("journal") or ""),
                "year": str(entry.get("meta_date_publication") or "")[:4],
                "score": float(entry.get("score") or 0.0),
            }
        )
    return {"count": int(payload.get("count") or 0), "papers": papers}


def gene_query(gene: str, term_label: str = "") -> str:
    """The search string for a gene, optionally narrowed to one clinical feature.

    Written as a function rather than inline so every (gene, term) query in the run has
    provably the same spelling — the cache key is the url, so a query that differs by a
    space is a different fetch and a different number.
    """
    gene = gene.strip()
    return f"{gene} AND {term_label.strip()}" if term_label.strip() else gene


def unique_pmids(rows: Sequence[dict[str, Any]]) -> list[str]:
    """The distinct PMIDs of a paper list, in first-seen order."""
    seen: dict[str, None] = {}
    for row in rows:
        pmid = str(row.get("pmid") or "")
        if pmid:
            seen.setdefault(pmid, None)
    return list(seen)
