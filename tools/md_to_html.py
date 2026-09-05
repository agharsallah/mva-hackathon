#!/usr/bin/env python3
"""Turn a Markdown report into one self-contained HTML page fit for printing.

* Markdown → HTML with tables and fenced code (the ``markdown`` package).
* ```` ```mermaid ```` fences become ``<pre class="mermaid">`` blocks rendered in the browser
  by Mermaid from the CDN, so the diagrams print as drawn on GitHub.
* Relative image paths are rewritten to absolute ``file://`` URLs, so the page renders from
  anywhere; relative links are rewritten to the repository's GitHub URL when ``--repo-url``
  is given, else left as text.

Pair with ``tools/md_to_pdf.mjs``::

    uv run python tools/md_to_html.py submissions/track1/iteration-1/report.md build/report.html
    node tools/md_to_pdf.mjs build/report.html submissions/track1/iteration-1/team_track1_report.pdf
"""

from __future__ import annotations

import argparse
import re
from html import escape
from pathlib import Path

import markdown

CSS = """
body{font-family:Inter,-apple-system,Helvetica,Arial,sans-serif;color:#222;max-width:900px;
  margin:0 auto;padding:24px;line-height:1.45;font-size:13px}
h1{font-size:24px;border-bottom:2px solid #333;padding-bottom:6px}
h2{font-size:18px;margin-top:28px;border-bottom:1px solid #ccc;padding-bottom:4px;
  page-break-after:avoid}
h3{font-size:15px;margin-top:20px;page-break-after:avoid}
table{border-collapse:collapse;width:100%;margin:10px 0;font-size:11.5px;page-break-inside:avoid}
th,td{border:1px solid #ccc;padding:4px 6px;vertical-align:top;text-align:left}
th{background:#f0f0f0}
code{font-family:'SF Mono',Menlo,Consolas,monospace;font-size:11px;background:#f4f4f4;
  padding:1px 3px;border-radius:3px}
pre{background:#f7f7f7;padding:8px;border-radius:4px;overflow-x:auto;font-size:11px;
  page-break-inside:avoid}
pre.mermaid{background:#fff;text-align:center}
img{max-width:100%;display:block;margin:10px auto;page-break-inside:avoid}
blockquote{border-left:3px solid #ccc;margin:8px 0;padding:2px 12px;color:#555;font-size:12px}
hr{border:0;border-top:1px solid #ddd;margin:20px 0}
a{color:#1d4ed8;text-decoration:none}
"""

MERMAID = '<script type="module">import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";mermaid.initialize({startOnLoad:true,theme:"neutral"});</script>'


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("source", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument(
        "--repo-url", default="", help="GitHub tree URL to resolve relative links against"
    )
    return parser.parse_args()


def convert(source: Path, repo_url: str = "") -> str:
    text = source.read_text(encoding="utf-8")
    base = source.parent.resolve()

    # Mermaid fences → placeholders survive Markdown conversion untouched.
    blocks: list[str] = []

    def keep(match: re.Match) -> str:
        blocks.append(match.group(1))
        return f"\n\nMERMAIDBLOCK{len(blocks) - 1}\n\n"

    text = re.sub(r"```mermaid\n(.*?)```", keep, text, flags=re.S)

    def relink(match: re.Match) -> str:
        label, target = match.group(1), match.group(2)
        if target.startswith(("http://", "https://", "#", "mailto:")):
            return match.group(0)
        path, _, anchor = target.partition("#")
        resolved = (base / path).resolve()
        if resolved.suffix.lower() in {".png", ".svg", ".jpg", ".jpeg"} and resolved.is_file():
            return f"[{label}]({resolved.as_uri()})"
        if repo_url:
            root = Path.cwd().resolve()
            try:
                rel = resolved.relative_to(root).as_posix()
            except ValueError:
                rel = path
            return f"[{label}]({repo_url.rstrip('/')}/{rel}{'#' + anchor if anchor else ''})"
        return match.group(0)

    text = re.sub(r"\[([^\]]*)\]\(([^)\s]+)\)", relink, text)
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "toc"])
    for index, block in enumerate(blocks):
        body = body.replace(
            f"<p>MERMAIDBLOCK{index}</p>", f'<pre class="mermaid">{escape(block)}</pre>'
        )
    title = re.search(r"^# (.+)$", source.read_text(encoding="utf-8"), flags=re.M)
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{escape(title.group(1) if title else source.stem)}</title>"
        f"<style>{CSS}</style>{MERMAID}</head><body>{body}</body></html>"
    )


def main() -> None:
    args = parse_args()
    html = convert(args.source, args.repo_url)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8")
    print(f"wrote {args.out} ({len(html) // 1024} KB)")


if __name__ == "__main__":
    main()
