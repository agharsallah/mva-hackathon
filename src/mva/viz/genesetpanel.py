"""The one place the gene-set build knows a *panel* exists.

:mod:`mva.viz.genesetbuild` is case-agnostic: it resolves whichever symbols it is handed
into whichever free-form groups the spec names. This module holds the two steps that are
specific to a project having an **annotated panel** — a BED of intervals the callset was
actually annotated over — and both take the BED as a parameter:

* :func:`borrow_bed_notes`, so the reason a gene is on the candidate list has one owner.
* :func:`check_panel`, which refuses to write a row where Ensembl and the BED disagree
  about a gene id.

A project with no panel imports neither and loses nothing. Kept apart from the build for
exactly that reason — see ``docs/notes/reusable-structure-toolkit.md``.
"""

from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from . import panelbed
from .genesetbuild import Resolved, Wanted


def borrow_bed_notes(wanted: Sequence[Wanted], bed: Path) -> list[Wanted]:
    """Fill an empty note from the panel BED, so one fact has one owner.

    The BED's sixth column already says why each panel gene is on the candidate list, so a
    spec row with a blank note borrows that line rather than restating it — which also
    means editing the BED updates the explorer on the next rebuild. ``bed`` is a
    parameter, not a constant: a project with no panel BED passes a path that does not
    exist and every note stays as the spec wrote it.
    """
    notes = {
        symbol: (entry.get("note") or "") for symbol, entry in panelbed.annotations(bed).items()
    }
    return [
        row if row.note or not notes.get(row.symbol) else replace(row, note=notes[row.symbol])
        for row in wanted
    ]


def check_panel(found: Sequence[Resolved], bed: Path, group: str) -> list[str]:
    """Every ``group`` gene's resolved id must equal the panel BED's. Returns the failures.

    The BED is the panel's source of truth: the callset was annotated against those exact
    intervals, so a gene whose live id has moved on cannot be shown carrying the proband's
    alleles. Reported as an assertion rather than silently preferring one side.

    ``group`` is the caller's own id for that role. Pass a group name no row uses (or an
    empty string) in a project with no annotated panel, and nothing is asserted.
    """
    if not group:
        return []
    annotations = panelbed.annotations(bed)
    problems = []
    for entry in found:
        if entry.wanted.group != group:
            continue
        expected = (annotations.get(entry.wanted.symbol) or {}).get("ensembl_id")
        if expected is None:
            problems.append(f"{entry.wanted.symbol}: group {group!r} but not in {bed}")
        elif expected != entry.ensembl_id:
            problems.append(
                f"{entry.wanted.symbol}: BED says {expected}, Ensembl says {entry.ensembl_id}"
            )
    return problems
