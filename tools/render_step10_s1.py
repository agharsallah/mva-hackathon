#!/usr/bin/env python3
"""Step 10, S1: the screen-wide PRISM sweep in three figures.

(a) ``step10-s1-volcano`` — every eligible drug's Cliff's delta against its one-sided p,
    in three panels that share one code path: the **positive control** (skin/melanoma lines
    vs the rest, every Launched compound), the rhabdomyosarcoma contrast and the
    aneuploidy contrast. The dashed line is the p a drug needs at rank 1 for q < 0.10; the
    grey band is the negative-control band. The positive control clears the line; neither
    real contrast does.
(b) ``step10-s1-percentiles`` — each drug's delta percentile in one contrast against the
    other. H093 needs a drug in the top-right corner *and* past both lines; the G3 list is
    the two thin strips along the top and right edges.
(c) ``step10-s1-funnel`` — how 6,790 PRISM compounds become 613 testable Launched drugs,
    8 G3-listed drugs and 0 drugs with q < 0.10 in both contrasts.

**Sources.** ``ressources/track2/it4/prism_sweep.tsv`` (+ manifest),
``ressources/track2/it4/generators/prism.tsv``, ``build/it4/track2-s1/controls.json`` and
``build/it4/track2-s1/positive-control-sweep.tsv`` — all written by
``tools/screen_sweep.py run``. Entry 154.

    uv run python tools/render_step10_s1.py

Outputs ``figures/it4/step10-s1-{volcano,percentiles,funnel}.{svg,html}`` plus one
``.provenance.json`` each, and prints each figure's legend line.
"""

from __future__ import annotations

import json
import math
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
import polars as pl
from plotly.subplots import make_subplots
from scipy import stats

from mva.drugs import provenance
from mva.render.theme import BAD, DECISION, GOOD, MACHINE, MUTED, RAW, install_template, legend_line

TABLE = Path("ressources/track2/it4/prism_sweep.tsv")
LIST = Path("ressources/track2/it4/generators/prism.tsv")
BUILD = Path("build/it4/track2-s1")
CONTROLS = BUILD / "controls.json"
POSITIVE = BUILD / "positive-control-sweep.tsv"
OUT = Path("figures/it4")
PREVIEW = BUILD / "preview"
ENTRY = "docs/iteration4/step-10/methodology/154-screen-wide-prism-sweep.md"
ALPHA = 0.10
#: Reported, never selected on: entry 151 placed it at the 99.4th percentile.
RETROSPECTIVE = "DASATINIB"
TITLES = {"rms": "rhabdomyosarcoma vs rest", "aneuploidy": "high vs low aneuploidy"}


def _write(
    fig: go.Figure, name: str, width: int, height: int, inputs: list[Path], legend: str
) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    PREVIEW.mkdir(parents=True, exist_ok=True)
    svg = OUT / f"step10-s1-{name}.svg"
    fig.write_image(svg, format="svg", width=width, height=height)
    fig.write_image(PREVIEW / f"{name}.png", format="png", width=width, height=height, scale=2)
    fig.write_html(svg.with_suffix(".html"), include_plotlyjs="cdn", full_html=True)
    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()
    manifest = {
        "name": svg.stem,
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "built_by": "tools/render_step10_s1.py",
        "code_version": commit,
        "inputs": [{"path": p.as_posix(), "sha256": provenance.digest(p)[0]} for p in inputs],
        "entry": ENTRY,
        "legend": legend,
        "patient_data": (
            "none. Public cell-line screen results only; no patient-derived value and no "
            "genomic position appears on any axis"
        ),
    }
    svg.with_suffix(".provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {svg}\n  {legend}\n")


def _reps(table: pl.DataFrame, contrast: str) -> pl.DataFrame:
    return table.filter(
        (pl.col("contrast") == contrast) & pl.col("representative") & pl.col("p_raw").is_not_null()
    )


def _panel(
    fig: go.Figure,
    col: int,
    rows: pl.DataFrame,
    *,
    listed: set[str],
    band: dict[str, Any] | None,
    boundary: float,
    boundary_text: str,
) -> None:
    """One volcano: blue = the family, yellow = G3-listed, green = q < alpha."""
    groups = (
        ("q < 0.10 (BH over the whole family)", GOOD, pl.col("q") < ALPHA),
        ("G3-listed (top 0.5 % of one contrast)", DECISION,
         (pl.col("q") >= ALPHA) & pl.col("drug").is_in(sorted(listed))),
        ("every other eligible drug", MACHINE,
         (pl.col("q") >= ALPHA) & ~pl.col("drug").is_in(sorted(listed))),
    )  # fmt: skip
    for name, hue, cond in groups:
        sub = rows.filter(cond)
        if sub.is_empty():
            continue
        fig.add_trace(
            go.Scatter(
                x=sub["cliffs_delta"], y=[-math.log10(p) for p in sub["p_raw"]],
                mode="markers", name=name, legendgroup=name,
                showlegend=col == (2 if hue is DECISION else 1),
                marker={"size": 6 if hue is MACHINE else 9, "color": hue.fill,
                        "line": {"color": hue.line, "width": 1}},
                hovertext=[f"{d}  n={a}/{b}  p={p:.2g}  q={q:.2g}" for d, a, b, p, q in
                           sub.select("drug", "n_in", "n_out", "p_raw", "q").rows()],
                hoverinfo="text",
            ),
            row=1, col=col,
        )  # fmt: skip
    # Label what this panel itself ranks at the top (its G3 picks, or the control's leaders),
    # plus the retrospective drug on the two real contrasts; staggered so labels do not stack.
    top = 4 if listed else 2
    marked = pl.col("rank") <= top
    if listed:
        marked = marked | (pl.col("drug") == RETROSPECTIVE)
    for i, r in enumerate(rows.filter(marked).sort("rank").iter_rows(named=True)):
        tag = " (retrospective)" if r["drug"] == RETROSPECTIVE else ""
        left = r["cliffs_delta"] > 0.5  # far-right points take their label on the left
        fig.add_annotation(
            x=r["cliffs_delta"], y=-math.log10(r["p_raw"]), text=r["drug"].title() + tag,
            showarrow=True, arrowhead=0, ax=-50 if left else 70, ay=-40 + 22 * i,
            font={"size": 9}, xanchor="right" if left else "left",
            arrowcolor=RAW.line if tag else MUTED.line, row=1, col=col,
        )  # fmt: skip
    if band is not None:
        fig.add_vrect(
            x0=band["delta_2.5pct"], x1=band["delta_97.5pct"], row=1, col=col,
            fillcolor=MUTED.line, opacity=0.15, line_width=0, layer="below",
        )  # fmt: skip
    fig.add_hline(
        y=-math.log10(boundary), row=1, col=col,
        line={"color": DECISION.line, "width": 1.6, "dash": "dash"},
        annotation_text=boundary_text, annotation_position="bottom left",
        annotation_font={"size": 10, "color": DECISION.line},
    )  # fmt: skip


def volcano(table: pl.DataFrame, listed: set[str], controls: dict[str, Any]) -> None:
    positive = pl.read_csv(POSITIVE, separator="\t", infer_schema_length=None).rename(
        {"delta": "cliffs_delta", "p": "p_raw"}
    )
    pc = controls["positive_control_sweep"]["calibration"]
    cal = controls["calibration"]
    titles = [
        f"positive control: skin vs rest ({pc['family_size']:,} drugs)",
        *(f"{TITLES[c]} ({cal[c]['family_size']} drugs)" for c in ("rms", "aneuploidy")),
    ]
    fig = make_subplots(rows=1, cols=3, shared_yaxes=True, horizontal_spacing=0.04,
                        subplot_titles=titles)  # fmt: skip
    _panel(fig, 1, positive, listed=set(), band=None, boundary=pc["largest_p_passing"],
           boundary_text=f"q = 0.10 · {pc['drugs_q_below_alpha']} drugs pass")  # fmt: skip
    for col, c in ((2, "rms"), (3, "aneuploidy")):
        _panel(
            fig, col, _reps(table, c), listed=listed, band=controls["negative_control"][c],
            boundary=cal[c]["p_needed_at_rank_1"],
            boundary_text=f"q < 0.10 needs p < {cal[c]['p_needed_at_rank_1']:.1e} · 0 pass",
        )  # fmt: skip
    fig.update_xaxes(title_text="Cliff's delta (+ = in-group more sensitive)", range=[-1.05, 1.05])
    fig.update_yaxes(title_text="-log10 one-sided p", row=1, col=1)
    fig.update_layout(
        title=("S1 — the same test finds BRAF inhibitors screen-wide, and nothing for the "
               "child's two contrasts"),
        legend={"orientation": "h", "y": -0.3}, margin={"t": 96, "b": 130},
    )  # fmt: skip
    legend = legend_line(
        GOOD, DECISION, MACHINE, MUTED, RAW,
        extra=("each dot = one drug's representative copy; dashed yellow = the p value BH needs "
               "for q < 0.10 (for the control: the largest passing p; for the two real contrasts: "
               "the rank-1 threshold 0.10 / 613, which no drug reaches); grey band = central 95 % "
               "of Cliff's delta over 200 seeded unrelated eligible Launched drugs; purple label "
               "= dasatinib, marked only because entry 151 already reported it"),
    )  # fmt: skip
    _write(fig, "volcano", 1400, 620, [TABLE, LIST, CONTROLS, POSITIVE], legend)


def percentiles(table: pl.DataFrame, listed: set[str]) -> None:
    rms = _reps(table, "rms").select("drug", x="percentile")
    aneu = _reps(table, "aneuploidy").select("drug", y="percentile")
    both = rms.join(aneu, on="drug")
    rho, p = stats.spearmanr(both["x"], both["y"])
    fig = go.Figure()
    for name, hue, cond in (
        ("every other eligible drug", MACHINE, ~pl.col("drug").is_in(sorted(listed))),
        ("G3-listed", DECISION, pl.col("drug").is_in(sorted(listed))),
    ):
        sub = both.filter(cond)
        fig.add_trace(go.Scatter(
            x=sub["x"], y=sub["y"], mode="markers", name=name, hovertext=sub["drug"],
            marker={"size": 6 if hue is MACHINE else 10, "color": hue.fill,
                    "line": {"color": hue.line, "width": 1}},
        ))  # fmt: skip
    marked = both.filter(pl.col("drug").is_in(sorted(listed | {RETROSPECTIVE}))).sort("x")
    for i, r in enumerate(marked.iter_rows(named=True)):
        fig.add_annotation(x=r["x"], y=r["y"], text=r["drug"].title(), showarrow=True,
                           arrowhead=0, ax=-40 if r["x"] > 50 else 40, ay=18 + 16 * (i % 3),
                           font={"size": 9})  # fmt: skip
    fig.add_shape(type="rect", x0=90, x1=100.5, y0=90, y1=100.5, line={"color": GOOD.line,
                  "dash": "dot"}, fillcolor=GOOD.fill, opacity=0.25, layer="below")  # fmt: skip
    fig.update_xaxes(title_text="percentile of Cliff's delta, rhabdomyosarcoma contrast",
                     range=[-1, 101])  # fmt: skip
    fig.update_yaxes(title_text="percentile of Cliff's delta, aneuploidy contrast", range=[-1, 101])
    fig.update_layout(
        title=(f"S1 — the two contrasts do not pick the same drugs "
               f"(Spearman ρ = {rho:+.3f}, p = {p:.2g}, {both.height} drugs)"),
        legend={"orientation": "h", "y": -0.16},
    )  # fmt: skip
    legend = legend_line(
        MACHINE, DECISION, GOOD,
        extra=("each dot = one eligible Launched drug placed by its delta percentile in each "
               "contrast; yellow = the 8 drugs G3 lists (top 0.5 % by p on either contrast); "
               "green square = the top decile of both, where a drug selective for both would sit "
               "(H093 additionally needs q < 0.10 in both, which no drug has)"),
    )  # fmt: skip
    _write(fig, "percentiles", 900, 760, [TABLE, LIST], legend)


def funnel(controls: dict[str, Any]) -> None:
    f = controls["funnel"]
    steps = [
        ("PRISM 24Q2 compounds", f["compounds_in_matrix"], RAW),
        ("marked Launched (20Q2 phase)", f["launched_in_matrix"], MACHINE),
        ("eligible copies (≥ 3 RMS, ≥ 20 per arm)", f["eligible_copies"], MACHINE),
        ("eligible drugs (one test each)", f["eligible_drugs"], MACHINE),
        ("G3-listed drugs", f["g3_listed"], DECISION),
        ("q < 0.10 in both contrasts", f["hit_both_drugs"], BAD),
    ]
    fig = go.Figure(go.Bar(
        x=[n for _, n, _ in steps], y=[s for s, _, _ in steps], orientation="h",
        marker={"color": [h.fill for *_, h in steps], "line": {"color": [h.line for *_, h in steps],
                "width": 1.5}},
        text=[f"{n:,}" for _, n, _ in steps], textposition="outside",
    ))  # fmt: skip
    for label, n, _ in steps:
        if n == 0:  # a log axis cannot draw a zero-length bar; say it in words at the label
            fig.add_annotation(x=0, y=label, text="0", showarrow=False, xanchor="left",
                               font={"size": 13, "color": BAD.line})  # fmt: skip
    unseen = sum(f["no_phase_in_any_20q2_file"].values())
    fig.update_xaxes(type="log", title_text="count (log scale)", range=[-0.3, 4.2])
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(
        title=(f"S1 — 6,790 compounds, 613 testable Launched drugs, 0 answers<br><sup>{unseen:,} "
               "REP.1M / REP.300 compounds carry no PRISM phase and could not be called "
               "Launched</sup>"),
        margin={"l": 300, "t": 84}, showlegend=False,
    )  # fmt: skip
    legend = legend_line(
        RAW, MACHINE, DECISION, BAD,
        extra=("purple = the raw screen; blue = each filter; yellow = the list G3 hands to the "
               "convergence test; red = the H093 count, zero (a zero bar is drawn at its label)"),
    )  # fmt: skip
    _write(fig, "funnel", 1000, 420, [CONTROLS], legend)


def main() -> int:
    install_template()
    table = pl.read_csv(TABLE, separator="\t", infer_schema_length=None)
    listed = set(pl.read_csv(LIST, separator="\t")["drug"].to_list())
    controls = json.loads(CONTROLS.read_text())
    volcano(table, listed, controls)
    percentiles(table, listed)
    funnel(controls)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
