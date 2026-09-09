"""Reading one ``submissions/<track>/iteration-<n>/`` folder into an object.

The folder is the unit the organisers receive: a README that declares its state, the
report, the methods form, the decode table and the coordinate-free selector spec. Nothing
in the database knows any of that, so this module is the parser — pure functions over a
repository root, no settings, no connection, no network.

Three properties are load-bearing.

**No genomic position leaves here.** The selector spec is coordinate-free *by
construction*: an allele is a table plus a ``WHERE`` clause, and the position is resolved
on a machine with database access into a gitignored file that never enters the tree. An
allele that carries a ``pos`` key would break that, so :func:`selectors` raises
:class:`PositionInSelectorError` rather than serving it. The same rule is checked from the
other side by ``tools/check_iteration.py``; duplicating it here is deliberate — a reader
must not be able to publish what a gate happens to be off for.

**The README is the source of truth for the state.** ``draft`` / ``ready`` / ``frozen`` is
read from the ``**Standing:**`` line with exactly the precedence
``tools/check_iteration.py`` uses, so the API and the gate can never disagree about what
an iteration is. The parsing is duplicated rather than imported because ``tools/`` is a
script directory, not an importable package.

**Markdown is returned verbatim.** ``report.markdown`` is the bytes on disk. The browser
renders it; this layer neither rewrites links nor summarises. The two markdown files that
*are* read as data — the decode table and the README's contributions section — are parsed
by :mod:`mva.viz.submissions_markdown`, which is the only module here that knows what a
pipe table is.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .submissions_markdown import contributions, decode_table, strip_markdown

#: Relative to the repository root, which is where the API is started from.
DEFAULT_ROOT = Path()

SUBMISSIONS_DIR = "submissions"
FIGURES_DIR = "figures"

#: ``**Frozen:**`` beats ``**Standing:**``; see :func:`state`.
FROZEN_MARKER = re.compile(r"\*\*Frozen:\*\*\s*(.*)")
STANDING_MARKER = re.compile(r"\*\*Standing:\*\*\s*(.*)")

SHA256 = re.compile(r"\b([0-9a-f]{64})\b")
#: The CSV lives under gitignored ``build/`` or, gitignored too, inside its own iteration folder.
CSV_PATH = re.compile(r"`((?:build/submission|submissions/[\w-]+/iteration-\d+)/[\w.-]+\.csv)`")
HYPOTHESIS_ID = re.compile(r"\bH\d{3}\b")
ITERATION_NAME = re.compile(r"^iteration-(\d+)$")

#: File name → the ``kind`` the browser groups deliverables by. Suffix rules first, then
#: exact names; anything unrecognised is ``other`` rather than dropped, because a folder
#: is allowed to carry material the contract has no word for yet.
DELIVERABLE_SUFFIXES = (
    ("_report.pdf", "report-pdf"),
    ("_methods_form.xlsx", "methods-xlsx"),
)
DELIVERABLE_NAMES = {
    "README.md": "readme",
    "report.md": "report-md",
    "methods-form.json": "methods-json",
    "decode-table.md": "decode-table",
    "spec.selectors.json": "selectors",
}


class PositionInSelectorError(ValueError):
    """Raised when a selector spec carries a genomic position instead of a selector.

    The whole point of ``spec.selectors.json`` being committed is that it describes the
    alleles without saying where they are. A ``pos`` key in it means the coordinate-free
    invariant was already broken on disk, and serving the file over HTTP would publish it.
    """


def iteration_folders(root: Path) -> list[Path]:
    """Every ``submissions/<track>/iteration-<n>/``, ordered by track then number.

    Numerically by iteration, so ``iteration-10`` sorts after ``iteration-2`` rather than
    before it the way a plain glob would put it.
    """
    found = [
        path
        for path in (root / SUBMISSIONS_DIR).glob("*/iteration-*")
        if path.is_dir() and ITERATION_NAME.match(path.name)
    ]
    return sorted(found, key=lambda path: (path.parent.name, number_of(path) or 0))


def number_of(folder: Path) -> int | None:
    """The ``n`` in ``iteration-<n>``, or ``None`` when the name is not one."""
    match = ITERATION_NAME.match(folder.name)
    return int(match.group(1)) if match else None


def state(readme: str) -> str:
    """``frozen`` beats ``ready`` beats ``draft``, read off the README's own declaration.

    Byte-for-byte the rule in ``tools/check_iteration.py``: a ``**Frozen:**`` line means
    uploaded; otherwise the ``**Standing:**`` text decides, and an unrecognisable standing
    is a draft rather than an error — an unfinished folder is exactly what a draft is.
    """
    if FROZEN_MARKER.search(readme):
        return "frozen"
    match = STANDING_MARKER.search(readme)
    text = match.group(1).lower() if match else ""
    if "draft" in text or "in progress" in text:
        return "draft"
    if "built" in text or "ready" in text or "not uploaded" in text:
        return "ready"
    return "draft"


def standing(readme: str) -> str:
    """The declared standing as plain text: the Frozen line if there is one, else Standing."""
    for pattern in (FROZEN_MARKER, STANDING_MARKER):
        match = pattern.search(readme)
        if match:
            return strip_markdown(match.group(1))
    return ""


def csv_record(readme: str, rows: int | None) -> dict[str, Any]:
    """What the README says about the predictions CSV: its path, its digest, its size.

    The file itself is **never** in the tree — it holds real coordinates and lives under
    gitignored ``build/``. All that is committed is the claim about it, which is what this
    returns. ``rows`` comes from the selector spec, not from the file, for the same reason.
    """
    named = CSV_PATH.search(readme)
    digest = SHA256.search(readme)
    return {
        "path": named.group(1) if named else None,
        "sha256": digest.group(1) if digest else None,
        "rows": rows,
    }


def deliverables(folder: Path) -> list[dict[str, Any]]:
    """Every file in the folder, with what it is and when it was written.

    Hidden files are skipped (``.DS_Store`` is not a deliverable). ``modified`` is UTC ISO
    so a stale render is visible as a date, which is the mistake the folder gate exists to
    catch.
    """
    rows = []
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.name.startswith("."):
            continue
        stat = path.stat()
        rows.append(
            {
                "name": path.name,
                "kind": deliverable_kind(path.name),
                "bytes": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(
                    timespec="seconds"
                ),
            }
        )
    return rows


def deliverable_kind(name: str) -> str:
    """Which of the contract's seven kinds a file name is."""
    for suffix, kind in DELIVERABLE_SUFFIXES:
        if name.endswith(suffix):
            return kind
    return DELIVERABLE_NAMES.get(name, "other")


def selectors(folder: Path) -> dict[str, Any]:
    """``spec.selectors.json``, verbatim, with the rows ranked and the positions refused.

    ``rank`` is added rather than stored: the CSV's row order *is* the ranking the scorer
    reads, so numbering it here keeps the browser from having to know that.
    """
    path = folder / "spec.selectors.json"
    if not path.is_file():
        return {"alleles": {}, "rows": [], "hypotheses": [], "derivation": None}
    spec = json.loads(path.read_text(encoding="utf-8"))
    derived = derivation(folder)
    if derived:
        spec = {**spec, "rows": derived["rows"], "hypotheses": derived["hypotheses"]}
    alleles = spec.get("alleles", {})
    for name, allele in alleles.items():
        if "pos" in allele:
            raise PositionInSelectorError(
                f"{path}: allele {name!r} carries a position; selectors only"
            )
    rows = [
        {
            "rank": rank,
            "variant": row.get("variant", ""),
            "partner": row.get("partner"),
            "epcr": float(row.get("epcr", 0)),
            "finding_type": row.get("finding_type", "primary"),
            "label": row.get("label", ""),
            "notes": row.get("notes", ""),
            "score": row.get("score"),
            "hypothesis": row.get("hypothesis"),
        }
        for rank, row in enumerate(spec.get("rows", []), 1)
    ]
    return {
        "alleles": alleles,
        "rows": rows,
        "hypotheses": spec.get("hypotheses", []),
        "derivation": derived
        and {
            "anchor": derived.get("anchor", {}),
            "parameters": derived.get("parameters", {}),
            "alleles": derived.get("alleles", {}),
            "arithmetic": derived.get("arithmetic", []),
        },
    }


def derivation(folder: Path) -> dict[str, Any] | None:
    """``derivation.json`` — the epcr ladder, notes, priors and facts the data decided.

    Written coordinate-free by ``tools/resolve_submission_spec.py`` when the selectors carry
    a ``derivation`` block; ``None`` for an iteration that still types its rows by hand.
    """
    path = folder / "derivation.json"
    if not path.is_file():
        return None
    found: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return found


def selector_text(folder: Path) -> str:
    """The raw selector file, for the hypothesis-id sweep. ``""`` when absent."""
    path = folder / "spec.selectors.json"
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def methods_form(folder: Path) -> list[dict[str, str]]:
    """``methods-form.json`` as ordered ``{row, answer}`` pairs.

    The organisers' template is a spreadsheet whose questions are numbered rows, so the
    keys are numeric strings and must be sorted numerically — string order would put row
    10 between 1 and 2 and quietly reorder the form.
    """
    path = folder / "methods-form.json"
    if not path.is_file():
        return []
    answers = json.loads(path.read_text(encoding="utf-8"))
    keys = [key for key in answers if key.isdigit()]
    return [{"row": key, "answer": str(answers[key])} for key in sorted(keys, key=int)]


def figures(root: Path, track: str, number: int) -> list[dict[str, str]]:
    """Every PNG under ``figures/<track>/``, with the URL that serves it.

    A missing directory contributes no rows rather than an error: a track whose figures
    were never rendered has nothing to show, which is a true statement about it.
    """
    directory = root / FIGURES_DIR / track
    if not directory.is_dir():
        return []
    return [
        {
            "slug": path.stem,
            "path": path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path),
            "url": f"/api/submissions/{track}/{number}/figure/{path.stem}",
        }
        for path in sorted(directory.glob("*.png"))
    ]


def report(folder: Path, root: Path) -> dict[str, str]:
    """``report.md`` verbatim, with the path a reader would open."""
    path = folder / "report.md"
    relative = path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path)
    return {
        "path": relative,
        "markdown": path.read_text(encoding="utf-8") if path.is_file() else "",
    }


def hypothesis_ids(*texts: str) -> list[str]:
    """Every ``H###`` mentioned, unique and sorted — the claims this iteration argues."""
    found: set[str] = set()
    for text in texts:
        found.update(HYPOTHESIS_ID.findall(text))
    return sorted(found)


def read(folder: Path, root: Path | None = None) -> dict[str, Any]:
    """One iteration folder as the contract's ``Iteration``, minus lineage and audit.

    Those two are added by :mod:`mva.viz.submissions`, because they need a database
    connection and this module deliberately has none.
    """
    base = (root or DEFAULT_ROOT).resolve()
    folder = folder.resolve()
    track = folder.parent.name
    number = number_of(folder) or 0
    readme_path = folder / "README.md"
    readme = readme_path.read_text(encoding="utf-8") if readme_path.is_file() else ""
    spec = selectors(folder)
    text = report(folder, base)
    return {
        "track": track,
        "number": number,
        "folder": folder.relative_to(base).as_posix()
        if folder.is_relative_to(base)
        else str(folder),
        "state": state(readme),
        "standing": standing(readme),
        "uploaded": state(readme) == "frozen",
        "csv": csv_record(readme, len(spec["rows"]) or None),
        "deliverables": deliverables(folder),
        "decode_table": decode_table(folder),
        "selectors": spec,
        "methods_form": methods_form(folder),
        "contributions": contributions(readme, folder, base),
        "hypotheses": hypothesis_ids(readme, text["markdown"], selector_text(folder)),
        "figures": figures(base, track, number),
        "report": text,
    }
