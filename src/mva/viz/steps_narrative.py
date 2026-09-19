"""The written half of a step: its summary, its reasoning, and what each figure means.

Everything else `/api/steps` serves is *derived* — the goal from the step map, the claims
from the register, the entries from the blind gate, the figures from the filesystem. Four
things cannot be derived, because they are judgements a person made:

``summary``
    what the step did and what came out of it, in a few sentences.
``why`` / ``verdict``
    why the question had to be asked here, and what the run concluded.
``inherits`` / ``hands_to``
    the join between steps. A journey is not a list; step 4 exists because step 2's filter
    threw away the thing step 4 had to score, and only prose says so.
``figures[].reads`` / ``figures[].means``
    what a chart literally shows, and what that is evidence *for*. A figure with no caption
    is decoration; the repository already had seventy of them.

**Sourced, never invented.** Every narrative names the methodology entries and step pages it
was written from, and :func:`validate` refuses one whose sources do not exist on disk. This
is the same rule the evidence ledger enforces on an observation: a claim about a run cites
the run.

**One owner.** The step's ``README.md`` remains the place a person reads; this file is the
machine-readable form of the same judgements, committed beside it, in the shape the page and
the report both consume. ``tools/check_step_narrative.py`` fails the build when a step that
has run has no narrative, or when a figure it drew has no caption.

**Positions.** Prose about genes, consequences and counts. The coordinate gate covers this
file like every other tracked file.
"""

from __future__ import annotations

import json
from pathlib import Path

#: The file, inside a step's documentation folder.
NARRATIVE = "narrative.json"

#: Fields every narrative must carry, all of them prose a person wrote.
REQUIRED = ("summary", "why", "verdict", "inherits", "hands_to", "figures", "sources")

#: Fields of one figure caption. ``reads`` is what the chart shows; ``means`` is what it is
#: evidence for. They are separate because the first is checkable and the second is argued.
FIGURE_FIELDS = ("name", "reads", "means")


class NarrativeError(ValueError):
    """A narrative that is malformed, unsourced, or out of step with the figures on disk."""


def path_for(docs_root: Path, iteration: str, slug: str) -> Path:
    """Where a step's narrative lives: beside the README that owns the same judgements."""
    return docs_root / iteration / slug / NARRATIVE


def _prose(data: dict, where: str) -> None:
    """The three fields a step must say in its own words."""
    missing = [field for field in REQUIRED if field not in data]
    if missing:
        raise NarrativeError(f"{where}: missing {', '.join(missing)}")
    for field in ("summary", "why", "verdict"):
        if not str(data[field]).strip():
            raise NarrativeError(f"{where}: {field} is empty")


def _joins(data: dict, where: str) -> None:
    """The two joints in the argument: what the step needed, and what needs it."""
    for field in ("inherits", "hands_to"):
        block = data[field]
        if not isinstance(block, dict) or "what" not in block or "steps" not in block:
            raise NarrativeError(f"{where}: {field} needs `steps` and `what`")
        if not isinstance(block["steps"], list):
            raise NarrativeError(f"{where}: {field}.steps must be a list of slugs")


def _sources(data: dict, repo_root: Path, where: str) -> None:
    """Every file the narrative was written from, and each one has to be there."""
    sources = data["sources"]
    if not isinstance(sources, list) or not sources:
        raise NarrativeError(f"{where}: sources must name at least one file this was written from")
    for source in sources:
        if not (repo_root / str(source)).exists():
            raise NarrativeError(f"{where}: source {source!r} does not exist")


def _figures(data: dict, figures: list[str], where: str) -> None:
    """A caption per figure, a figure per caption — drift either way is a page telling a
    reader something the files do not support."""
    captioned = {}
    for figure in data["figures"]:
        gaps = [field for field in FIGURE_FIELDS if not str(figure.get(field, "")).strip()]
        if gaps:
            raise NarrativeError(f"{where}: a figure caption is missing {', '.join(gaps)}")
        captioned[figure["name"]] = figure

    unknown = sorted(set(captioned) - set(figures))
    if unknown:
        raise NarrativeError(f"{where}: captions for figures the step did not draw: {unknown}")
    uncaptioned = sorted(set(figures) - set(captioned))
    if uncaptioned:
        raise NarrativeError(f"{where}: figures with no caption: {uncaptioned}")


def validate(data: dict, *, repo_root: Path, figures: list[str], where: str) -> None:
    """Raise :class:`NarrativeError` unless the narrative is complete and sourced.

    ``figures`` is the list of filenames the step actually drew.
    """
    _prose(data, where)
    _joins(data, where)
    _sources(data, repo_root, where)
    _figures(data, figures, where)


def read(
    docs_root: Path, iteration: str, slug: str, *, repo_root: Path, figures: list[str]
) -> dict | None:
    """One step's narrative, validated, or ``None`` when the step has none written yet.

    A step with no narrative is a true state — nothing has been written about it — and the
    page says so rather than showing an empty panel. The *gate* is what decides whether that
    state is acceptable for a step that has run.
    """
    path = path_for(docs_root, iteration, slug)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    validate(data, repo_root=repo_root, figures=figures, where=path.as_posix())
    return data
