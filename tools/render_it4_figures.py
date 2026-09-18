#!/usr/bin/env python3
"""Render iteration 4's figures from the run's JSON — never from a database.

Three figures, all of them built only from files the workflow already wrote, so a figure can
never quote a number the report does not:

1. **score histogram, one per lane** — the shape of that model's scores, with the confirmed
   pair's two alleles marked. A lane that could not score one half says so on the figure.
2. **agreement heat map** — Spearman ρ (rank correlation) between every pair of lanes, with
   the shared-allele count in each cell. A cell with too few shared alleles is left blank
   rather than filled with a zero.
3. **confirmed-rank bar chart** — where each lane put the confirmed pair, beside the two RRF
   consensus ranks (catalogue-free and all lanes).

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

from mva.render.theme import (
    DECISION,
    GOOD,
    GRID,
    MACHINE,
    MUTED,
    SUBTLE_INK,
    install_template,
    legend_line,
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


def histogram(report: Mapping[str, Any], run_id: str) -> tuple[go.Figure, str, str]:
    """One lane's score distribution, with the confirmed pair's two alleles marked."""
    dist = report["sections"]["distribution"]
    model = report.get("model", "model")
    centres, counts, width = _bars(dist)
    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=centres,
            y=counts,
            width=width,
            marker_color=MACHINE.fill,
            marker_line=dict(color=MACHINE.line, width=1),
            name=f"{model} scores",
            hovertemplate="score %{x:.3f}<br>%{y} alleles<extra></extra>",
        )
    )
    missing: list[str] = []
    for mark in dist.get("marks", []):
        if mark.get("score") is None:
            missing.append(str(mark.get("role") or "half"))
            continue
        figure.add_vline(
            x=float(mark["score"]),
            line=dict(color=GOOD.line, width=2, dash="dash"),
            annotation_text=f"{mark.get('role')} ({_pct(mark.get('percentile'))})",
            annotation_position="top",
            annotation_font=dict(color=GOOD.line, size=11),
        )
    if missing:
        figure.add_annotation(
            text=f"not scored by this lane: {', '.join(missing)}",
            xref="paper",
            yref="paper",
            x=0.99,
            y=0.98,
            showarrow=False,
            font=dict(color=SUBTLE_INK, size=11),
            align="right",
        )
    figure.update_layout(
        title_text=f"{model} — score distribution ({dist.get('n', 0)} alleles)",
        xaxis_title="model score (higher = more damaging, as this model defines it)",
        yaxis_title="alleles",
        height=420,
        showlegend=False,
        bargap=0.02,
        meta=_meta(run_id, source=f"results.it4_model_reports ({model})", figure="score-histogram"),
    )
    caption = (
        f"Where {model}'s scores fall across the record set, and where the confirmed pair's "
        f"two alleles sit in it."
    )
    return figure, caption, legend_line(MACHINE, GOOD, extra="dashed line = a confirmed allele")


def heat_map(merged: Mapping[str, Any]) -> tuple[go.Figure, str, str]:
    """Spearman ρ between lanes, with n printed in every cell."""
    agreement = merged.get("agreement", {})
    models = list(agreement.get("models", []))
    cells = {(c["a"], c["b"]): c for c in agreement.get("cells", [])}
    z = [[_rho(cells.get((a, b))) for b in models] for a in models]
    text = [[_cell_text(cells.get((a, b))) for b in models] for a in models]
    figure = go.Figure(
        go.Heatmap(
            z=z,
            x=models,
            y=models,
            text=text,
            texttemplate="%{text}",
            zmin=-1,
            zmax=1,
            colorscale=[[0.0, "#c0392b"], [0.5, "#ffffff"], [1.0, "#3f8f47"]],
            colorbar=dict(title="Spearman ρ"),
            hovertemplate="%{y} vs %{x}<br>%{text}<extra></extra>",
        )
    )
    figure.update_layout(
        title_text="Do the lanes order the alleles the same way?",
        height=460,
        meta=_meta(
            merged.get("run_id", ""), source="warehouse.allele_scores", figure="agreement-matrix"
        ),
    )
    caption = (
        "Spearman ρ over the alleles both lanes scored, with the shared-allele count beneath "
        "it. A blank cell had too few shared alleles or no variance — an absent number, not a "
        "zero."
    )
    return (
        figure,
        caption,
        legend_line(GOOD, MUTED, extra="red = the lanes disagree; n = shared alleles"),
    )


def rank_bars(merged: Mapping[str, Any]) -> tuple[go.Figure, str, str]:
    """Where every lane put the confirmed pair, beside the two consensus ranks."""
    labels: list[str] = []
    values: list[float] = []
    colours: list[str] = []
    notes: list[str] = []
    for lane in merged.get("lanes", []):
        confirmed = lane.get("confirmed") or {}
        labels.append(lane["model"])
        rank = confirmed.get("rank")
        values.append(float(rank) if rank else 0.0)
        colours.append(DECISION.fill if lane.get("catalogue_adjacent") else MACHINE.fill)
        notes.append(
            f"rank {rank} of {confirmed.get('n_ranked', 0)}"
            if rank
            else "no opinion (a half was unscored)"
        )
    for label, key in (("RRF catalogue-free", "catalogue_free"), ("RRF all lanes", "all_lanes")):
        block = merged.get("consensus", {}).get(key, {})
        labels.append(label)
        rank = block.get("rank")
        values.append(float(rank) if rank else 0.0)
        colours.append(GOOD.fill)
        notes.append(f"rank {rank} of {block.get('n_pairs', 0)}" if rank else "not ranked")
    figure = go.Figure(
        go.Bar(
            x=labels,
            y=values,
            marker_color=colours,
            marker_line=dict(color=SUBTLE_INK, width=1),
            text=notes,
            textposition="outside",
            hovertemplate="%{x}<br>%{text}<extra></extra>",
        )
    )
    figure.update_layout(
        title_text="The confirmed pair's rank, per lane and fused",
        yaxis_title="rank among biallelic pairs (1 = best)",
        yaxis=dict(autorange="reversed", gridcolor=GRID),
        height=440,
        showlegend=False,
        meta=_meta(
            merged.get("run_id", ""),
            source="results.it4_model_ranks",
            figure="confirmed-rank",
        ),
    )
    caption = (
        "One bar per lane plus the two fused ranks. A bar at zero means that lane could not "
        "score both halves of the pair and is recorded as having no opinion."
    )
    return (
        figure,
        caption,
        legend_line(
            MACHINE, DECISION, GOOD, extra="yellow = a catalogue-adjacent lane; green = the fusion"
        ),
    )


# ── helpers ──────────────────────────────────────────────────────────────────────────────


def _meta(run_id: str, *, source: str, figure: str) -> dict[str, str]:
    return {"script": SCRIPT, "source": source, "run_id": run_id, "figure": figure}


def _bars(dist: Mapping[str, Any]) -> tuple[list[float], list[int], float]:
    """Bin centres, counts and bar width, read straight out of the stored histogram.

    The report JSON stores the binned counts rather than the 40,000 raw scores, so this
    figure and the report's section 3 can never disagree about the same distribution.
    """
    block = dist.get("histogram") or {}
    edges = [float(e) for e in block.get("edges", [])]
    counts = [int(c) for c in block.get("counts", [])]
    if len(edges) < 2 or not counts:
        return ([], [], 0.0)
    width = (edges[-1] - edges[0]) / max(len(counts), 1)
    centres = [(edges[i] + edges[i + 1]) / 2 for i in range(len(counts))]
    return (centres, counts, width or 0.01)


def _rho(cell: Mapping[str, Any] | None) -> float | None:
    return None if cell is None or cell.get("rho") is None else float(cell["rho"])


def _cell_text(cell: Mapping[str, Any] | None) -> str:
    if cell is None:
        return ""
    rho, n = cell.get("rho"), cell.get("n", 0)
    return f"n={n}" if rho is None else f"{float(rho):+.2f}<br>n={n}"


def _pct(value: Any) -> str:
    return "—" if value is None else f"{float(value):.1f} %"


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
        paths = write(figure, out_dir, slug)
        written += len(paths)
        print(f"{slug:<34} {caption}")
        print(f"  > {legend}")
    for builder, slug in ((heat_map, "agreement-matrix"), (rank_bars, "confirmed-rank")):
        figure, caption, legend = builder(merged)
        paths = write(figure, out_dir, slug)
        written += len(paths)
        print(f"{slug:<34} {caption}")
        print(f"  > {legend}")
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
