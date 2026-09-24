#!/usr/bin/env python3
"""Step 9, E4: the PRISM replication in three figures.

(a) ``step9-e4-effects`` — a forest plot: Cliff's delta with its bootstrap CI for every
    candidate in both pre-registered contrasts, candidates grouped by repurposing
    direction, with the negative-control band (the central 95 % of 200 unrelated Launched
    drugs put through the same test) shaded behind.
(b) ``step9-e4-background`` — where the candidates sit among *every* compound the screen
    tested: the RMS contrast on the left with the statins marked, the aneuploidy contrast
    on the right with dasatinib and the Mps1/Aurora class marked.
(c) ``step9-e4-coverage`` — how many of the 14 rhabdomyosarcoma lines each candidate was
    actually measured on, in each release. The coverage, not the p value, is the binding
    constraint on this experiment.

**Sources.** ``ressources/track2/prism_replication.tsv`` and its provenance manifest,
``build/it4/track2-e4/background-*.parquet``, ``build/it4/track2-e4/controls.json``,
``build/it4/track2-e4/coverage.tsv`` — all written by ``tools/screen_replication.py run``.
Entry 151.

    uv run python tools/render_step9_e4.py

Outputs ``figures/it4/step9-e4-{effects,background,coverage}.{svg,html}`` plus one
``.provenance.json`` each, and prints each figure's legend line.
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import plotly.graph_objects as go
import polars as pl
from plotly.subplots import make_subplots

from mva.drugs import provenance
from mva.render.theme import BAD, DECISION, GOOD, MACHINE, MUTED, RAW, install_template, legend_line

TABLE = Path("ressources/track2/prism_replication.tsv")
BUILD = Path("build/it4/track2-e4")
OUT = Path("figures/it4")
PREVIEW = Path("build/it4/track2-e4/preview")
ENTRY = "docs/iteration4/step-9/methodology/151-prism-replication-of-the-track2-leads.md"
LINEAGE = "lineage-vs-all"
ANEUPLOIDY = "aneuploidy-high-vs-low"
#: The eight approved statins, separated from the other compounds PRISM annotates
#: ``HMGCR INHIBITOR`` (meglutol, alpha-asarone, procaine), which are not statins.
STATINS = (
    "LOVASTATIN",
    "SIMVASTATIN",
    "ATORVASTATIN",
    "PRAVASTATIN",
    "FLUVASTATIN",
    "ROSUVASTATIN",
    "PITAVASTATIN",
    "MEVASTATIN",
)
#: The candidate key is a normalised name (no spaces or hyphens); two of them need help
#: to read as English on an axis.
PRETTY = {"VALPROICACID": "Valproic acid", "ALPHAASARONE": "Alpha-asarone"}
DIRECTION_TITLE = {
    "D2": "D2 aneuploidy stress",
    "D3": "D3 raise BubR1",
    "D4": "D4 tumour context (statins)",
    "D5": "D5 senolytic / mTOR",
}


def _label(key: str) -> str:
    """``VALPROICACID`` -> ``Valproic acid``; every other key title-cases cleanly."""
    return PRETTY.get(key, key.title())


def _write(
    fig: go.Figure, name: str, width: int, height: int, inputs: list[Path], legend: str
) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    PREVIEW.mkdir(parents=True, exist_ok=True)
    svg = OUT / f"step9-e4-{name}.svg"
    fig.write_image(svg, format="svg", width=width, height=height)
    fig.write_image(PREVIEW / f"{name}.png", format="png", width=width, height=height, scale=2)
    fig.write_html(svg.with_suffix(".html"), include_plotlyjs="cdn", full_html=True)
    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()
    svg.with_suffix(".provenance.json").write_text(
        json.dumps(
            {
                "name": svg.stem,
                "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "built_by": "tools/render_step9_e4.py",
                "code_version": commit,
                "inputs": [
                    {"path": p.as_posix(), "sha256": provenance.digest(p)[0]} for p in inputs
                ],
                "entry": ENTRY,
                "legend": legend,
                "patient_data": (
                    "none. Public cell-line screen results only; no patient-derived value and "
                    "no genomic position appears on any axis"
                ),
            },
            indent=2,
        )
        + "\n"
    )
    print(f"wrote {svg}\n  {legend}\n")


def effects_figure(table: pl.DataFrame, controls: dict[str, Any]) -> None:
    """Forest plot of both primary contrasts, grouped by direction, over the control band."""
    rows = table.filter(
        pl.col("representative")
        & (pl.col("status") == "tested")
        & pl.col("contrast").is_in([LINEAGE, ANEUPLOIDY])
    )
    order: list[tuple[str, str]] = []
    for direction in ("D2", "D3", "D4", "D5"):
        names = sorted(set(rows.filter(pl.col("direction_id") == direction)["candidate"].to_list()))
        order += [(direction, n) for n in names]
    labels = [f"{d} · {_label(n)}" for d, n in order]
    fig = make_subplots(
        rows=1, cols=2, shared_yaxes=True, horizontal_spacing=0.06,
        subplot_titles=(
            "rhabdomyosarcoma lines vs the rest (14 vs 884)",
            "high- vs low-aneuploidy lines (350 vs 338)",
        ),
    )  # fmt: skip
    for col, contrast in ((1, LINEAGE), (2, ANEUPLOIDY)):
        sub = rows.filter(pl.col("contrast") == contrast)
        by_key = {(r["direction_id"], r["candidate"]): r for r in sub.iter_rows(named=True)}
        for hit, hue, tag in (
            (True, GOOD, "raw one-sided p < 0.05"),
            (False, MACHINE, "raw one-sided p ≥ 0.05"),
        ):
            xs, ys, lo, hi, text = [], [], [], [], []
            for i, key in enumerate(order):
                r = by_key.get(key)
                if r is None or (r["p_raw"] < 0.05) != hit:
                    continue
                xs.append(r["cliffs_delta"])
                ys.append(labels[i])
                lo.append(r["cliffs_delta"] - r["ci_low"])
                hi.append(r["ci_high"] - r["cliffs_delta"])
                text.append(
                    f"n={r['n_in']}/{r['n_out']}  p={r['p_raw']:.3g}"
                    + (f"  q={r['p_adjusted']:.3g}" if r["p_adjusted"] is not None else "")
                )
            if not xs:
                continue
            fig.add_trace(
                go.Scatter(
                    x=xs, y=ys, mode="markers", name=tag, legendgroup=tag,
                    showlegend=col == 1, hovertext=text, hoverinfo="text+x",
                    marker={"size": 9, "color": hue.fill, "line": {"color": hue.line, "width": 2}},
                    error_x={"type": "data", "array": hi, "arrayminus": lo, "visible": True,
                             "color": hue.line, "thickness": 1.4, "width": 0},
                ),
                row=1, col=col,
            )  # fmt: skip
    # The band is added after the traces: Plotly attaches a row/col shape only to a
    # subplot that already holds data, and silently drops it otherwise.
    for col, contrast in ((1, LINEAGE), (2, ANEUPLOIDY)):
        band = controls["negative_control"][contrast]
        fig.add_vrect(
            x0=band["delta_2.5pct"], x1=band["delta_97.5pct"], row=1, col=col,
            fillcolor=MUTED.line, opacity=0.18, line_width=0, layer="below",
            annotation_text=(
                f"control band · {band['n']} unrelated drugs · "
                f"{band['fraction_p_below_0.05'] * 100:.0f} % reach raw p < 0.05"
            ),
            annotation_position="bottom", annotation_font_size=10,
            annotation_font_color=MUTED.line,
        )  # fmt: skip
        for edge in (band["delta_2.5pct"], band["delta_97.5pct"]):
            fig.add_vline(
                x=edge, row=1, col=col, line={"color": MUTED.line, "width": 1, "dash": "dash"}
            )
        fig.add_vline(x=0, row=1, col=col, line={"color": MUTED.line, "width": 1, "dash": "dot"})
    fig.update_xaxes(
        title_text="Cliff's delta (+ = the in-group is more sensitive)", range=[-1.05, 1.05]
    )
    fig.update_yaxes(categoryorder="array", categoryarray=labels[::-1], autorange=None)
    fig.update_layout(
        title="E4 — every Track 2 candidate in two PRISM contrasts, over the negative-control band",
        legend={"orientation": "h", "y": -0.16},
        margin={"l": 200, "r": 30, "t": 96},
    )
    legend = legend_line(
        GOOD, MACHINE, MUTED,
        extra=("green = raw one-sided p < 0.05, blue = not; bars = 95 % percentile bootstrap CI "
               "on Cliff's delta; grey band = the central 95 % of 200 unrelated Launched drugs "
               "put through the identical test (the calibration band); dotted line = no effect. "
               "Only rows measured on at least 3 in-group lines are drawn — the missing "
               "candidates are the coverage figure's subject"),
    )  # fmt: skip
    _write(fig, "effects", 1180, 720, [TABLE, BUILD / "controls.json"], legend)


def background_figure(table: pl.DataFrame, controls: dict[str, Any]) -> None:
    """Where the candidates sit among every compound the screen tested."""
    fig = make_subplots(
        rows=1, cols=2, horizontal_spacing=0.09,
        subplot_titles=(
            "rhabdomyosarcoma contrast — where the statins sit",
            "aneuploidy contrast — dasatinib and the Mps1/Aurora class",
        ),
    )  # fmt: skip
    lit = {
        r["item_name"]
        for r in controls["literature_direction_check"]["results"]
        if r["p_raw"] is not None
    }
    for col, contrast, marks in (
        (1, LINEAGE, [(n, RAW) for n in STATINS]),
        (2, ANEUPLOIDY, [("DASATINIB", GOOD)]),
    ):
        back = pl.read_parquet(BUILD / f"background-{contrast}.parquet").filter(
            pl.col("status") == "tested"
        )
        fig.add_trace(
            go.Histogram(
                x=back["delta"], nbinsx=70, name=f"all {back.height:,} compounds tested",
                marker={"color": MACHINE.fill, "line": {"color": MACHINE.line, "width": 0.4}},
                showlegend=col == 1, legendgroup="all",
            ),
            row=1, col=col,
        )  # fmt: skip
        if col == 2:
            deltas = back.filter(pl.col("item_name").is_in(sorted(lit)))["delta"].to_list()
            for i, d in enumerate(deltas):
                fig.add_vline(
                    x=d,
                    row=1,
                    col=col,
                    line={"color": BAD.line, "width": 1.1, "dash": "dot"},
                    opacity=0.75,
                )
                if i == 0:
                    fig.add_trace(
                        go.Scatter(
                            x=[None], y=[None], mode="lines", name=(
                                f"{len(deltas)} Mps1 / Aurora inhibitors (literature direction)"
                            ),
                            line={"color": BAD.line, "width": 1.1, "dash": "dot"},
                        ),
                        row=1, col=col,
                    )  # fmt: skip
        table_rows = {
            r["candidate"]: r
            for r in table.filter(
                (pl.col("contrast") == contrast)
                & pl.col("representative")
                & (pl.col("status") == "tested")
            ).iter_rows(named=True)
        }
        # Labels go on one staggered marker row above the histogram: five vline
        # annotations on a shared axis overprint each other into an unreadable smear.
        counts = np.histogram(back["delta"].to_numpy(), bins=70)[0]
        top = float(counts.max())
        marked = sorted(
            ((n, h, table_rows[n]) for n, h in marks if n in table_rows),
            key=lambda m: m[2]["cliffs_delta"],
        )
        for i, (name, hue, r) in enumerate(marked):
            pct = float((back["delta"] <= r["cliffs_delta"]).mean()) * 100
            fig.add_vline(x=r["cliffs_delta"], row=1, col=col, line={"color": hue.line, "width": 2})
            fig.add_trace(
                go.Scatter(
                    x=[r["cliffs_delta"]], y=[top * (1.07 + 0.09 * (i % 3))],
                    mode="markers+text", text=[f"{name.title()} · {pct:.0f}th"],
                    textposition="top center",
                    textfont={"size": 10, "color": hue.line},
                    marker={"size": 7, "color": hue.fill,
                            "line": {"color": hue.line, "width": 1.5}},
                    name=(
                        "approved statin measured on ≥ 3 RMS lines"
                        if col == 1
                        else "dasatinib (D5)"
                    ),
                    legendgroup=f"mark{col}", showlegend=i == 0,
                    hovertext=[f"δ={r['cliffs_delta']:+.3f}  p={r['p_raw']:.3g}"],
                    hoverinfo="text",
                ),
                row=1, col=col,
            )  # fmt: skip
    fig.update_xaxes(title_text="Cliff's delta (+ = the in-group is more sensitive)")
    fig.update_yaxes(title_text="compounds", row=1, col=1)
    fig.update_layout(
        title="E4 — the candidates against the whole screen, not only against each other",
        legend={"orientation": "h", "y": -0.18},
        bargap=0.02,
        margin={"t": 96},
    )
    legend = legend_line(
        MACHINE, RAW, GOOD, BAD,
        extra=("blue bars = every compound the contrast could test; purple lines = the approved "
               "statins that cleared the 3-line minimum, with their percentile among all "
               "compounds; green = dasatinib; dotted red = each Mps1 / Aurora inhibitor, whose "
               "leftward mass reproduces Cohen-Sharir 2021's direction (aneuploid lines are "
               "*less* sensitive to short-term checkpoint inhibition)"),
    )  # fmt: skip
    sweeps = [BUILD / f"background-{c}.parquet" for c in (LINEAGE, ANEUPLOIDY)]
    _write(fig, "background", 1180, 560, [TABLE, *sweeps], legend)


def coverage_figure() -> None:
    """How many rhabdomyosarcoma lines each candidate was actually measured on."""
    cov = pl.read_csv(BUILD / "coverage.tsv", separator="\t").sort(
        "in_group_lines_measured", "candidate", descending=[True, False]
    )
    labels = [f"{r['direction_id']} · {_label(r['candidate'])}" for r in cov.iter_rows(named=True)]
    measured = cov["in_group_lines_measured"].to_list()
    colours = [GOOD if m >= 14 else (DECISION if m >= 3 else BAD) for m in measured]
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=measured, y=labels, orientation="h", name="RMS lines measured (of 14)",
            marker={"color": [c.fill for c in colours],
                    "line": {"color": [c.line for c in colours], "width": 1.5}},
            text=[str(m) for m in measured], textposition="outside",
        )
    )  # fmt: skip
    fig.add_trace(
        go.Scatter(
            x=[-0.7] * cov.height, y=labels, mode="text",
            text=["20Q2 ✓" if b else "20Q2 ✗" for b in cov["in_secondary"].to_list()],
            textfont={"size": 10, "color": MUTED.line},
            showlegend=False, hoverinfo="skip",
        )
    )  # fmt: skip
    fig.add_vline(x=3, line={"color": BAD.line, "width": 1.5, "dash": "dash"})
    fig.update_xaxes(
        title_text="rhabdomyosarcoma lines with a value, PRISM 24Q2 primary", range=[-1.6, 16]
    )
    fig.update_layout(
        title=(
            f"E4 — coverage is the binding constraint: {sum(m < 3 for m in measured)} of "
            f"{cov.height} candidates miss the 3-line floor"
        ),
        margin={"l": 210, "r": 30, "t": 84},
        showlegend=False,
        height=760,
    )
    legend = legend_line(
        GOOD, DECISION, BAD,
        extra=("green = all 14 RMS lines (the compound is in PRISM's REP.1M or REP.300 "
               "sub-screen); yellow = 3 to 13, testable but weak; red = fewer than 3, reported "
               "as untestable, not as a null result; dashed red = the 3-line floor; the small "
               "text says whether the drug is also in the 20Q2 secondary release"),
    )  # fmt: skip
    _write(fig, "coverage", 1000, 760, [BUILD / "coverage.tsv"], legend)


def main() -> int:
    install_template()
    table = pl.read_csv(TABLE, separator="\t", infer_schema_length=10000)
    controls = json.loads((BUILD / "controls.json").read_text())
    effects_figure(table, controls)
    background_figure(table, controls)
    coverage_figure()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
