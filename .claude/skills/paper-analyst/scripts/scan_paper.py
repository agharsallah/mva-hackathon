#!/usr/bin/env python3
"""Scan a paper PDF and produce everything Pass 1 and Pass 2 need.

Outputs (in --out directory):
  text.txt         layout-preserving full text (pdftotext -layout)
  manifest.json    pages, text-layer status, sections, identifiers, links,
                   figure/table caption inventory, rasterised page paths,
                   extracted table CSVs, reference-section location
  pages/           PNG of every page carrying a figure or table caption
                   (or all pages with --all-pages)
  tables/          best-effort CSV per detected table (pdfplumber)
  references.txt   raw text of the reference section, if found

Usage:
  python scan_paper.py paper.pdf --out work/paper1 [--dpi 110] [--all-pages]
                                 [--no-raster] [--no-tables]

Requires poppler-utils (pdfinfo, pdffonts, pdftotext, pdftoppm) and pdfplumber.
Degrades gracefully: any missing tool is reported in manifest["errors"].
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

SECTION_PATTERNS = [
    ("abstract", r"^\s*(?:\d+\.?\s*)?abstract\b"),
    ("introduction", r"^\s*(?:\d+\.?\s*)?introduction\b"),
    ("background", r"^\s*(?:\d+\.?\s*)?(?:background|preliminaries)\b"),
    ("related_work", r"^\s*(?:\d+\.?\s*)?(?:related work|prior work|literature review)\b"),
    (
        "methods",
        r"^\s*(?:\d+\.?\s*)?(?:methods?|methodology|approach|materials and methods|proposed method|model|our (?:method|approach))\b",
    ),
    (
        "experiments",
        r"^\s*(?:\d+\.?\s*)?(?:experiments?|experimental (?:setup|results)|evaluation|results?(?: and discussion)?)\b",
    ),
    ("discussion", r"^\s*(?:\d+\.?\s*)?discussion\b"),
    ("limitations", r"^\s*(?:\d+\.?\s*)?limitations?\b"),
    (
        "broader_impact",
        r"^\s*(?:\d+\.?\s*)?(?:broader impacts?|ethics statement|ethical considerations|societal impact)\b",
    ),
    ("reproducibility", r"^\s*(?:\d+\.?\s*)?reproducibility(?: statement)?\b"),
    ("conclusion", r"^\s*(?:\d+\.?\s*)?(?:conclusions?|concluding remarks|summary and outlook)\b"),
    ("acknowledgements", r"^\s*acknowledg?e?ments?\b"),
    ("references", r"^\s*(?:references|bibliography|literature cited)\s*$"),
    ("appendix", r"^\s*(?:appendix|appendices|supplementary (?:material|information))\b"),
    (
        "data_availability",
        r"^\s*(?:data|code|software) (?:and (?:code|data|software) )?availability\b",
    ),
]

CAPTION_RE = re.compile(
    r"^\s*(?P<kind>Fig(?:ure)?\.?|Table|Supplementary (?:Fig(?:ure)?\.?|Table)|Extended Data Fig(?:ure)?\.?|Algorithm|Listing)\s*"
    r"(?P<num>S?\d+[A-Za-z]?)\s*[.:|\-]?\s*(?P<cap>.{0,200})",
    re.IGNORECASE,
)

URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>\"'\)\]\},;]+")
DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>\)\],;]+)")
ARXIV_RE = re.compile(r"arXiv:\s*(\d{4}\.\d{4,5}(?:v\d+)?)", re.IGNORECASE)
ARXIV_URL_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5}(?:v\d+)?)", re.IGNORECASE)
ACCESSION_PATTERNS = {
    "GEO": r"\bGS[EM]\d{3,}\b",
    "SRA": r"\b[SED]R[APRSX]\d{5,}\b",
    "PDB": r"\bPDB(?:\s*ID)?[:\s]+([1-9][A-Za-z0-9]{3})\b",
    "UniProt": r"\b(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})\b",
    "BioProject": r"\bPRJ[EDN][A-Z]\d+\b",
    "ClinicalTrials": r"\bNCT\d{8}\b",
    "Zenodo": r"zenodo\.org/records?/\d+",
    "OSF": r"osf\.io/[a-z0-9]{5}\b",
}

CODE_HOSTS = (
    "github.com",
    "gitlab.com",
    "bitbucket.org",
    "codeberg.org",
    "huggingface.co",
    "colab.research.google.com",
    "paperswithcode.com",
    "sourceforge.net",
)
DATA_HOSTS = (
    "zenodo.org",
    "figshare.com",
    "osf.io",
    "datadryad.org",
    "kaggle.com",
    "ncbi.nlm.nih.gov",
    "ebi.ac.uk",
    "uniprot.org",
    "rcsb.org",
    "ensembl.org",
    "gdc.cancer.gov",
    "synapse.org",
    "physionet.org",
    "openneuro.org",
    "dataverse",
    "data.mendeley.com",
    "ucsc.edu",
    "cellxgene",
    "tcga",
    "archive.org",
    "drive.google.com",
    "dropbox.com",
)


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def have(tool):
    return shutil.which(tool) is not None


def clean_url(u):
    u = u.rstrip(".,;:)]}'\"")
    # join URLs broken across line by hyphenation is not attempted; keep as-is
    return u


def classify_url(u):
    low = u.lower()
    if any(h in low for h in CODE_HOSTS):
        return "code"
    if any(h in low for h in DATA_HOSTS):
        return "data"
    if "doi.org" in low:
        return "doi"
    if "arxiv.org" in low:
        return "arxiv"
    return "other"


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("pdf")
    ap.add_argument("--out", required=True)
    ap.add_argument(
        "--dpi",
        type=int,
        default=110,
        help="rasterisation DPI (110 keeps token cost low; use 150-200 for dense figures)",
    )
    ap.add_argument(
        "--all-pages", action="store_true", help="rasterise every page, not only figure/table pages"
    )
    ap.add_argument("--no-raster", action="store_true")
    ap.add_argument("--no-tables", action="store_true")
    args = ap.parse_args()

    pdf = args.pdf
    out = args.out
    os.makedirs(out, exist_ok=True)
    manifest = {
        "pdf": os.path.abspath(pdf),
        "out": os.path.abspath(out),
        "errors": [],
        "warnings": [],
    }

    if not os.path.exists(pdf):
        manifest["errors"].append(f"file not found: {pdf}")
        print(json.dumps(manifest, indent=2))
        sys.exit(1)

    # --- pdfinfo ---
    pages = None
    if have("pdfinfo"):
        r = run(["pdfinfo", pdf])
        info = {}
        for line in r.stdout.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                info[k.strip()] = v.strip()
        manifest["pdfinfo"] = {
            k: info[k]
            for k in (
                "Title",
                "Author",
                "Creator",
                "Producer",
                "CreationDate",
                "Pages",
                "Page size",
                "File size",
            )
            if k in info
        }
        try:
            pages = int(info.get("Pages", "0"))
        except ValueError:
            pages = None
    else:
        manifest["errors"].append("pdfinfo not available")
    manifest["pages"] = pages

    # --- text layer check ---
    text_layer = None
    if have("pdffonts"):
        r = run(["pdffonts", pdf])
        font_lines = [l for l in r.stdout.splitlines()[2:] if l.strip()]
        text_layer = len(font_lines) > 0
    manifest["has_text_layer"] = text_layer
    if text_layer is False:
        manifest["warnings"].append(
            "No fonts found: PDF is scanned/raster. pdftotext will be empty; rasterise pages and read visually (or OCR)."
        )

    # --- text extraction ---
    text = ""
    text_path = os.path.join(out, "text.txt")
    if have("pdftotext") and text_layer is not False:
        r = run(["pdftotext", "-layout", pdf, text_path])
        if r.returncode != 0:
            manifest["errors"].append(f"pdftotext failed: {r.stderr.strip()[:200]}")
        elif os.path.exists(text_path):
            with open(text_path, encoding="utf-8", errors="replace") as f:
                text = f.read()
    if not text:
        try:
            import pdfplumber

            with pdfplumber.open(pdf) as doc:
                text = "\n\f".join((p.extract_text() or "") for p in doc.pages)
            with open(text_path, "w", encoding="utf-8") as f:
                f.write(text)
        except Exception as e:  # pragma: no cover
            manifest["errors"].append(f"text extraction failed: {e}")
    manifest["text_path"] = text_path if text else None
    manifest["text_chars"] = len(text)
    if text and len(text) < 500 * (pages or 1):
        manifest["warnings"].append(
            "Very little text per page; check for a partial text layer or a scanned PDF."
        )

    # pages are separated by form feed in pdftotext output
    page_texts = text.split("\f") if text else []
    if pages is None and page_texts:
        pages = len(page_texts)
        manifest["pages"] = pages

    # --- first-page metadata guess ---
    first = page_texts[0] if page_texts else ""
    first_lines = [l.strip() for l in first.splitlines() if l.strip()]
    manifest["first_page_lines"] = first_lines[:12]
    m = re.search(
        r"abstract\s*[.:\-—]?\s*(.{100,2500}?)(?:\n\s*\n|\b1\s+Introduction\b|\bIntroduction\b|Keywords|Index Terms)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    manifest["abstract_guess"] = re.sub(r"\s+", " ", m.group(1)).strip() if m else None

    # --- identifiers ---
    dois = sorted(set(clean_url(d) for d in DOI_RE.findall(text)))
    arxivs = sorted(set(ARXIV_RE.findall(text)) | set(ARXIV_URL_RE.findall(text)))
    manifest["identifiers"] = {
        "doi_candidates": dois[:15],
        "arxiv_candidates": arxivs[:10],
        "note": "First-page DOI/arXiv usually identifies this paper; others belong to references.",
    }
    first_dois = DOI_RE.findall(first)
    first_arxiv = ARXIV_RE.findall(first) + ARXIV_URL_RE.findall(first)
    manifest["identifiers"]["this_paper_doi_guess"] = (
        clean_url(first_dois[0]) if first_dois else None
    )
    manifest["identifiers"]["this_paper_arxiv_guess"] = first_arxiv[0] if first_arxiv else None

    acc = {}
    for name, pat in ACCESSION_PATTERNS.items():
        found = re.findall(pat, text)
        found = [f if isinstance(f, str) else f[0] for f in found]
        if found:
            acc[name] = sorted(set(found))[:20]
    manifest["accessions"] = acc

    # --- links ---
    links = {}
    for u in URL_RE.findall(text):
        u = clean_url(u)
        if len(u) < 8:
            continue
        links.setdefault(classify_url(u), set()).add(u)
    manifest["links"] = {k: sorted(v) for k, v in links.items()}
    manifest["code_links"] = manifest["links"].get("code", [])
    manifest["data_links"] = manifest["links"].get("data", [])

    # --- sections ---
    sections = []
    numbered = re.compile(r"^\s*(\d+(\.\d+)*\.?|[IVX]+\.|[A-Z]\.)\s+\S")
    for pi, ptxt in enumerate(page_texts, start=1):
        for line in ptxt.splitlines():
            s = line.strip()
            if not s or len(s) > 80:
                continue
            # A heading is either numbered ("3 Method", "IV. Results") or stands alone
            # on its line with at most a few words. This keeps table rows such as
            # "Method  CoNLL  OntoNotes" and sentences like "Results show..." out.
            is_numbered = bool(numbered.match(s))
            words = s.split()
            if not is_numbered and (
                len(words) > 5 or (s.endswith((".", ",", ";")) and len(words) > 3)
            ):
                continue
            if not is_numbered and re.search(r"\d", s):
                continue
            for name, pat in SECTION_PATTERNS:
                if re.match(pat, s, re.IGNORECASE):
                    sections.append({"section": name, "heading": s, "page": pi})
                    break
    # de-duplicate consecutive repeats
    dedup = []
    for s in sections:
        if not dedup or (dedup[-1]["section"], dedup[-1]["page"]) != (s["section"], s["page"]):
            dedup.append(s)
    manifest["sections"] = dedup
    present = {s["section"] for s in dedup}
    expected = [
        "abstract",
        "introduction",
        "related_work",
        "methods",
        "experiments",
        "limitations",
        "conclusion",
        "references",
    ]
    manifest["sections_missing"] = [e for e in expected if e not in present]

    # --- references section text ---
    ref_start = next((s for s in dedup if s["section"] == "references"), None)
    if ref_start and text:
        idx = -1
        for m_ref in re.finditer(
            r"(?:^|[\n\f])[ \t]*(?:\d+\.?\s*)?(references|bibliography|literature cited)[ \t]*(?=[\n\f])",
            text,
            re.IGNORECASE,
        ):
            idx = m_ref.start()  # keep the last occurrence
        if idx != -1:
            ref_text = text[idx:]
            # cut at appendix if it follows
            ap_m = re.search(r"\n\s*(appendix|supplementary)", ref_text, re.IGNORECASE)
            if ap_m and ap_m.start() > 2000:
                ref_text = ref_text[: ap_m.start()]
            ref_path = os.path.join(out, "references.txt")
            with open(ref_path, "w", encoding="utf-8") as f:
                f.write(ref_text)
            manifest["references_path"] = ref_path
            # rough count: lines starting with [n] or n. or author-year patterns
            n_brackets = len(re.findall(r"^\s*\[\d+\]", ref_text, re.MULTILINE))
            n_numbered = len(re.findall(r"^\s*\d{1,3}\.\s", ref_text, re.MULTILINE))
            manifest["reference_count_guess"] = max(n_brackets, n_numbered) or None

    # --- captions inventory ---
    captions = []
    for pi, ptxt in enumerate(page_texts, start=1):
        for line in ptxt.splitlines():
            m = CAPTION_RE.match(line)
            if m:
                kind = m.group("kind").lower()
                kind = (
                    "figure"
                    if kind.startswith("fig") or "fig" in kind
                    else ("table" if "table" in kind else kind.rstrip("."))
                )
                if m.group("kind").lower().startswith("supplementary") or m.group(
                    "kind"
                ).lower().startswith("extended"):
                    kind = "supp_" + kind
                cap = m.group("cap").strip()
                # skip in-text mentions like "Figure 3 shows" - keep those that look like captions (have colon/period or are long)
                if len(cap) < 15 and not re.search(r"[.:]", line[: m.end("num") + 3]):
                    continue
                captions.append(
                    {"kind": kind, "number": m.group("num"), "page": pi, "caption": cap[:200]}
                )
    # de-dup by (kind, number): keep the entry with longest caption
    best = {}
    for c in captions:
        k = (c["kind"], c["number"])
        if k not in best or len(c["caption"]) > len(best[k]["caption"]):
            best[k] = c
    captions = sorted(best.values(), key=lambda c: (c["page"], c["kind"], c["number"]))
    manifest["captions"] = captions
    fig_pages = sorted({c["page"] for c in captions})
    manifest["figure_table_pages"] = fig_pages

    # --- rasterise ---
    manifest["rasterised_pages"] = {}
    if not args.no_raster and have("pdftoppm") and pages:
        pages_dir = os.path.join(out, "pages")
        os.makedirs(pages_dir, exist_ok=True)
        targets = (
            list(range(1, pages + 1)) if args.all_pages or (text_layer is False) else fig_pages
        )
        if not targets and not args.all_pages:
            manifest["warnings"].append(
                "No figure/table captions detected; nothing rasterised. Use --all-pages if figures exist."
            )
        for p in targets:
            prefix = os.path.join(pages_dir, f"p{p:03d}")
            r = run(
                ["pdftoppm", "-png", "-r", str(args.dpi), "-f", str(p), "-l", str(p), pdf, prefix]
            )
            if r.returncode != 0:
                manifest["errors"].append(f"pdftoppm failed on page {p}: {r.stderr.strip()[:120]}")
                continue
            produced = [
                f for f in os.listdir(pages_dir) if f.startswith(f"p{p:03d}") and f.endswith(".png")
            ]
            if produced:
                final = os.path.join(pages_dir, f"page-{p:03d}.png")
                os.replace(os.path.join(pages_dir, produced[0]), final)
                manifest["rasterised_pages"][str(p)] = final
    elif not have("pdftoppm"):
        manifest["errors"].append("pdftoppm not available; cannot rasterise pages")

    # --- tables ---
    manifest["tables"] = []
    if not args.no_tables and text_layer is not False:
        try:
            import csv

            import pdfplumber

            tables_dir = os.path.join(out, "tables")
            os.makedirs(tables_dir, exist_ok=True)
            table_pages = (
                sorted({c["page"] for c in captions if c["kind"].endswith("table")}) or fig_pages
            )
            with pdfplumber.open(pdf) as doc:
                for p in table_pages:
                    if p - 1 >= len(doc.pages):
                        continue
                    try:
                        found = doc.pages[p - 1].extract_tables()
                    except Exception as e:
                        manifest["warnings"].append(f"table extraction failed on page {p}: {e}")
                        continue
                    for ti, tbl in enumerate(found, start=1):
                        rows = [
                            [(c or "").replace("\n", " ").strip() for c in row]
                            for row in tbl
                            if row
                        ]
                        if len(rows) < 2 or max(len(r) for r in rows) < 2:
                            continue
                        path = os.path.join(tables_dir, f"page{p:03d}_table{ti}.csv")
                        with open(path, "w", newline="", encoding="utf-8") as f:
                            csv.writer(f).writerows(rows)
                        manifest["tables"].append(
                            {
                                "page": p,
                                "rows": len(rows),
                                "cols": max(len(r) for r in rows),
                                "csv": path,
                            }
                        )
        except ImportError:
            manifest["warnings"].append(
                "pdfplumber not installed; table CSVs skipped (pip install pdfplumber)"
            )

    # --- summary ---
    manifest["summary"] = {
        "pages": pages,
        "text_layer": text_layer,
        "sections_found": [s["section"] for s in dedup],
        "n_figures": sum(1 for c in captions if c["kind"] == "figure"),
        "n_tables": sum(1 for c in captions if c["kind"] == "table"),
        "n_supplementary": sum(1 for c in captions if c["kind"].startswith("supp")),
        "n_code_links": len(manifest["code_links"]),
        "n_data_links": len(manifest["data_links"]),
        "n_rasterised": len(manifest["rasterised_pages"]),
        "n_tables_csv": len(manifest["tables"]),
        "reference_count_guess": manifest.get("reference_count_guess"),
    }
    manifest["next_steps"] = [
        "Read text.txt (Pass 1: title, abstract, intro, headings, conclusion).",
        "Open each PNG in pages/ and apply references/figure-analysis.md.",
        "Run fetch_metadata.py with this_paper_doi_guess or this_paper_arxiv_guess.",
        "If code_links is non-empty, run inspect_repo.py on the GitHub URL.",
    ]

    with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    # print a compact version to stdout (omit long lists)
    compact = {
        k: v
        for k, v in manifest.items()
        if k not in ("captions", "sections", "links", "first_page_lines", "abstract_guess")
    }
    compact["captions_preview"] = captions[:8]
    compact["sections_preview"] = dedup[:12]
    print(json.dumps(compact, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
