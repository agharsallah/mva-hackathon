#!/usr/bin/env python3
"""Render the transfer figure: what each iteration-5 route cost to move to a second disease.

One figure, two panels, both built only from ``transfer_summary.tsv`` (so it cannot quote a
number the table does not hold):

* **left** — lines a person had to write per route, split into configuration (a new case
  card), portability code (a constant that became a parameter) and new capability (something
  the first case never had). The bar at the bottom is iteration 4's transfer for the same
  disease — a 378-line purpose-built driver (entry 156) — as the yardstick being beaten.
* **right** — per route: did the second case's positive control pass, did the *first* case's
  committed tables stay byte-identical, and how many rows the transferred run wrote.

    uv run python tools/render_it5_s1.py

Inputs ``ressources/track2/it5/transfer/transfer_summary.tsv``; outputs
``figures/it5/s1-transfer.{svg,html}`` and a ``.provenance.json`` beside them.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from mva.drugs import provenance
from mva.render.theme import BAD, DECISION, GOOD, MACHINE, MUTED, RAW, install_template, legend_line

SCRIPT = "tools/render_it5_s1.py"
ENTRY = "docs/iteration5/step-1/methodology/162-the-three-routes-on-bloom-syndrome.md"
TABLE = Path("ressources/track2/it5/transfer/transfer_summary.tsv")
OUT = Path("figures/it5")

#: The yardstick: iteration 4's transfer of its chain to the same second disease.
BASELINE_LABEL = "iteration 4 (entry 156)<br>purpose-built driver"
BASELINE_LINES = 378
BASELINE_SOURCE = "tools/transfer_it4.py, docs/iteration4/step-11 (entry 156)"


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _int(value: str) -> int:
    return int(value or 0)


def cost_panel(figure: go.Figure, rows: list[dict[str, str]]) -> None:
    labels = [*[f"{r['route']}<br>{r['name'][:34]}" for r in rows][::-1], BASELINE_LABEL]
    series = (
        ("configuration (a new case card)", [_int(r["config_lines"]) for r in rows][::-1], RAW),
        (
            "portability code + refactor (constant → parameter)",
            [_int(r["portability_and_refactor_lines"]) for r in rows][::-1],
            DECISION,
        ),
        (
            "new capability (not a transfer cost)",
            [_int(r["new_capability_lines_added"]) for r in rows][::-1],
            MACHINE,
        ),
    )
    for name, values, hue in series:
        figure.add_trace(
            go.Bar(
                y=labels,
                x=[*values, 0],
                name=name,
                orientation="h",
                marker={"color": hue.fill, "line": {"color": hue.line, "width": 1.4}},
                hovertemplate="%{y}<br>" + name + ": %{x} lines<extra></extra>",
            ),
            row=1,
            col=1,
        )
    figure.add_trace(
        go.Bar(
            y=labels,
            x=[0] * len(rows) + [BASELINE_LINES],
            name=f"the yardstick: {BASELINE_LINES}-line one-off driver",
            orientation="h",
            marker={"color": BAD.fill, "line": {"color": BAD.line, "width": 1.4}},
            hovertemplate="%{y}: %{x} lines<extra></extra>",
        ),
        row=1,
        col=1,
    )


def status_panel(figure: go.Figure, rows: list[dict[str, str]]) -> None:
    columns = ["positive control<br>(second case)", "first case<br>byte-identical", "rows written"]
    labels = [*[f"{r['route']}<br>{r['name'][:34]}" for r in rows][::-1], BASELINE_LABEL]
    for index, row in enumerate(rows[::-1]):
        control = row["positive_control"]
        passed = row["positive_control_passed"] == "yes"
        identical = row["first_case_outputs_identical"] == "yes"
        written = sum(int(p.split("=")[1]) for p in row["transfer_output_rows"].split(";") if p)
        cells = (
            (columns[0], GOOD if passed else BAD, control),
            (columns[1], GOOD if identical else BAD, row["first_case_outputs_identical"]),
            (columns[2], MACHINE, f"{written} rows"),
        )
        for column, hue, text in cells:
            figure.add_trace(
                go.Scatter(
                    x=[column],
                    y=[labels[index]],
                    mode="markers+text",
                    marker={
                        "size": 46,
                        "color": hue.fill,
                        "line": {"color": hue.line, "width": 1.6},
                        "symbol": "square",
                    },
                    text=[text if column == columns[2] else ("pass" if hue is GOOD else "fail")],
                    textposition="middle center",
                    textfont={"size": 11},
                    hovertext=[text],
                    hoverinfo="text",
                    showlegend=False,
                ),
                row=1,
                col=2,
            )
    figure.add_trace(
        go.Scatter(
            x=columns,
            y=[BASELINE_LABEL] * 3,
            mode="markers+text",
            marker={
                "size": 46,
                "color": MUTED.fill,
                "line": {"color": MUTED.line, "width": 1.4},
                "symbol": "square",
            },
            text=["n/a", "n/a", "n/a"],
            textposition="middle center",
            textfont={"size": 11},
            hovertext=["the yardstick is a line count, not a run of these routes"] * 3,
            hoverinfo="text",
            showlegend=False,
        ),
        row=1,
        col=2,
    )


def build(rows: list[dict[str, str]]) -> tuple[go.Figure, str]:
    figure = make_subplots(
        rows=1,
        cols=2,
        column_widths=[0.62, 0.38],
        shared_yaxes=True,
        horizontal_spacing=0.06,
        subplot_titles=(
            "lines a person wrote to add the second disease",
            "did it work, and did the first case survive?",
        ),
    )
    cost_panel(figure, rows)
    status_panel(figure, rows)
    figure.update_layout(
        barmode="stack",
        title=(
            "Transferring iteration 5's routes to a second disease "
            "(BUB1B / MVA → BLM / Bloom syndrome)"
        ),
        height=420,
        legend={"orientation": "h", "y": -0.18},
        meta={"script": SCRIPT, "source": TABLE.as_posix()},
    )
    figure.update_xaxes(title="lines", row=1, col=1)
    figure.update_xaxes(showgrid=False, row=1, col=2)
    figure.update_yaxes(showgrid=False, row=1, col=2)
    legend = legend_line(
        RAW,
        DECISION,
        MACHINE,
        GOOD,
        BAD,
        extra=(
            "purple = configuration (a case card), yellow = code that turned a constant into a "
            "parameter, blue = a new capability that is not a transfer cost, green = a check "
            "that passed, red = the one-off driver this replaces"
        ),
    )
    return figure, legend


def write(figure: go.Figure, out_dir: Path, slug: str, legend: str, source: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    svg = out_dir / f"{slug}.svg"
    try:
        figure.write_image(svg, format="svg", width=1150, height=figure.layout.height or 420)
    except Exception as error:  # kaleido is optional; the HTML still carries the figure
        print(f"  {slug}.svg not written ({type(error).__name__}: {error})")
    figure.write_html(svg.with_suffix(".html"), include_plotlyjs="cdn", full_html=True)
    manifest: dict[str, Any] = provenance.envelope(slug, SCRIPT)
    manifest.update(
        {
            "entry": ENTRY,
            "inputs": [
                {"path": source.as_posix(), "sha256": provenance.digest(source)[0]},
                {"name": "yardstick", "role": BASELINE_SOURCE, "lines": BASELINE_LINES},
            ],
            "legend": legend,
            "assumptions": (
                "a line count is a proxy for effort; the two counts are comparable only in "
                "that both are lines a person had to write for the same second disease"
            ),
            "patient_data": "none: line counts, row counts and pass/fail flags",
            "sources": {"genomic": "none", "clinical": "none"},
        }
    )
    provenance.write(manifest, svg.with_suffix(".provenance.json"))
    print(f"wrote {svg}\n  > {legend}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--table", type=Path, default=TABLE)
    parser.add_argument("--out-dir", type=Path, default=OUT)
    args = parser.parse_args()
    install_template()
    rows = read_tsv(args.table)
    figure, legend = build(rows)
    write(figure, args.out_dir, "s1-transfer", legend, args.table)
    print(json.dumps({r["route"]: r["config_lines"] for r in rows}))


if __name__ == "__main__":
    main()
