"""The research journey as JSON: every step of every iteration, and where each one stands.

Until now a research step existed in three places that never met — a goal in
``mva.science.steps``, claims in the register, figures on disk — and on no page of its
own. The research pages are built from this one endpoint so that adding a step, or a whole
iteration, needs no repetition anywhere: the step map declares it, the register says what
was claimed about it, the blind gate says what it read, and the figure directory says what
it drew.

Four things cannot be derived, because they are judgements — what the step concluded, why
the question belonged here, what it inherits and hands on, and what each figure means. Those
come from :mod:`mva.viz.steps_narrative`, are committed beside the step's README, and are
enforced by ``tools/check_step_narrative.py``: a step that has run and says nothing fails the
build, and so does a figure nobody read.

**Why the blind gate appears here.** The plan asks for the blinding checklist to be
*generated* from the gate rather than typed. The gate already returns rows
(:mod:`mva.science.blind`); this route serves them per step, so the page and the report
show the same verdict the CLI enforces.

**Positions.** Goals, claims and file names only. No genomic coordinate exists on this
surface to withhold.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..science import blind
from ..science import steps as steps_module
from ..science.hypothesis import HYPOTHESIS_TABLE
from ..science.step import Step
from ..warehouse.settings import Postgres
from . import steps_narrative, submissions_reader
from .response import Envelope, live
from .science import HYPOTHESIS_COLUMNS, HYPOTHESIS_ORDER, register
from .steps_artifacts import MEDIA_TYPES, entry_number, entry_title, figure_rows

SOURCE = "src/mva/science/steps.py"

#: The repository root, against which every declared figure path resolves.
REPO_ROOT = Path()

#: Where the methodology entries live.
DOCS_ROOT = Path("docs")

#: Where a submission iteration's folder lives, given its number.
SUBMISSIONS_ROOT = Path("submissions")


def _latest_by_id(rows: list[dict]) -> list[dict]:
    """One row per claim — the newest revision, which is what a board shows."""
    newest: dict[str, dict] = {}
    for row in rows:
        current = newest.get(row["hypothesis_id"])
        if current is None or int(row["revision"]) >= int(current["revision"]):
            newest[row["hypothesis_id"]] = row
    return [newest[key] for key in sorted(newest)]


def _submissions(iteration: str, root: Path) -> list[dict]:
    """The submission folders this iteration's work would be uploaded as.

    ``iteration2`` feeds ``submissions/<track>/iteration-2``; the numbering is the same on
    both sides by construction. A folder that does not exist contributes no row, so a
    tooling iteration that never became a submission says so by having none.

    ``state`` is read by the same function ``tools/check_iteration.py`` uses, so the card
    and the gate cannot disagree about whether a folder has been uploaded.
    """
    digits = "".join(c for c in iteration if c.isdigit())
    if not digits:
        return []
    rows = []
    for track in ("track1", "track2"):
        folder = root / track / f"iteration-{int(digits)}"
        if not folder.is_dir():
            continue
        readme = folder / "README.md"
        text = readme.read_text(encoding="utf-8") if readme.is_file() else ""
        rows.append(
            {
                "track": track,
                "number": int(digits),
                "folder": folder.as_posix(),
                "state": submissions_reader.state(text),
            }
        )
    return rows


def _summary(iteration: str) -> str:
    """The map module's own opening line, with its docstring furniture taken off."""
    line = steps_module.summary(iteration).replace("``", "")
    _, separator, rest = line.partition("—")
    return (rest if separator else line).strip()


def _index(claims_by_iteration: dict[str, int], root: Path, docs_root: Path) -> list[dict]:
    """Every iteration at a glance: what it was, how far it got, what it fed.

    The switcher needs this before it knows which iteration the reader wants, and every
    field is counted from the same declarations the cards are built from — so the strip
    and the cards can never disagree about how many steps an iteration has.

    **Undeclared iterations are listed too.** ``docs/iteration3/`` holds a plan and nothing
    else: it was drafted, absorbed into iteration 4 and never given a step map. Leaving it
    out would make the journey read as 1 → 2 → 4 with no explanation, so it appears with
    ``declared: false`` and no steps, which is exactly what is true of it.
    """
    rows = []
    for name in steps_module.iterations():
        declared = [s for s in steps_module.steps_for(name) if s.kind != "platform"]
        rows.append(
            {
                "iteration": name,
                "summary": _summary(name),
                "declared": True,
                "current": name == steps_module.ITERATION,
                "steps": len(declared),
                "done": sum(1 for s in declared if s.status == "done"),
                "open": sum(1 for s in declared if s.status == "open"),
                "claims": claims_by_iteration.get(name, 0),
                "submissions": _submissions(name, root),
                "docs": f"docs/{name}",
            }
        )
    known = {row["iteration"] for row in rows}
    for folder in sorted(docs_root.glob("iteration*")):
        if not folder.is_dir() or folder.name in known:
            continue
        rows.append(
            {
                "iteration": folder.name,
                "summary": "planned only — no step map is declared for it",
                "declared": False,
                "current": False,
                "steps": 0,
                "done": 0,
                "open": 0,
                "claims": claims_by_iteration.get(folder.name, 0),
                "submissions": _submissions(folder.name, root),
                "docs": f"docs/{folder.name}",
            }
        )
    return sorted(rows, key=lambda row: row["iteration"])


def _captioned(figures: list[dict], narrative: dict | None) -> list[dict]:
    """The figure rows with their caption folded in, so a page needs one list, not two.

    The validator guarantees a caption for every figure once a narrative exists, so the
    lookup below can only miss when the step has none written yet.
    """
    if narrative is None:
        return figures
    captions = {caption["name"]: caption for caption in narrative["figures"]}
    return [figure | {"caption": captions.get(figure["name"])} for figure in figures]


def _entries(report: blind.Report, slug: str, iteration: str) -> list[dict]:
    """The blinding checklist rows for one step, straight from the gate.

    Each row now also carries the entry's number and its own heading, so a card can name
    what was written rather than print a filename at the reader.
    """
    return [
        {
            "entry": entry.path.name,
            "number": entry_number(entry.path.name),
            "title": entry_title(entry.path),
            "url": f"/api/steps/{iteration}/{slug}/entry/{entry.path.name}",
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
    repo_root: Path = REPO_ROOT,
) -> dict:
    """One iteration's step map, with its claims, its figures and its blind-gate rows."""
    try:
        declared = steps_module.steps_for(iteration)
    except KeyError as unknown:
        raise HTTPException(status_code=404, detail=str(unknown)) from None

    register_rows = register(settings, HYPOTHESIS_TABLE, HYPOTHESIS_COLUMNS, HYPOTHESIS_ORDER)
    latest = _latest_by_id(register_rows["rows"])
    # A row written before the iteration column existed belongs to iteration 1.
    filed = [row.get("iteration") or steps_module.FIRST_ITERATION for row in latest]
    claims = [row for row, name in zip(latest, filed, strict=True) if name == iteration]
    counted = Counter(filed)
    gate = blind.check(docs_root, iteration)

    def described(slug: str, drawn: list[dict]) -> dict | None:
        """The step's written narrative, or ``None`` — see :mod:`mva.viz.steps_narrative`."""
        return steps_narrative.read(
            docs_root,
            iteration,
            slug,
            repo_root=repo_root,
            figures=[figure["name"] for figure in drawn],
        )

    drawn = {
        step.slug: figure_rows(iteration, step.slug, step.figures, repo_root) for step in declared
    }

    return {
        "iteration": iteration,
        "iterations": list(steps_module.iterations()),
        "current": steps_module.ITERATION,
        "register_exists": register_rows["table_exists"],
        "submissions": _submissions(iteration, repo_root / SUBMISSIONS_ROOT),
        "index": _index(counted, repo_root / SUBMISSIONS_ROOT, docs_root),
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
                "track": step.track,
                "unblocks": list(step.unblocks),
                "docs": step.docs,
                "takes_hypotheses": step.takes_hypotheses,
                "hypotheses": [row for row in claims if row["step"] == step.slug],
                "figures": _captioned(drawn[step.slug], described(step.slug, drawn[step.slug])),
                "entries": _entries(gate, step.slug, iteration),
                "narrative": described(step.slug, drawn[step.slug]),
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


def _declared_step(iteration: str, slug: str) -> Step:
    """One declared step, or a 404. Neither artifact route reads the register, so neither
    needs a database: a figure is a file the *step map* declared, not a row."""
    try:
        return steps_module.by_slug(slug, iteration=iteration)
    except KeyError as unknown:
        raise HTTPException(status_code=404, detail=str(unknown)) from None


def step_figure_path(iteration: str, slug: str, name: str, *, repo_root: Path = REPO_ROOT) -> Path:
    """The path of one declared figure, or a 404 naming what the step did draw.

    The lookup *is* the validation: ``name`` is matched against the rows the payload
    publishes, so a request can only ever reach a file the step map declared. There is no
    path arithmetic here for a traversal to exploit.
    """
    step = _declared_step(iteration, slug)
    rows = figure_rows(iteration, slug, step.figures, repo_root)
    for figure in rows:
        if figure["name"] == name:
            return repo_root / figure["path"]
    drew = ", ".join(f["name"] for f in rows) or "nothing"
    raise HTTPException(status_code=404, detail=f"{slug} drew {drew}, not {name!r}")


def step_entry_path(iteration: str, slug: str, name: str, *, docs_root: Path = DOCS_ROOT) -> Path:
    """The path of one methodology entry of this step, validated the same way — against the
    entries the blind gate walked, never against the request's own spelling."""
    _declared_step(iteration, slug)
    rows = _entries(blind.check(docs_root, iteration), slug, iteration)
    for entry in rows:
        if entry["entry"] == name:
            return Path(entry["path"])
    wrote = ", ".join(e["entry"] for e in rows) or "nothing"
    raise HTTPException(status_code=404, detail=f"{slug} wrote {wrote}, not {name!r}")


def add_artifact_routes(api: APIRouter, settings: Postgres) -> None:
    """The bytes behind the names ``/api/steps`` lists: figures and methodology entries.

    ``settings`` is unused on purpose: neither route reads the register, so neither can be
    made to wait on a database to hand back a PNG.
    """
    del settings

    @api.get(
        "/steps/{iteration}/{slug}/figure/{name}",
        tags=["science"],
        summary="one figure a step drew, as it was rendered",
        response_class=FileResponse,
    )
    def step_figure(iteration: str, slug: str, name: str) -> FileResponse:
        """One figure file. Bytes, not an envelope — an ``<img src>`` cannot read JSON."""
        path = step_figure_path(iteration, slug, name)
        return FileResponse(
            path, media_type=MEDIA_TYPES.get(path.suffix, "application/octet-stream")
        )

    @api.get(
        "/steps/{iteration}/{slug}/entry/{name}",
        response_model=Envelope,
        tags=["science"],
        summary="one methodology entry of a step, verbatim",
    )
    def step_entry(iteration: str, slug: str, name: str) -> dict:
        """The entry as it is on disk — the audit log is quoted, never summarised."""
        path = step_entry_path(iteration, slug, name)
        return live(
            {
                "entry": name,
                "number": entry_number(name),
                "title": entry_title(path),
                "path": path.as_posix(),
                "markdown": path.read_text(encoding="utf-8"),
            },
            path.as_posix(),
        )
