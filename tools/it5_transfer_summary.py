#!/usr/bin/env python3
"""Measure what it cost to move iteration 5's three routes to a second disease.

The claim each route makes is "case-agnostic, parameterised by a card". This script turns
that claim into numbers a reader can check, from the repository itself:

* **config lines** — the new case-card files the transfer needed, counted with ``git``
  (an untracked file counts every line, a tracked one counts its added lines).
* **code lines** — lines added and removed in the *shared* modules and drivers, split into
  two kinds: a **portability** change (a constant became a parameter) and a **new
  capability** (something the first case never had, here R1's external-measurement check).
  Only the first kind is a cost of the transfer; the second is counted and named separately.
* **identical-output proof** — the sha256 of the first case's committed tables, re-measured
  after the parameterisation, against the digests recorded in their own manifests.
* **positive control** — read from each transferred table's manifest, never retyped.
* **wall clock** — read from ``build/<case>/timing.json``, written by the runs themselves.

Case-agnostic: the routes, their file sets and the two cases are a declared plan
(:data:`PLAN`), so a third case is a new plan entry, not new code.

    uv run python tools/it5_transfer_summary.py
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from pathlib import Path
from typing import Any

from it5_transfer_plan import COLUMNS, PLAN, RoutePlan
from mva.drugs import provenance

SCRIPT = "tools/it5_transfer_summary.py"
ENTRY = "docs/iteration5/step-1/methodology/162-the-three-routes-on-bloom-syndrome.md"


def _git(*args: str) -> str:
    # Fixed argv, no shell: the paths come from PLAN, never from user input.
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def _tracked(path: str) -> bool:
    return bool(_git("ls-files", "--", path).strip())


def _numstat(path: str) -> tuple[int, int]:
    """``(added, removed)`` for one path against HEAD; a new file counts all its lines."""
    if not _tracked(path):
        text = Path(path).read_text(encoding="utf-8") if Path(path).is_file() else ""
        return (len(text.splitlines()), 0)
    out = _git("diff", "--numstat", "HEAD", "--", path).strip()
    if not out:
        return (0, 0)
    added, removed, _ = out.split("\t", 2)
    return (int(added), int(removed))


def _function_span(path: str, name: str) -> int:
    """Lines from ``def <name>`` to the next top-level statement — the capability's size."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith(f"def {name}(")), None)
    if start is None:
        return 0
    for index in range(start + 1, len(lines)):
        if lines[index] and not lines[index][0].isspace() and not lines[index].startswith(")"):
            return index - start
    return len(lines) - start


def _rows(path: Path) -> int:
    if not path.is_file():
        return 0
    with path.open(encoding="utf-8", newline="") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def _digest_matches_manifest(table: str) -> bool | None:
    """Does the table's own manifest still describe the bytes on disk?"""
    path, manifest = Path(table), Path(table).with_suffix(".provenance.json")
    if not (path.is_file() and manifest.is_file()):
        return None
    doc = json.loads(manifest.read_text(encoding="utf-8"))
    recorded = json.dumps(doc)
    return provenance.digest(path)[0] in recorded


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _held_out_per_drug(path: Path) -> tuple[str, bool]:
    """R1: one held-out control per compound, and the no-drug column that must fail."""
    rows = _read_tsv(path)
    treated = [r for r in rows if r["drug_name"] != "Untreated"]
    untreated = next((r for r in rows if r["drug_name"] == "Untreated"), None)
    passed = [r for r in treated if r["control_passed"] == "true"]
    negative_ok = untreated is not None and untreated["control_passed"] != "true"
    text = (
        f"{len(passed)}/{len(treated)} compounds passed the held-out panel; "
        f"the untreated column {'failed as designed' if negative_ok else 'PASSED — wrong'}"
    )
    return text, bool(passed) and negative_ok


def _dataset_interpretable(path: Path) -> tuple[str, bool]:
    """R2: the gating control is a property of the dataset; the primary one must be usable."""
    rows = _read_tsv(path)
    per = {r["dataset"]: r["dataset_interpretable"] == "True" for r in rows}
    ok = [name for name, value in per.items() if value]
    primary = any(name.startswith("mitchell") and value for name, value in per.items())
    text = f"{len(ok)}/{len(per)} datasets interpretable ({', '.join(sorted(ok))})"
    return text, primary


def _manifest_recall(path: Path) -> tuple[str, bool]:
    """R3: retrieval and extraction recall over the declared control PMIDs."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    value = doc.get("positive_control") or {}
    verdict = "passed" if value.get("passed") else "FAILED"
    text = f"{verdict}: retrieval {value.get('retrieval')}, extraction {value.get('extraction')}"
    return text, bool(value.get("passed"))


CONTROL_READERS = {
    "held_out_per_drug": _held_out_per_drug,
    "dataset_interpretable": _dataset_interpretable,
    "manifest_recall": _manifest_recall,
}


def _control(plan: RoutePlan) -> tuple[str, bool]:
    path = Path(plan.control_from)
    if not plan.control_from or not path.is_file():
        return "not run", False
    return CONTROL_READERS[plan.control_kind](path)


def summarise(timing: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for plan in PLAN:
        config = sum(_numstat(p)[0] for p in plan.config_files)
        added = removed = capability = 0
        for path in plan.code_files:
            a, r = _numstat(path)
            added, removed = added + a, removed + r
            if path in plan.new_capability:
                capability += _function_span(path, plan.new_capability[path][0])
        capability += sum(_numstat(p)[0] for p in plan.new_capability_files)
        added += sum(_numstat(p)[0] for p in plan.new_capability_files)
        moved = sum(_numstat(p)[0] for p in plan.moved_files)
        identical = [_digest_matches_manifest(t) for t in plan.baseline_tables]
        control_text, control_ok = _control(plan)
        rows.append(
            {
                "route": plan.route,
                "name": plan.name,
                "new_config_files": len(plan.config_files),
                "config_lines": config,
                "shared_code_files_changed": sum(
                    1 for p in plan.code_files if _numstat(p) != (0, 0)
                ),
                "code_lines_added": added,
                "code_lines_removed": removed,
                "portability_and_refactor_lines": added - capability,
                "new_capability_lines_added": capability,
                "moved_lines": moved,
                "code_change_needed": "yes" if added - capability > 0 else "no",
                "first_case_outputs_identical": (
                    "yes" if identical and all(identical) else "NO — check"
                ),
                "positive_control_passed": "yes" if control_ok else "no",
                "positive_control": control_text,
                "transfer_output_rows": ";".join(
                    f"{Path(t).name}={_rows(Path(t))}" for t in plan.transfer_tables
                ),
                "wall_clock_s": timing.get(plan.route, ""),
            }
        )
    return rows


def detail() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for plan in PLAN:
        for path in plan.config_files:
            added, removed = _numstat(path)
            out.append(
                {
                    "route": plan.route,
                    "file": path,
                    "kind": "config (new case card)",
                    "lines_added": added,
                    "lines_removed": removed,
                    "note": "the only place the second disease is named",
                }
            )
        for path in plan.new_capability_files:
            added, removed = _numstat(path)
            out.append(
                {
                    "route": plan.route,
                    "file": path,
                    "kind": "new capability (not a transfer cost)",
                    "lines_added": added,
                    "lines_removed": removed,
                    "note": "the external check, in its own module",
                }
            )
        for path in plan.moved_files:
            added, removed = _numstat(path)
            out.append(
                {
                    "route": plan.route,
                    "file": path,
                    "kind": "moved code (module-size gate, no behaviour change)",
                    "lines_added": added,
                    "lines_removed": removed,
                    "note": "existing code lifted out to keep its driver under 400 lines",
                }
            )
        for path in plan.code_files:
            added, removed = _numstat(path)
            if (added, removed) == (0, 0):
                continue
            note = "portability: a constant became a parameter"
            if path in plan.new_capability:
                note = f"portability + new capability ({plan.new_capability[path][1]})"
            out.append(
                {
                    "route": plan.route,
                    "file": path,
                    "kind": "shared code",
                    "lines_added": added,
                    "lines_removed": removed,
                    "note": note,
                }
            )
    return out


def write_tsv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=columns, delimiter="\t", extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--out", type=Path, default=Path("ressources/track2/it5/transfer"))
    parser.add_argument("--timing", type=Path, default=Path("build/it5/transfer/timing.json"))
    args = parser.parse_args()
    timing = json.loads(args.timing.read_text(encoding="utf-8")) if args.timing.is_file() else {}
    rows = summarise(timing.get("wall_clock_s", {}))
    files = detail()
    n = write_tsv(args.out / "transfer_summary.tsv", rows, COLUMNS)
    m = write_tsv(
        args.out / "transfer_diffstat.tsv",
        files,
        ["route", "file", "kind", "lines_added", "lines_removed", "note"],
    )
    for name, table, count in (
        ("transfer_summary", args.out / "transfer_summary.tsv", n),
        ("transfer_diffstat", args.out / "transfer_diffstat.tsv", m),
    ):
        doc = provenance.envelope(name, SCRIPT)
        doc.update(
            {
                "entry": ENTRY,
                "inputs": [
                    {
                        "name": "git working tree",
                        "role": "line counts, measured with git diff --numstat against HEAD",
                        "head": _git("rev-parse", "HEAD").strip(),
                    },
                    {
                        "name": "the transferred routes' own tables and manifests",
                        "role": "row counts, positive-control verdicts, digest checks",
                    },
                    {
                        "file": args.timing.as_posix(),
                        "role": "wall clock per route, recorded by the runs",
                    },
                ],
                "parameters": {
                    "cases": timing.get("cases", {}),
                    "routes": {p.route: p.name for p in PLAN},
                    "new_capability_excluded": {
                        f"{path}:{fn}": why
                        for p in PLAN
                        for path, (fn, why) in p.new_capability.items()
                    },
                },
                "rows": count,
                "outputs": [provenance.output(table, count)],
                "assumptions": (
                    "a line of a new case card is configuration; a line in a shared module or "
                    "driver is code. Blank lines and docstrings are counted, because a card is "
                    "read by a person and its prose is part of the cost. "
                    "portability_and_refactor_lines is the remainder after the declared new "
                    "capability and moved files are removed, so it still contains the churn of "
                    "splitting a driver that the repo's 400-line module gate forced; the entry "
                    "quotes the cleaner pre-split figures (112 / 45 / 114) beside it"
                ),
                "limitations": (
                    "line counts are a proxy for effort, not effort; a one-line change can be "
                    "harder than a hundred. The comparison with entry 156's 378-line driver is "
                    "like for like only in that both counts are lines a person had to write"
                ),
                "validation": (
                    "first_case_outputs_identical re-checks each first-case table against the "
                    "digest in its own manifest after the parameterisation"
                ),
                "sources": {
                    "genomic": "none: line counts and row counts",
                    "clinical": "none",
                },
            }
        )
        provenance.write(doc, table.with_suffix(".provenance.json"))
    print(f"wrote {args.out}/transfer_summary.tsv ({n} rows) and transfer_diffstat.tsv ({m} rows)")
    for row in rows:
        print(
            f"  {row['route']}: config {row['config_lines']} lines, "
            f"code +{row['code_lines_added']}/-{row['code_lines_removed']} "
            f"({row['portability_and_refactor_lines']} portability+refactor), "
            f"first case identical: {row['first_case_outputs_identical']}"
        )


if __name__ == "__main__":
    main()
