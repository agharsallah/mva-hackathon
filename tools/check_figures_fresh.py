#!/usr/bin/env python3
"""Fail when a committed figure is older than the numbers it claims to show.

A figure in this repository is a *rendering of a table*, and the rule is that it cannot
disagree with the table it claims to show. Nothing enforced the one way that promise breaks
in practice: the analysis is re-exported, the renderer is not re-run, and a stale PNG stays
committed under a caption that now quotes a different number.

That is not hypothetical. Entry 090 re-scored every allele the vendor never reported and
flipped H020's verdict; four of step 2's exhibits were still the pre-flip render nine hours
later, and only a timestamp comparison distinguished them from the fresh ones.

**The rule.** For every ``figures/track1/<iteration>/step-<n>/`` directory, if that step's
``build/<it>/step-<n>/analysis.json`` exists, every rendered artifact in the directory must
be at least as new as it.

**Why it skips when the analysis is absent.** ``build/`` is gitignored: it holds the run's
own outputs and, for some steps, real coordinates. CI and a fresh clone have the figures and
not the analysis, and a gate that cannot see the input has nothing to compare against — so
it reports the directory as skipped rather than inventing a verdict. The gate therefore
binds on the machine that renders, which is the machine that can get it wrong.

Usage::

    uv run python tools/check_figures_fresh.py
    uv run python tools/check_figures_fresh.py --quiet
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

#: Where rendered exhibits live, and where the numbers behind them are exported.
FIGURE_ROOT = Path("figures/track1")
BUILD_ROOT = Path("build")

#: The file every step's exporter writes. One name, so a new step is covered by existing.
ANALYSIS = "analysis.json"

#: Rendered artifacts. HTML pages are included because the interactive report is the
#: primary artifact and the PNG is the convenience copy — a stale page is the worse failure.
RENDERED = ("*.png", "*.svg", "*.html")

#: ``figures/track1/iteration2`` holds the work whose build directory is ``build/it2``.
ITERATION = re.compile(r"^iteration(\d+)$")

#: Tolerance in seconds. A render and an export in the same command can land microseconds
#: apart in either order on a filesystem with coarse timestamps; a minute is far below the
#: gap that means "somebody forgot to re-render" and far above clock noise.
SLACK = 60.0


@dataclass(frozen=True)
class Stale:
    figure: Path
    analysis: Path
    behind_seconds: float

    def __str__(self) -> str:
        minutes = self.behind_seconds / 60
        return f"{self.figure}: {minutes:,.0f} min older than {self.analysis}"


def build_dir(iteration: str, step: str) -> Path:
    """``iteration2``/``step-2`` -> ``build/it2/step-2``."""
    match = ITERATION.match(iteration)
    return BUILD_ROOT / (f"it{match.group(1)}" if match else iteration) / step


def rendered(directory: Path) -> list[Path]:
    return sorted(path for pattern in RENDERED for path in directory.glob(pattern))


def check(root: Path) -> tuple[list[Stale], list[str]]:
    """Every stale artifact, and a line per directory describing what was done."""
    stale: list[Stale] = []
    report: list[str] = []
    figure_root = root / FIGURE_ROOT
    if not figure_root.is_dir():
        return stale, ["no figures/track1 — nothing to check"]
    for step_dir in sorted(figure_root.glob("*/step-*")):
        if not step_dir.is_dir():
            continue
        rel = step_dir.relative_to(root)
        analysis = root / build_dir(step_dir.parent.name, step_dir.name) / ANALYSIS
        if not analysis.is_file():
            report.append(f"{rel}: skipped, no {analysis.relative_to(root)}")
            continue
        cutoff = analysis.stat().st_mtime - SLACK
        behind = [path for path in rendered(step_dir) if path.stat().st_mtime < cutoff]
        stale.extend(
            Stale(path.relative_to(root), analysis.relative_to(root), cutoff - path.stat().st_mtime)
            for path in behind
        )
        report.append(
            f"{rel}: {len(rendered(step_dir))} rendered, {len(behind)} older than the analysis"
        )
    return stale, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--quiet", action="store_true", help="print only the failures")
    args = parser.parse_args(argv)

    stale, report = check(args.root)
    if not args.quiet:
        for line in report:
            print(line)
    if stale:
        print(f"\n{len(stale)} figure(s) older than the analysis they are drawn from:")
        for item in stale:
            print(f"  {item}")
        print("\nRe-export, then re-render, then commit both. For iteration 2 step 2:")
        print("  uv run python tools/export_it2_step2_analysis.py")
        print("  uv run python tools/render_it2_step2_figures.py")
        print("  uv run python tools/render_it2_step2_results.py")
        print("  uv run python tools/render_it2_phase_block.py")
        return 1
    if not args.quiet:
        print("figures: fresh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
