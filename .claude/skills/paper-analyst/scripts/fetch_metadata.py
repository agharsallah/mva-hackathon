#!/usr/bin/env python3
"""Fetch paper metadata, references, citing papers and code links from free APIs.

Sources (all keyless; set SEMANTIC_SCHOLAR_API_KEY / OPENALEX_MAILTO for higher limits):
  Semantic Scholar Graph API  - core metadata, tldr, fields, citation counts,
                                reference list, citing papers with isInfluential
  OpenAlex                    - topics/concepts, cited_by_count, OA status, venue
  Crossref                    - publisher metadata, licence, ISSN
  arXiv                       - abstract, categories, comments (often mention code)
  Hugging Face papers         - models/datasets/spaces linked to an arXiv id

Usage:
  python fetch_metadata.py --doi 10.1038/s41586-021-03819-2 --out meta.json
  python fetch_metadata.py --arxiv 1706.03762 --out meta.json
  python fetch_metadata.py --title "Attention is all you need" --out meta.json
  python fetch_metadata.py --url https://arxiv.org/abs/1706.03762 --out meta.json
  Options: --refs 100 --cites 50 --timeout 20

Never crashes on network failure: every source is wrapped, errors go to
result["errors"], and result["fallback_urls"] lists the exact URLs to fetch
manually (e.g. with a web-fetch tool) to obtain the same JSON.
"""

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

UA = "paper-analyst-skill/1.0 (research metadata lookup)"
S2 = "https://api.semanticscholar.org/graph/v1"
S2_FIELDS = "paperId,externalIds,title,abstract,venue,publicationVenue,year,publicationDate,authors,citationCount,influentialCitationCount,referenceCount,fieldsOfStudy,s2FieldsOfStudy,publicationTypes,journal,openAccessPdf,tldr,isOpenAccess"
S2_REF_FIELDS = "title,authors,year,venue,citationCount,externalIds,isInfluential,intents,contexts"
S2_CITE_FIELDS = "title,authors,year,venue,citationCount,externalIds,isInfluential,intents"


def get(url, timeout, headers=None, retries=2):
    hdrs = {"User-Agent": UA, "Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read().decode("utf-8", errors="replace")
                ctype = r.headers.get("Content-Type", "")
                if "json" in ctype or data.lstrip().startswith(("{", "[")):
                    return json.loads(data), None
                return data, None
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                time.sleep(2 + attempt * 2)
                continue
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")[:200]
            except Exception:
                pass
            last = f"HTTP {e.code} for {url} {body}"
            if e.code in (403, 404):
                break
        except Exception as e:
            last = f"{type(e).__name__}: {e} for {url}"
            if attempt < retries:
                time.sleep(1)
    return None, last


def norm_doi(doi):
    doi = doi.strip()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)
    doi = re.sub(r"^doi:\s*", "", doi, flags=re.IGNORECASE)
    return doi.rstrip(".,;")


def norm_arxiv(aid):
    aid = aid.strip()
    m = re.search(r"(\d{4}\.\d{4,5})(v\d+)?", aid)
    if m:
        return m.group(1)
    m = re.search(r"([a-z\-]+(?:\.[A-Z]{2})?/\d{7})", aid)
    return m.group(1) if m else aid


def parse_url(url):
    low = url.lower()
    m = re.search(r"arxiv\.org/(?:abs|pdf|html)/([^\s?#]+)", low)
    if m:
        return {"arxiv": norm_arxiv(m.group(1))}
    m = re.search(r"doi\.org/(10\.\S+)", url)
    if m:
        return {"doi": norm_doi(m.group(1))}
    m = re.search(r"(10\.\d{4,9}/[^\s?#]+)", url)
    if m:
        return {"doi": norm_doi(m.group(1))}
    m = re.search(r"semanticscholar\.org/paper/(?:.*/)?([0-9a-f]{40})", low)
    if m:
        return {"s2id": m.group(1)}
    m = re.search(r"openalex\.org/(W\d+)", url)
    if m:
        return {"openalex": m.group(1)}
    m = re.search(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", low)
    if m:
        return {"pmid": m.group(1)}
    return {"url": url}


def s2_author_list(auths):
    return [{"name": a.get("name"), "authorId": a.get("authorId")} for a in (auths or [])]


def compact_paper(p):
    if not p:
        return None
    ext = p.get("externalIds") or {}
    return {
        "title": p.get("title"),
        "authors": [a.get("name") for a in (p.get("authors") or [])],
        "year": p.get("year"),
        "venue": p.get("venue"),
        "citationCount": p.get("citationCount"),
        "doi": ext.get("DOI"),
        "arxiv": ext.get("ArXiv"),
        "isInfluential": p.get("isInfluential"),
        "intents": p.get("intents"),
    }


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--doi")
    ap.add_argument("--arxiv")
    ap.add_argument("--title")
    ap.add_argument("--url")
    ap.add_argument("--out")
    ap.add_argument("--refs", type=int, default=100, help="max references to fetch (0 to skip)")
    ap.add_argument("--cites", type=int, default=50, help="max citing papers to fetch (0 to skip)")
    ap.add_argument("--timeout", type=int, default=20)
    args = ap.parse_args()

    ids = {}
    if args.url:
        ids.update(parse_url(args.url))
    if args.doi:
        ids["doi"] = norm_doi(args.doi)
    if args.arxiv:
        ids["arxiv"] = norm_arxiv(args.arxiv)
    if args.title:
        ids["title"] = args.title.strip()
    if not ids:
        ap.error("give one of --doi, --arxiv, --title, --url")

    T = args.timeout
    result = {"query": ids, "sources": {}, "errors": [], "fallback_urls": []}
    s2_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
    s2_headers = {"x-api-key": s2_key} if s2_key else None
    mailto = os.environ.get("OPENALEX_MAILTO", "paper-analyst@example.org")

    # ---------- resolve title -> ids via S2 search ----------
    if "title" in ids and not any(k in ids for k in ("doi", "arxiv", "s2id")):
        q = urllib.parse.quote(ids["title"])
        url = f"{S2}/paper/search?query={q}&limit=3&fields=paperId,title,year,externalIds,authors"
        data, err = get(url, T, s2_headers)
        if data and data.get("data"):
            top = data["data"][0]
            result["title_match_candidates"] = [
                {"title": d.get("title"), "year": d.get("year"), "paperId": d.get("paperId")}
                for d in data["data"]
            ]
            ext = top.get("externalIds") or {}
            ids["s2id"] = top.get("paperId")
            if ext.get("DOI"):
                ids["doi"] = ext["DOI"]
            if ext.get("ArXiv"):
                ids["arxiv"] = ext["ArXiv"]
            result["warnings"] = [
                "Title search: verify title_match_candidates[0] is the intended paper."
            ]
        else:
            result["errors"].append(err or "S2 title search returned nothing")
            result["fallback_urls"].append(url)
            # OpenAlex title search fallback
            oa_url = f"https://api.openalex.org/works?search={q}&per-page=3&mailto={mailto}"
            data, err = get(oa_url, T)
            if data and data.get("results"):
                top = data["results"][0]
                doi = top.get("doi") or ""
                if doi:
                    ids["doi"] = norm_doi(doi)
                ids["openalex"] = top.get("id", "").rsplit("/", 1)[-1]
                result["title_match_candidates"] = [
                    {
                        "title": d.get("title"),
                        "year": d.get("publication_year"),
                        "openalex": d.get("id"),
                    }
                    for d in data["results"]
                ]
            else:
                result["errors"].append(err or "OpenAlex title search returned nothing")
                result["fallback_urls"].append(oa_url)

    # ---------- Semantic Scholar ----------
    s2_id = None
    if ids.get("s2id"):
        s2_id = ids["s2id"]
    elif ids.get("doi"):
        s2_id = "DOI:" + ids["doi"]
    elif ids.get("arxiv"):
        s2_id = "ARXIV:" + ids["arxiv"]
    elif ids.get("pmid"):
        s2_id = "PMID:" + ids["pmid"]

    s2 = None
    if s2_id:
        url = f"{S2}/paper/{urllib.parse.quote(s2_id, safe=':')}?fields={S2_FIELDS}"
        s2, err = get(url, T, s2_headers)
        if s2:
            ext = s2.get("externalIds") or {}
            ids.setdefault("doi", ext.get("DOI")) if ext.get("DOI") else None
            ids.setdefault("arxiv", ext.get("ArXiv")) if ext.get("ArXiv") else None
            result["sources"]["semantic_scholar"] = {
                "paperId": s2.get("paperId"),
                "title": s2.get("title"),
                "abstract": s2.get("abstract"),
                "tldr": (s2.get("tldr") or {}).get("text"),
                "year": s2.get("year"),
                "publicationDate": s2.get("publicationDate"),
                "venue": s2.get("venue"),
                "publicationVenue": s2.get("publicationVenue"),
                "journal": s2.get("journal"),
                "publicationTypes": s2.get("publicationTypes"),
                "authors": s2_author_list(s2.get("authors")),
                "fieldsOfStudy": s2.get("fieldsOfStudy"),
                "s2FieldsOfStudy": sorted(
                    {
                        f.get("category")
                        for f in (s2.get("s2FieldsOfStudy") or [])
                        if f.get("category")
                    }
                ),
                "citationCount": s2.get("citationCount"),
                "influentialCitationCount": s2.get("influentialCitationCount"),
                "referenceCount": s2.get("referenceCount"),
                "externalIds": ext,
                "openAccessPdf": (s2.get("openAccessPdf") or {}).get("url"),
                "isOpenAccess": s2.get("isOpenAccess"),
            }
            pid = s2.get("paperId")
            if args.refs and pid:
                rurl = f"{S2}/paper/{pid}/references?fields={S2_REF_FIELDS}&limit={min(args.refs, 1000)}"
                refs, rerr = get(rurl, T, s2_headers)
                if refs:
                    items = []
                    for r in refs.get("data", []):
                        cp = compact_paper(r.get("citedPaper"))
                        if cp:
                            cp["isInfluential"] = r.get("isInfluential")
                            cp["intents"] = r.get("intents")
                            ctx = r.get("contexts") or []
                            cp["context_example"] = ctx[0][:200] if ctx else None
                            items.append(cp)
                    result["references"] = items
                    result["references_note"] = (
                        "intents: background | methodology | result. isInfluential marks references S2 judges central."
                    )
                else:
                    result["errors"].append(rerr)
                    result["fallback_urls"].append(rurl)
            if args.cites and pid:
                curl = f"{S2}/paper/{pid}/citations?fields={S2_CITE_FIELDS}&limit={min(args.cites, 1000)}"
                cites, cerr = get(curl, T, s2_headers)
                if cites:
                    items = []
                    for c in cites.get("data", []):
                        cp = compact_paper(c.get("citingPaper"))
                        if cp:
                            cp["isInfluential"] = c.get("isInfluential")
                            cp["intents"] = c.get("intents")
                            items.append(cp)
                    items.sort(
                        key=lambda x: (not x.get("isInfluential"), -(x.get("citationCount") or 0))
                    )
                    result["citing_papers"] = items
                    result["citing_papers_note"] = (
                        "Sorted: influential first, then by citation count. Use for Impact & follow-ups."
                    )
                else:
                    result["errors"].append(cerr)
                    result["fallback_urls"].append(curl)
        else:
            result["errors"].append(err)
            result["fallback_urls"].append(url)

    # ---------- OpenAlex ----------
    oa_url = None
    if ids.get("openalex"):
        oa_url = f"https://api.openalex.org/works/{ids['openalex']}?mailto={mailto}"
    elif ids.get("doi"):
        oa_url = f"https://api.openalex.org/works/https://doi.org/{urllib.parse.quote(ids['doi'], safe='/')}?mailto={mailto}"
    elif ids.get("arxiv"):
        oa_url = f"https://api.openalex.org/works/https://doi.org/10.48550/arXiv.{ids['arxiv']}?mailto={mailto}"
    if oa_url:
        oa, err = get(oa_url, T)
        if oa and isinstance(oa, dict) and oa.get("results"):
            oa = oa["results"][0] if oa["results"] else None
        if oa and oa.get("id"):
            loc = oa.get("primary_location") or {}
            src = loc.get("source") or {}
            result["sources"]["openalex"] = {
                "id": oa.get("id"),
                "title": oa.get("title") or oa.get("display_name"),
                "publication_year": oa.get("publication_year"),
                "publication_date": oa.get("publication_date"),
                "type": oa.get("type"),
                "venue": src.get("display_name"),
                "venue_type": src.get("type"),
                "issn": src.get("issn_l"),
                "publisher": src.get("host_organization_name"),
                "volume": (oa.get("biblio") or {}).get("volume"),
                "issue": (oa.get("biblio") or {}).get("issue"),
                "first_page": (oa.get("biblio") or {}).get("first_page"),
                "last_page": (oa.get("biblio") or {}).get("last_page"),
                "cited_by_count": oa.get("cited_by_count"),
                "counts_by_year": oa.get("counts_by_year"),
                "is_oa": (oa.get("open_access") or {}).get("is_oa"),
                "oa_url": (oa.get("open_access") or {}).get("oa_url"),
                "is_retracted": oa.get("is_retracted"),
                "topics": [
                    {
                        "name": t.get("display_name"),
                        "field": (t.get("field") or {}).get("display_name"),
                        "subfield": (t.get("subfield") or {}).get("display_name"),
                        "score": t.get("score"),
                    }
                    for t in (oa.get("topics") or [])[:5]
                ],
                "concepts": [
                    c.get("display_name")
                    for c in (oa.get("concepts") or [])
                    if (c.get("score") or 0) > 0.3
                ][:12],
                "keywords": [k.get("display_name") for k in (oa.get("keywords") or [])][:12],
                "authorships": [
                    {
                        "name": (a.get("author") or {}).get("display_name"),
                        "institutions": [
                            i.get("display_name") for i in (a.get("institutions") or [])
                        ],
                        "corresponding": a.get("is_corresponding"),
                    }
                    for a in (oa.get("authorships") or [])
                ],
                "funders": [g.get("funder_display_name") for g in (oa.get("grants") or [])],
                "referenced_works_count": oa.get("referenced_works_count"),
                "related_works": (oa.get("related_works") or [])[:10],
            }
            if oa.get("is_retracted"):
                result.setdefault("warnings", []).append("OpenAlex marks this work as RETRACTED.")
        else:
            result["errors"].append(err or "OpenAlex returned no work")
            result["fallback_urls"].append(oa_url)

    # ---------- Crossref ----------
    if ids.get("doi"):
        cr_url = f"https://api.crossref.org/works/{urllib.parse.quote(ids['doi'], safe='/')}?mailto={mailto}"
        cr, err = get(cr_url, T)
        if cr and cr.get("message"):
            m = cr["message"]
            result["sources"]["crossref"] = {
                "type": m.get("type"),
                "title": (m.get("title") or [None])[0],
                "container_title": (m.get("container-title") or [None])[0],
                "short_container_title": (m.get("short-container-title") or [None])[0],
                "publisher": m.get("publisher"),
                "volume": m.get("volume"),
                "issue": m.get("issue"),
                "page": m.get("page"),
                "issued": (m.get("issued") or {}).get("date-parts", [[None]])[0],
                "authors": [
                    {
                        "given": a.get("given"),
                        "family": a.get("family"),
                        "orcid": a.get("ORCID"),
                        "affiliation": [x.get("name") for x in (a.get("affiliation") or [])],
                    }
                    for a in (m.get("author") or [])
                ],
                "license": [l.get("URL") for l in (m.get("license") or [])],
                "issn": m.get("ISSN"),
                "is_referenced_by_count": m.get("is-referenced-by-count"),
                "references_count": m.get("references-count"),
                "update_to": m.get("update-to"),
                "relation": m.get("relation"),
            }
            if m.get("update-to"):
                result.setdefault("warnings", []).append(
                    "Crossref: this DOI is an update (erratum/correction/retraction notice) to another work; check 'update_to'."
                )
        else:
            result["errors"].append(err or "Crossref returned nothing")
            result["fallback_urls"].append(cr_url)

    # ---------- arXiv ----------
    if ids.get("arxiv"):
        ax_url = f"http://export.arxiv.org/api/query?id_list={ids['arxiv']}"
        ax, err = get(ax_url, T, {"Accept": "application/atom+xml"})
        if ax and isinstance(ax, str) and "<entry>" in ax:
            try:
                ns = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
                root = ET.fromstring(ax)
                e = root.find("a:entry", ns)
                cats = [c.get("term") for c in e.findall("a:category", ns)]
                comment = e.find("arxiv:comment", ns)
                jref = e.find("arxiv:journal_ref", ns)
                adoi = e.find("arxiv:doi", ns)
                result["sources"]["arxiv"] = {
                    "id": ids["arxiv"],
                    "title": re.sub(
                        r"\s+", " ", e.findtext("a:title", default="", namespaces=ns)
                    ).strip(),
                    "abstract": re.sub(
                        r"\s+", " ", e.findtext("a:summary", default="", namespaces=ns)
                    ).strip(),
                    "authors": [
                        a.findtext("a:name", default="", namespaces=ns)
                        for a in e.findall("a:author", ns)
                    ],
                    "published": e.findtext("a:published", default=None, namespaces=ns),
                    "updated": e.findtext("a:updated", default=None, namespaces=ns),
                    "categories": cats,
                    "primary_category": (
                        e.find("arxiv:primary_category", ns).get("term")
                        if e.find("arxiv:primary_category", ns) is not None
                        else (cats[0] if cats else None)
                    ),
                    "comment": comment.text.strip()
                    if comment is not None and comment.text
                    else None,
                    "journal_ref": jref.text.strip() if jref is not None and jref.text else None,
                    "doi": adoi.text.strip() if adoi is not None and adoi.text else None,
                    "pdf_url": f"https://arxiv.org/pdf/{ids['arxiv']}",
                }
                if result["sources"]["arxiv"]["doi"] and not ids.get("doi"):
                    ids["doi"] = result["sources"]["arxiv"]["doi"]
                    result.setdefault("warnings", []).append(
                        "arXiv lists a DOI for a published version; rerun with --doi to get venue details."
                    )
            except ET.ParseError as pe:
                result["errors"].append(f"arXiv XML parse error: {pe}")
        else:
            result["errors"].append(err or "arXiv returned no entry")
            result["fallback_urls"].append(ax_url)

        # Hugging Face linked artefacts (models/datasets/spaces citing this arXiv id)
        hf_url = f"https://huggingface.co/api/arxiv/{ids['arxiv']}/repos"
        hf, err = get(hf_url, T)
        if hf and isinstance(hf, dict):
            result["sources"]["huggingface"] = {
                "models": [m.get("id") for m in (hf.get("models") or [])][:20],
                "datasets": [d.get("id") for d in (hf.get("datasets") or [])][:20],
                "spaces": [s.get("id") for s in (hf.get("spaces") or [])][:20],
            }
        elif err and "404" not in err:
            result["errors"].append(err)
            result["fallback_urls"].append(hf_url)

    # ---------- code links (from any source) ----------
    code_links = set()
    for src in result["sources"].values():
        blob = json.dumps(src)
        for m in re.finditer(
            r"https?://(?:github\.com|gitlab\.com|bitbucket\.org)/[\w\-\.]+/[\w\-\.]+", blob
        ):
            code_links.add(m.group(0).rstrip(".,)"))
    result["code_links_from_metadata"] = sorted(code_links)

    # ---------- merged view ----------
    s2s = result["sources"].get("semantic_scholar", {})
    oas = result["sources"].get("openalex", {})
    crs = result["sources"].get("crossref", {})
    axs = result["sources"].get("arxiv", {})
    merged = {
        "title": s2s.get("title") or oas.get("title") or crs.get("title") or axs.get("title"),
        "authors": [a["name"] for a in s2s.get("authors", [])]
        or [a["name"] for a in oas.get("authorships", [])]
        or [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in crs.get("authors", [])]
        or axs.get("authors"),
        "year": s2s.get("year")
        or oas.get("publication_year")
        or (crs.get("issued") or [None])[0]
        or (axs.get("published") or "")[:4]
        or None,
        "venue": (s2s.get("publicationVenue") or {}).get("name")
        or s2s.get("venue")
        or oas.get("venue")
        or crs.get("container_title")
        or ("arXiv preprint" if axs else None),
        "venue_type": (s2s.get("publicationVenue") or {}).get("type")
        or oas.get("venue_type")
        or crs.get("type"),
        "publisher": oas.get("publisher") or crs.get("publisher"),
        "volume": oas.get("volume") or crs.get("volume"),
        "issue": oas.get("issue") or crs.get("issue"),
        "pages": crs.get("page")
        or (f"{oas.get('first_page')}-{oas.get('last_page')}" if oas.get("first_page") else None),
        "doi": ids.get("doi"),
        "arxiv": ids.get("arxiv"),
        "abstract": s2s.get("abstract") or axs.get("abstract"),
        "tldr": s2s.get("tldr"),
        "fields": sorted(
            set(
                (s2s.get("fieldsOfStudy") or [])
                + (s2s.get("s2FieldsOfStudy") or [])
                + [t["name"] for t in oas.get("topics", []) if t.get("name")]
            )
        ),
        "arxiv_categories": axs.get("categories"),
        "citation_count": {
            "semantic_scholar": s2s.get("citationCount"),
            "openalex": oas.get("cited_by_count"),
            "crossref": crs.get("is_referenced_by_count"),
        },
        "influential_citation_count": s2s.get("influentialCitationCount"),
        "is_retracted": oas.get("is_retracted"),
        "open_access_pdf": s2s.get("openAccessPdf") or oas.get("oa_url") or axs.get("pdf_url"),
        "checked_on": time.strftime("%Y-%m-%d"),
    }
    result["merged"] = merged
    result["errors"] = [e for e in result["errors"] if e]
    if result["errors"] and not result["sources"]:
        result["status"] = (
            "ALL SOURCES FAILED - fetch fallback_urls with a web-fetch tool if permitted; otherwise web-search '<title> semanticscholar' and '<title> arxiv' and fetch those pages (see SKILL.md Network fallback), or mark metadata 'unverified'."
        )
    elif result["errors"]:
        result["status"] = "PARTIAL - some sources failed; see errors and fallback_urls."
    else:
        result["status"] = "OK"

    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        # stdout: compact
        compact = {
            "status": result["status"],
            "merged": merged,
            "n_references": len(result.get("references", [])),
            "n_citing": len(result.get("citing_papers", [])),
            "code_links_from_metadata": result["code_links_from_metadata"],
            "errors": result["errors"],
            "fallback_urls": result["fallback_urls"],
            "warnings": result.get("warnings", []),
            "saved_to": args.out,
        }
        print(json.dumps(compact, indent=2, ensure_ascii=False))
    else:
        print(text)


if __name__ == "__main__":
    main()
