"""Gate: a step that has run must say what it did, and every figure must be read.

The repository's standing rule is that a result is not a result until it is written down.
The dashboard made that visible: `/track1/iteration1/step-6` renders the goal, the claims,
the entries and the figures — all derived — and then had nothing to say about *what the step
concluded* or *what any of its charts mean*, because nobody had written it.

This gate is that requirement, enforced:

* every research step whose status is ``done`` or ``open`` carries a ``narrative.json``;
* the narrative is complete (summary, why, verdict, what it inherits, what it hands on);
* every figure the step drew has a caption, and no caption names a figure it did not draw;
* every source the narrative cites exists on disk.

A ``planned`` step is exempt: there is nothing to summarise about a step that has not run,
and inventing one would be worse than the silence.

Run: ``uv run python tools/check_step_narrative.py`` — exits non-zero and names every gap.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mva.science import steps as steps_module
from mva.science.step import PLATFORM
from mva.viz.steps_artifacts import figure_rows
from mva.viz.steps_narrative import NarrativeError, path_for, validate

#: A step in one of these states has run, so it has something to say.
RAN = ("done", "open")


def problems(repo_root: Path) -> list[str]:
    """Every gap, as a line a reader can act on. Empty means the gate passes."""
    docs_root = repo_root / "docs"
    found: list[str] = []
    for iteration in steps_module.iterations():
        for step in steps_module.steps_for(iteration):
            if step.kind == PLATFORM or step.status not in RAN:
                continue
            path = path_for(docs_root, iteration, step.slug)
            drawn = [
                figure["name"]
                for figure in figure_rows(iteration, step.slug, step.figures, repo_root)
            ]
            if not path.is_file():
                found.append(
                    f"{iteration}/{step.slug} is {step.status} but has no {path.name}: "
                    f"{len(drawn)} figure(s) and no written summary"
                )
                continue
            try:
                validate(
                    json.loads(path.read_text(encoding="utf-8")),
                    repo_root=repo_root,
                    figures=drawn,
                    where=path.relative_to(repo_root).as_posix(),
                )
            except (NarrativeError, json.JSONDecodeError) as bad:
                found.append(str(bad))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(), help="repository root")
    args = parser.parse_args()

    found = problems(args.root)
    for line in found:
        print(f"step narrative: {line}")
    if found:
        print(f"step narrative: {len(found)} gap(s)")
        return 1
    print("step narrative: every step that has run is written up, every figure is read")
    return 0


if __name__ == "__main__":
    sys.exit(main())
