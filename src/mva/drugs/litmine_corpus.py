"""A literature corpus for one gene, built from topic queries and cached as plain text.

Route R3 of iteration 5 asks the literature — not a database — which interventions change a
protein's level, modification or function. The first half of that is a *corpus*: every paper
the queries retrieve, with its abstract and, when Europe PMC holds an open-access copy, its
full text, each saved as a UTF-8 file whose sha256 the corpus table records. The quote
verifier (:mod:`mva.drugs.litmine_verify`) later checks every extracted quote against exactly
these bytes, so the corpus is the ground truth of the route.

Case-agnostic: the gene symbol, its aliases, the topic words and the disease phrase are all
parameters (:class:`CorpusSpec`). Nothing here names a PMID, so a positive control that
expects a known paper to come back is a real test of the queries.

Two sources, both public:

``Europe PMC search``  ``/search`` (JSON, ``resultType=core``): PMID, title, year, abstract,
                       PMCID and the open-access flag, up to 1000 records per page.
``Europe PMC full text`` ``/{PMCID}/fullTextXML`` (JATS XML) for open-access records only.

Search replies go through the shared :class:`~mva.drugs.cache.Fetcher` (JSON, cached, polite).
Full-text XML is not JSON, so :class:`TextCache` keeps the same contract for text: one file
per URL under ``build/``, a minimum interval between live calls, and no silent failure.
"""

from __future__ import annotations

import hashlib
import html
import re
import time
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .cache import USER_AGENT, Fetcher, SourceError

__all__ = [
    "EPMC",
    "CorpusSpec",
    "Document",
    "LitQuery",
    "TextCache",
    "build_queries",
    "jats_text",
    "run_queries",
    "save_documents",
    "sha256_text",
    "strip_markup",
]

EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"

#: Europe PMC's page ceiling for ``/search``.
PAGE_SIZE = 1000


@dataclass(frozen=True)
class LitQuery:
    """One named query. ``family`` groups queries for the recall table."""

    qid: str
    family: str
    term: str


@dataclass(frozen=True)
class CorpusSpec:
    """Everything the queries are built from. No PMID, author or title ever goes in here."""

    gene: str
    aliases: tuple[str, ...]
    topics: Mapping[str, tuple[str, ...]]
    disease_phrases: tuple[str, ...] = ()
    max_records: int = 1000


@dataclass
class Document:
    """One retrieved paper: metadata plus the queries that found it."""

    pmid: str
    title: str
    year: str
    pmcid: str
    open_access: bool
    abstract: str
    queries: list[str] = field(default_factory=list)


def _or_group(words: Iterable[str]) -> str:
    quoted = [f'"{w}"' if " " in w else w for w in dict.fromkeys(words) if w]
    return "(" + " OR ".join(quoted) + ")"


def build_queries(spec: CorpusSpec) -> list[LitQuery]:
    """Gene × topic queries, plus one query per disease phrase, all on title + abstract.

    ``TITLE_ABS`` keeps a paper that mentions the gene only in a supplementary table out of
    the corpus; ``SRC:MED`` keeps records that carry a PMID.
    """
    gene = f"TITLE_ABS:{_or_group((spec.gene, *spec.aliases))}"
    out = [
        LitQuery(
            f"topic:{name}", "gene_topic", f"{gene} AND TITLE_ABS:{_or_group(words)} AND SRC:MED"
        )
        for name, words in spec.topics.items()
    ]
    for index, phrase in enumerate(spec.disease_phrases, start=1):
        out.append(LitQuery(f"disease:{index}", "disease", f'TITLE_ABS:"{phrase}" AND SRC:MED'))
    return out


def strip_markup(text: str) -> str:
    """HTML/XML tags out, entities decoded, runs of whitespace collapsed to one space."""
    no_tags = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(no_tags)).strip()


def run_queries(
    fetcher: Fetcher, queries: Sequence[LitQuery], *, max_records: int = PAGE_SIZE
) -> tuple[dict[str, Document], list[dict[str, Any]]]:
    """Run every query; return ``(documents by pmid, per-query log)``.

    One page of up to ``max_records`` per query. The log records the hit count Europe PMC
    reports and how many records were taken, so a truncated query is visible, not silent.
    """
    docs: dict[str, Document] = {}
    log: list[dict[str, Any]] = []
    for query in queries:
        payload = fetcher.get_json(
            f"{EPMC}/search",
            {
                "query": query.term,
                "format": "json",
                "resultType": "core",
                "pageSize": min(max_records, PAGE_SIZE),
                "cursorMark": "*",
            },
        )
        results = ((payload or {}).get("resultList") or {}).get("result") or []
        taken = 0
        for record in results:
            pmid = str(record.get("pmid") or "")
            if not pmid:
                continue
            taken += 1
            doc = docs.get(pmid) or _document(record)
            docs[pmid] = doc
            doc.queries.append(query.qid)
        log.append(
            {
                "qid": query.qid,
                "family": query.family,
                "term": query.term,
                "hit_count": int((payload or {}).get("hitCount") or 0),
                "taken": taken,
            }
        )
    return docs, log


def _document(record: Mapping[str, Any]) -> Document:
    return Document(
        pmid=str(record.get("pmid") or ""),
        title=strip_markup(str(record.get("title") or "")).rstrip("."),
        year=str(record.get("pubYear") or ""),
        pmcid=str(record.get("pmcid") or ""),
        open_access=str(record.get("isOpenAccess") or "N") == "Y",
        abstract=strip_markup(str(record.get("abstractText") or "")),
    )


# ── full text ─────────────────────────────────────────────────────────────────────────────


@dataclass
class TextCache:
    """A cached, rate-limited GET for non-JSON bodies (full-text XML)."""

    cache_dir: Path
    min_interval_s: float = 0.34
    live_calls: int = 0
    failures: list[str] = field(default_factory=list)
    _last: float = 0.0
    _client: Any = None

    def get(self, url: str) -> str | None:
        """The body at ``url``; ``None`` on a 404 (no full text exists). Other errors raise."""
        key = hashlib.sha256(url.encode()).hexdigest()
        path = self.cache_dir / f"{key}.xml"
        missing = self.cache_dir / f"{key}.404"
        if path.exists():
            return path.read_text(encoding="utf-8")
        if missing.exists():
            return None
        import httpx  # deferred: a cache-only run must not need it

        if self._client is None:
            self._client = httpx.Client(timeout=60.0, headers={"User-Agent": USER_AGENT})
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        status = 0
        for attempt in range(3):
            gap = time.monotonic() - self._last
            if gap < self.min_interval_s:
                time.sleep(self.min_interval_s - gap)
            reply = self._client.get(url)
            self._last = time.monotonic()
            self.live_calls += 1
            status = reply.status_code
            if status == 404:
                missing.write_text(url, encoding="utf-8")
                return None
            if status < 400:
                body = str(reply.text)
                path.write_text(body, encoding="utf-8")
                return body
            if status not in (429, 500, 502, 503, 504):
                raise SourceError(url, f"HTTP {status}")
            time.sleep(1.5 * (2**attempt))
        # A server that keeps failing is recorded, not hidden: the caller counts these and
        # the corpus manifest reports them; the paper keeps its abstract.
        self.failures.append(f"{url} HTTP {status}")
        return None


#: JATS elements whose text is prose worth quoting. References and tables are left out:
#: a quote from a reference list is someone else's title, not this paper's finding.
_PROSE = {"title", "p", "article-title", "caption"}
_SKIP = {"ref-list", "table-wrap", "table", "xref", "fn-group", "ack"}


def jats_text(xml: str) -> str:
    """The prose of a JATS article (front abstract + body), as one whitespace-collapsed line."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return ""
    parts: list[str] = []

    def walk(node: ET.Element, inside_skip: bool) -> None:
        tag = node.tag.split("}")[-1]
        skip = inside_skip or tag in _SKIP
        if tag in _PROSE and not skip:
            parts.append("".join(_itertext_skipping(node)))
            return
        for child in node:
            walk(child, skip)

    for section in ("abstract", "body"):
        for node in root.iter():
            if node.tag.split("}")[-1] == section:
                walk(node, False)
    return strip_markup(" ".join(parts))


def _itertext_skipping(node: ET.Element) -> Iterable[str]:
    """``itertext`` that drops tables and reference lists nested inside a paragraph."""
    if node.text:
        yield node.text
    for child in node:
        if child.tag.split("}")[-1] not in {"table-wrap", "table"}:
            yield from _itertext_skipping(child)
        if child.tail:
            yield child.tail


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def save_documents(
    docs: Mapping[str, Document],
    out_dir: Path,
    texts: TextCache,
    *,
    fulltext_for: set[str],
) -> list[dict[str, Any]]:
    """Write ``<pmid>.abstract.txt`` (and ``<pmid>.fulltext.txt``) and return corpus rows.

    Full text is fetched only for PMIDs in ``fulltext_for`` that Europe PMC flags open
    access. One corpus row per (pmid, text kind), carrying the sha256 of the exact file.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for pmid in sorted(docs, key=int):
        doc = docs[pmid]
        kinds: list[tuple[str, str]] = []
        if doc.abstract:
            kinds.append(("abstract", f"{doc.title}. {doc.abstract}"))
        if pmid in fulltext_for and doc.open_access and doc.pmcid:
            xml = texts.get(f"{EPMC}/{doc.pmcid}/fullTextXML")
            body = jats_text(xml) if xml else ""
            if body:
                kinds.append(("fulltext", body))
        for kind, text in kinds:
            (out_dir / f"{pmid}.{kind}.txt").write_text(text, encoding="utf-8")
            rows.append(
                {
                    "pmid": pmid,
                    "title": doc.title,
                    "year": doc.year,
                    "source": "europepmc",
                    "text_kind": kind,
                    "text_sha256": sha256_text(text),
                    "queries": ";".join(doc.queries),
                }
            )
    return rows
