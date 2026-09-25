#!/usr/bin/env python3
"""Step 10, S2: convergence and checks in three figures.

(a) ``step10-s2-upset`` - which generators name which drugs: an UpSet view (bars = drugs in
    exactly that combination of generators, dots = the combination), the combinations of
    two or more generators labelled with their drugs.
(b) ``step10-s2-null`` - the permutation null of "drugs named by >= k generators" for every
    test in ``convergence.json`` (the primary, the registered exclusion, each sensitivity),
    the observed count and the null's 95th percentile.
(c) ``step10-s2-checks`` - every converging drug x (the generators that name it, K1, K2, K3,
    survivor) plus every drug within each generator's top ``--show-top``, coloured by verdict.

**Sources.** ``<candidates>.tsv`` and ``<work>/convergence.json``, both written by
``tools/converge.py run``; the generator tables under ``--generators-dir``. Entry 155.

    uv run python tools/render_step10_s2.py
    uv run python tools/render_step10_s2.py --candidates build/it4/track2-s2/dry/candidates.tsv \\
        --work build/it4/track2-s2/dry --out build/it4/track2-s2/dry/figures   # the dry run

Outputs ``<out>/step10-s2-{upset,null,checks}.{svg,html}`` plus one ``.provenance.json``
each, a PNG preview under ``<work>/preview``, and prints each figure's legend line.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from collections import Counter
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from mva.drugs import provenance
from mva.render.theme import BAD, DECISION, GOOD, MACHINE, MUTED, install_template, legend_line

ENTRY = "docs/iteration4/step-10/methodology/155-convergence-and-checks.md"
VERDICT = {"pass": GOOD, "caution": DECISION, "fail": BAD}


def _write(
    fig: go.Figure, args: argparse.Namespace, name: str, size: tuple[int, int], legend: str
) -> None:
    out: Path = args.out
    preview = args.work / "preview"
    out.mkdir(parents=True, exist_ok=True)
    preview.mkdir(parents=True, exist_ok=True)
    svg = out / f"step10-s2-{name}.svg"
    fig.write_image(svg, format="svg", width=size[0], height=size[1])
    fig.write_image(preview / f"{name}.png", format="png", width=size[0], height=size[1], scale=2)
    fig.write_html(svg.with_suffix(".html"), include_plotlyjs="cdn", full_html=True)
    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()
    inputs = [args.candidates, args.work / "convergence.json"]
    manifest = {
        "name": svg.stem,
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "built_by": "tools/render_step10_s2.py",
        "code_version": commit,
        "inputs": [{"path": p.as_posix(), "sha256": provenance.digest(p)[0]} for p in inputs],
        "entry": ENTRY,
        "legend": legend,
        "patient_data": (
            "none on any axis: drug names, generator ids, counts and check verdicts. K2's genome "
            "half is PharmCAT actionability words only (entry 152)"
        ),
    }
    svg.with_suffix(".provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {svg}\n  {legend}\n")


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def upset_figure(
    rows: list[dict[str, str]], generators: list[str], args: argparse.Namespace, k: int
) -> None:
    combos = Counter(r["generators"] for r in rows)
    drugs_by: dict[str, list[str]] = {}
    for r in rows:
        drugs_by.setdefault(r["generators"], []).append(r["drug"].title())
    order = sorted(combos, key=lambda c: (-len(c.split("|")), -combos[c], c))
    sizes = {g: sum(1 for r in rows if g in r["generators"].split("|")) for g in generators}
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, row_heights=[0.62, 0.38], vertical_spacing=0.03
    )
    colours = [GOOD.line if len(c.split("|")) >= k else MACHINE.line for c in order]
    labels = [
        ", ".join(drugs_by[c][:4]) + (" …" if len(drugs_by[c]) > 4 else "")
        if len(c.split("|")) >= k
        else ""
        for c in order
    ]
    fig.add_bar(
        x=list(range(len(order))),
        y=[combos[c] for c in order],
        marker_color=colours,
        text=[
            f"{combos[c]}<br>{lab}" if lab else str(combos[c])
            for c, lab in zip(order, labels, strict=True)
        ],
        textposition="outside",
        cliponaxis=False,
        showlegend=False,
        row=1,
        col=1,
    )
    for gi, gen in enumerate(generators):
        on = [i for i, c in enumerate(order) if gen in c.split("|")]
        off = [i for i in range(len(order)) if i not in on]
        fig.add_scatter(
            x=off,
            y=[gi] * len(off),
            mode="markers",
            marker=dict(color=MUTED.fill, size=11),
            showlegend=False,
            row=2,
            col=1,
        )
        fig.add_scatter(
            x=on,
            y=[gi] * len(on),
            mode="markers",
            marker=dict(color="#333333", size=11),
            showlegend=False,
            row=2,
            col=1,
        )
    for i, combo in enumerate(order):
        members = [generators.index(g) for g in combo.split("|")]
        if len(members) > 1:
            fig.add_scatter(
                x=[i, i],
                y=[min(members), max(members)],
                mode="lines",
                line=dict(color="#333333", width=2),
                showlegend=False,
                row=2,
                col=1,
            )
    fig.update_yaxes(title_text="drugs in exactly this combination", row=1, col=1)
    fig.update_yaxes(
        tickvals=list(range(len(generators))),
        ticktext=[f"{g} ({sizes[g]})" for g in generators],
        row=2,
        col=1,
    )
    fig.update_xaxes(showticklabels=False, row=2, col=1)
    fig.update_layout(
        title=f"Which generators name which approved drugs ({len(rows)} drugs, k = {k})"
    )
    legend = legend_line(
        GOOD,
        MACHINE,
        MUTED,
        extra="green bar = a combination of ≥ k generators (a converging drug), blue bar = one "
        "generator alone; dark dot = the generator is in the combination, grey dot = it is "
        "not; (n) = drugs the generator lists",
    )
    _write(fig, args, "upset", (1000, 620), legend)


def null_figure(summary: dict[str, Any], args: argparse.Namespace) -> None:
    tests = summary["tests"]
    ncols = min(3, len(tests))
    nrows = -(-len(tests) // ncols)
    titles = [f"{t['label']}<br><sub>{t.get('role', '')}</sub>" for t in tests]
    fig = make_subplots(
        rows=nrows, cols=ncols, subplot_titles=titles, shared_yaxes=True, vertical_spacing=0.22
    )
    for i, test in enumerate(tests):
        row, col = i // ncols + 1, i % ncols + 1
        hist = {int(n): c for n, c in test["histogram"].items()}
        above = [n > test["null_p95"] for n in hist]
        fig.add_bar(
            x=list(hist),
            y=list(hist.values()),
            marker_color=[DECISION.fill if a else MACHINE.fill for a in above],
            marker_line_color=[DECISION.line if a else MACHINE.line for a in above],
            showlegend=False,
            row=row,
            col=col,
        )
        hue = GOOD if test["beats_p95"] else BAD
        fig.add_vline(x=test["observed"], line=dict(color=hue.line, width=3), row=row, col=col)
        axis = "" if i == 0 else str(i + 1)
        fig.add_annotation(
            x=test["observed"],
            y=0.95,
            xref=f"x{axis}",
            yref=f"y{axis} domain",
            text=(
                f" observed {test['observed']}<br> p95 {test['null_p95']:.1f}"
                f"<br> p = {test['p_value']:.3g}"
            ),
            showarrow=False,
            font=dict(color=hue.line, size=11),
            xanchor="left",
            yanchor="top",
            align="left",
        )
        fig.update_xaxes(dtick=1, row=row, col=col)
        if row == nrows:
            fig.update_xaxes(
                title_text=f"drugs named by ≥ {test['k']} generators", row=row, col=col
            )
    for row in range(1, nrows + 1):
        fig.update_yaxes(title_text=f"draws (of {tests[0]['draws']:,})", row=row, col=1)
    fig.update_layout(
        title=(
            "Convergence against a permutation null (each list redrawn from its own universe, "
            f"seed {summary.get('seed', '')})"
        ),
        margin=dict(t=120),
    )
    legend = legend_line(
        MACHINE,
        DECISION,
        extra="bars = the null distribution; yellow bars = null counts above its 95th "
        "percentile (the pre-registered bar the observed count had to reach); solid line = the "
        "observed count, green when it clears the bar, red when it does not; only the first "
        "panel is a verdict input",
    )
    _write(fig, args, "null", (1100, 330 * nrows + 80), legend)


def checks_figure(
    rows: list[dict[str, str]], generators: list[str], args: argparse.Namespace
) -> None:
    top = args.show_top

    def best_rank(r: dict[str, str]) -> int:
        ranks = [int(r[f"rank_{g}"]) for g in generators if r.get(f"rank_{g}")]
        return min(ranks) if ranks else 10**9

    shown = [r for r in rows if r["converging"] == "true" or best_rank(r) <= top]
    shown.sort(key=lambda r: (r["converging"] != "true", r["generators"], best_rank(r)))
    converging = sum(1 for r in shown if r["converging"] == "true")
    note = (
        f"The checks: {converging} converging drug(s), then each generator's top {top} "
        f"({len(shown)} of {len(rows)} drugs; all in candidates.tsv)"
    )
    cols = [*generators, "K1 direction", "K2 safety", "K3 screen", "survivor"]
    z_text: list[list[str]] = []
    colours: list[list[str]] = []
    for r in shown:
        text_row, colour_row = [], []
        for g in generators:
            rank = r.get(f"rank_{g}", "")
            text_row.append(f"#{rank}" if rank else "")
            colour_row.append(MACHINE.fill if rank else "#ffffff")
        for cid in ("k1", "k2", "k3"):
            status = r[f"{cid}_status"]
            text_row.append(status)
            colour_row.append(VERDICT[status].fill if status in VERDICT else MUTED.fill)
        survivor = r["survivor"] == "true"
        text_row.append("yes" if survivor else "no")
        colour_row.append(GOOD.fill if survivor else BAD.fill)
        z_text.append(text_row)
        colours.append(colour_row)
    fig = go.Figure()
    for yi, (text_row, colour_row) in enumerate(zip(z_text, colours, strict=True)):
        for xi, (text, colour) in enumerate(zip(text_row, colour_row, strict=True)):
            fig.add_shape(
                type="rect",
                x0=xi - 0.48,
                x1=xi + 0.48,
                y0=yi - 0.45,
                y1=yi + 0.45,
                fillcolor=colour,
                line=dict(color="#dddddd"),
            )
            fig.add_annotation(x=xi, y=yi, text=text, showarrow=False, font=dict(size=11))
    fig.update_xaxes(
        tickvals=list(range(len(cols))),
        ticktext=cols,
        side="top",
        range=[-0.6, len(cols) - 0.4],
        showgrid=False,
    )
    fig.update_yaxes(
        tickvals=list(range(len(shown))),
        ticktext=[r["drug"].title() for r in shown],
        showgrid=False,
        range=[len(shown) - 0.4, -0.6],
    )
    fig.update_layout(title=note, margin=dict(l=200, t=110))
    legend = legend_line(
        GOOD,
        DECISION,
        BAD,
        MACHINE,
        MUTED,
        extra="generator columns: blue = the generator names the drug (#rank within it); K "
        "columns: green = pass, yellow = caution (kept, reason in the table), red = fail, grey "
        "= not run; survivor: green = converges and fails no check",
    )
    _write(fig, args, "checks", (1000, 160 + 34 * max(len(shown), 4)), legend)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--candidates", type=Path, default=Path("ressources/track2/it4/candidates.tsv")
    )
    parser.add_argument("--work", type=Path, default=Path("build/it4/track2-s2"))
    parser.add_argument("--out", type=Path, default=Path("figures/it4"))
    parser.add_argument("--show-top", type=int, default=10, help="per-generator rows in (c)")
    args = parser.parse_args(argv)
    install_template()
    rows = _read(args.candidates)
    summary = json.loads((args.work / "convergence.json").read_text())
    generators = list(summary["generators"])
    k = int(summary["tests"][0]["k"])
    upset_figure(rows, generators, args, k)
    null_figure(summary, args)
    checks_figure(rows, generators, args)
    # A sanity line for the log: pairwise overlaps, from the same summary the figures used.
    pairs = {
        f"{a}|{b}": summary["pairwise_shared"].get(f"{a}|{b}", 0)
        for a, b in combinations(generators, 2)
    }
    print("pairwise shared:", pairs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
