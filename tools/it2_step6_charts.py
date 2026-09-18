"""The chart shapes step 6's exhibits are drawn with, separated from what they mean.

One bounded concern: every function here takes rows from ``analysis.json`` and returns a
``plotly`` figure. The captions, the legends and the decision about which exhibits exist live
in ``tools/render_it2_step6_figures.py``, because those are claims about the data and these
are only shapes.

Two conventions, both forced by the data rather than chosen:

* **A rank a route never gave is drawn as a hole, not as a large number.** Reciprocal rank
  fusion gives an unlisted candidate the same placeholder rank everywhere; colouring that
  like a real rank would turn silence into agreement, which is the one thing these figures
  exist to prevent.
* **Ranks run best at the top.** Plotly's categorical y-axis builds upwards, so every
  horizontal chart here reverses its rows explicitly rather than leaving the reader to
  discover that rank 1 is at the bottom.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import plotly.graph_objects as go

from mva.render import theme

#: Left margin for the horizontal charts: a rank, a gene symbol and its allele classes.
LABEL_MARGIN = 330

#: Fused ranks drawn per figure. More rows than this is a download, not a figure.
ROWS = 20

#: The rank a route gives everything it never listed. Drawn as absent, never as a number.
ABSENT = 51


def _label(row: dict) -> str:
    """A y-axis label unique to the *pair*, not to its gene.

    Plotly merges categorical rows that share a label, and rank inheritance puts eleven pairs
    of one gene at one fused rank — so "#2 CLCNKB" eleven times silently collapses into a
    single row and the cells of ten pairs land on top of each other. The alleles go in the
    label for that reason, not for decoration.
    """
    alleles = str(row["pair_id"]).split("|", 1)[1].replace("|", " + ").rstrip(" +")
    return f"#{row['fused_rank']} {row['gene']} · {alleles}"


def matrix_figure(cells: list[dict], routes: list[dict]) -> go.Figure:
    """Routes against the leading pairs: where each instrument put each candidate."""
    order = [r["route"] for r in sorted(routes, key=lambda r: (not r["admitted"], r["route"]))]
    pairs: dict[str, dict] = {}
    for cell in cells:
        if int(cell["fused_rank"]) <= ROWS:
            pairs.setdefault(cell["pair_id"], cell)
    rows = sorted(pairs.values(), key=lambda r: -int(r["fused_rank"]))
    by_key = {(c["pair_id"], c["route"]): c for c in cells}

    z: list[list[int | None]] = []
    text: list[list[str]] = []
    for row in rows:
        found: list[dict | None] = [by_key.get((row["pair_id"], route)) for route in order]
        # A cell the route never listed carries no rank at all: ``None`` in ``z`` so the
        # heatmap leaves a hole, and the words in ``text`` so the hole says what it is.
        z.append([None if c is None or c["defaulted"] else int(c["route_rank"]) for c in found])
        text.append(
            [
                "not listed"
                if c is None or c["defaulted"]
                else f"{int(c['route_rank'])}{'*' if c['inherited'] else ''}"
                for c in found
            ]
        )

    figure = go.Figure(
        go.Heatmap(
            z=z,
            x=[
                r if next(q["admitted"] for q in routes if q["route"] == r) else f"{r} (w 0)"
                for r in order
            ],
            y=[_label(row) for row in rows],
            text=text,
            texttemplate="%{text}",
            textfont={"size": 10},
            hovertemplate="%{y}<br>%{x}: %{text}<extra></extra>",
            colorscale=[
                [0.0, theme.GOOD.line],
                [0.05, theme.DECISION.line],
                [1.0, theme.MUTED.fill],
            ],
            zmin=1,
            zmax=50,
            showscale=False,
            xgap=2,
            ygap=2,
        )
    )
    figure.update_layout(
        margin={"l": LABEL_MARGIN, "r": 20, "t": 10, "b": 50},
        plot_bgcolor=theme.MUTED.fill,
        yaxis={"automargin": True, "tickfont": {"size": 10}},
    )
    return figure


def leaveout_figure(stability: list[dict]) -> go.Figure:
    """Where the all-routes leader lands once each route is silenced."""
    rows = sorted(stability, key=lambda r: (r["leader_rank"] is None, -(r["leader_rank"] or 0)))
    values = [r["leader_rank"] if r["leader_rank"] is not None else ABSENT * 2 for r in rows]
    figure = go.Figure(
        go.Bar(
            x=values,
            y=[f"without {r['removed']}" for r in rows],
            orientation="h",
            marker={
                "color": [
                    theme.GOOD.line if r["leader_kept_rank_one"] else theme.BAD.line for r in rows
                ]
            },
            text=[
                "rank 1 — unchanged"
                if r["leader_kept_rank_one"]
                else f"falls to rank {r['leader_rank'] or 'outside the table'}"
                for r in rows
            ],
            textposition="outside",
            hovertemplate="%{y}: %{text}<extra></extra>",
        )
    )
    figure.update_layout(
        margin={"l": 170, "r": 160, "t": 10, "b": 45},
        xaxis={"title": {"text": "fused rank of the all-routes leader"}, "rangemode": "tozero"},
        yaxis={"automargin": True},
        showlegend=False,
    )
    return figure


def evidence_figure(evidence: list[dict]) -> go.Figure:
    """Which of the four disjoint sources speak for each leading pair."""
    rows = [r for r in evidence if int(r["fused_rank"]) <= ROWS][:12]
    rows = list(reversed(rows))
    inputs = (
        ("has_hpo", "HPO terms", theme.RAW.line),
        ("has_vcf", "the VCF", theme.MACHINE.line),
        ("has_reads", "the raw reads", theme.GOOD.line),
        ("has_literature", "the literature", theme.DECISION.line),
    )
    figure = go.Figure()
    for field, label, colour in inputs:
        figure.add_bar(
            x=[1 if row[field] else 0 for row in rows],
            y=[_label(row) for row in rows],
            name=label,
            orientation="h",
            marker={"color": colour},
            hovertemplate=f"%{{y}} — {label}<extra></extra>",
        )
    figure.update_layout(
        barmode="stack",
        margin={"l": LABEL_MARGIN, "r": 20, "t": 10, "b": 45},
        xaxis={
            "title": {"text": "disjoint sources speaking for the pair"},
            "dtick": 1,
            "range": [0, 4],
        },
        yaxis={"automargin": True, "tickfont": {"size": 10}},
        legend={"orientation": "h", "y": -0.22},
    )
    return figure


def weights_figure(leaders: list[dict]) -> go.Figure:
    """Equal weights against measured-error-rate weights, for the head of the ranking."""
    rows = [r for r in leaders if r["rank_sensitivity"] is not None][:ROWS]
    rows = list(reversed(rows))
    figure = go.Figure()
    figure.add_bar(
        x=[int(r["fused_rank"]) for r in rows],
        y=[_label(r) for r in rows],
        name="equal weights",
        orientation="h",
        marker={"color": theme.MACHINE.line},
    )
    figure.add_bar(
        x=[int(r["rank_sensitivity"]) for r in rows],
        y=[_label(r) for r in rows],
        name="measured-error-rate weights",
        orientation="h",
        marker={"color": theme.DECISION.line},
    )
    figure.update_layout(
        barmode="group",
        margin={"l": LABEL_MARGIN, "r": 20, "t": 10, "b": 45},
        xaxis={"title": {"text": "fused rank (lower is better)"}, "rangemode": "tozero"},
        yaxis={"automargin": True, "tickfont": {"size": 10}},
        legend={"orientation": "h", "y": -0.22},
    )
    return figure


def reach_figure(reach: list[dict]) -> go.Figure:
    """How far down the fused ranking each class of gene sits — the fusion's decoy null."""
    colours = {"target": theme.GOOD.line, "decoy": theme.BAD.line, "neither": theme.MUTED.line}
    rows = sorted(reach, key=lambda r: r["best_rank"])
    figure = go.Figure()
    figure.add_bar(
        x=[r["class"] for r in rows],
        y=[r["best_rank"] for r in rows],
        name="best fused rank",
        marker={"color": [colours.get(r["class"], theme.MUTED.line) for r in rows]},
        text=[f"best {r['best_rank']}" for r in rows],
        textposition="outside",
    )
    figure.add_scatter(
        x=[r["class"] for r in rows],
        y=[r["median_rank"] for r in rows],
        name="median fused rank",
        mode="markers+text",
        marker={"color": theme.INK, "size": 11, "symbol": "diamond"},
        text=[f"median {r['median_rank']:.0f}" for r in rows],
        textposition="top center",
    )
    figure.update_layout(
        margin={"l": 70, "r": 20, "t": 10, "b": 45},
        yaxis={"title": {"text": "fused rank (lower is better)"}, "rangemode": "tozero"},
        legend={"orientation": "h", "y": -0.22},
    )
    return figure
