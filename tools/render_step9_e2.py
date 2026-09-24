#!/usr/bin/env python3
"""Step 9, E2: the child's phenotype twin among MGI mice. Three figures (entry 150).

**a — rank.** Every Bub1b genotype's percentile among 76,699 MGI genotypes (log axis, lower =
closer to the top), for the two pre-registered rollups. Colour = MGI allele class. The grey band
is the central 90 % of where the *best* Bub1b genotype lands for 1,000 IC-matched random term
sets; the dashed lines are H085's 5 % prediction and 25 % refutation thresholds.

**b — why.** The child's 8 HPO terms x the MP terms of the two genotypes the rollups disagree
on (H/H hypomorph vs K243R/+ knock-in). Cell = Resnik similarity (nats) of the pair.

**c — controls.** Each disease's causal gene: percentile of its best genotype for 20 draws of 8
of the disease's own HPO terms (dots) and their median (bar), beside the child -> Bub1b result.

**Source.** ``ressources/phenotype/phenotype_twin.json`` (``tools/phenotype_twin.py run``).

Usage::

    uv run python tools/render_step9_e2.py

Outputs ``figures/it4/step9-e2-{rank,terms,controls}.{svg,html}`` + ``.provenance.json``; prints
the legend line to paste under each figure.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SOURCE = Path("ressources/phenotype/phenotype_twin.json")
OUT = Path("figures/it4")
STUDY = "with-parental"
ENTRY = "docs/iteration4/step-9/methodology/150-the-childs-phenotype-twin-among-mgi-mice.md"
SHORT = {
    "HP:0002859": "rhabdomyosarcoma",
    "HP:0000121": "nephrocalcinosis",
    "HP:0004322": "short stature",
    "HP:0001508": "failure to thrive",
    "HP:0003202": "skeletal muscle atrophy",
    "HP:0001622": "premature birth",
    "HP:0001518": "small for gest. age",
    "HP:0200067": "parental miscarriage",
}


def _label(composition: str) -> str:
    """Allele pairs of Bub1b only, shortened; other genes named after a plus."""
    parts = composition.split(",")
    head = parts[0].replace("Bub1b<", "").replace(">", "")
    return head + (" + " + ", ".join(p.split("<")[0] for p in parts[1:]) if parts[1:] else "")


def _save(fig: Any, name: str, width: int, height: int) -> Path:
    path = OUT / f"step9-e2-{name}.svg"
    fig.write_image(path, format="svg", width=width, height=height)
    fig.write_html(path.with_suffix(".html"), include_plotlyjs="cdn", full_html=True)
    return path


def rank_figure(data: dict[str, Any]) -> Any:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    from mva.render.theme import BAD, GOOD, MACHINE, MUTED

    study = data["studies"][STUDY]
    hue = {"hypomorph": GOOD, "null": BAD, "knock-in": MACHINE, "other": MUTED}
    rows = [g for g in study["genotypes"] if g["symmetric_score"] > 0]
    fig = make_subplots(
        rows=1,
        cols=2,
        shared_yaxes=True,
        horizontal_spacing=0.04,
        subplot_titles=("symmetric BMA (primary)", "Phenodigm-style"),
    )
    labels = [f"{_label(g['composition'])} ({g['genotype_id']})" for g in rows]
    for col, metric in ((1, "symmetric"), (2, "phenodigm")):
        for cls, h in hue.items():
            pick = [i for i, g in enumerate(rows) if g["allele_class"] == cls]
            if not pick:
                continue
            fig.add_trace(
                go.Scatter(
                    x=[rows[i][f"{metric}_percentile"] for i in pick],
                    y=[labels[i] for i in pick],
                    mode="markers",
                    marker={"size": 11, "color": h.fill, "line": {"color": h.line, "width": 1.5}},
                    name=cls,
                    legendgroup=cls,
                    showlegend=col == 1,
                    text=[f"rank {rows[i][f'{metric}_rank']:,}" for i in pick],
                    hovertemplate="%{y}<br>%{x:.2f} %<br>%{text}<extra></extra>",
                ),
                row=1,
                col=col,
            )
    # Shapes after the traces: plotly skips subplots that are still empty.
    for col, metric in ((1, "symmetric"), (2, "phenodigm")):
        pct = sorted(study["null"]["percentiles"][metric])
        lo, hi = pct[len(pct) // 20], pct[len(pct) * 19 // 20]
        fig.add_vrect(
            x0=lo,
            x1=hi,
            fillcolor=MUTED.fill,
            opacity=0.6,
            line_width=0,
            layer="below",
            row=1,
            col=col,
        )
        for x, dash in ((5, "dash"), (25, "dot")):
            fig.add_vline(x=x, line={"color": BAD.line, "dash": dash, "width": 1}, row=1, col=col)
    fig.update_xaxes(type="log", range=[-1.3, 2], title_text="percentile of 76,699 genotypes (log)")
    fig.update_yaxes(categoryorder="array", categoryarray=labels[::-1])
    fig.update_layout(
        margin={"l": 380, "r": 30, "t": 100, "b": 60},
        legend={"y": 1.12, "x": 0.45},
        title="Every Bub1b mouse genotype vs the child's 8 terms",
    )
    return fig


def terms_figure(data: dict[str, Any]) -> Any:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    from mva.render.theme import GOOD, PAPER

    study = data["studies"][STUDY]
    matrices = study["term_matrix"]
    order = [study["best"]["phenodigm"]["genotype_id"], study["best"]["symmetric"]["genotype_id"]]
    titles = [
        f"{_label(matrices[g]['composition'])} — best by {m}"
        for g, m in zip(order, ("Phenodigm-style", "symmetric BMA"), strict=True)
    ]
    widths = [len(matrices[g]["mp"]) for g in order]
    fig = make_subplots(
        rows=1,
        cols=2,
        shared_yaxes=True,
        horizontal_spacing=0.03,
        column_widths=widths,
        subplot_titles=titles,
    )
    rows = [SHORT.get(t, t) for t in study["query"]]
    zmax = max(max(max(r) for r in matrices[g]["values"]) for g in order)
    for col, gid in enumerate(order, start=1):
        m = matrices[gid]
        fig.add_trace(
            go.Heatmap(
                z=m["values"],
                x=m["mp_names"],
                y=rows,
                zmin=0,
                zmax=zmax,
                colorscale=[[0, PAPER], [1, GOOD.line]],
                showscale=col == 2,
                colorbar={"title": "Resnik (nats)"},
                text=[[f"{v:.1f}" if v >= 2 else "" for v in r] for r in m["values"]],
                texttemplate="%{text}",
                hovertemplate="%{y} × %{x}: %{z:.2f}<extra></extra>",
            ),
            row=1,
            col=col,
        )
    fig.update_xaxes(tickangle=-50, tickfont={"size": 10})
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(
        margin={"l": 150, "r": 30, "t": 70, "b": 250},
        title="Which child term meets which mouse term, and how specifically",
    )
    return fig


def controls_figure(data: dict[str, Any]) -> Any:
    import plotly.graph_objects as go

    from mva.render.theme import BAD, GOOD, MACHINE, RAW

    study = data["studies"][STUDY]
    fig = go.Figure()
    names = []
    for c in data["controls"]:
        name = f"{c['disease_name']} → {c['gene']}"
        names.append(name)
        pct = c["percentiles"]["symmetric"]
        med = c["median_percentile"]["symmetric"]
        h = GOOD if med <= 5 else BAD
        fig.add_trace(
            go.Bar(
                x=[med],
                y=[name],
                orientation="h",
                showlegend=False,
                marker={"color": h.fill, "line": {"color": h.line}},
            )
        )
        fig.add_trace(
            go.Scatter(
                x=pct,
                y=[name] * len(pct),
                mode="markers",
                showlegend=False,
                marker={"size": 5, "color": MACHINE.line, "opacity": 0.6},
            )
        )
    child = "the child's 8 terms → Bub1b"
    fig.add_trace(
        go.Bar(
            x=[study["best"]["symmetric"]["percentile"]],
            y=[child],
            orientation="h",
            showlegend=False,
            marker={"color": RAW.fill, "line": {"color": RAW.line}},
        )
    )
    fig.add_vline(x=5, line={"color": BAD.line, "dash": "dash", "width": 1})
    fig.update_xaxes(
        type="log",
        range=[-2, 2],
        title_text="best causal-gene genotype percentile (log; symmetric BMA)",
    )
    fig.update_yaxes(categoryorder="array", categoryarray=[child, *names][::-1])
    fig.update_layout(
        margin={"l": 330, "r": 30, "t": 60, "b": 60},
        barmode="overlay",
        title="Positive controls: does the method find a disease's known mouse gene?",
    )
    return fig


def main() -> int:
    from mva.render.theme import BAD, GOOD, MACHINE, MUTED, RAW, install_template

    install_template()
    data: dict[str, Any] = json.loads(SOURCE.read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    written = [
        _save(rank_figure(data), "rank", 1150, 560),
        _save(terms_figure(data), "terms", 1300, 640),
        _save(controls_figure(data), "controls", 1050, 460),
    ]
    print(
        "rank:    **Legend** — green = hypomorph (H086's prediction); red = null / knockout; "
        f"blue = knock-in; grey band = {MUTED.label}: central 90 % of the null; "
        "dashed red = 5 % (H085 prediction), dotted red = 25 % (refutation)."
    )
    print(
        f"terms:   **Legend** — white to green = Resnik similarity 0 to max ({GOOD.label} "
        "= a specific shared ancestor); blank row = the term found no informative partner."
    )
    print(
        f"controls: **Legend** — green = median ≤ 5 % ({GOOD.label}); red = above ({BAD.label}); "
        f"blue dots = the 20 draws ({MACHINE.label}); purple = the child ({RAW.label}); "
        "dashed = 5 %."
    )
    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()
    for path in written:
        provenance = {
            "name": path.stem,
            "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "built_by": "tools/render_step9_e2.py",
            "code_version": commit,
            "inputs": [
                {"path": str(SOURCE), "sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest()}
            ],
            "study": STUDY,
            "entry": ENTRY,
        }
        path.with_suffix(".provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
