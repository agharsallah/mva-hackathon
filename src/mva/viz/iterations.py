"""Every iteration of both tracks on one page: ``GET /api/iterations``.

The repository numbers two different things "iteration". A **research iteration**
(``docs/iteration<n>/``) is one route through the case; a **submission iteration**
(``submissions/<track>/iteration-<n>/``) is one folder the organisers would receive. The
numbers do not line up — Track 2's iteration-4 folder is built from research iteration 4,
Track 1 has no iteration-4 folder, research iteration 3 is a plan and nothing else — and
until now no page showed both axes at once. This route does, and says which research
iterations each folder cites (read off the folder README's contributions table, never
typed).

Each research iteration carries its **data catalogue** (:mod:`mva.viz.iteration_catalog`)
over every methodology entry in its folder; each submission folder carries the coverage of
its own catalogue, whose rows the ``/api/submissions`` dossier serves in full. The ledger
block counts how many lineage edges name the entry that produced them — the fact that
decides whether an iteration's tables can be traced to it by the ledger alone.

Cached under one key, like ``/api/submissions``: the ledger, the table list and the
register are three round trips to the hosted database. ``?refresh=true`` rebuilds.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from ..science import steps as steps_module
from ..science.hypothesis import HYPOTHESIS_TABLE
from ..science.step import PLATFORM
from ..warehouse.settings import Postgres
from . import iteration_catalog, iterations_io, submissions, submissions_lineage, submissions_reader
from .cache import Cache
from .response import Envelope, cached
from .science import HYPOTHESIS_COLUMNS, HYPOTHESIS_ORDER, register

CACHE_KEY = "iterations"

SOURCE = (
    "docs/iteration*/**/methodology/*.md + submissions/*/iteration-*/README.md + "
    "warehouse.data_lineage + warehouse.hypotheses + *.provenance.json"
)

DOCS_DIR = "docs"

#: Which step tracks each track's pages collect — the rule ``tools/gen_steps_nav.py`` uses
#: to generate ``/track1/<iteration>`` and ``/track2/<iteration>``.
TRACK_COLLECTS = {"track1": ("track1", "both"), "track2": ("track2",)}


def research_entries(root: Path, iteration: str) -> list[str]:
    """Every methodology entry filed under ``docs/<iteration>/``, as repo paths."""
    folder = root / DOCS_DIR / iteration
    return sorted(p.relative_to(root).as_posix() for p in folder.glob("**/methodology/*.md"))


def claim_counts(settings: Postgres) -> dict[str, Counter[str]]:
    """Latest status of every register claim, counted per iteration."""
    try:
        rows = register(settings, HYPOTHESIS_TABLE, HYPOTHESIS_COLUMNS, HYPOTHESIS_ORDER)["rows"]
    except Exception:
        return {}
    newest: dict[str, dict[str, Any]] = {}
    for row in rows:
        held = newest.get(row["hypothesis_id"])
        if held is None or int(row["revision"]) >= int(held["revision"]):
            newest[row["hypothesis_id"]] = row
    counts: dict[str, Counter[str]] = {}
    for row in newest.values():
        name = row.get("iteration") or steps_module.FIRST_ITERATION
        counts.setdefault(name, Counter())[str(row.get("status") or "unknown")] += 1
    return counts


def research_names(root: Path) -> list[str]:
    """Declared iterations plus any ``docs/iteration*`` folder without a step map."""
    names = set(steps_module.iterations())
    names |= {p.name for p in (root / DOCS_DIR).glob("iteration*") if p.is_dir()}
    return sorted(names, key=lambda name: int("".join(c for c in name if c.isdigit()) or 0))


def research_row(
    name: str,
    claims: Counter[str],
    catalog: dict[str, Any],
    folders: dict[str, list[str]],
) -> dict[str, Any]:
    """One research iteration: its steps per track, its claims, its entries, its catalogue."""
    declared = name in steps_module.iterations()
    steps = [s for s in steps_module.steps_for(name) if s.kind != PLATFORM] if declared else []
    numbers = sorted(
        m.group("number")
        for path in catalog["entries"]
        if (m := iteration_catalog.ENTRY_PATH.search(path))
    )
    routes = {
        track: f"/{track}/{name}" if any(s.track in wanted for s in steps) else None
        for track, wanted in TRACK_COLLECTS.items()
    }
    prefix = f"{DOCS_DIR}/{name}/"
    return {
        "iteration": name,
        "summary": steps_module.summary(name).replace("``", "") if declared else "planned only",
        "declared": declared,
        "current": name == steps_module.ITERATION,
        "steps": len(steps),
        "done": sum(1 for s in steps if s.status == "done"),
        "open": sum(1 for s in steps if s.status == "open"),
        "tracks": {t: sum(1 for s in steps if s.track == t) for t in ("track1", "track2", "both")},
        "claims": dict(sorted(claims.items())),
        "entries": {
            "count": len(numbers),
            "first": numbers[0] if numbers else "",
            "last": numbers[-1] if numbers else "",
        },
        "submissions": sorted(k for k, paths in folders.items() if any(prefix in p for p in paths)),
        "routes": routes,
        "docs": f"{DOCS_DIR}/{name}",
        "catalog": catalog,
    }


def submission_row(iteration: dict[str, Any], entries: list[str]) -> dict[str, Any]:
    """One submission folder, summarised from the ``/api/submissions`` object."""
    research = sorted(
        {m.group("iteration") for p in entries if (m := iteration_catalog.ENTRY_PATH.search(p))}
        - {None}
    )
    probes = iteration["audit"]["probes"]
    lineage = iteration["lineage"]
    return {
        "key": f"{iteration['track']}/iteration-{iteration['number']}",
        "track": iteration["track"],
        "number": iteration["number"],
        "folder": iteration["folder"],
        "state": iteration["state"],
        "standing": iteration["standing"],
        "uploaded": iteration["uploaded"],
        "judged_by": "oracle" if iteration["track"] == "track1" else "panel",
        "research": research,
        "entries": len(entries),
        "hypotheses": len(iteration["hypotheses"]),
        "figures": len(iteration["figures"]),
        "steps": len(iteration["contributions"]),
        "reply": next((str(p["response"]) for p in probes if p.get("response")), None),
        "lineage": {
            "available": lineage["available"],
            "edges": len(lineage["edges"]),
            "sources": len(lineage["sources"]),
        },
        "catalog": iteration["catalog"]["coverage"],
    }


def attributed(ledger: submissions_lineage.Ledger) -> int:
    """Edges whose ``notes`` cite the methodology entry that produced them."""
    return sum(
        1 for e in ledger.edges if iteration_catalog.cited_entries(str(e.get("notes") or ""))
    )


def payload(settings: Postgres, root: Path | None = None) -> dict[str, Any]:
    """The overview: research iterations, submission folders, and the ledger's attribution."""
    base = (root or submissions_reader.DEFAULT_ROOT).resolve()
    ledger = submissions_lineage.read_ledger(settings)
    known = iterations_io.known_tables(settings)
    tracked = iterations_io.tracked_files(base)
    claims = claim_counts(settings)
    dossier = submissions.payload(settings, base, ledger=ledger, known=known, tracked=tracked)

    rows = []
    folders: dict[str, list[str]] = {}
    for iteration in dossier["iterations"]:
        entries = submissions_lineage.contribution_entries(iteration["contributions"])
        row = submission_row(iteration, entries)
        folders[row["key"]] = entries
        rows.append(row)

    research = [
        research_row(
            name,
            claims.get(name, Counter()),
            iteration_catalog.build(base, research_entries(base, name), ledger, known, tracked),
            folders,
        )
        for name in research_names(base)
    ]
    return {
        "research": research,
        "submissions": rows,
        "ledger": {
            "available": ledger.available,
            "edges": len(ledger.edges),
            "attributed": attributed(ledger),
            "note": ledger.note,
        },
    }


def add_routes(api: APIRouter, settings: Postgres, cache: Cache, root: Path | None = None) -> None:
    """Register ``GET /api/iterations`` on the warehouse router."""

    @api.get(
        "/iterations",
        response_model=Envelope,
        tags=["submissions"],
        summary="every research iteration and submission folder, with its data catalogue",
    )
    def iterations(refresh: bool = False) -> dict:
        """Both iteration axes at once.

        ``research[]`` is one row per ``docs/iteration<n>/`` (declared or plan-only) with
        its steps per track, its claims by latest status, its methodology entry range and
        its full catalogue. ``submissions[]`` is one row per ``submissions/<track>/
        iteration-<n>/`` with the research iterations its README cites, its reply when
        uploaded, its lineage size and its catalogue coverage.

        ``ledger.attributed`` counts edges whose ``notes`` cite an entry; the rest can be
        tied to an iteration only through the catalogue's derived ``role``.
        """
        return cached(
            cache.get_or_build(CACHE_KEY, lambda: payload(settings, root), refresh), SOURCE
        )
