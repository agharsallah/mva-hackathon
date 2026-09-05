#!/usr/bin/env python3
"""Generate APA 7, BibTeX and Vancouver citations plus a YAML header snippet.

Input: the JSON written by fetch_metadata.py (uses its "merged" block), or
manual flags when no metadata could be fetched.

Usage:
  python make_citation.py meta.json
  python make_citation.py --title "..." --authors "Ada Lovelace; Alan Turing" --year 2024 \
      --venue "NeurIPS" --doi 10.1234/abc [--arxiv 2401.01234] [--volume 12 --issue 3 --pages 1-10]
  Options: --key mykey2024 (BibTeX key override), --json (machine-readable output)

Rules follow references/citation-formats.md. Fields that are unknown are omitted,
never invented. Output notes which fields were missing so they can be filled by hand.
"""

import argparse
import json
import re
import unicodedata

PARTICLES = {
    "van",
    "von",
    "de",
    "del",
    "della",
    "der",
    "den",
    "da",
    "di",
    "du",
    "la",
    "le",
    "dos",
    "das",
    "bin",
    "ibn",
    "al",
    "el",
    "ter",
    "ten",
}


def split_name(name):
    """Return (family, given). Handles 'Family, Given' and 'Given Family' and particles."""
    name = re.sub(r"\s+", " ", name.strip())
    if not name:
        return "", ""
    if "," in name:
        fam, giv = [x.strip() for x in name.split(",", 1)]
        return fam, giv
    parts = name.split(" ")
    if len(parts) == 1:
        return parts[0], ""
    # particles: "Ludwig van Beethoven" -> family "van Beethoven"
    i = len(parts) - 1
    while i - 1 > 0 and parts[i - 1].lower() in PARTICLES:
        i -= 1
    return " ".join(parts[i:]), " ".join(parts[:i])


def initials(given, sep=" ", dot=True):
    if not given:
        return ""
    toks = re.split(r"[\s\-]+", given)
    hyph = "-" in given
    out = []
    for t in toks:
        if not t:
            continue
        out.append(t[0].upper() + ("." if dot else ""))
    if hyph and len(out) == 2:
        return out[0] + "-" + out[1]
    return sep.join(out)


def ascii_slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


STOP = {
    "a",
    "an",
    "the",
    "on",
    "of",
    "for",
    "and",
    "in",
    "to",
    "with",
    "toward",
    "towards",
    "via",
    "from",
    "by",
    "is",
    "are",
    "at",
    "into",
    "using",
}


def first_title_word(title):
    for w in re.findall(r"[A-Za-z][A-Za-z0-9\-]*", title or ""):
        if w.lower() not in STOP:
            return ascii_slug(w)
    return "paper"


def apa(meta):
    fams = [split_name(a) for a in meta["authors"]]

    def fmt(fg):
        fam, giv = fg
        ini = initials(giv)
        return f"{fam}, {ini}" if ini else fam

    n = len(fams)
    if n == 0:
        auth = ""
    elif n == 1:
        auth = fmt(fams[0])
    elif n <= 20:
        auth = ", ".join(fmt(f) for f in fams[:-1]) + ", & " + fmt(fams[-1])
    else:
        auth = ", ".join(fmt(f) for f in fams[:19]) + ", . . . " + fmt(fams[-1])
    year = meta.get("year") or "n.d."
    title = meta.get("title") or "[Title unknown]"
    venue = meta.get("venue")
    vol, iss, pages, doi = meta.get("volume"), meta.get("issue"), meta.get("pages"), meta.get("doi")
    link = f"https://doi.org/{doi}" if doi else (meta.get("url") or "")
    vt = (meta.get("venue_type") or "").lower()
    is_preprint = (
        (not venue) or "arxiv" in (venue or "").lower() or "preprint" in (venue or "").lower()
    )
    is_conf = (
        "conference" in vt
        or "proceedings" in vt
        or re.search(
            r"\b(proceedings|conference|workshop|symposium|neurips|icml|iclr|cvpr|iccv|eccv|acl|emnlp|naacl|aaai|ijcai|kdd|sigir|www|chi|osdi|sosp|nsdi|usenix|recomb|ismb)\b",
            venue or "",
            re.IGNORECASE,
        )
    )
    if is_preprint and meta.get("arxiv"):
        s = f"{auth} ({year}). *{title}*. arXiv. https://doi.org/10.48550/arXiv.{meta['arxiv']}"
    elif is_conf:
        pp = f" (pp. {pages.replace('-', '–')})" if pages else ""
        book = (
            venue
            if re.search(r"proceedings|advances in", venue, re.IGNORECASE)
            else f"Proceedings of {venue}"
        )
        s = f"{auth} ({year}). {title}. In *{book}*{pp}. {link}".strip()
    else:
        vi = f", *{vol}*" if vol else ""
        vi += f"({iss})" if iss else ""
        pp = f", {pages.replace('-', '–')}" if pages else ""
        s = (
            f"{auth} ({year}). {title}. *{venue}*{vi}{pp}. {link}".strip()
            if venue
            else f"{auth} ({year}). *{title}*. {link}".strip()
        )
    return re.sub(r"\s+\.", ".", s).strip()


def bibtex(meta, key=None):
    fams = [split_name(a) for a in meta["authors"]]
    authors = " and ".join(f"{f}, {g}".rstrip(", ") for f, g in fams) if fams else ""
    first_fam = ascii_slug(fams[0][0]) if fams else "anon"
    key = key or f"{first_fam}{meta.get('year') or ''}{first_title_word(meta.get('title'))}"
    title = meta.get("title") or ""
    # protect acronyms / all-caps tokens
    title_prot = re.sub(
        r"\b([A-Z][A-Z0-9\-]+[A-Z0-9]|[A-Za-z]*[A-Z][a-z]*[A-Z][A-Za-z]*)\b", r"{\1}", title
    )
    venue = meta.get("venue")
    vt = (meta.get("venue_type") or "").lower()
    is_preprint = (
        (not venue) or "arxiv" in (venue or "").lower() or "preprint" in (venue or "").lower()
    )
    is_conf = (
        "conference" in vt
        or "proceedings" in vt
        or re.search(
            r"\b(proceedings|conference|workshop|symposium|neurips|icml|iclr|cvpr|iccv|eccv|acl|emnlp|naacl|aaai|ijcai|kdd|sigir|chi|osdi|sosp|nsdi|usenix|recomb|ismb)\b",
            venue or "",
            re.IGNORECASE,
        )
    )
    fields = [("title", title_prot), ("author", authors)]
    if is_preprint and meta.get("arxiv"):
        kind = "misc"
        fields += [
            ("year", meta.get("year")),
            ("eprint", meta["arxiv"]),
            ("archivePrefix", "arXiv"),
        ]
        cats = meta.get("arxiv_categories") or []
        if cats:
            fields.append(("primaryClass", cats[0]))
        fields.append(("doi", f"10.48550/arXiv.{meta['arxiv']}"))
    elif is_conf:
        kind = "inproceedings"
        fields += [
            ("booktitle", venue),
            ("pages", (meta.get("pages") or "").replace("-", "--") or None),
            ("year", meta.get("year")),
            ("doi", meta.get("doi")),
        ]
    else:
        kind = "article"
        fields += [
            ("journal", venue),
            ("volume", meta.get("volume")),
            ("number", meta.get("issue")),
            ("pages", (meta.get("pages") or "").replace("-", "--") or None),
            ("year", meta.get("year")),
            ("doi", meta.get("doi")),
        ]
    if meta.get("url") and not meta.get("doi"):
        fields.append(("url", meta["url"]))
    body = ",\n".join(f"  {k:<14}= {{{v}}}" for k, v in fields if v not in (None, "", []))
    return f"@{kind}{{{key},\n{body}\n}}", key


def vancouver(meta):
    fams = [split_name(a) for a in meta["authors"]]
    names = [f"{f} {initials(g, sep='', dot=False)}".strip() for f, g in fams]
    if len(names) > 6:
        auth = ", ".join(names[:6]) + ", et al."
    else:
        auth = ", ".join(names)
    title = meta.get("title") or ""
    venue = meta.get("short_venue") or meta.get("venue") or ""
    year = meta.get("year") or ""
    vol, iss, pages, doi = meta.get("volume"), meta.get("issue"), meta.get("pages"), meta.get("doi")
    if (not venue or "arxiv" in venue.lower()) and meta.get("arxiv"):
        return f"{auth.rstrip('.')}. {title}. arXiv [Preprint]. {year}. Available from: https://arxiv.org/abs/{meta['arxiv']}"
    tail = f"{year}"
    if vol:
        tail += f";{vol}"
        if iss:
            tail += f"({iss})"
    if pages:
        tail += f":{pages}"
    s = f"{auth.rstrip('.')}. {title}. {venue}. {tail}."
    if doi:
        s += f" doi:{doi}"
    return s


def yaml_header(meta, key):
    def q(v):
        return json.dumps(v, ensure_ascii=False) if v is not None else "null"

    authors = ", ".join(q(a) for a in meta["authors"])
    return "\n".join(
        [
            "---",
            f"title: {q(meta.get('title'))}",
            f"authors: [{authors}]",
            f"year: {meta.get('year') or 'null'}",
            f"venue: {q(meta.get('venue'))}",
            f"doi: {q(meta.get('doi'))}",
            f"arxiv: {q(meta.get('arxiv'))}",
            f"url: {q(meta.get('url') or (f'https://doi.org/{meta['doi']}' if meta.get('doi') else (f'https://arxiv.org/abs/{meta['arxiv']}' if meta.get('arxiv') else None)))}",
            f"bibkey: {key}",
            "---",
        ]
    )


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("metadata_json", nargs="?")
    ap.add_argument("--title")
    ap.add_argument("--authors", help="semicolon-separated, 'Given Family' or 'Family, Given'")
    ap.add_argument("--year")
    ap.add_argument("--venue")
    ap.add_argument("--venue-type", help="journal | conference | preprint")
    ap.add_argument("--doi")
    ap.add_argument("--arxiv")
    ap.add_argument("--volume")
    ap.add_argument("--issue")
    ap.add_argument("--pages")
    ap.add_argument("--url")
    ap.add_argument("--key")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    meta = {"authors": []}
    missing = []
    if args.metadata_json:
        with open(args.metadata_json, encoding="utf-8") as f:
            data = json.load(f)
        m = data.get("merged", data)
        meta.update(
            {
                k: m.get(k)
                for k in (
                    "title",
                    "year",
                    "venue",
                    "venue_type",
                    "volume",
                    "issue",
                    "pages",
                    "doi",
                    "arxiv",
                    "arxiv_categories",
                )
            }
        )
        meta["authors"] = m.get("authors") or []
        cr = (data.get("sources") or {}).get("crossref") or {}
        if cr.get("short_container_title"):
            meta["short_venue"] = cr["short_container_title"]
        # prefer Crossref's structured names when present
        if cr.get("authors") and len(cr["authors"]) == len(meta["authors"]):
            meta["authors"] = [
                f"{a.get('family', '')}, {a.get('given', '')}".strip(", ") for a in cr["authors"]
            ]
    for k in ("title", "year", "venue", "doi", "arxiv", "volume", "issue", "pages", "url"):
        v = getattr(args, k)
        if v:
            meta[k] = v
    if args.venue_type:
        meta["venue_type"] = args.venue_type
    if args.authors:
        meta["authors"] = [a.strip() for a in args.authors.split(";") if a.strip()]
    if meta.get("year"):
        try:
            meta["year"] = int(str(meta["year"])[:4])
        except ValueError:
            pass

    for k in ("title", "authors", "year", "venue"):
        if not meta.get(k):
            missing.append(k)
    if not meta.get("doi") and not meta.get("arxiv"):
        missing.append("doi/arxiv")
    if not meta.get("authors"):
        meta["authors"] = []

    bib, key = bibtex(meta, args.key)
    out = {
        "apa": apa(meta),
        "bibtex": bib,
        "vancouver": vancouver(meta),
        "bibkey": key,
        "in_text_apa": (
            f"({split_name(meta['authors'][0])[0]}"
            + (
                " et al."
                if len(meta["authors"]) > 2
                else (
                    f" & {split_name(meta['authors'][1])[0]}" if len(meta["authors"]) == 2 else ""
                )
            )
            + f", {meta.get('year') or 'n.d.'})"
        )
        if meta["authors"]
        else None,
        "yaml_header": yaml_header(meta, key),
        "missing_fields": missing,
        "note": "Fields listed in missing_fields were omitted, not guessed. Vancouver uses the full journal name unless Crossref supplied an abbreviation.",
    }
    if args.json:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print("APA 7:\n" + out["apa"] + "\n")
        print("BibTeX:\n" + out["bibtex"] + "\n")
        print("Vancouver:\n" + out["vancouver"] + "\n")
        print("In-text (APA): " + str(out["in_text_apa"]) + "\n")
        print("YAML header:\n" + out["yaml_header"] + "\n")
        if missing:
            print("Missing (omitted, fill by hand if known): " + ", ".join(missing))


if __name__ == "__main__":
    main()
