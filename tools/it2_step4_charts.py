"""The chart shapes step 4's exhibits are drawn with, separated from what they mean.

One bounded concern: every function here takes rows from ``analysis.json`` and returns a
``plotly`` figure. The captions, the legends and the decisions about which exhibits exist
live in ``tools/render_it2_step4_figures.py``, because those are claims about the data and
these are only shapes.

Every ratio is drawn on a **log axis**. The ordering spans eleven orders of magnitude — the
leader at 3.4e5 against a median gene at 0.01 — and a linear axis would render every gene
but the top three as a flat line at zero.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import plotly.graph_objects as go

from mva.render import theme

#: Left margin for the horizontal charts. Their category labels are a gene symbol with a
#: shape and a tier attached — "RAI1  (compound, mechanism-term)" — so a word-width margin
#: clips them. Set from the longest label actually drawn, not guessed.
LABEL_MARGIN = 260

#: Right margin for the horizontal charts: the outside text is a thousands-separated ratio
#: up to seven characters wide, and a short margin truncates the leader's own number.
VALUE_MARGIN = 120

#: Ratio of 1 — the line above which evidence argues for a gene and below which against it.
NEUTRAL = 1.0


def _log(value: float | None, floor: float = 1e-6) -> float:
    return math.log10(max(float(value or floor), floor))


def leaders_figure(leaders: list[dict]) -> go.Figure:
    """The top of the ordering, coloured by where each gene came from.

    Green for a gene the symptoms nominated, purple for one nobody has curated, grey for a
    decoy. The decoys are on the same axis deliberately: they went through the identical
    scoring, and a ranking that cannot show where its controls landed is asking to be taken
    on trust.
    """
    rows = list(reversed(leaders))
    colours = []
    for row in rows:
        if row.get("is_decoy"):
            colours.append(theme.BAD.fill)
        elif row.get("is_target"):
            colours.append(theme.GOOD.fill)
        elif row.get("curated"):
            colours.append(theme.MACHINE.fill)
        else:
            colours.append(theme.RAW.fill)
    labels = []
    for row in rows:
        origin = row.get("tier") or ("decoy" if row.get("is_decoy") else "no tier")
        labels.append(f"{row['gene']}  ({row['shape']}, {origin})")
    figure = go.Figure(
        go.Bar(
            x=[_log(row["combined_lr"]) for row in rows],
            y=labels,
            orientation="h",
            marker_color=colours,
            marker_line_color=theme.MUTED.line,
            text=[f"{float(row['combined_lr']):,.0f}" for row in rows],
            textposition="outside",
            hovertemplate="%{y}<br>likelihood ratio %{text}<extra></extra>",
        )
    )
    figure.update_layout(
        xaxis_title="log₁₀ likelihood ratio",
        margin={"l": LABEL_MARGIN, "r": VALUE_MARGIN, "t": 10, "b": 40},
        showlegend=False,
    )
    figure.add_vline(x=0, line_dash="dot", line_color=theme.MUTED.line)
    return figure


def decomposition_figure(row: dict) -> go.Figure:
    """The leading pair's arithmetic, term by term, as the waterfall it actually is.

    Each bar is one lane's contribution in log₁₀, so the bars add up to the total rather
    than merely sitting beside it. A damped lane is drawn at zero with its name kept, which
    is the point: the reader sees that ClinVar and a missense predictor were both consulted
    and only one was counted.
    """
    terms = [
        (name, float(value))
        for name, value in (
            pair.split("=", 1) for pair in str(row.get("terms", "")).split(";") if "=" in pair
        )
    ]
    names = [name for name, _ in terms]
    values = [_log(value, 1e-9) for _, value in terms]
    figure = go.Figure(
        go.Waterfall(
            orientation="v",
            measure=["relative"] * len(values) + ["total"],
            x=[*names, "combined"],
            y=[*values, 0],
            connector={"line": {"color": theme.MUTED.line}},
            increasing={"marker": {"color": theme.GOOD.fill}},
            decreasing={"marker": {"color": theme.BAD.fill}},
            totals={"marker": {"color": theme.MACHINE.fill}},
        )
    )
    figure.update_layout(
        yaxis_title="log₁₀ contribution",
        xaxis_tickangle=-45,
        margin={"l": 70, "r": 20, "t": 10, "b": 140},
        showlegend=False,
    )
    return figure


def groups_figure(groups: list[dict]) -> go.Figure:
    """Where each class of gene sits, median and ninetieth percentile side by side.

    Two bars per class rather than one, because a median says where the bulk is and a top
    decile says whether anything unusual happened; the decoys are the row the other bars are
    read against.
    """
    order = ["core", "mechanism-term", "net", "decoy", "curated-other", "uncurated-other"]
    rows = sorted(
        groups, key=lambda row: order.index(row["grouping"]) if row["grouping"] in order else 99
    )
    labels = [f"{row['grouping']}  (n={int(row['genes']):,})" for row in rows]
    figure = go.Figure(
        [
            go.Bar(
                name="median gene",
                x=labels,
                y=[_log(row["median_lr"]) for row in rows],
                marker_color=theme.MACHINE.fill,
                marker_line_color=theme.MACHINE.line,
            ),
            go.Bar(
                name="90th percentile",
                x=labels,
                y=[_log(row["p90_lr"]) for row in rows],
                marker_color=theme.GOOD.fill,
                marker_line_color=theme.GOOD.line,
            ),
        ]
    )
    figure.update_layout(
        barmode="group",
        yaxis_title="log₁₀ likelihood ratio",
        margin={"l": 70, "r": 20, "t": 10, "b": 90},
    )
    figure.add_hline(y=0, line_dash="dot", line_color=theme.MUTED.line)
    return figure


def lanes_figure(lanes: list[dict]) -> go.Figure:
    """Which tool actually spoke, per consequence class — the coverage, not the calibration.

    A lane with a published calibration that answers for one allele in fifty contributed
    almost nothing to the ordering, and that is a fact about this run rather than about the
    tool.
    """
    rows = sorted(lanes, key=lambda row: int(row["allele_slots"]), reverse=True)[:12]
    rows.reverse()
    palette = {
        "alphamissense": theme.SEQUENCE[1],
        "spliceai": theme.SEQUENCE[0],
        "clinvar": theme.SEQUENCE[2],
        "consequence": theme.SEQUENCE[3],
        "no lane spoke": theme.MUTED.fill,
    }
    figure = go.Figure(
        go.Bar(
            x=[int(row["allele_slots"]) for row in rows],
            y=[f"{row['lane_class']} → {row['scored_by']}" for row in rows],
            orientation="h",
            marker_color=[palette.get(str(row["scored_by"]), theme.MUTED.fill) for row in rows],
            text=[f"{float(row['percent']):.1f}%" for row in rows],
            textposition="outside",
        )
    )
    figure.update_layout(
        xaxis_title="allele slots the lane spoke for",
        margin={"l": LABEL_MARGIN, "r": VALUE_MARGIN, "t": 10, "b": 40},
        showlegend=False,
    )
    return figure


def phenotype_bins_figure(bins: list[dict]) -> go.Figure:
    """The measured recall curve, read as what a rank is worth.

    The step's one methodological liberty, drawn rather than described: each bar is the
    fraction of held-out causal genes that landed in that band of ranks divided by the
    fraction of all genes the band contains. Above 1 the rank is evidence for a gene; below
    it, against.
    """
    labels = [f"{int(row['low']) + 1}–{int(row['high'])}" for row in bins]
    values = [_log(row["likelihood_ratio"]) for row in bins]
    colours = [theme.GOOD.fill if value > 0 else theme.BAD.fill for value in values]
    figure = go.Figure(
        go.Bar(
            x=labels,
            y=values,
            marker_color=colours,
            marker_line_color=theme.MUTED.line,
            text=[f"{float(row['likelihood_ratio']):.2f}×" for row in bins],
            textposition="outside",
        )
    )
    figure.update_layout(
        xaxis_title="rank the symptom ranker gave the gene",
        yaxis_title="log₁₀ likelihood ratio",
        margin={"l": 70, "r": 20, "t": 10, "b": 60},
        showlegend=False,
    )
    figure.add_hline(y=0, line_dash="dot", line_color=theme.MUTED.line)
    return figure


def null_figure(buckets: list[dict], observed: float) -> go.Figure:
    """The permuted draws as a distribution, with the observed leader marked on it.

    Each bar is how many random seven-term sets produced a top ratio in that band. The
    dashed line is what the child's own terms produced. The distance between them is the
    result; the p-value is only that distance counted.
    """
    figure = go.Figure(
        go.Bar(
            x=[(float(row["low"]) + float(row["high"])) / 2 for row in buckets],
            y=[int(row["draws"]) for row in buckets],
            marker_color=theme.MUTED.fill,
            marker_line_color=theme.MUTED.line,
            name="random term sets",
        )
    )
    figure.add_vline(
        x=_log(observed),
        line_dash="dash",
        line_color=theme.GOOD.line,
        annotation_text="the child's own terms",
        annotation_position="top left",
    )
    figure.update_layout(
        xaxis_title="log₁₀ top likelihood ratio reached by the run",
        yaxis_title="permuted draws",
        margin={"l": 70, "r": 20, "t": 10, "b": 50},
        showlegend=False,
    )
    return figure


def shapes_figure(shapes: list[dict]) -> go.Figure:
    """How many hypotheses of each shape exist — the denominator every ratio is quoted against.

    The ``single`` bar is the one a hard filter would have deleted outright: a gene with one
    damaging allele and no partner, kept at the square root of its evidence.
    """
    rows = sorted(shapes, key=lambda row: int(row["hypotheses"]), reverse=True)
    figure = go.Figure(
        go.Bar(
            x=[row["shape"] for row in rows],
            y=[int(row["hypotheses"]) for row in rows],
            marker_color=[
                theme.SEQUENCE[index % len(theme.SEQUENCE)] for index in range(len(rows))
            ],
            text=[f"{int(row['hypotheses']):,}<br>{int(row['genes']):,} genes" for row in rows],
            textposition="outside",
        )
    )
    figure.update_layout(
        yaxis_title="hypotheses scored",
        margin={"l": 70, "r": 20, "t": 10, "b": 40},
        showlegend=False,
    )
    return figure


def ablation_figure(combined: list[dict], genotype_only: list[dict]) -> go.Figure:
    """What the DNA alone would have nominated, against what the two routes together did.

    Not a null — a control. It answers the question a reader of a genome-wide ranking
    actually has: how much of this ordering is the symptoms, and how much is the DNA?
    """
    ranks = {row["gene"]: index + 1 for index, row in enumerate(genotype_only)}
    rows = [row for row in combined if row["gene"] in ranks][:12]
    rows.reverse()
    figure = go.Figure(
        [
            go.Bar(
                name="both routes",
                y=[row["gene"] for row in rows],
                x=[_log(row["combined_lr"]) for row in rows],
                orientation="h",
                marker_color=theme.GOOD.fill,
                marker_line_color=theme.GOOD.line,
            ),
            go.Bar(
                name="DNA alone (phenotype lane = 1)",
                y=[row["gene"] for row in rows],
                x=[_log(genotype_only[ranks[row["gene"]] - 1]["lr"]) for row in rows],
                orientation="h",
                marker_color=theme.MACHINE.fill,
                marker_line_color=theme.MACHINE.line,
            ),
        ]
    )
    figure.update_layout(
        barmode="group",
        xaxis_title="log₁₀ likelihood ratio",
        margin={"l": LABEL_MARGIN, "r": VALUE_MARGIN, "t": 10, "b": 40},
    )
    return figure
