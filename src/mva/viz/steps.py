"""The research journey as JSON: every step of every iteration, and where each one stands.

Until now a research step existed in three places that never met — a goal in
``mva.science.steps``, claims in the register, figures on disk — and on no page of its
own. The ``/steps`` page is built from this one endpoint so that adding a step, or a whole
iteration, needs no hand-written prose anywhere: the step map declares it, the register
says what was claimed about it, the blind gate says what it read, and the figure directory
says what it drew.

**Why the blind gate appears here.** The plan asks for the blinding checklist to be
*generated* from the gate rather than typed. The gate already returns rows
(:mod:`mva.science.blind`); this route serves them per step, so the page and the report
show the same verdict the CLI enforces.

**Positions.** Goals, claims and file names only. No genomic coordinate exists on this
surface to withhold.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..science import blind
from ..science import steps as steps_module
from ..science.hypothesis import HYPOTHESIS_TABLE
from ..warehouse.settings import Postgres
from .response import Envelope, live
from .science import HYPOTHESIS_COLUMNS, HYPOTHESIS_ORDER, register

SOURCE = "src/mva/science/steps.py"

#: Where a step's figures live, by convention: ``figures/track1/<iteration>/<slug>/``.
FIGURES_ROOT = Path("figures/track1")

#: Where the methodology entries live.
DOCS_ROOT = Path("docs")


def _latest_by_id(rows: list[dict]) -> list[dict]:
    """One row per claim — the newest revision, which is what a board shows."""
    newest: dict[str, dict] = {}
    for row in rows:
        current = newest.get(row["hypothesis_id"])
        if current is None or int(row["revision"]) >= int(current["revision"]):
            newest[row["hypothesis_id"]] = row
    return [newest[key] for key in sorted(newest)]


def _figures(iteration: str, slug: str, root: Path) -> list[str]:
    """Figure filenames for one step. A directory that was never drawn has none, which is
    a true statement about the step rather than an error."""
    folder = root / iteration / slug
    if not folder.is_dir():
        return []
    return sorted(p.name for p in folder.iterdir() if p.is_file() and not p.name.startswith("."))


def _entries(report: blind.Report, slug: str) -> list[dict]:
    """The blinding checklist rows for one step, straight from the gate."""
    return [
        {
            "entry": entry.path.name,
            "path": str(entry.path),
            "declares_inputs": entry.declares_inputs,
            "inputs": list(entry.inputs),
            "unblinds": entry.unblinds,
            "violations": [str(v) for v in entry.violations],
        }
        for entry in report.entries
        if entry.step == slug
    ]


def payload(
    settings: Postgres,
    iteration: str,
    *,
    docs_root: Path = DOCS_ROOT,
    figures_root: Path = FIGURES_ROOT,
) -> dict:
    """One iteration's step map, with its claims, its figures and its blind-gate rows."""
    try:
        declared = steps_module.steps_for(iteration)
    except KeyError as unknown:
        raise HTTPException(status_code=404, detail=str(unknown)) from None

    register_rows = register(settings, HYPOTHESIS_TABLE, HYPOTHESIS_COLUMNS, HYPOTHESIS_ORDER)
    claims = [
        row
        for row in _latest_by_id(register_rows["rows"])
        # A row written before the iteration column existed belongs to iteration 1.
        if (row.get("iteration") or steps_module.FIRST_ITERATION) == iteration
    ]
    gate = blind.check(docs_root, iteration)

    return {
        "iteration": iteration,
        "iterations": list(steps_module.iterations()),
        "current": steps_module.ITERATION,
        "register_exists": register_rows["table_exists"],
        "blind": {
            "still_blind": gate.blind,
            "unblinded_by": str(gate.unblinded_by) if gate.unblinded_by else None,
            "problems": list(gate.problems),
        },
        "steps": [
            {
                "slug": step.slug,
                "title": step.title,
                "goal": step.goal,
                "kind": step.kind,
                "status": step.status,
                "unblocks": list(step.unblocks),
                "docs": step.docs,
                "takes_hypotheses": step.takes_hypotheses,
                "hypotheses": [row for row in claims if row["step"] == step.slug],
                "figures": _figures(iteration, step.slug, figures_root),
                "entries": _entries(gate, step.slug),
            }
            for step in declared
        ],
    }


def add_routes(api: APIRouter, settings: Postgres) -> None:
    """Register the step-map route on the warehouse router."""

    @api.get(
        "/steps",
        response_model=Envelope,
        tags=["science"],
        summary=f"the research steps of one iteration, from {SOURCE}",
    )
    def research_steps(iteration: str = "") -> dict:
        """Every step of ``iteration`` (default: the current one), with its claims.

        A step's ``hypotheses`` are the latest revision of each claim filed under it, and
        its ``entries`` are the blind gate's rows for its methodology entries — the
        blinding checklist, generated rather than typed.
        """
        return live(payload(settings, iteration or steps_module.ITERATION), SOURCE)
