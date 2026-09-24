#!/usr/bin/env python3
"""Step 9, E1: the BubR1 stability atlas in three figures.

(a) ``step9-e1-atlas`` — ThermoMPNN ΔΔG along the protein (mean over the 19 substitutions at
    each residue), annotated domains beneath, and the published labelled alleles at their own
    ΔΔG, coloured by class. The child's allele is **not** on this figure.
(b) ``step9-e1-distribution`` — ΔΔG over all 19,950 substitutions, the pre-registered
    top-20 % cut, and the child's value (rounded to 0.1 kcal/mol) as one line.
(c) ``step9-e1-roc`` — ROC of the scores on the labelled alleles (primary and extended sets).

**Sources.** ``ressources/track2/bub1b_atlas.parquet`` (``tools/variant_atlas.py build``),
``build/it4/track2-e1/evaluate.json`` (``evaluate``), ``build/it4/track2-e1/child.json``
(``place``; read for two rounded numbers only). Entry 149.

    uv run python tools/render_step9_e1.py

Outputs ``figures/it4/step9-e1-{atlas,distribution,roc}.{svg,html}`` + one
``.provenance.json`` each; prints each figure's legend line.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

ATLAS = Path("ressources/track2/bub1b_atlas.parquet")
LABELS = Path("ressources/track2/bub1b_published_alleles.tsv")
EVALUATE = Path("build/it4/track2-e1/evaluate.json")
CHILD = Path("build/it4/track2-e1/child.json")
OUT = Path("figures/it4")
PREVIEW = Path("build/it4/track2-e1/preview")
ENTRY = "docs/iteration4/step-9/methodology/149-the-stability-atlas-and-the-childs-missense.md"
#: Domains drawn on the track under panel (a): (label, UniProt/literature feature name).
TRACK = (
    ("TPR (BUB1 N-terminal)", "BUB1 N-terminal"),
    ("KNL1-binding", "Necessary for interaction with KNL1"),
    ("D-box", "D-box"),
    ("GLEBS bound (lit.)", "BUB3-binding (GLEBS) bound"),
    ("pseudokinase", "Protein kinase"),
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(fig: Any, name: str, width: int, height: int, inputs: list[Path], legend: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    PREVIEW.mkdir(parents=True, exist_ok=True)
    svg = OUT / f"step9-e1-{name}.svg"
    fig.write_image(svg, format="svg", width=width, height=height)
    fig.write_image(PREVIEW / f"{name}.png", format="png", width=width, height=height)
    fig.write_html(svg.with_suffix(".html"), include_plotlyjs="cdn", full_html=True)
    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()
    provenance = {
        "name": svg.stem,
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "built_by": "tools/render_step9_e1.py",
        "code_version": commit,
        "inputs": [{"path": str(p), "sha256": _sha(p)} for p in inputs],
        "entry": ENTRY,
        "legend": legend,
        "patient_data": (
            "none on the position axis; panel (b) shows the child's ΔΔG rounded to 0.1 "
            "kcal/mol and its percentile rounded to an integer (from build/, not committed)"
            if name == "distribution"
            else "none"
        ),
    }
    svg.with_suffix(".provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(f"wrote {svg}\n  {legend}")


def atlas_figure(atlas: pl.DataFrame, alleles: list[dict[str, Any]]) -> None:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    from mva.render.theme import BAD, MACHINE, MUTED, legend_line

    per = atlas.group_by("position").agg(pl.mean("ddg"), pl.first("plddt")).sort("position")
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2],
                        vertical_spacing=0.04)  # fmt: skip
    fig.add_trace(
        go.Scatter(x=per["position"], y=per["ddg"], mode="lines", name="mean ΔΔG per residue",
                   line={"color": MACHINE.line, "width": 1}),
        row=1, col=1,
    )  # fmt: skip
    for label, hue in (("abundance-lowering", BAD), ("stable", MACHINE)):
        mine = [a for a in alleles if a["label"] == label]
        fig.add_trace(
            go.Scatter(
                x=[int(a["change"][1:-1]) for a in mine], y=[a["ddg"] for a in mine],
                mode="markers+text", text=[a["change"] for a in mine], textposition="top center",
                marker={"size": 11, "color": hue.fill, "line": {"color": hue.line, "width": 2},
                        "symbol": "circle" if label != "stable" else "square"},
                name=f"published allele: {label}",
            ),
            row=1, col=1,
        )  # fmt: skip
    for i, (label, feature) in enumerate(TRACK):
        spans = (
            atlas.filter(pl.col("features").str.contains(feature, literal=True))
            .group_by("position").len()["position"].sort().to_list()
        )  # fmt: skip
        if not spans:
            continue
        fig.add_trace(
            go.Scatter(x=[spans[0], spans[-1]], y=[i, i], mode="lines+text",
                       line={"color": MUTED.line, "width": 8}, text=[label, ""],
                       textposition="middle left", showlegend=False, hoverinfo="skip"),
            row=2, col=1,
        )  # fmt: skip
    fig.update_yaxes(title_text="ThermoMPNN ΔΔG, kcal/mol (+ = destabilising)", row=1, col=1)
    fig.update_yaxes(visible=False, range=[-0.8, len(TRACK) - 0.2], row=2, col=1)
    fig.update_xaxes(title_text="BubR1 residue (UniProt O60566)", range=[-190, 1060], row=2, col=1)
    fig.update_layout(
        title="BubR1 stability atlas: published MVA alleles on the ΔΔG profile",
        legend={"orientation": "h", "y": -0.2},
        margin={"l": 70, "r": 30},
    )
    legend = legend_line(
        MACHINE, BAD, MUTED,
        extra=("blue line = mean ΔΔG of the 19 substitutions at each residue; red circles = "
               "published abundance-lowering alleles, blue squares = published stable alleles "
               "(each at its own ΔΔG); grey bars = annotated domains. The child's allele is "
               "not drawn"),
    )  # fmt: skip
    _write(fig, "atlas", 1200, 560, [ATLAS, LABELS, EVALUATE], legend)


def distribution_figure(atlas: pl.DataFrame, child: dict[str, Any]) -> None:
    import numpy as np
    import plotly.graph_objects as go

    from mva.render.theme import DECISION, MACHINE, RAW, legend_line

    ddg = atlas["ddg"].to_numpy()
    cut = float(np.percentile(ddg, 80))
    value = round(float(child["ddg"]), 1)
    pct = round(float(child["ddg_percentile"]))
    fig = go.Figure(
        go.Histogram(x=ddg, nbinsx=120, marker={"color": MACHINE.fill,
                     "line": {"color": MACHINE.line, "width": 0.5}}, name="all substitutions")
    )  # fmt: skip
    fig.add_vline(x=cut, line={"color": DECISION.line, "dash": "dash", "width": 2},
                  annotation_text=f"top-20 % cut ({cut:.2f})",
                  annotation_position="top left")  # fmt: skip
    fig.add_vline(x=value, line={"color": RAW.line, "width": 3},
                  annotation_text=f"the child's missense allele: ≈{value:.1f} kcal/mol, "
                                  f"percentile ≈{pct} (top {100 - pct} %)",
                  annotation_position="top right")  # fmt: skip
    fig.update_layout(
        title=f"ΔΔG of all {len(ddg):,} possible BubR1 substitutions",
        xaxis_title="ThermoMPNN ΔΔG, kcal/mol (+ = destabilising)",
        yaxis_title="substitutions", showlegend=False,
    )  # fmt: skip
    legend = legend_line(
        MACHINE, DECISION, RAW,
        extra=("blue bars = every possible substitution; yellow dashed = the pre-registered "
               "top-20 % cut (H084); purple = the child's allele, value rounded to 0.1"),
    )  # fmt: skip
    _write(fig, "distribution", 1000, 460, [ATLAS, CHILD], legend)


def roc_figure(report: dict[str, Any]) -> None:
    import plotly.graph_objects as go

    from mva.render.theme import MUTED, SEQUENCE, legend_line

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", name="chance (AUROC 0.5)",
                             line={"color": MUTED.line, "dash": "dot"}))  # fmt: skip
    series = []
    for set_name, dash in (("primary", "solid"), ("extended", "dash")):
        result = report["sets"][set_name]
        n = f"{result['n_positive']} vs {result['n_negative']}"
        series += [
            (f"ΔΔG, {set_name} ({n})", result["raw"]["ddg"], "auroc", "ci95", "roc", 0, dash),
            (f"ESM1b LLR, {set_name}", result["raw"]["esm1b_llr_negated"], "auroc", "ci95",
             "roc", 1, dash),
            (f"ΔΔG+RSA+pLDDT LOO, {set_name}", result["models"]["ddg+rsa+plddt"], "auroc_loo",
             "ci95_loo", "roc_loo", 4, dash),
        ]  # fmt: skip
    for label, row, key, ci, roc, hue, dash in series:
        x, y = zip(*row[roc], strict=True)
        low, high = row[ci]
        fig.add_trace(go.Scatter(
            x=x, y=y, mode="lines+markers", line={"color": SEQUENCE[hue], "dash": dash,
                                                    "shape": "linear"},
            name=f"{label}: AUROC {row[key]:.2f} [{low:.2f}, {high:.2f}]"))  # fmt: skip
    fig.update_layout(
        title="Do the scores separate abundance-lowering from stable published alleles?",
        xaxis_title="false-positive rate (stable called abundance-lowering)",
        yaxis_title="true-positive rate", legend={"y": -0.25, "orientation": "h"},
        xaxis={"range": [-0.02, 1.02]}, yaxis={"range": [-0.02, 1.02], "scaleanchor": "x"},
    )  # fmt: skip
    legend = legend_line(
        MUTED,
        extra=("blue = raw ThermoMPNN ΔΔG; purple = ESM1b LLR (sequence-only comparator); red = "
               "ridge logistic ΔΔG+RSA+pLDDT, leave-one-out; solid = primary (MVA alleles only), "
               "dashed = extended (+ one non-MVA stable allele); brackets = bootstrap 95 % CI"),
    )  # fmt: skip
    _write(fig, "roc", 900, 760, [EVALUATE], legend)


def main() -> int:
    from mva.render.theme import install_template

    install_template()
    atlas = pl.read_parquet(ATLAS)
    report = json.loads(EVALUATE.read_text())
    atlas_figure(atlas, report["sets"]["extended"]["alleles"])
    distribution_figure(atlas, json.loads(CHILD.read_text())["primary"])
    roc_figure(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
