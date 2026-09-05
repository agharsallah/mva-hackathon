"""Reading the two markdown files an iteration folder carries as data, not as prose.

``decode-table.md`` and the README's "which steps contributed" section are tables a human
wrote and a page needs as rows. Everything here is a pure string function over lines — no
paths beyond resolving a relative link, no I/O beyond one ``read_text``, no markdown
library. A regex parser is enough because these files are *written* by this repository's
own tools and have a fixed shape; a general markdown parse would be a bigger dependency
answering a question nobody asked.

Cells are returned with their emphasis, backticks and links flattened
(:func:`strip_markdown`), because a table cell's value is what it says, not how it was
typeset. The one exception is :func:`pipe_table`, which hands back raw cells so a caller
that needs the links inside one still has them.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

MARKDOWN_LINK = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")

#: The heading whose table lists which research steps fed this iteration.
CONTRIBUTIONS_HEADING = "## Which steps contributed"

#: The two prose lines under the decode table, each its own field in the contract.
DECODE_SUMMARY_PREFIX = "Prior entropy"
DECODE_ORDER_PREFIX = "Rows, in rank order"

DECODE_FILE = "decode-table.md"


def strip_markdown(text: str) -> str:
    """Link text, no emphasis, no code ticks — what a table cell *says*."""
    return MARKDOWN_LINK.sub(r"\1", text).replace("**", "").replace("`", "").strip()


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_separator(cells: list[str]) -> bool:
    return all(set(cell) <= set("-: ") and cell for cell in cells)


def pipe_table(lines: list[str]) -> tuple[list[str], list[list[str]]]:
    """The first contiguous markdown pipe table in ``lines``, as header and rows.

    Returns ``([], [])`` when there is none. The separator row is dropped; every other row
    is kept as its **raw** cells, so a caller that needs the links inside a cell still has
    them.
    """
    block: list[list[str]] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            block.append(_cells(stripped))
        elif block:
            break
    if not block:
        return [], []
    header, rest = block[0], block[1:]
    return header, [row for row in rest if not _is_separator(row)]


def line_starting(lines: list[str], prefix: str) -> str:
    """The first line whose flattened text starts with ``prefix``, flattened. ``""`` if none."""
    for line in lines:
        if strip_markdown(line).startswith(prefix):
            return strip_markdown(line)
    return ""


def decode_table(folder: Path) -> dict[str, Any]:
    """``decode-table.md``: what every possible scorer reply would mean.

    Three fields, because the file carries three different things — the reply→meaning
    table, the one-line information-gain summary, and the rank order the CSV rows were
    written in. All three are label-only; the file names no coordinate.
    """
    path = folder / DECODE_FILE
    if not path.is_file():
        return {"columns": [], "rows": [], "summary": "", "row_order": ""}
    lines = path.read_text(encoding="utf-8").splitlines()
    columns, rows = pipe_table(lines)
    return {
        "columns": [strip_markdown(cell) for cell in columns],
        "rows": [[strip_markdown(cell) for cell in row] for row in rows],
        "summary": line_starting(lines, DECODE_SUMMARY_PREFIX),
        "row_order": line_starting(lines, DECODE_ORDER_PREFIX),
    }


def contributions(readme: str, folder: Path, root: Path) -> list[dict[str, Any]]:
    """The "which steps contributed" table, with every methodology link resolved.

    The README's links are relative to the folder; a browser served from ``/api`` cannot
    resolve those, so each becomes a repository-relative path here. An ``http`` link is
    passed through unchanged — it is already absolute.
    """
    lines = readme.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if line.startswith(CONTRIBUTIONS_HEADING)), None
    )
    if start is None:
        return []
    _, rows = pipe_table([line for line in lines[start:] if line.strip()])
    return [
        {
            "step": strip_markdown(row[0]),
            "contribution": strip_markdown(row[1]),
            "methodology": links(row[2], folder, root),
        }
        for row in rows
        if len(row) >= 3
    ]


def links(cell: str, folder: Path, root: Path) -> list[dict[str, str]]:
    """Every markdown link in one cell, as ``{label, path}`` with the path resolved."""
    return [
        {"label": strip_markdown(label), "path": resolve_link(target, folder, root)}
        for label, target in MARKDOWN_LINK.findall(cell)
    ]


def resolve_link(target: str, folder: Path, root: Path) -> str:
    """One relative link, as a repository-relative path. URLs and anchors pass through."""
    if target.startswith(("http://", "https://", "#")):
        return target
    candidate = (folder / target.split("#", 1)[0]).resolve()
    root = root.resolve()
    if candidate.is_relative_to(root):
        return candidate.relative_to(root).as_posix()
    return target
