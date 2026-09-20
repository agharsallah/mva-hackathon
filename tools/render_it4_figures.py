#!/usr/bin/env python3
"""Render iteration 4's figures from the run's JSON — never from a database.

Four figures, all of them built only from files the workflow already wrote, so a figure can
never quote a number the report does not:

1. **score histogram, one per lane** — the shape of that model's scores, with the confirmed
   pair's two alleles marked. A lane that could not score one half says so on the figure.
2. **agreement heat map** — Spearman ρ (rank correlation) between every pair of lanes, with
   the shared-allele count in each cell. A cell with too few shared alleles is left blank
   rather than filled with a zero.
3. **confirmed-rank bar chart** — where each lane put the confirmed pair, beside the two RRF
   consensus ranks (catalogue-free and all lanes).
4. **coverage matrix** — lanes down, consequence classes across, share scored in each cell.
   The empty column is the point: every MVP lane is blind to the same classes, and the
   confirmed pair has an allele in one of them.

Inputs: ``build/it4/merged.json`` and ``build/it4/reports/<lane>.json``.
Outputs: ``figures/it4/<slug>.svg`` and ``<slug>.html``. Every figure carries a Plotly
``layout.meta`` block naming this script, the source file and the run id.

Usage::

    uv run python tools/render_it4_figures.py
    uv run python tools/render_it4_figures.py --fixtures   # smoke test, writes under build/

``--fixtures`` runs the whole workflow over ``fixtures/it4/`` into
``build/it4/figures-fixture/`` and renders from that. Those figures are synthetic and must
never be committed — that is exactly why they land under ``build/``.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import plotly.graph_objects as go

from it4_figure_builders import coverage_matrix, heat_map, histogram, rank_bars
from mva.render.theme import (
    install_template,
)

SCRIPT = "tools/render_it4_figures.py"
DEFAULT_MERGED = Path("build/it4/merged.json")
DEFAULT_REPORTS = Path("build/it4/reports")
DEFAULT_OUT = Path("figures/it4")
FIXTURE_ROOT = Path("build/it4/figures-fixture")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--merged", type=Path, default=DEFAULT_MERGED)
    parser.add_argument("--reports", type=Path, default=DEFAULT_REPORTS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--fixtures",
        action="store_true",
        help="run the workflow on fixtures/it4 and render into build/it4/figures-fixture/",
    )
    parser.add_argument(
        "--config", default="src/mva/zoo/zoo.example.toml", help="config for --fixtures"
    )
    return parser.parse_args()


# ── figures ──────────────────────────────────────────────────────────────────────────────


def write(figure: go.Figure, out_dir: Path, slug: str) -> list[Path]:
    """Write one figure as SVG (for the report) and HTML (for the dashboard)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    svg = out_dir / f"{slug}.svg"
    try:
        figure.write_image(svg, format="svg", width=1000, height=figure.layout.height or 420)
        written.append(svg)
    except Exception as error:  # kaleido is optional; report the miss and keep the HTML
        print(f"  {slug}.svg not written ({type(error).__name__}: {error})")
    html = out_dir / f"{slug}.html"
    figure.write_html(html, include_plotlyjs="cdn", full_html=True)
    written.append(html)
    return written


def render_all(
    merged: Mapping[str, Any], reports: Sequence[Mapping[str, Any]], out_dir: Path
) -> int:
    """Every figure of one run. Returns how many files were written."""
    install_template()
    written = 0
    run_id = str(merged.get("run_id", ""))
    for report in reports:
        figure, caption, legend = histogram(report, run_id)
        slug = f"score-histogram-{report.get('model', 'model')}"
        written += len(write(figure, out_dir, slug))
        print(f"{slug:<34} {caption}\n  > {legend}")
    for builder, slug in ((heat_map, "agreement-matrix"), (rank_bars, "confirmed-rank")):
        figure, caption, legend = builder(merged)
        written += len(write(figure, out_dir, slug))
        print(f"{slug:<34} {caption}\n  > {legend}")
    if reports:
        figure, caption, legend = coverage_matrix(reports, run_id)
        written += len(write(figure, out_dir, "coverage-matrix"))
        print(f"{'coverage-matrix':<34} {caption}\n  > {legend}")
    return written


def load_reports(directory: Path) -> list[Mapping[str, Any]]:
    return [
        json.loads(path.read_text(encoding="utf-8")) for path in sorted(directory.glob("*.json"))
    ]


def main() -> None:
    args = parse_args()
    merged_path, reports_dir, out_dir = args.merged, args.reports, args.out_dir
    if args.fixtures:
        from mva.zoo.workflow import run
        from mva.zoo.workflow_types import Deps

        root = FIXTURE_ROOT
        run(
            args.config,
            deps=Deps.fixtures("fixtures/it4"),
            out_dir=root / "build",
            reports_dir=root / "reports-md",
            docs_runs_dir=root / "runs",
            merged_path=root / "report.md",
        )
        merged_path = root / "build" / "merged.json"
        reports_dir = root / "build" / "reports"
        out_dir = root / "figures"
        print(f"fixture run rendered into {out_dir} (synthetic; never commit these)")
    if not merged_path.is_file():
        raise SystemExit(f"no merged JSON at {merged_path}; run `mva-zoo run` first")
    merged = json.loads(merged_path.read_text(encoding="utf-8"))
    count = render_all(merged, load_reports(reports_dir), out_dir)
    print(f"{count} files written to {out_dir}")


if __name__ == "__main__":
    main()
