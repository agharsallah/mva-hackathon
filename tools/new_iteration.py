#!/usr/bin/env python3
"""Open the next submission iteration and freeze the one the oracle just answered.

One iteration = one folder under ``submissions/<track>/`` plus one folder of research
steps under ``docs/iteration<n>/``. When a reply arrives, this tool does the bookkeeping
that is easy to get half-right by hand:

1. **freezes** the current iteration — a dated ``**Frozen:**`` line at the top of
   ``submissions/<track>/iteration-<n>/README.md`` and of ``docs/iteration<n>/README.md``
   (``tools/check_iteration.py`` then refuses any further change under the folder);
2. **opens** ``docs/iteration<n+1>/``: an index, and for every research step a ``README.md``
   (goal, standing, a link to where the step stood at the end of iteration *n*) and an
   empty ``methodology/README.md``; the ``hypotheses/`` mirrors are written by
   ``mva-science export`` once ``ITERATION`` is bumped;
3. **opens** ``submissions/<track>/iteration-<n+1>/``: a README that records the reply and
   the decode-table row it matched, a ``report.md`` skeleton, ``methods-form.json`` copied
   with the model number bumped, and ``spec.selectors.json`` copied as the starting point;
4. **bumps** ``ITERATION`` in ``src/mva/science/steps.py``.

Nothing is deleted or overwritten: the tool refuses to run if the next iteration exists.
The Markdown it writes comes from ``tools/iteration_templates/`` — edit the templates, not
this file, to change what a new iteration starts with.

    uv run python tools/new_iteration.py --track track1 --reply 'partial match rank 1, F-max 0.5'
    uv run python tools/new_iteration.py --track track1 --reply '...' --no-freeze   # no upload
    uv run python tools/new_iteration.py --track track1 --reply '...' --dry-run
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

ITERATION_LINE = re.compile(r'^ITERATION = "iteration(\d+)"$', re.MULTILINE)


@dataclass(frozen=True)
class Plan:
    root: Path
    track: str
    current: int
    reply: str
    freeze: bool
    today: str

    @property
    def nxt(self) -> int:
        return self.current + 1

    def docs(self, n: int) -> Path:
        return self.root / "docs" / f"iteration{n}"

    def sub(self, n: int) -> Path:
        return self.root / "submissions" / self.track / f"iteration-{n}"


def read_iteration(steps_py: Path) -> int:
    match = ITERATION_LINE.search(steps_py.read_text(encoding="utf-8"))
    if not match:
        raise SystemExit(f"{steps_py}: no ITERATION line found")
    return int(match.group(1))


def research_steps(root: Path) -> list[tuple[str, str, str]]:
    """``(slug, title, goal)`` for every research step, read from the step map."""
    # Loaded from the file, under a private name: importing ``mva.science.steps`` from a
    # caller-supplied root must not shadow the installed package for the rest of the process.
    path = root / "src" / "mva" / "science" / "steps.py"
    spec = importlib.util.spec_from_file_location("_iteration_step_map", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"{path}: cannot load the step map")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # ``@dataclass`` looks the module up by name
    spec.loader.exec_module(module)
    return [(s.slug, s.title, s.goal) for s in module.research_steps()]


TEMPLATES = Path(__file__).resolve().parent / "iteration_templates"


def template(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def fields(plan: Plan, **extra: str) -> dict[str, str]:
    """The placeholders every template may use, plus the caller's extras."""
    base = {
        "n": str(plan.current),
        "next": str(plan.nxt),
        "track": plan.track,
        "track_title": plan.track.capitalize(),
        "today": plan.today,
        "reply": plan.reply,
        "folder": f"submissions/{plan.track}/iteration-{plan.nxt}",
    }
    return base | extra


def freeze_line(plan: Plan, kind: str) -> str:
    continues = (
        f"submissions/{plan.track}/iteration-{plan.nxt}/"
        if kind == "folder"
        else f"docs/iteration{plan.nxt}/"
    )
    return template("frozen-banner.md").format_map(fields(plan, kind=kind, continues=continues))


def insert_after_title(text: str, block: str) -> str:
    lines = text.split("\n", 1)
    return lines[0] + "\n\n" + block + (lines[1].lstrip("\n") if len(lines) > 1 else "")


def step_readme(plan: Plan, slug: str, title: str, goal: str) -> str:
    number = slug.split("-")[1]
    return template("step-readme.md").format_map(
        fields(plan, slug=slug, number=number, title=title, goal=goal)
    )


def methodology_readme(plan: Plan, slug: str) -> str:
    return template("methodology-readme.md").format_map(fields(plan, slug=slug))


def docs_index(plan: Plan, steps: list[tuple[str, str, str]]) -> str:
    rows = "\n".join(
        f"| [{slug}]({slug}/README.md) | {goal} | opened, nothing run |" for slug, _, goal in steps
    )
    return template("docs-index.md").format_map(fields(plan, rows=rows))


def submission_readme(plan: Plan) -> str:
    return template("submission-readme.md").format_map(fields(plan))


def report_skeleton(plan: Plan) -> str:
    return template("report-skeleton.md").format_map(fields(plan))


def write(path: Path, text: str, dry_run: bool) -> None:
    print(f"  {'would write' if dry_run else 'write'} {path}")
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def run(plan: Plan, dry_run: bool) -> None:
    steps_py = plan.root / "src" / "mva" / "science" / "steps.py"
    if plan.docs(plan.nxt).exists() or plan.sub(plan.nxt).exists():
        raise SystemExit(f"iteration {plan.nxt} already exists; refusing to overwrite")
    if not plan.sub(plan.current).is_dir():
        raise SystemExit(f"{plan.sub(plan.current)} does not exist")
    steps = research_steps(plan.root)

    if plan.freeze:
        for path, kind in (
            (plan.sub(plan.current) / "README.md", "folder"),
            (plan.docs(plan.current) / "README.md", "index"),
        ):
            if path.is_file():
                text = path.read_text(encoding="utf-8")
                if "**Frozen:**" not in text:
                    write(path, insert_after_title(text, freeze_line(plan, kind)), dry_run)

    write(plan.docs(plan.nxt) / "README.md", docs_index(plan, steps), dry_run)
    for slug, title, goal in steps:
        write(
            plan.docs(plan.nxt) / slug / "README.md", step_readme(plan, slug, title, goal), dry_run
        )
        write(
            plan.docs(plan.nxt) / slug / "methodology" / "README.md",
            methodology_readme(plan, slug),
            dry_run,
        )

    write(plan.sub(plan.nxt) / "README.md", submission_readme(plan), dry_run)
    write(plan.sub(plan.nxt) / "report.md", report_skeleton(plan), dry_run)
    previous_form = plan.sub(plan.current) / "methods-form.json"
    if previous_form.is_file():
        form = json.loads(previous_form.read_text(encoding="utf-8"))
        form["8"] = str(plan.nxt)
        write(
            plan.sub(plan.nxt) / "methods-form.json",
            json.dumps(form, ensure_ascii=False, indent=2) + "\n",
            dry_run,
        )
    previous_selectors = plan.sub(plan.current) / "spec.selectors.json"
    if previous_selectors.is_file():
        write(
            plan.sub(plan.nxt) / "spec.selectors.json",
            previous_selectors.read_text(encoding="utf-8"),
            dry_run,
        )

    text = steps_py.read_text(encoding="utf-8")
    write(steps_py, ITERATION_LINE.sub(f'ITERATION = "iteration{plan.nxt}"', text), dry_run)
    verb = "planned" if dry_run else "opened"
    print(f"\niteration {plan.nxt} {verb}. Next: `uv run mva-science export` for the hypotheses/")
    print("mirrors, then fill the '(fill in)' lines before anything runs.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--track", required=True, help="track1 or track2")
    parser.add_argument(
        "--reply", required=True, help="the oracle's reply, as the decode table names it"
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--no-freeze",
        action="store_true",
        help="redesign without an upload: leave the current iteration open",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    current = read_iteration(root / "src" / "mva" / "science" / "steps.py")
    plan = Plan(
        root,
        args.track,
        current,
        args.reply.strip(),
        not args.no_freeze,
        datetime.now(UTC).date().isoformat(),
    )
    run(plan, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
