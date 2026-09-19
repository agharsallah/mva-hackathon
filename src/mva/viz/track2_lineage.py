"""What the Track 2 tables rest on: the recorded edges, and the answer without a database.

``tools/record_track2_lineage.py`` writes one edge per source of each Track 2 table into
``warehouse.data_lineage`` (:mod:`mva.warehouse.track2_lineage`). This module reads them
back for ``/api/track2``, and continues the walk: a ``card`` edge stops at a file, but a
``submission`` edge points at ``track1/iteration-1``, whose own edges point at the result
tables, which point at the callset object in the store. That chain is the reason Track 2 is
traceable to patient evidence at all, so it is walked rather than truncated.

Two properties, both shared with :mod:`mva.viz.submissions_lineage` on purpose.

**A missing database degrades, it does not fail.** Everything the edges assert is *also*
knowable from the manifests on disk, because that is where the recorder reads it from. So
on a checkout with no credentials the sources are still listed — the card by digest, each
API host by roll-up digest, the Track 1 iteration, the target table — and only ``edges``
goes empty. ``available`` says which answer the reader has and ``note`` names the exception
class, because "there is no lineage" and "we could not read the lineage" are different
sentences.

**No coordinate passes through here.** Edges name tables, hosts, digests and transforms.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..warehouse.submission_lineage import TABLE_REF
from ..warehouse.track2_lineage import (
    SOURCE_ITERATION,
    TRACK2_SCHEMA,
    TRANSFER_COMPARISON,
    planned_edges,
)
from .submissions_lineage import Ledger, walk

#: A transfer case's tables are recorded under this prefix, plus the one cross-case table
#: at the Track 2 root. Both are listed separately on the page: a transfer case has no
#: ``submission`` edge, and a reader must be able to see that rather than infer it.
TRANSFER_PREFIX = "transfer."

#: What each kind of source is, in one line, for the page's own explanation of the block.
KIND_NOTES = {
    "card": "the mechanism card every Track 2 query was derived from",
    "api": "a public API the snapshot read; the digest rolls up its cached replies",
    "submission": "the Track 1 iteration whose research record the card was written from",
    "table": "the target set the drug, trial and literature searches were run over",
}


def track2_edges(ledger: Ledger) -> list[dict[str, Any]]:
    """Every edge recorded *for* a Track 2 table, newest first as the ledger returns them."""
    return [edge for edge in ledger.edges if edge.get("target_schema") == TRACK2_SCHEMA]


def seeds(edges: list[dict[str, Any]]) -> list[str]:
    """The targets to continue the walk from: the referenced tables and the iteration.

    A ``card`` edge names a file and an ``api`` edge names a host; neither is a target of
    anything, so the walk stops there. ``track1/iteration-1`` and ``track2.targets`` are
    both targets of their own edges, so both extend the chain.
    """
    found: set[str] = set()
    for edge in edges:
        reference = str(edge.get("source_ref") or "")
        if reference == SOURCE_ITERATION or TABLE_REF.match(reference):
            found.add(reference)
    return sorted(found)


def _source(edge: dict[str, Any]) -> dict[str, str]:
    kind = str(edge.get("source_kind") or "")
    return {
        "kind": kind,
        "ref": str(edge.get("source_ref") or ""),
        "version": str(edge.get("source_version") or ""),
        "sha256": str(edge.get("source_sha256") or ""),
        "note": str(edge.get("notes") or "") or KIND_NOTES.get(kind, ""),
    }


def is_transfer(edge: dict[str, Any]) -> bool:
    """True for an edge about a transfer case rather than about the proband's card."""
    target = str(edge.get("target_table") or "")
    return target.startswith(TRANSFER_PREFIX) or target == TRANSFER_COMPARISON


def _deduplicate(sources: list[dict[str, str]]) -> list[dict[str, str]]:
    """One row per ``(kind, ref, sha256)``; the first mention wins and keeps its note.

    The digest is part of the key rather than only the reference: the same API host read by
    two tables is two different sets of replies, and collapsing them would claim one
    roll-up digest covers both.
    """
    seen: set[tuple[str, str, str]] = set()
    unique = []
    for source in sources:
        key = (source["kind"], source["ref"], source["sha256"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(source)
    return unique


def build(ledger: Ledger, root: Path | None = None) -> dict[str, Any]:
    """The ``lineage`` block for ``/api/track2``: available, note, sources, edges, transfer.

    ``transfer`` is always populated, database or not, because it is read off the manifests
    on disk. It is the one block a reader needs to check the claim that a transfer case has
    **no** ``submission`` source: the edges are there to count.
    """
    planned = planned_edges(root)
    on_disk = _deduplicate([_source(edge) for edge in planned])
    transfer = [edge for edge in planned if is_transfer(edge)]
    if not ledger.available:
        return {
            "available": False,
            "note": f"{ledger.note}; the sources below are the manifests' own claims",
            "sources": on_disk,
            "edges": [],
            "transfer": transfer,
        }
    recorded = track2_edges(ledger)
    collected = list(recorded)
    for edge in walk(ledger.edges, seeds(recorded)):
        if edge not in collected:
            collected.append(edge)
    sources = _deduplicate([_source(edge) for edge in recorded] + on_disk)
    return {
        "available": True,
        "note": (
            f"{len(recorded)} edge(s) recorded for schema '{TRACK2_SCHEMA}', "
            f"{len(collected) - len(recorded)} more reached by walking back; "
            f"{len(transfer)} of the planned edges belong to a transfer case and carry no "
            "submission source"
        ),
        "sources": sources,
        "edges": collected,
        "transfer": transfer,
    }
