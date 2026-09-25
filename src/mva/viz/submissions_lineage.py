"""What one submission iteration rests on: the edge walk, and the answer without a database.

``warehouse.data_lineage`` is an edge list — *this table came from that input, this way*.
A submission is the end of a chain through it: the selector tables came from an annotation
run, which came from the raw callset, which came from an object in the store with a
verified digest. This module walks that chain backwards from the tables the iteration's
selectors name and returns both the edges it crossed and the **roots** it landed on.

Two design points.

**The walk starts from the selectors, not from a hard-coded table list.** An iteration
declares which result tables its alleles resolve against; that declaration is the entry
point, so a future iteration built on different tables traces itself with no code change.
``results.gene_biallelic`` and ``warehouse.hpo_gene_scores`` are added because the verdict
rests on them even though no allele selector names them.

**A missing database degrades, it does not fail.** The page must render on a checkout with
no credentials. Everything knowable from disk — the clinical document and its digest, the
selector file and its digest, the table *names* — is knowable without connecting, so those
sources are always returned and only ``edges`` goes empty. ``available`` says which answer
the reader is looking at and ``note`` names the exception class that caused it, because
"there is no lineage" and "we could not read the lineage" are different sentences.

**No coordinate passes through here.** Lineage rows name objects, tables, digests and
transforms; none of those is a position.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..warehouse.postgres import safe_identifier
from ..warehouse.settings import Postgres
from ..warehouse.submission_lineage import (
    CLINICAL_FILE,
    CLINICAL_VERSION,
    JOINED_TABLES,
    SUBMISSION_SCHEMA,
    TABLE_REF,
    sha256_of,
)
from .queries import access

#: The whole edge list, with ``is_current`` computed the way
#: :func:`mva.warehouse.lineage_edges.edges` computes it: the newest edge for a target is
#: the one that describes it now, and the older rows stay as the record of it changing.
EDGE_SQL = """
    SELECT produced_at, target_schema, target_table, target_rows, source_kind,
           source_ref, source_version, source_sha256, transform, tool, notes,
           produced_at = max(produced_at) OVER (
               PARTITION BY target_schema, target_table) AS is_current
    FROM pg.{schema}.data_lineage
    ORDER BY produced_at DESC
"""

#: The table the raw callset lands in. Its edges carry the object-store URL, the version id
#: and the digest that were verified on ingest — the deepest root a submission has.
RAW_TABLE = "variants_raw"

#: A ``source_ref`` or ``source_kind`` mentioning one of these is a public reference input
#: — an ontology release, a gene model, a variant database — not a patient object.
REFERENCE_HINTS = ("hpo", "ensembl", "clinvar", "gnomad", "alphafold", "uniprot")

#: Why each non-selector table is in the source list, so the page can say it.
TABLE_NOTES = {
    "results.gene_biallelic": "the biallelic gene set the verdict was drawn from",
    "warehouse.hpo_gene_scores": "the phenotype ranking that ordered the candidates",
}


@dataclass(frozen=True)
class Ledger:
    """Every lineage edge, or the reason there are none."""

    edges: list[dict[str, Any]] = field(default_factory=list)
    available: bool = True
    note: str = ""


def read_ledger(settings: Postgres) -> Ledger:
    """Read ``warehouse.data_lineage`` whole, or report why it could not be read.

    One query for every iteration on the page: the table is a few hundred rows, and
    walking it in Python is cheaper than a recursive query per iteration.

    Catching bare :class:`Exception` is deliberate and narrow in effect. The failures that
    matter here — no credentials, DNS, a refused connection, a missing table — surface from
    DuckDB's ``ATTACH`` as a family of unrelated classes, and the caller's contract is
    "``available`` is false and ``note`` says why" for **all** of them.
    """
    sql = EDGE_SQL.format(schema=safe_identifier(settings.schema))
    try:
        rows = access.fetch(settings, sql)
    except Exception as error:
        return Ledger(
            [],
            False,
            f"warehouse unreachable ({type(error).__name__}); "
            "sources below are the ones knowable from disk",
        )
    return Ledger(rows, True, f"{len(rows)} edge(s) in warehouse.data_lineage")


def _keys(edge: dict[str, Any]) -> tuple[str, str]:
    """The two names an edge's target answers to: the bare table and ``schema.table``."""
    table = str(edge.get("target_table") or "")
    schema = str(edge.get("target_schema") or "")
    return table, f"{schema}.{table}"


def walk(edges: list[dict[str, Any]], seeds: list[str]) -> list[dict[str, Any]]:
    """Every edge reachable from ``seeds`` by following ``source_ref`` back to a table.

    Breadth-first over an index keyed by *both* spellings of a target, because an edge
    records ``target_schema`` and ``target_table`` separately while a selector names
    ``results.coding_candidates``. A ``source_ref`` that is not a ``schema.table`` — an
    ``s3://`` URL, a file, an ontology release — is a root: it is kept as an edge and the
    walk stops there.
    """
    index: dict[str, list[dict[str, Any]]] = {}
    for edge in edges:
        for key in _keys(edge):
            index.setdefault(key, []).append(edge)

    seen: set[str] = set()
    collected: list[dict[str, Any]] = []
    frontier = list(seeds)
    while frontier:
        key = frontier.pop()
        if key in seen:
            continue
        seen.add(key)
        for edge in index.get(key, []):
            if edge not in collected:
                collected.append(edge)
            reference = str(edge.get("source_ref") or "")
            if TABLE_REF.match(reference) and reference not in seen:
                frontier.append(reference)
            bare = reference.rsplit(".", maxsplit=1)[-1]
            if TABLE_REF.match(reference) and bare in index and bare not in seen:
                frontier.append(bare)
    return collected


def iteration_edges(ledger: Ledger, track: str, number: int) -> list[dict[str, Any]]:
    """The edges recorded *for* this iteration by ``resolve_submission_spec --record-lineage``."""
    target = f"{track}/iteration-{number}"
    return [
        edge
        for edge in ledger.edges
        if edge.get("target_schema") == SUBMISSION_SCHEMA and edge.get("target_table") == target
    ]


def _source(kind: str, ref: str, version: str, sha256: str, note: str) -> dict[str, str]:
    return {
        "kind": kind,
        "ref": ref,
        "version": version or "",
        "sha256": sha256 or "",
        "note": note,
    }


def disk_sources(root: Path, folder: Path, tables: list[str]) -> list[dict[str, str]]:
    """The sources that need no database: the phenotype document, the spec, the table names."""
    selectors = folder / "spec.selectors.json"
    relative = (
        selectors.relative_to(root).as_posix()
        if selectors.is_relative_to(root)
        else selectors.as_posix()
    )
    found = [
        _source(
            "clinical",
            CLINICAL_FILE,
            CLINICAL_VERSION,
            sha256_of(root / CLINICAL_FILE),
            "the delivered phenotype; it named no variant but decided which gene was believed",
        )
    ]
    # A panel-judged iteration has no predictions file and so no selector spec; naming the
    # file anyway would list a source that does not exist.
    if selectors.is_file():
        found.append(
            _source(
                "file",
                relative,
                "",
                sha256_of(selectors),
                "the committed, coordinate-free selectors the predictions CSV was resolved from",
            )
        )
    found += [
        _source(
            "table",
            table,
            "",
            "",
            TABLE_NOTES.get(table, "a selector resolves an allele against this table"),
        )
        for table in tables
    ]
    return found


def _raw_sources(collected: list[dict[str, Any]], ledger: Ledger) -> list[dict[str, str]]:
    """The callset object itself, from ``variants_raw``'s edges.

    Preferred from the walked edges. When the recorded chain does not spell the hop out,
    the object is still named — every result table in this warehouse descends from the one
    callset — and the source's ``note`` says the walk did not reach it, so the claim is
    never stronger than the evidence.
    """
    walked = [edge for edge in collected if edge.get("target_table") == RAW_TABLE]
    note = "the delivered callset, verified on ingest"
    if not walked:
        walked = [edge for edge in ledger.edges if edge.get("target_table") == RAW_TABLE]
        note += " (named from the ledger; the recorded edges do not chain back to it)"
    return [
        _source(
            "raw",
            str(edge.get("source_ref") or ""),
            str(edge.get("source_version") or ""),
            str(edge.get("source_sha256") or ""),
            note,
        )
        for edge in walked
        if str(edge.get("source_ref") or "").startswith("s3://")
    ]


def _reference_sources(collected: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Public reference inputs met on the way: an ontology release, a gene model, ClinVar."""
    found = []
    for edge in collected:
        reference = str(edge.get("source_ref") or "")
        kind = str(edge.get("source_kind") or "")
        if TABLE_REF.match(reference) or reference.startswith("s3://"):
            continue
        haystack = f"{reference} {kind}".lower()
        if any(hint in haystack for hint in REFERENCE_HINTS):
            found.append(
                _source(
                    "reference",
                    reference,
                    str(edge.get("source_version") or ""),
                    str(edge.get("source_sha256") or ""),
                    f"input to {edge.get('target_schema')}.{edge.get('target_table')}",
                )
            )
    return found


def _other_roots(collected: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Every other root the walk stopped at — a downloaded file, a public API, a card.

    Kept under the edge's own ``source_kind``: a PRISM release and a mechanism card are
    different kinds of root, and the page groups by kind. Tables, the callset object and the
    reference inputs are listed by the functions above and skipped here.
    """
    found = []
    for edge in collected:
        reference = str(edge.get("source_ref") or "")
        kind = str(edge.get("source_kind") or "")
        haystack = f"{reference} {kind}".lower()
        if (
            not reference
            or TABLE_REF.match(reference)
            or reference.startswith("s3://")
            or kind in ("table", "submission")
            or any(hint in haystack for hint in REFERENCE_HINTS)
        ):
            continue
        found.append(
            _source(
                kind or "file",
                reference,
                str(edge.get("source_version") or ""),
                str(edge.get("source_sha256") or ""),
                f"input to {edge.get('target_schema')}.{edge.get('target_table')}",
            )
        )
    return found


def _deduplicate(sources: list[dict[str, str]]) -> list[dict[str, str]]:
    """One row per ``(kind, ref)``; the first mention wins and keeps its note."""
    seen: set[tuple[str, str]] = set()
    unique = []
    for source in sources:
        key = (source["kind"], source["ref"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(source)
    return unique


def contribution_entries(contributions: list[dict[str, Any]]) -> list[str]:
    """Every methodology entry the README's contributions table links, as a repo path."""
    return sorted(
        {
            str(link.get("path") or "")
            for row in contributions
            for link in row.get("methodology", [])
            if link.get("path")
        }
    )


def entry_tables(ledger: Ledger, entries: list[str]) -> list[str]:
    """The ``schema.table`` of every edge whose ``notes`` cite one of ``entries``.

    A panel-judged iteration has no selectors, so the selector walk cannot find the tables
    it argues from. The contributions table can: it links the entries that built them, and
    each recorder writes its entry's path into the edge's ``notes``
    (``entry docs/<iteration>/step-<n>/methodology/<entry>.md``). An iteration whose
    entries recorded no edge gains nothing here.
    """
    if not entries:
        return []
    return sorted(
        {
            f"{edge.get('target_schema')}.{edge.get('target_table')}"
            for edge in ledger.edges
            if any(entry in str(edge.get("notes") or "") for entry in entries)
        }
    )


def build(
    ledger: Ledger,
    root: Path,
    folder: Path,
    track: str,
    number: int,
    tables: list[str],
    cited: list[str] | None = None,
) -> dict[str, Any]:
    """The ``Lineage`` object for one iteration: available, note, sources, edges.

    ``tables`` are the selector tables (listed as sources even with no database);
    ``cited`` are the tables its contributing entries recorded (:func:`entry_tables`), which
    extend the walk but are only known from the ledger.
    """
    seeds = sorted(set(tables) | set(JOINED_TABLES) | set(cited or []))
    on_disk = disk_sources(root, folder, sorted(set(tables) | set(JOINED_TABLES)))
    if not ledger.available:
        return {
            "available": False,
            "note": ledger.note,
            "sources": _deduplicate(on_disk),
            "edges": [],
        }
    collected = walk(ledger.edges, seeds)
    for edge in iteration_edges(ledger, track, number):
        if edge not in collected:
            collected.append(edge)
    sources = (
        _raw_sources(collected, ledger)
        + on_disk
        + _reference_sources(collected)
        + _other_roots(collected)
    )
    return {
        "available": True,
        "note": f"{len(collected)} edge(s) reached from {len(seeds)} table(s)",
        "sources": _deduplicate(sources),
        "edges": collected,
    }


def selector_tables(selectors: dict[str, Any]) -> list[str]:
    """Every distinct table the iteration's alleles resolve against, sorted."""
    return sorted({allele["table"] for allele in selectors.get("alleles", {}).values()})
