"""The data catalogue of one iteration: every dataset its methodology entries name.

An iteration's record is its methodology entries, and every entry names the data it
touched — ``results.gene_biallelic``, ``ressources/track2/shortlist.tsv``,
``build/it4/tables/lincs.parquet``. This module reads those names out of the entries and
joins each one to what the repository records about it: the warehouse lineage edges for a
table, the provenance manifest beside a file (:mod:`mva.viz.iteration_manifest`). The
result is a catalogue that nobody typed, so it cannot drift from the record it describes.

**Two roles, and the weaker one is the default.** A dataset is ``produced`` by the
iteration only when something recorded says so: a lineage edge or manifest that cites one
of the entries (``entry docs/…/154-….md`` or ``entry 154``), or a recorded producer — the
edge's ``tool``, the manifest's ``built_by`` — that the same entry names in its text.
Every other dataset is ``cited``: the entry names it, which says nothing about whether it
was read or written. Mentioning is evidence of use, not of production.

**What is not catalogued.** The bookkeeping tables (the lineage ledger itself, the probe
ledger, the register) are the machinery that describes data, listed on ``/catalog``;
figures are the iteration's output, listed with its steps. Neither is a dataset here.

**Bare table names** (```gene_biallelic```) are matched only inside backticks and only
when exactly one schema has a table by that name, so prose words are never mistaken for
tables. No genomic position passes through this module: entries are coordinate-gated.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import iteration_manifest
from .submissions_lineage import Ledger

#: A methodology entry's path: its iteration, step and three-digit number.
ENTRY_PATH = re.compile(
    r"docs/(?:(?P<iteration>iteration\d+)/(?P<step>step-\d+)|step-0)/methodology/"
    r"(?P<number>\d{3})[-_][\w.-]+\.md"
)

#: How an edge's ``notes`` or a manifest cites an entry: by path, or as ``entry 154``.
ENTRY_CITATION = re.compile(r"methodology/(\d{3})[-_]|\bentr(?:y|ies)\s+(\d{3})\b")

#: ``schema.table`` in prose. The look-behind keeps a file name (``x/results.tsv``) out.
QUALIFIED = re.compile(
    r"(?<![\w/.-])(results|track2|warehouse)\.([a-z][a-z0-9_]*[a-z0-9])(?![\w*-])"
)

#: A table named alone, in backticks.
BARE = re.compile(r"`([a-z][a-z0-9_]{2,})`")

#: A repository data file. ``.md`` counts only under ``ressources/`` (the delivered documents).
FILE_REF = re.compile(
    r"(?<![\w/.-])((?:ressources|build|data)/(?:[\w.-]+/)*[\w.-]+"
    r"\.(?:tsv|csv|json|jsonl|parquet|bed|txt|npz|vcf\.gz|bed\.gz|tsv\.gz))(?![\w/-])"
    r"|(?<![\w/.-])(ressources/(?:[\w.-]+/)*[\w.-]+\.md)(?![\w/-])"
)

#: An object in the store: the raw delivery.
OBJECT_REF = re.compile(r"(?<![\w/])(s3://[\w./-]+[\w])")

#: A recorded producer, cut down to the part an entry would name.
PRODUCER = re.compile(r"(tools/[\w/.-]+\.(?:py|mjs)|mva-[\w]+ [\w-]+|mva\.[\w.]+)")

#: The machinery that describes data rather than being data — listed on ``/catalog``.
BOOKKEEPING = {
    "data_lineage",
    "source_objects",
    "source_files",
    "derivation_runs",
    "warehouse_catalog",
    "probe_ledger",
    "hypotheses",
    "evidence",
}

#: A ``schema.table`` match whose "table" is really a file extension.
EXTENSIONS = {"tsv", "csv", "json", "md", "py", "parquet", "txt", "html", "png", "svg"}

CLINICAL_PREFIX = "ressources/hackathon-rules/Challenge_Clinical_Phenotype"
REFERENCE_PREFIX = "ressources/reference/"


@dataclass
class Entry:
    """One methodology entry (or README) the catalogue scans."""

    path: str
    number: str
    step: str
    text: str


@dataclass
class Seen:
    """What the entries say about one dataset, before the ledger is joined."""

    ref: str
    kind: str
    entries: set[str] = field(default_factory=set)
    steps: set[str] = field(default_factory=set)
    producers_named: set[str] = field(default_factory=set)


def read_entries(root: Path, paths: Iterable[str]) -> list[Entry]:
    """The entries at ``paths``, in path order; a missing file is skipped, not guessed."""
    found = []
    for path in sorted(set(paths)):
        file = root / path
        if not file.is_file():
            continue
        match = ENTRY_PATH.search(path)
        number = match.group("number") if match else ""
        step = f"{match.group('iteration')}/{match.group('step')}" if match else ""
        if match and not match.group("iteration"):
            step = "step-0"
        found.append(Entry(path, number, step, file.read_text(encoding="utf-8")))
    return found


def cited_entries(text: str) -> set[str]:
    """Every entry number a note or manifest cites."""
    return {a or b for a, b in ENTRY_CITATION.findall(text)}


def producer_token(tool: str) -> str:
    """The part of a recorded ``tool`` string an entry would name, or ''."""
    match = PRODUCER.search(tool or "")
    return match.group(1) if match else ""


def table_index(ledger: Ledger, known: Iterable[str] = ()) -> dict[str, list[str]]:
    """Bare table name → every ``schema.table`` that has it, from the ledger and ``known``."""
    index: dict[str, set[str]] = {}
    names = {f"{e.get('target_schema')}.{e.get('target_table')}" for e in ledger.edges}
    for qualified in names | set(known):
        schema, _, table = qualified.partition(".")
        if schema and table:
            index.setdefault(table, set()).add(qualified)
    return {table: sorted(refs) for table, refs in index.items()}


def _file_kind(ref: str) -> str:
    if ref.startswith(CLINICAL_PREFIX):
        return "clinical"
    if ref.startswith(REFERENCE_PREFIX):
        return "reference"
    return "file"


def mentions(entries: list[Entry], tables: dict[str, list[str]]) -> dict[str, Seen]:
    """Every dataset the entries name, keyed by ref, with who named it."""
    seen: dict[str, Seen] = {}

    def note(ref: str, kind: str, entry: Entry) -> None:
        row = seen.setdefault(ref, Seen(ref, kind))
        if entry.number:
            row.entries.add(entry.number)
        if entry.step:
            row.steps.add(entry.step)

    for entry in entries:
        for schema, table in QUALIFIED.findall(entry.text):
            if table not in BOOKKEEPING and table not in EXTENSIONS:
                note(f"{schema}.{table}", "table", entry)
        for name in BARE.findall(entry.text):
            refs = tables.get(name, [])
            if len(refs) == 1 and name not in BOOKKEEPING:
                note(refs[0], "table", entry)
        for data, document in FILE_REF.findall(entry.text):
            ref = data or document
            if "provenance" not in ref.rsplit("/", 1)[-1]:
                note(ref, _file_kind(ref), entry)
        for ref in OBJECT_REF.findall(entry.text):
            note(ref, "raw", entry)
    return seen


def _produced(row: Seen, cites: set[str], producers: set[str], texts: dict[str, str]) -> bool:
    """True when a recorded producer ties the dataset to one of the entries that name it."""
    if cites & row.entries:
        return True
    return any(token and token in texts[number] for number in row.entries for token in producers)


def _table_row(row: Seen, ledger: Ledger, known: set[str], texts: dict[str, str]) -> dict:
    schema, _, table = row.ref.partition(".")
    edges = [
        e
        for e in ledger.edges
        if e.get("target_schema") == schema and e.get("target_table") == table
    ]
    current = [e for e in edges if e.get("is_current")] or edges[:1]
    cites = set().union(*(cited_entries(str(e.get("notes") or "")) for e in edges))
    producers = {producer_token(str(e.get("tool") or "")) for e in edges} - {""}
    head = current[0] if current else {}
    return _dataset(
        row,
        role="produced" if _produced(row, cites, producers, texts) else "cited",
        rows=head.get("target_rows"),
        built_by=str(head.get("tool") or ""),
        built_at=str(head.get("produced_at") or ""),
        lineage="edge" if edges else "none",
        provenance="warehouse.data_lineage" if edges else "",
        inputs=[
            {"ref": str(e.get("source_ref") or ""), "sha256": str(e.get("source_sha256") or "")}
            for e in current
        ],
        committed=False,
        exists=bool(edges) or row.ref in known,
    )


def _file_row(
    row: Seen, root: Path, tracked: set[str] | None, texts: dict[str, str], ledger: Ledger
) -> dict:
    """A data file: its manifest, else a ledger edge that records it as an input."""
    manifest = iteration_manifest.read(root, row.ref)
    if manifest is None:
        edges = [e for e in ledger.edges if str(e.get("source_ref") or "") == row.ref]
        if edges:
            return _recorded_input(row, edges, root, tracked)
    cites = cited_entries(manifest.text) if manifest else set()
    producers = {producer_token(manifest.built_by)} - {""} if manifest else set()
    committed = row.ref in tracked if tracked is not None else not row.ref.startswith("build/")
    return _dataset(
        row,
        role="produced" if _produced(row, cites, producers, texts) else "cited",
        rows=manifest.rows if manifest else None,
        sha256=manifest.sha256 if manifest else "",
        version=manifest.version if manifest else "",
        built_by=manifest.built_by if manifest else "",
        built_at=manifest.built_at if manifest else "",
        lineage="manifest" if manifest else "none",
        provenance=manifest.path if manifest else "",
        inputs=manifest.inputs if manifest else [],
        committed=committed,
        exists=(root / row.ref).exists(),
    )


def _recorded_input(
    row: Seen, edges: list[dict[str, Any]], root: Path, tracked: set[str] | None
) -> dict:
    """A file no manifest describes but the ledger records, with its digest, as an input."""
    head = edges[0]
    return _dataset(
        row,
        sha256=str(head.get("source_sha256") or ""),
        version=str(head.get("source_version") or ""),
        lineage="edge",
        provenance="warehouse.data_lineage",
        committed=row.ref in tracked if tracked is not None else not row.ref.startswith("build/"),
        exists=(root / row.ref).exists(),
    )


def _object_row(row: Seen, ledger: Ledger) -> dict:
    """An object-store reference: the object itself, or a prefix the ledger's objects sit under."""
    edges = [
        e
        for e in ledger.edges
        if (ref := str(e.get("source_ref") or "")) == row.ref or ref.startswith(f"{row.ref}/")
    ]
    head = edges[0] if len({str(e.get("source_ref")) for e in edges}) == 1 else {}
    return _dataset(
        row,
        role="cited",
        sha256=str(head.get("source_sha256") or ""),
        version=str(head.get("source_version") or ""),
        lineage="edge" if edges else "none",
        provenance="warehouse.data_lineage" if edges else "",
        exists=bool(edges),
    )


def _dataset(row: Seen, **fields: Any) -> dict[str, Any]:
    return {
        "ref": row.ref,
        "kind": row.kind,
        "role": fields.get("role", "cited"),
        "entries": sorted(row.entries),
        "steps": sorted(row.steps),
        "rows": fields.get("rows"),
        "sha256": fields.get("sha256", ""),
        "version": fields.get("version", ""),
        "built_by": fields.get("built_by", ""),
        "built_at": fields.get("built_at", ""),
        "lineage": fields.get("lineage", "none"),
        "provenance": fields.get("provenance", ""),
        "inputs": fields.get("inputs", []),
        "committed": fields.get("committed", False),
        "exists": fields.get("exists", False),
    }


def coverage(datasets: list[dict[str, Any]]) -> dict[str, int]:
    """The counts the overview draws: how much of the catalogue has recorded lineage."""
    return {
        "datasets": len(datasets),
        "produced": sum(1 for d in datasets if d["role"] == "produced"),
        "with_lineage": sum(1 for d in datasets if d["lineage"] != "none"),
        "tables": sum(1 for d in datasets if d["kind"] == "table"),
        "files": sum(1 for d in datasets if d["kind"] != "table" and d["kind"] != "raw"),
    }


#: Sort order: produced before cited, then tables, files, raw, and by name.
KIND_ORDER = {"raw": 0, "clinical": 1, "table": 2, "file": 3, "reference": 4}


def build(
    root: Path,
    paths: Iterable[str],
    ledger: Ledger,
    known: Iterable[str] = (),
    tracked: set[str] | None = None,
) -> dict[str, Any]:
    """The ``IterationCatalog`` for the entries at ``paths``.

    ``known`` is every ``schema.table`` the database holds (so a table with no edge is still
    found); ``tracked`` is ``git ls-files`` (``None`` falls back to "``build/`` is not
    committed").
    """
    entries = read_entries(root, paths)
    known_tables = set(known)
    seen = mentions(entries, table_index(ledger, known_tables))
    texts = {entry.number: entry.text for entry in entries if entry.number}
    datasets = []
    for row in seen.values():
        if row.kind == "table":
            datasets.append(_table_row(row, ledger, known_tables, texts))
        elif row.kind == "raw":
            datasets.append(_object_row(row, ledger))
        else:
            datasets.append(_file_row(row, root, tracked, texts, ledger))
    datasets.sort(key=lambda d: (d["role"] != "produced", KIND_ORDER.get(d["kind"], 9), d["ref"]))
    return {
        "available": ledger.available,
        "note": (
            f"{len(datasets)} dataset(s) named by {len(entries)} entr(y/ies)"
            if ledger.available
            else f"{ledger.note}; tables carry lineage 'none' because the ledger was not read"
        ),
        "entries": [entry.path for entry in entries],
        "datasets": datasets,
        "coverage": coverage(datasets),
    }


def tables_of(catalog: dict[str, Any]) -> list[str]:
    """The tables a catalogue names that the database or ledger knows — extra walk seeds."""
    return sorted(d["ref"] for d in catalog["datasets"] if d["kind"] == "table" and d["exists"])
