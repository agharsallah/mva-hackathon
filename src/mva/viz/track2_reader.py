"""Reading ``ressources/track2/`` into an object: the card, the five tables, the manifests.

Pure functions over a repository root. No settings, no connection, no network — the Track 2
tables are committed text files, so everything here answers on a bare checkout. The two
parts that *do* need a database (the lineage walk) live in :mod:`mva.viz.track2_lineage`.

Three properties are load-bearing.

**Rows are typed on the way out, by one rule.** A TSV field is text; the JSON a chart
consumes is not. :mod:`mva.viz.track2_catalog` declares a type per column and this module
applies it — ``integer`` to ``int`` or ``None``, ``boolean`` to ``true``/``false`` or
``None``, ``list`` split on ``|``, everything else left as text. An empty field becomes
``None`` for the typed columns and ``""`` for text, because *unknown* is a value the page
must be able to render as a gap rather than as a zero.

**The catalogue is the manifest, not a retelling of it.** ``built_at``, ``code_version``,
``method`` and the input list come out of ``*.provenance.json`` verbatim, so the page and
the committed manifest cannot drift.

**A missing file is an empty answer, not an error.** A checkout that has never run
``mva-drugs snapshot`` has no TSVs; the route must still serve the card, the register and
the strategy. Every reader here returns ``[]`` or ``{}`` for what is not there.

No coordinate can appear: these tables name genes, drugs, trials and papers.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from . import track2_catalog

#: Relative to the repository root, which is where the API is started from.
DEFAULT_ROOT = Path()

TRACK2_DIR = "ressources/track2"

#: The five tables, in the order the snapshot writes them and the page shows them.
TABLES = ("targets", "drug_candidates", "trials", "literature", "pathways")

#: The separator :mod:`mva.drugs.tables` joins list fields with. TSV has no nesting.
LIST_SEPARATOR = "|"

#: ``H003`` and ``H003-H009``: a claim id, and a range of them written as one.
HYPOTHESIS_ID = re.compile(r"\bH(\d{3})\b")
HYPOTHESIS_RANGE = re.compile(r"\bH(\d{3})\s*[-–]\s*H(\d{3})\b")


def directory(root: Path | None = None) -> Path:
    return (root or DEFAULT_ROOT).resolve() / TRACK2_DIR


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def card(root: Path | None = None) -> dict[str, Any]:
    """``mechanism.json`` verbatim — the Track 1 → Track 2 hand-off, coordinate-free by rule."""
    loaded = _load(directory(root) / "mechanism.json")
    return loaded if isinstance(loaded, dict) else {}


def card_text(root: Path | None = None) -> str:
    """The card as raw text, for the hypothesis-id sweep. ``""`` when it is not there."""
    path = directory(root) / "mechanism.json"
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def summary(root: Path | None = None) -> dict[str, Any]:
    """``snapshot.json`` verbatim: row counts, request counts, and every query with its hits."""
    loaded = _load(directory(root) / "snapshot.json")
    return loaded if isinstance(loaded, dict) else {}


def manifest(table: str, root: Path | None = None) -> dict[str, Any]:
    """One ``<table>.provenance.json`` verbatim, or ``{}`` when the snapshot never ran."""
    loaded = _load(directory(root) / f"{table}.provenance.json")
    return loaded if isinstance(loaded, dict) else {}


def _cell(value: str, kind: str) -> Any:
    """One TSV field, typed by the catalogue's rule. Empty means unknown, so ``None``."""
    text = value.strip()
    if kind == "list":
        return [part for part in text.split(LIST_SEPARATOR) if part] if text else []
    if not text:
        return None if kind in ("integer", "boolean") else ""
    if kind == "boolean":
        return text.lower() == "true"
    if kind == "integer":
        try:
            return int(float(text))
        except ValueError:
            return None
    return text


def read_table(table: str, root: Path | None = None) -> tuple[list[str], list[dict[str, Any]]]:
    """``(header, rows)`` for one Track 2 TSV, typed per :mod:`mva.viz.track2_catalog`.

    ``csv`` with ``delimiter="\\t"`` rather than ``str.split``: the writer never quotes, but
    a title carrying a quote character would still be mis-split by a naive reader, and
    getting that wrong shows up as a shifted column three fields later.
    """
    path = directory(root) / f"{table}.tsv"
    if not path.is_file():
        return [], []
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.reader(stream, delimiter="\t")
        try:
            header = next(reader)
        except StopIteration:
            return [], []
        types = [track2_catalog.column_type(table, name) for name in header]
        rows = [
            {
                name: _cell(row[index] if index < len(row) else "", kind)
                for index, (name, kind) in enumerate(zip(header, types, strict=True))
            }
            for row in reader
            if row
        ]
    return header, rows


def catalog_entry(table: str, header: list[str], rows: int, root: Path | None = None) -> dict:
    """One table's row in the catalogue: what it is, how it was built, from what."""
    found = manifest(table, root)
    outputs = found.get("outputs") or [{}]
    return {
        "table": table,
        "path": str(outputs[0].get("path") or f"{TRACK2_DIR}/{table}.tsv"),
        "rows": rows,
        "columns": track2_catalog.describe(table, header),
        "sha256": str(outputs[0].get("sha256") or ""),
        "built_at": str(found.get("built_at") or ""),
        "code_version": str(found.get("code_version") or ""),
        "method": str(found.get("method") or ""),
        "inputs": [
            {
                "name": str(entry.get("name") or ""),
                "url": str(entry.get("url") or ""),
                "retrieved_at": str(entry.get("retrieved_at") or ""),
                "version": entry.get("version"),
                "sha256": str(entry.get("sha256") or ""),
            }
            for entry in found.get("inputs") or []
        ],
    }


def tables(root: Path | None = None) -> tuple[dict[str, list[dict[str, Any]]], list[dict]]:
    """Every table's rows, and the catalogue describing them. One pass over disk."""
    rows: dict[str, list[dict[str, Any]]] = {}
    catalog: list[dict] = []
    for table in TABLES:
        header, parsed = read_table(table, root)
        rows[table] = parsed
        if header:
            catalog.append(catalog_entry(table, header, len(parsed), root))
    return rows, catalog


def cited_hypotheses(text: str) -> list[str]:
    """Every claim id the card cites, ranges expanded: ``H003-H009`` is seven claims.

    The card states its provenance in prose — "written from the research record
    (H003-H009)" — so both spellings have to be read. Expanding the range is the only
    inference made here, and it is one the notation itself asserts.
    """
    found: set[str] = set()
    for low, high in HYPOTHESIS_RANGE.findall(text):
        found.update(f"H{number:03d}" for number in range(int(low), int(high) + 1))
    found.update(f"H{number}" for number in HYPOTHESIS_ID.findall(text))
    return sorted(found)


def register(hypotheses: list[dict[str, Any]], step: str = "step-8") -> list[dict[str, Any]]:
    """The claims filed under one step, as the page's register rows.

    One row per claim, not its history: the exported record carries each claim's current
    state plus a revision count, so ``revision`` is that count. See
    :mod:`mva.viz.submissions_audit` for the same limitation stated at length.
    """
    return [
        {
            "hypothesis_id": str(entry.get("id") or ""),
            "step": str(entry.get("step") or ""),
            "status": str(entry.get("status") or ""),
            "confidence": entry.get("confidence"),
            "statement": str(entry.get("statement") or ""),
            "prediction": str(entry.get("prediction") or ""),
            "refuted_by": str(entry.get("refuted_by") or ""),
            "revision": int(entry.get("revisions") or 1),
        }
        for entry in hypotheses
        if str(entry.get("step") or "") == step
    ]
