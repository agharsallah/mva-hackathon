#!/usr/bin/env python3
"""Iteration 5, route R4: the decision analysis in four figures.

(a) ``r4-decision-tree`` - world-states as a tree (one level per uncertain variable, edge =
    value and prior weight) ending in the best action in that state and its utility.
(b) ``r4-voi-curve`` - EVPI and each test's EVSI against one prior, one panel per variable,
    the exact flip points (where the best action changes) marked and the segments named.
(c) ``r4-heatmap`` - the top candidates x world-states, heuristic utility in each cell,
    expected utility in the last column.
(d) ``r4-tornado`` - the tornado over the config's parameter ranges (metric from the config).

**Source.** ``<work>/decision_summary.json``, written by ``tools/it5_decision.py``. Nothing
is computed here that the summary does not hold, except layout.

    uv run python tools/render_it5_r4.py --work ressources/track2/it5 --out figures/it5
    uv run python tools/render_it5_r4.py            # the dry run (build/, never committed)

Writes ``<out>/r4-<name>.{svg,html}`` + ``.provenance.json`` and PNG previews under
``--preview`` (default ``build/it5/r4/preview``); prints each figure's legend line.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from mva.drugs import provenance
from mva.render.theme import (
    BAD,
    DECISION,
    GOOD,
    MACHINE,
    RAW,
    install_template,
    legend_line,
)

DRY = Path("build/it5/r4/dryrun")
NOTE = "triage heuristic, not a calibrated posterior"
DASHES = ("solid", "dashdot", "dot")


def _write(
    fig: go.Figure, args: argparse.Namespace, name: str, size: tuple[int, int], legend: str
) -> None:
    out: Path = args.out
    preview: Path = args.preview
    out.mkdir(parents=True, exist_ok=True)
    preview.mkdir(parents=True, exist_ok=True)
    svg = out / f"r4-{name}.svg"
    fig.write_image(svg, format="svg", width=size[0], height=size[1])
    fig.write_image(preview / f"{name}.png", format="png", width=size[0], height=size[1], scale=2)
    fig.write_html(svg.with_suffix(".html"), include_plotlyjs="cdn", full_html=True)
    source = args.work / "decision_summary.json"
    manifest = {
        **provenance.envelope(svg.stem, "tools/render_it5_r4.py"),
        "inputs": [
            {"path": provenance.repo_relative(source), "sha256": provenance.digest(source)[0]}
        ],
        "entry": (
            "docs/iteration5/step-1/methodology/"
            "161-the-decision-and-what-the-next-measurement-is-worth.md"
        ),
        "legend": legend,
        "wording": NOTE,
        "patient_data": "none: drug names, state labels, weights and utilities; no position",
    }
    provenance.write(manifest, svg.with_suffix(".provenance.json"))
    print(f"wrote {provenance.repo_relative(svg)}\n  {legend}\n")


def _box(fig: go.Figure, x: float, y: float, text: str, hue: Any) -> None:
    fig.add_annotation(
        x=x,
        y=y,
        text=text,
        showarrow=False,
        bgcolor=hue.fill,
        bordercolor=hue.line,
        borderwidth=1.5,
        borderpad=6,
        font=dict(size=12),
    )


def tree(summary: dict[str, Any], args: argparse.Namespace) -> None:
    states = summary["states"]
    names = list(summary["priors"])
    leaves = [[pair.split("=", 1) for pair in s["state"].split(" & ")] for s in states]
    ys = {i: len(states) - 1 - i for i in range(len(states))}
    fig = go.Figure()

    def node_y(prefix: tuple[tuple[str, str], ...]) -> float:
        kids = [
            ys[i]
            for i, leaf in enumerate(leaves)
            if tuple(map(tuple, leaf[: len(prefix)])) == prefix
        ]
        return sum(kids) / len(kids)

    prefixes: list[tuple[tuple[str, str], ...]] = [()]
    for level in range(1, len(names) + 1):
        prefixes += list(dict.fromkeys(tuple(map(tuple, leaf[:level])) for leaf in leaves))
    for prefix in prefixes[1:]:
        parent, (var, val) = prefix[:-1], prefix[-1]
        x0 = len(parent)
        x1 = len(prefix) + (0.45 if len(prefix) == len(names) else 0)
        y0, y1 = node_y(parent), node_y(prefix)
        fig.add_shape(
            type="line", x0=x0, y0=y0, x1=x1, y1=y1, line=dict(color=MACHINE.line, width=1.5)
        )
        weight = summary["priors"][var][val]
        fig.add_annotation(
            x=(x0 + x1) / 2,
            y=(y0 + y1) / 2,
            text=f"{val} ({weight:.2f})",
            showarrow=False,
            yshift=9,
            font=dict(size=11, color=MACHINE.line),
        )
    for level, var in enumerate(names):
        for prefix in (p for p in prefixes if len(p) == level):
            _box(fig, level, node_y(prefix), f"<b>{var}</b>?", DECISION if level == 0 else RAW)
    for i, s in enumerate(states):
        hue = BAD if s["best"] == summary["baseline"] or s["utility"] <= 0 else GOOD
        tie = f"<br>(tie: {', '.join(s.get('tied', []))})" if s.get("tied") else ""
        _box(fig, len(names) + 0.45, ys[i], f"{s['best']}{tie}<br>u = {s['utility']:.3f}", hue)
    best = summary["best"]
    voi = " · ".join(
        f"{v['kind'].upper()} {'' if v['kind'] == 'evpi' else v['target'] + ' '}{v['value']:.3f}"
        for v in summary["voi"]
    )
    tie = f", tied with {', '.join(best.get('tied', []))}" if best.get("tied") else ""
    head = f"decide now: <b>{best['action']}</b>{tie} (EU {best['expected_utility']:.3f}) · {NOTE}"
    head += f"<br>{voi}"
    fig.update_layout(
        title=dict(text=f"Which candidate in which world-state<br><sup>{head}</sup>"),
        showlegend=False,
        margin=dict(l=40, r=40, t=110, b=30),
    )
    fig.update_xaxes(visible=False, range=[-0.4, len(names) + 0.9])
    fig.update_yaxes(visible=False, range=[-0.7, len(states) - 0.3])
    legend = legend_line(
        extra=(
            "yellow = the first uncertain fact, purple = further facts about the child's alleles, "
            "edge = value (prior weight), green = the best drug in that state, red = only the "
            "baseline (defer) is best"
        )
    )
    _write(fig, args, "decision-tree", (1100, 140 + 110 * len(states)), legend)


def voi_curve(summary: dict[str, Any], args: argparse.Namespace) -> None:
    variables = list(summary["priors"])
    fig = make_subplots(
        rows=1,
        cols=len(variables),
        shared_yaxes=True,
        horizontal_spacing=0.06,
        subplot_titles=[f"P({v}={next(iter(summary['priors'][v]))})" for v in variables],
    )
    tests = {v["target"]: v for v in summary["voi"] if v["kind"] == "evsi"}
    for col, var in enumerate(variables, start=1):
        pts = [p for p in summary["sweep"] if p["variable"] == var]
        xs = [p["p"] for p in pts]
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=[p["evpi"] for p in pts],
                name="EVPI",
                legendgroup="evpi",
                showlegend=col == 1,
                line=dict(color=MACHINE.line, width=2.5),
            ),
            row=1,
            col=col,
        )
        for name, test in tests.items():
            dash = DASHES[list(tests).index(name) % len(DASHES)]
            fig.add_trace(
                go.Scatter(
                    x=xs,
                    y=[p[f"evsi:{name}"] for p in pts],
                    name=f"EVSI {name} (tests {test['variable']})",
                    legendgroup=name,
                    showlegend=col == 1,
                    line=dict(color=GOOD.line, dash=dash, width=2),
                ),
                row=1,
                col=col,
            )
        segs = [f for f in summary["flips"] if f["variable"] == var]
        for seg in segs:
            if seg["start"] > 0:
                fig.add_vline(
                    x=seg["start"],
                    line=dict(color=DECISION.line, dash="dash", width=1.5),
                    row=1,
                    col=col,
                )
            fig.add_annotation(
                x=(seg["start"] + seg["end"]) / 2,
                y=1.0,
                yref="y domain",
                xref=f"x{col if col > 1 else ''}",
                text=seg["action"],
                showarrow=False,
                font=dict(size=10, color=DECISION.line),
                textangle=-90 if seg["end"] - seg["start"] < 0.2 else 0,
                yanchor="top",
            )
        prior = next(iter(summary["priors"][var].values()))
        fig.add_vline(x=prior, line=dict(color=RAW.line, dash="dot", width=2), row=1, col=col)
        fig.update_xaxes(range=[0, 1], title_text="prior weight", row=1, col=col)
    fig.update_yaxes(title_text="value of information (utility units)", row=1, col=1)
    fig.update_layout(
        title=dict(text=f"What a test is worth, and where the choice flips<br><sup>{NOTE}</sup>"),
        margin=dict(t=90, b=110),
        legend=dict(orientation="h", yanchor="top", y=-0.2, x=0),
    )
    legend = legend_line(
        extra=(
            "blue = EVPI (upper bound), green = EVSI of a named test (one dash style per test, "
            "the legend names the variable it measures), yellow dashed = exact flip point "
            "(segment labels = best action), purple dotted = the configured prior"
        )
    )
    _write(fig, args, "voi-curve", (560 * len(variables) + 120, 520), legend)


def heatmap(summary: dict[str, Any], args: argparse.Namespace) -> None:
    rows = summary["utilities"][: args.top]
    states = [s["state"] for s in summary["states"]]
    cols = [*states, "expected utility"]
    z = [[r[f"u[{s}]"] for s in states] + [r["expected_utility"] for _ in [0]] for r in rows]
    labels = []
    for r in rows:
        tag = " [control failed]" if "failed" in r["controls"] else ""
        labels.append(f"{r['action']} · {r['safety_class']}{tag}")
    short = [" · ".join(pair.split("=", 1)[-1] for pair in c.split(" & ")) for c in cols]
    axis = " · ".join(summary["priors"])
    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=short,
            y=labels,
            colorscale=[[0, "#ffffff"], [1, GOOD.line]],
            zmin=0,
            zmax=max(1e-9, *(max(r) for r in z)),
            text=[[f"{v:.2f}" for v in r] for r in z],
            texttemplate="%{text}",
            colorbar=dict(title="utility"),
        )
    )
    for s, state in enumerate(summary["states"]):
        names = [r["action"] for r in rows]
        for best in (state["best"], *state.get("tied", [])):
            if best in names:
                y = names.index(best)
                fig.add_shape(type="rect", x0=s - 0.5, x1=s + 0.5, y0=y - 0.5, y1=y + 0.5,
                              line=dict(color=DECISION.line, width=3))  # fmt: skip
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title_text=f"world-state ({axis}) · expected utility", side="bottom")
    fig.update_layout(
        title=dict(text=f"Top {len(rows)} actions x world-states<br><sup>{NOTE}</sup>"),
        margin=dict(l=320, t=90, b=90),
    )
    legend = legend_line(
        extra=(
            "white to green = heuristic utility 0 to max, yellow outline = the best action in that "
            "state (every tied action outlined), row label = action · per-child safety class"
        )
    )
    _write(fig, args, "heatmap", (1180, 160 + 34 * len(rows)), legend)


def tornado(summary: dict[str, Any], args: argparse.Namespace) -> None:
    rows = list(reversed(summary["tornado"]))
    if not rows:
        return
    metric = rows[0]["metric"]
    base = min(min(r["metric_low"], r["metric_high"]) for r in rows)
    fig = go.Figure()
    for r in rows:
        lo, hi = sorted((r["metric_low"], r["metric_high"]))
        hue = BAD if r["flips"] else MACHINE
        fig.add_trace(
            go.Bar(
                y=[f"{r['param']} [{r['low']}–{r['high']}]"],
                x=[max(hi - lo, 1e-6)],
                base=[lo],
                orientation="h",
                marker=dict(color=hue.fill, line=dict(color=hue.line, width=1)),
                showlegend=False,
                hovertext=f"best {r['best_low']} → {r['best_high']}",
            )
        )
    fig.update_layout(
        title=dict(text=f"Tornado: {metric} over each parameter's range<br><sup>{NOTE}</sup>"),
        margin=dict(l=420, t=90),
        xaxis_title=metric,
        barmode="overlay",
    )
    fig.update_xaxes(rangemode="tozero" if base >= 0 else "normal")
    legend = legend_line(
        extra=(
            "blue bar = the metric's range as one parameter moves low→high, the rest held; red = "
            "the best action changes within that range"
        )
    )
    _write(fig, args, "tornado", (1100, 140 + 32 * len(rows)), legend)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    parser.add_argument("--work", type=Path, default=DRY, help="folder with decision_summary.json")
    parser.add_argument(
        "--out", type=Path, default=None, help="figure folder (default <work>/figures)"
    )
    parser.add_argument("--top", type=int, default=15, help="heatmap rows")
    parser.add_argument(
        "--preview",
        type=Path,
        default=Path("build/it5/r4/preview"),
        help="PNG previews (kept under build/, never committed)",
    )
    args = parser.parse_args()
    args.out = args.out or args.work / "figures"
    install_template()
    summary = json.loads((args.work / "decision_summary.json").read_text(encoding="utf-8"))
    tree(summary, args)
    voi_curve(summary, args)
    heatmap(summary, args)
    tornado(summary, args)


if __name__ == "__main__":
    main()
