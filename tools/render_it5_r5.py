#!/usr/bin/env python3
"""Iteration 5, route R5 (entry 163): cross-iteration synthesis and R2 calibration figure.

Renders ``figures/it5/r5-cross-iteration.{svg,html}`` + ``.provenance.json`` from
``ressources/track2/it5/unified/unified_summary.json``:

* Panel (a): Uncalibrated (It5 R4, ``w_R2 = 1.00``) vs. Hierarchy-Calibrated (It6 R5,
  ``w_R2 = 0.25``) utility across the key Track 2 candidates, showing how Rung-3 in-vivo
  ``Bub1b^{H/H}`` mouse rescues (``NMN`` 0.480, approved ``NIACIN``/``NICOTINAMIDE`` 0.192)
  overtake R2's single-line screen residuals (``GLICLAZIDE``/``MIGALASTAT`` 0.700 -> 0.175).
* Panel (b): 20-step calibration sweep over ``w_R2 in [0.05, 1.00]``, marking the overall
  flip boundary (``w_R2* = 0.686``) and FDA-approved flip boundary (``w_R2* = 0.274``) while
  showing that ``EVPI = 0.1800`` and ``EVSI(chx_chase_blot) = 0.106-0.124`` (59.1-69.1% of
  EVPI) remain strictly positive across the entire parameter range.
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

ENTRY = (
    "docs/iteration5/step-1/methodology/"
    "163-cross-iteration-synthesis-and-calibrated-decision-analysis.md"
)
NOTE = "triage heuristic, not a calibrated posterior"


def render_cross_iteration(summary: dict[str, Any]) -> tuple[go.Figure, str]:
    ledger = {row["drug"]: row for row in summary["ledger"]}
    sweep = summary["sweep"]

    focus_drugs = [
        ("NMN", "NMN (R1|R3, in-vivo mouse, unassessed)"),
        ("DASATINIB", "DASATINIB (it4|it5 twin|prism+R3, inactive)"),
        ("NIACIN", "NIACIN (it2|it4|it5 Rung-3 approved)"),
        ("NICOTINAMIDE", "NICOTINAMIDE (it2|it5 Rung-3 approved)"),
        ("GLICLAZIDE", "GLICLAZIDE (it5 R2 HCT116 screen)"),
        ("MIGALASTAT", "MIGALASTAT (it5 R2 HCT116 screen)"),
        ("BORTEZOMIB", "BORTEZOMIB (it2|it5 R1|R2|R3 stability)"),
        ("ROMIDEPSIN", "ROMIDEPSIN (it4|it5 R3 HDAC)"),
        ("VALPROIC ACID", "VALPROIC ACID (it2|it5 R3 HDAC)"),
    ]
    labels = [label for _, label in reversed(focus_drugs)]
    uncal_vals = []
    cal_vals = []
    for key, _ in reversed(focus_drugs):
        row = ledger[key]
        if key == "DASATINIB":
            uncal_vals.append(float(row["uncalibrated_u_inactive"]))
            cal_vals.append(float(row["calibrated_u_inactive"]))
        else:
            uncal_vals.append(float(row["uncalibrated_u_unstable"]))
            cal_vals.append(float(row["calibrated_u_unstable"]))

    fig = make_subplots(
        rows=1,
        cols=2,
        column_widths=[0.48, 0.52],
        horizontal_spacing=0.12,
        subplot_titles=(
            "(a) State utility: Uncalibrated R4 vs. Calibrated R5 (w_R2 = 0.25)",
            "(b) Route-weight sweep (w_R2 in [0.05, 1.00]): leader flips vs. VOI invariance",
        ),
    )

    fig.add_trace(
        go.Bar(
            y=labels,
            x=uncal_vals,
            orientation="h",
            name="Uncalibrated R4 (w_R2 = 1.00)",
            marker=dict(color=RAW.fill, line=dict(color=RAW.line, width=1.2)),
            text=[f"{v:.3f}" for v in uncal_vals],
            textposition="outside",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(
            y=labels,
            x=cal_vals,
            orientation="h",
            name="Calibrated R5 (w_R2 = 0.25)",
            marker=dict(color=GOOD.fill, line=dict(color=GOOD.line, width=1.2)),
            text=[f"{v:.3f}" for v in cal_vals],
            textposition="outside",
        ),
        row=1,
        col=1,
    )

    xs = [float(r["r2_route_weight"]) for r in sweep]
    r2_u = [float(r["r2_effective_unstable_max"]) for r in sweep]
    r3_u = [float(r["r3_effective_unstable_max"]) for r in sweep]
    evpis = [float(r["evpi"]) for r in sweep]
    evsis = [float(r["evsi_blot_chx"]) for r in sweep]

    fig.add_trace(
        go.Scatter(
            x=xs,
            y=r2_u,
            mode="lines+markers",
            name="R2 screen riser u_unstable (GLICLAZIDE / MIGALASTAT = 0.70 w_R2)",
            line=dict(color=BAD.line, width=2.5, dash="dash"),
            marker=dict(size=6, color=BAD.line),
        ),
        row=1,
        col=2,
    )
    fig.add_trace(
        go.Scatter(
            x=xs,
            y=[0.480 for _ in xs],
            mode="lines",
            name="In-vivo mouse rescue u_unstable (NMN = 0.480)",
            line=dict(color=GOOD.line, width=2.5),
        ),
        row=1,
        col=2,
    )
    fig.add_trace(
        go.Scatter(
            x=xs,
            y=r3_u,
            mode="lines",
            name="Approved R3 rescue u_unstable (NIACIN / NICOTINAMIDE = 0.192)",
            line=dict(color=MACHINE.line, width=2.5),
        ),
        row=1,
        col=2,
    )
    fig.add_trace(
        go.Scatter(
            x=xs,
            y=evpis,
            mode="lines",
            name="EVPI = 0.1800 (100% on missense_class across all w_R2)",
            line=dict(color=DECISION.line, width=2.2, dash="dot"),
        ),
        row=1,
        col=2,
    )
    fig.add_trace(
        go.Scatter(
            x=xs,
            y=evsis,
            mode="lines+markers",
            name="EVSI(chx_chase_blot) = 0.106–0.124 (59.1%–69.1% of EVPI)",
            line=dict(color=DECISION.line, width=3.0),
            marker=dict(size=6, color=DECISION.fill, line=dict(color=DECISION.line, width=1.2)),
        ),
        row=1,
        col=2,
    )

    fig.add_vline(
        x=0.2743,
        line_dash="dot",
        line_color=MACHINE.line,
        row=1,
        col=2,
    )
    fig.add_vline(
        x=0.6857,
        line_dash="dot",
        line_color=GOOD.line,
        row=1,
        col=2,
    )
    fig.add_annotation(
        x=0.285,
        y=0.66,
        text="<b>Approved flip w_R2* = 0.274</b><br>(NIACIN / NICOTINAMIDE > GLICLAZIDE)",
        showarrow=False,
        xanchor="left",
        align="left",
        font=dict(size=11, color=MACHINE.line),
        row=1,
        col=2,
    )
    fig.add_annotation(
        x=0.70,
        y=0.34,
        text="<b>Overall flip w_R2* = 0.686</b><br>(NMN > GLICLAZIDE)",
        showarrow=False,
        xanchor="left",
        align="left",
        font=dict(size=11, color=GOOD.line),
        row=1,
        col=2,
    )

    fig.update_xaxes(title_text=f"State utility ({NOTE})", range=[0, 0.82], row=1, col=1)
    fig.update_xaxes(
        title_text="R2 route weight w_R2 (proteome screen scale)", range=[0.02, 1.03], row=1, col=2
    )
    fig.update_yaxes(title_text="Utility / Value of Information", range=[0, 0.78], row=1, col=2)

    fig.update_layout(
        title=dict(
            text=(
                "Cross-iteration Track 2 synthesis (Iterations 2, 4, 5): "
                "hierarchy calibration flips the drug rank while the Western "
                "blot's EVSI stays invariant"
            ),
            x=0.02,
        ),
        barmode="group",
        legend=dict(orientation="h", y=-0.26, x=0.0, yanchor="top"),
        margin=dict(l=290, r=40, t=90, b=170),
    )
    leg = legend_line(
        GOOD,
        MACHINE,
        DECISION,
        RAW,
        BAD,
        extra=(
            "panel (a) bars compare uncalibrated R4 (w_R2=1.00) vs calibrated R5 (w_R2=0.25); "
            "panel (b) sweeps w_R2 in [0.05, 1.00] showing leader flips at w_R2*=0.686 and "
            "0.274 while EVPI=0.1800 and EVSI(chx_chase_blot)=0.106-0.124 stay strictly positive"
        ),
    )
    return fig, leg


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--work", type=Path, default=Path("ressources/track2/it5/unified"))
    ap.add_argument("--out", type=Path, default=Path("figures/it5"))
    ap.add_argument("--preview", type=Path, default=Path("build/it5/r5/preview"))
    args = ap.parse_args()

    install_template()
    source = args.work / "unified_summary.json"
    summary = json.loads(source.read_text(encoding="utf-8"))
    fig, leg = render_cross_iteration(summary)

    args.out.mkdir(parents=True, exist_ok=True)
    args.preview.mkdir(parents=True, exist_ok=True)
    svg = args.out / "r5-cross-iteration.svg"
    fig.write_image(svg, format="svg", width=1360, height=580)
    fig.write_image(
        args.preview / "r5-cross-iteration.png", format="png", width=1360, height=580, scale=2
    )
    fig.write_html(svg.with_suffix(".html"), include_plotlyjs="cdn", full_html=True)

    manifest = {
        **provenance.envelope(svg.stem, "tools/render_it5_r5.py"),
        "inputs": [
            {"path": provenance.repo_relative(source), "sha256": provenance.digest(source)[0]}
        ],
        "entry": ENTRY,
        "legend": leg,
        "wording": NOTE,
        "patient_data": (
            "none: drug names, route weights, utilities, and VOI metrics; no genomic coordinates"
        ),
    }
    provenance.write(manifest, svg.with_suffix(".provenance.json"))
    print(f"wrote {provenance.repo_relative(svg)}\n  {leg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
