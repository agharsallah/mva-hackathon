#!/usr/bin/env python3
"""Iteration 5, route R2: three figures from the tables the two drivers wrote.

* ``r2-proliferation`` — why the correction is needed and what it leaves: BUB1B's raw log2
  fold change against the proliferation score across 875 compounds, the fitted line, and
  the corrected residual of each compound.
* ``r2-control`` — the two positive controls side by side: the HSP70 induction that gates
  the proteome route (rank of each HSP90 inhibitor among 875) and the checkpoint-sibling
  ranks in LINCS, uncorrected and corrected.
* ``r2-hits`` — the approved corrected risers: effect size against corrected z, sized by
  breadth, against the two cuts.

    uv run python tools/render_it5_r2.py

Reads ``ressources/track2/it5/*.tsv`` and ``build/it5/r2/*.json``; writes
``figures/it5/r2-*.svg`` (+ ``.html`` and one ``.provenance.json`` each) and prints legends.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import plotly.graph_objects as go
import polars as pl
from plotly.subplots import make_subplots

from mva.drugs import provenance
from mva.render.theme import BAD, DECISION, GOOD, MACHINE, MUTED, RAW, install_template, legend_line

TABLES = Path("ressources/track2/it5")
BUILD = Path("build/it5/r2")
OUT = Path("figures/it5")
ENTRY = (
    "docs/iteration5/step-1/methodology/"
    "159-which-drugs-raise-bubr1-protein-once-proliferation-is-removed.md"
)
Z_MIN, BROAD = 3.0, 0.05
PATIENT_DATA = (
    "none. Public proteomics and LINCS values, gene symbols and drug names only; no "
    "patient value and no genomic position appears on any axis"
)


def _write(
    fig: go.Figure, name: str, width: int, height: int, inputs: list[Path], legend: str
) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    svg = OUT / f"{name}.svg"
    fig.write_image(svg, format="svg", width=width, height=height)
    fig.write_html(svg.with_suffix(".html"), include_plotlyjs="cdn", full_html=True)
    manifest = provenance.envelope(name, built_by="tools/render_it5_r2.py")
    manifest.update(
        {
            "entry": ENTRY,
            "inputs": [{"path": p.as_posix(), "sha256": provenance.digest(p)[0]} for p in inputs],
            "legend": legend,
            "patient_data": PATIENT_DATA,
        }
    )
    provenance.write(manifest, svg.with_suffix(".provenance.json"))
    print(f"wrote {svg}\n  {legend}\n")


def _hits() -> pl.DataFrame:
    return pl.read_csv(TABLES / "proteome_hits.tsv", separator="\t", infer_schema_length=5000)


def proliferation_figure() -> None:
    table = _hits().filter(pl.col("dataset") == "mitchell2023")
    fig = make_subplots(
        rows=1,
        cols=2,
        horizontal_spacing=0.11,
        subplot_titles=(
            "BUB1B protein follows the mitotic program (875 compounds, HCT116)",
            "what the correction leaves: residual per compound",
        ),
    )
    hit = table.filter(pl.col("hit"))
    rest = table.filter(~pl.col("hit"))
    for frame, hue, tag in (
        (rest, MUTED, "not a corrected riser"),
        (hit, GOOD, "corrected riser (z ≥ 3, raw > 0)"),
    ):
        fig.add_trace(
            go.Scatter(
                x=frame["proliferation_score"],
                y=frame["raw_log2fc"],
                mode="markers",
                name=tag,
                marker={"color": hue.fill, "line": {"color": hue.line, "width": 1}, "size": 7},
                text=frame["compound"],
                hovertemplate="%{text}<br>score %{x:.2f}<br>log2 FC %{y:.2f}<extra></extra>",
            ),
            row=1,
            col=1,
        )
    summary = json.loads((BUILD / "proteome_summary.json").read_text())
    fit = summary["datasets"]["mitchell2023"]["fit"]
    score = table["proliferation_score"].to_numpy().astype(float)
    xs = [float(score.min()), float(score.max())]
    intercept = float(table["raw_log2fc"].to_numpy().astype(float).mean()) - fit[
        "slope_on_score"
    ] * float(score.mean())
    fig.add_trace(
        go.Scatter(
            x=xs,
            y=[intercept + fit["slope_on_score"] * x for x in xs],
            mode="lines",
            name=f"fit: slope {fit['slope_on_score']}, r² {fit['r2']}",
            line={"color": DECISION.line, "dash": "dash"},
        ),
        row=1,
        col=1,
    )
    ranked = table.filter(pl.col("rank") > 0).sort("rank")
    fig.add_trace(
        go.Scatter(
            x=ranked["rank"],
            y=ranked["robust_z"],
            mode="markers",
            showlegend=False,
            marker={
                "color": [GOOD.fill if h else MUTED.fill for h in ranked["hit"]],
                "line": {"color": MACHINE.line, "width": 0.5},
                "size": 6,
            },
            text=ranked["compound"],
            hovertemplate="%{text}<br>rank %{x}<br>z %{y:.2f}<extra></extra>",
        ),
        row=1,
        col=2,
    )
    fig.add_hline(y=Z_MIN, line={"color": DECISION.line, "dash": "dash"}, row=1, col=2)
    fig.update_xaxes(title_text="proliferation score (median G2/M log2 FC)", row=1, col=1)
    fig.update_yaxes(title_text="BUB1B log2 fold change", row=1, col=1)
    fig.update_xaxes(title_text="compound rank (corrected)", row=1, col=2)
    fig.update_yaxes(title_text="robust z of the residual", row=1, col=2)
    fig.update_layout(height=520, legend={"orientation": "h", "y": -0.2})
    legend = legend_line(
        GOOD,
        MUTED,
        DECISION,
        extra=(
            "left: each dot is one compound, the dashed line the fitted proliferation "
            "dependence; right: the same compounds by corrected rank, dashed line = the "
            "z ≥ 3 cut"
        ),
    )
    _write(fig, "r2-proliferation", 1180, 520, [TABLES / "proteome_hits.tsv"], legend)


def control_figure() -> None:
    controls = pl.read_csv(TABLES / "proteome_control.tsv", separator="\t", infer_schema_length=500)
    lincs = pl.read_csv(TABLES / "lincs_cc_control.tsv", separator="\t", infer_schema_length=500)
    fig = make_subplots(
        rows=1,
        cols=2,
        horizontal_spacing=0.14,
        subplot_titles=(
            "(a) proteome control: rank of each inducer (875 compounds)",
            "(b) LINCS control: checkpoint siblings among 7,233 knockouts",
        ),
    )
    mitchell = controls.filter(pl.col("dataset") == "mitchell2023").with_columns(
        pl.col("rank").cast(pl.Int64, strict=False)
    )
    labels = [
        f"{r['protein']} ← {r['inducer'].split('_')[0]}{'' if r['gates'] else ' (context)'}"
        for r in mitchell.iter_rows(named=True)
    ]
    fig.add_trace(
        go.Bar(
            x=mitchell["rank"],
            y=labels,
            orientation="h",
            showlegend=False,
            marker_color=[
                GOOD.fill if r["rank"] <= r["cut_rank"] else BAD.fill
                for r in mitchell.iter_rows(named=True)
            ],
            marker_line_color=MACHINE.line,
            hovertemplate="rank %{x}<extra></extra>",
        ),
        row=1,
        col=1,
    )
    fig.add_vline(
        x=int(mitchell["cut_rank"][0]), line={"color": DECISION.line, "dash": "dash"}, row=1, col=1
    )
    sib = lincs.filter(
        (pl.col("role") == "named sibling") & pl.col("variant").is_in(["raw", "cc_primary"])
    )
    for variant, hue in (("raw", RAW), ("cc_primary", MACHINE)):
        part = sib.filter(pl.col("variant") == variant).with_columns(
            pl.col("percentile").cast(pl.Float64, strict=False)
        )
        shown = part.filter(pl.col("has_consensus_row"))
        fig.add_trace(
            go.Bar(
                x=shown["percentile"],
                y=shown["gene"],
                orientation="h",
                name="uncorrected" if variant == "raw" else "cell-cycle corrected",
                marker_color=hue.fill,
                marker_line_color=hue.line,
                hovertemplate="%{y}: %{x:.2f} %<extra></extra>",
            ),
            row=1,
            col=2,
        )
    fig.add_vline(x=5, line={"color": DECISION.line, "dash": "dash"}, row=1, col=2)
    fig.update_xaxes(
        title_text="rank among 875 compounds (1 = strongest)", type="log", row=1, col=1
    )
    fig.update_xaxes(
        title_text="percentile among knockouts (log; lower = more alike)", type="log", row=1, col=2
    )
    fig.update_layout(height=520, barmode="group", legend={"orientation": "h", "y": -0.2})
    legend = legend_line(
        GOOD,
        BAD,
        DECISION,
        RAW,
        MACHINE,
        extra=(
            "(a) green = inducer inside the gating cut, red = outside; (b) purple = "
            "uncorrected, blue = corrected; BUB3, MAD1L1 and MAD2L1 have no knockout row "
            "and are not drawn; dashed = the 5 % cut"
        ),
    )
    _write(
        fig,
        "r2-control",
        1180,
        520,
        [TABLES / "proteome_control.tsv", TABLES / "lincs_cc_control.tsv"],
        legend,
    )


def hits_figure() -> None:
    table = _hits().filter((pl.col("dataset") == "mitchell2023") & (pl.col("rank") > 0))
    fig = go.Figure()
    groups = (
        ("approved, corrected riser", table.filter(pl.col("hit") & pl.col("approved")), GOOD),
        (
            "corrected riser, not approved",
            table.filter(pl.col("hit") & ~pl.col("approved")),
            MACHINE,
        ),
        (
            "z ≥ 3 but the protein fell (arrest, not a raise)",
            table.filter((pl.col("robust_z") >= Z_MIN) & ~pl.col("hit")),
            BAD,
        ),
        ("rest", table.filter(pl.col("robust_z") < Z_MIN), MUTED),
    )
    for tag, frame, hue in groups:
        if not frame.height:
            continue
        size = [8 + 26 * min(float(b or 0), 0.3) for b in frame["breadth"]]
        fig.add_trace(
            go.Scatter(
                x=frame["raw_log2fc"],
                y=frame["robust_z"],
                mode="markers",
                name=tag,
                marker={"color": hue.fill, "line": {"color": hue.line, "width": 1}, "size": size},
                text=frame["compound"],
                hovertemplate="%{text}<br>log2 FC %{y:.2f}<extra></extra>",
            ),
        )
    named = table.filter(pl.col("hit") & pl.col("approved"))
    fig.add_trace(
        go.Scatter(
            x=named["raw_log2fc"],
            y=named["robust_z"],
            mode="text",
            showlegend=False,
            text=[c.lower() for c in named["compound"]],
            textposition="top center",
            textfont={"size": 10},
        ),
    )
    fig.add_hline(y=Z_MIN, line={"color": DECISION.line, "dash": "dash"})
    fig.add_vline(x=0, line={"color": DECISION.line, "dash": "dot"})
    fig.add_vline(x=math.log2(1.25), line={"color": DECISION.line, "dash": "dash"})
    fig.update_layout(
        title="BUB1B protein: corrected response vs effect size (875 compounds, HCT116, 24 h)",
        xaxis_title="raw log2 fold change (dashed = +25 % protein)",
        yaxis_title="robust z of the proliferation-corrected residual",
        height=560,
        legend={"orientation": "h", "y": -0.18},
    )
    legend = legend_line(
        GOOD,
        MACHINE,
        BAD,
        MUTED,
        DECISION,
        extra=(
            "marker size = breadth (share of all proteins the compound raises); dashed "
            "horizontal = z ≥ 3, dashed vertical = +25 % protein, dotted = no change"
        ),
    )
    _write(fig, "r2-hits", 1080, 560, [TABLES / "proteome_hits.tsv"], legend)


def main() -> None:
    install_template()
    proliferation_figure()
    control_figure()
    hits_figure()


if __name__ == "__main__":
    main()
