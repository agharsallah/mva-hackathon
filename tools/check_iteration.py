#!/usr/bin/env python3
"""Fail when a submission iteration folder is not what its README says it is.

``submissions/<track>/iteration-<n>/`` is the unit the organisers receive and the judges
read. Its README declares a state — **draft**, **ready** (built, not uploaded) or **frozen**
(uploaded) — and this gate checks that the folder honours it:

- every deliverable is present: ``README.md``, ``report.md``, the rendered
  ``<user>_<track>_report.pdf``, ``methods-form.json`` and its ``.xlsx``, ``decode-table.md``,
  ``spec.selectors.json`` (draft: only README, report and selectors are required);
- rendered files are **newer** than their sources (a stale PDF is the classic last-minute
  mistake);
- the methods form answers every question the template asks (rows 7–18) and keeps the
  abstract at or under 500 words; the model number equals the iteration number;
- the selectors are internally consistent: every row names known alleles, every hypothesis
  names known alleles or ``_unknown*``, epcr values are strictly descending, at most 10 rows;
- the README records a sha256 and, when the CSV it names exists locally, the digest matches;
- a frozen folder has **no** uncommitted change under it;
- no ``TODO`` / ``TBD`` / ``FIXME`` survives in a ready or frozen folder.

Usage::

    uv run python tools/check_iteration.py                       # every iteration folder
    uv run python tools/check_iteration.py submissions/track1/iteration-1
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

STATES = ("draft", "ready", "frozen")
FORM_ROWS = [str(n) for n in range(7, 19)]
ABSTRACT_ROW = "18"
MODEL_ROW = "8"
ABSTRACT_WORDS = 500
SHA256 = re.compile(r"\b([0-9a-f]{64})\b")
CSV_PATH = re.compile(r"`(build/submission/[\w.-]+\.csv)`")
PLACEHOLDER = re.compile(r"\b(TODO|TBD|FIXME)\b")
UNKNOWN_PREFIX = "_unknown"


@dataclass
class Report:
    folder: Path
    state: str = "draft"
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def fail(self, text: str) -> None:
        self.problems.append(text)

    def warn(self, text: str) -> None:
        self.warnings.append(text)

    @property
    def ok(self) -> bool:
        return not self.problems


def read_state(readme: str) -> str:
    """The state the README declares: ``frozen`` beats ``ready`` beats ``draft``."""
    if re.search(r"\*\*Frozen:\*\*", readme):
        return "frozen"
    standing = re.search(r"\*\*Standing:\*\*\s*(.+)", readme)
    text = standing.group(1).lower() if standing else ""
    if "draft" in text or "in progress" in text:
        return "draft"
    if "built" in text or "ready" in text or "not uploaded" in text:
        return "ready"
    return "draft"


def iteration_number(folder: Path) -> int | None:
    match = re.search(r"iteration-(\d+)$", folder.name)
    return int(match.group(1)) if match else None


def newer(rendered: Path, source: Path) -> bool:
    return rendered.stat().st_mtime >= source.stat().st_mtime


def check_files(folder: Path, report: Report) -> None:
    required = ["README.md", "report.md", "spec.selectors.json"]
    if report.state != "draft":
        required += ["methods-form.json", "decode-table.md"]
    for name in required:
        if not (folder / name).is_file():
            report.fail(f"missing {name}")
    if report.state == "draft":
        return
    pdfs = sorted(folder.glob("*_report.pdf"))
    if not pdfs:
        report.fail("missing <user>_<track>_report.pdf")
    elif (folder / "report.md").is_file() and not newer(pdfs[0], folder / "report.md"):
        report.fail(f"{pdfs[0].name} is older than report.md — re-render")
    forms = sorted(folder.glob("*_methods_form.xlsx"))
    if not forms:
        report.fail("missing <user>_<track>_methods_form.xlsx")
    elif (folder / "methods-form.json").is_file() and not newer(
        forms[0], folder / "methods-form.json"
    ):
        report.fail(f"{forms[0].name} is older than methods-form.json — re-fill")


def check_placeholders(folder: Path, report: Report) -> None:
    if report.state == "draft":
        return
    for path in sorted(folder.glob("*.md")) + sorted(folder.glob("*.json")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if PLACEHOLDER.search(line):
                report.fail(f"{path.name}:{number}: placeholder left in a {report.state} folder")


def check_methods_form(folder: Path, report: Report) -> None:
    path = folder / "methods-form.json"
    if not path.is_file():
        return
    answers = json.loads(path.read_text(encoding="utf-8"))
    for row in FORM_ROWS:
        if not str(answers.get(row, "")).strip():
            report.fail(f"methods-form.json: row {row} unanswered")
    words = len(str(answers.get(ABSTRACT_ROW, "")).split())
    if words > ABSTRACT_WORDS:
        report.fail(f"methods-form.json: abstract is {words} words, limit {ABSTRACT_WORDS}")
    number = iteration_number(folder)
    if number is not None and str(answers.get(MODEL_ROW, "")).strip() != str(number):
        report.fail(
            f"methods-form.json: model number {answers.get(MODEL_ROW)!r} ≠ iteration {number}"
        )


def check_selectors(folder: Path, report: Report) -> None:
    path = folder / "spec.selectors.json"
    if not path.is_file():
        return
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        report.fail(f"spec.selectors.json: not valid JSON ({error})")
        return
    alleles = set(spec.get("alleles", {}))
    for name, raw in spec.get("alleles", {}).items():
        if "pos" in raw:
            report.fail(f"spec.selectors.json: allele {name!r} carries a position — selectors only")
    check_rows(spec.get("rows", []), alleles, report)
    for hypothesis in spec.get("hypotheses", []):
        for name in hypothesis.get("alleles", []):
            if name not in alleles and not name.startswith(UNKNOWN_PREFIX):
                label = hypothesis.get("label")
                report.fail(
                    f"spec.selectors.json: hypothesis {label!r} names unknown allele {name!r}"
                )


def check_rows(rows: list[dict], alleles: set[str], report: Report) -> None:
    if not rows:
        report.fail("spec.selectors.json: no rows")
    if len(rows) > 10:
        report.fail(f"spec.selectors.json: {len(rows)} rows, the scorer accepts 10")
    for i, row in enumerate(rows, 1):
        for key in ("variant", "partner"):
            name = row.get(key)
            if name and name not in alleles:
                report.fail(f"spec.selectors.json: row {i} {key} {name!r} is not a declared allele")
        if not 0 < float(row.get("epcr", 0)) <= 1:
            report.fail(f"spec.selectors.json: row {i} epcr must be in (0, 1]")
    epcrs = [float(r.get("epcr", 0)) for r in rows]
    if any(a <= b for a, b in itertools.pairwise(epcrs)):
        report.fail("spec.selectors.json: epcr values must be strictly descending")


def check_digest(folder: Path, root: Path, readme: str, report: Report) -> None:
    if report.state == "draft":
        return
    digests = SHA256.findall(readme)
    if not digests:
        report.fail("README.md records no sha256 for the predictions CSV")
        return
    named = CSV_PATH.search(readme)
    if not named:
        report.warn("README.md names no build/submission/*.csv path")
        return
    csv = root / named.group(1)
    if not csv.is_file():
        report.warn(f"{named.group(1)} not on this machine; digest not verified")
        return
    actual = hashlib.sha256(csv.read_bytes()).hexdigest()
    if actual not in digests:
        report.fail(f"README sha256 does not match {named.group(1)} ({actual[:12]}…)")


def check_frozen(folder: Path, root: Path, report: Report) -> None:
    if report.state != "frozen":
        return
    rel = folder.relative_to(root).as_posix()
    diff = subprocess.run(
        ["git", "status", "--porcelain", "--", rel],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,  # a folder outside any repository is reported below, not raised
    )
    if diff.stdout.strip():
        report.fail(
            "frozen folder has uncommitted changes:\n    "
            + diff.stdout.strip().replace("\n", "\n    ")
        )


def check_folder(folder: Path, root: Path) -> Report:
    report = Report(folder)
    readme_path = folder / "README.md"
    if not readme_path.is_file():
        report.fail("missing README.md")
        return report
    readme = readme_path.read_text(encoding="utf-8")
    report.state = read_state(readme)
    if "**Standing:**" not in readme and "**Frozen:**" not in readme:
        report.fail("README.md has no **Standing:** line")
    check_files(folder, report)
    check_placeholders(folder, report)
    check_methods_form(folder, report)
    check_selectors(folder, report)
    check_digest(folder, root, readme, report)
    check_frozen(folder, root, report)
    return report


def iteration_folders(root: Path) -> list[Path]:
    return sorted(p for p in (root / "submissions").glob("*/iteration-*") if p.is_dir())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("folders", nargs="*", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    folders = [f.resolve() for f in args.folders] or iteration_folders(root)
    failed = 0
    for folder in folders:
        report = check_folder(folder, root)
        rel = folder.relative_to(root).as_posix() if folder.is_relative_to(root) else str(folder)
        if not args.quiet or not report.ok:
            verdict = "ok" if report.ok else f"{len(report.problems)} problem(s)"
            print(f"{rel}: {report.state} — {verdict}")
        for problem in report.problems:
            print(f"  ✗ {problem}")
        for warning in report.warnings:
            print(f"  ! {warning}")
        failed += not report.ok
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
