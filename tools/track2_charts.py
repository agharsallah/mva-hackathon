"""The chart shapes step 7's exhibits are drawn with, separated from what they mean.

One bounded concern: every function takes rows from ``build/track2/analysis.json`` and returns
a ``plotly`` figure. Captions, legends and the decision about which exhibits exist live in
``tools/render_track2_figures.py``, because those are claims about the data and these are
only shapes.

Colour discipline, from the dictionary: **green** = a rung high enough to argue (>= 4),
**yellow** = the decision band (rungs 2-3, argued with a stated caveat, and the 0.10
non-specificity line), **red** = set aside (an anti-direction, the standard of care),
**blue** = machinery (counts), **grey** = rung 1, named and never submitted.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import plotly.graph_objects as go

from mva.render import theme

#: Rung → fill colour. Rung 1 is muted on purpose: it is a name, not a candidate.
RUNG_FILL = {
    5: theme.GOOD.fill,
    4: theme.GOOD.fill,
    3: theme.DECISION.fill,
    2: theme.DECISION.fill,
    1: theme.MUTED.fill,
}
#: The pre-registered non-specificity threshold (H049).
JACCARD_LINE = 0.10
#: Rows drawn on the ladder matrix. More than this is a table, not a figure.
MAX_DRUGS = 28


def _fill(row: dict) -> str:
    """Red when set aside; blue when only the automated tests speak (a trial in the tumour,
    not a mechanism finding); otherwise the curated rung's colour."""
    flags = list(row.get("flags") or [])
    if any(f in ("A1", "A2", "standard_of_care") for f in flags):
        return theme.BAD.fill
    if not row.get("curated_rung"):
        return theme.MACHINE.fill
    return RUNG_FILL.get(int(row["rung"]), theme.MUTED.fill)


def _order(rows: list[dict]) -> list[str]:
    """Drugs with a curated result first (by rung), then the automated-only ones."""
    best: dict[str, tuple[int, int]] = {}
    for r in rows:
        curated = 1 if r.get("curated_rung") else 0
        key = (curated, int(r["rung"]))
        best[r["drug_name"]] = max(best.get(r["drug_name"], (0, 0)), key)
    return sorted(best, key=lambda d: (-best[d][0], -best[d][1], d))[:MAX_DRUGS]


def ladder_matrix(rows: list[dict], directions: list[str]) -> go.Figure:
    """Drugs down, directions across, each cell the rung - coloured by what the rung allows."""
    drugs = _order(rows)
    cells = {(r["drug_name"], r["direction_id"]): r for r in rows}
    fig = go.Figure()
    for x, direction in enumerate(directions):
        for y, drug in enumerate(drugs):
            row = cells.get((drug, direction))
            if row is None:
                continue
            fig.add_shape(
                type="rect",
                x0=x - 0.45,
                x1=x + 0.45,
                y0=y - 0.42,
                y1=y + 0.42,
                fillcolor=_fill(row),
                line={"color": theme.PAPER, "width": 1},
            )
            label = str(row["rung"])
            if row.get("proxy"):
                label += "*"
            fig.add_annotation(
                x=x, y=y, text=label, showarrow=False, font={"size": 12, "color": theme.INK}
            )
    fig.update_xaxes(
        tickvals=list(range(len(directions))),
        ticktext=directions,
        range=[-0.6, len(directions) - 0.4],
        side="top",
        showgrid=False,
    )
    fig.update_yaxes(
        tickvals=list(range(len(drugs))),
        ticktext=[d.title() for d in drugs],
        range=[len(drugs) - 0.4, -0.6],
        showgrid=False,
    )
    fig.update_layout(
        template=theme.TEMPLATE_NAME,
        height=max(360, 26 * len(drugs) + 80),
        margin={"l": 220, "r": 20, "t": 50, "b": 20},
    )
    return fig


def rung_funnel(by_rung: dict[str, int], shortlisted: int, total: int) -> go.Figure:
    """How 359 approved drugs shrink to a shortlist: drugs at each best rung, then the cut."""
    rungs = ["5", "4", "3", "2", "1"]
    counts = [int(by_rung.get(r, 0)) for r in rungs]
    labels = [*(f"rung {r}" for r in rungs), "shortlisted"]
    values = [*counts, shortlisted]
    colours = [*(RUNG_FILL[int(r)] for r in rungs), theme.GOOD.fill]
    fig = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker={"color": colours, "line": {"color": theme.INK, "width": 0.5}},
            text=[str(v) for v in values],
            textposition="outside",
        )
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title=f"drugs (of {total} graded)", range=[0, max(values) * 1.18])
    fig.update_layout(template=theme.TEMPLATE_NAME, height=320, margin={"l": 110, "r": 40})
    return fig


def decoy_overlap(rows: list[dict]) -> go.Figure:
    """Jaccard per direction, one bar group per decoy, with the pre-registered line."""
    decoys = sorted({r["decoy"] for r in rows})
    directions = [
        d
        for d in ("D1", "D2", "D3", "D4", "pathway", "all")
        if any(r["direction_id"] == d for r in rows)
    ]
    fig = go.Figure()
    palette = [theme.MACHINE.fill, theme.RAW.fill, theme.MUTED.fill]
    for i, decoy in enumerate(decoys):
        by_dir = {r["direction_id"]: r for r in rows if r["decoy"] == decoy}
        values = [float(by_dir[d]["jaccard"]) if d in by_dir else 0.0 for d in directions]
        fig.add_bar(
            name=decoy,
            x=directions,
            y=values,
            marker={
                "color": palette[i % len(palette)],
                "line": {"color": theme.INK, "width": 0.5},
            },
            text=[f"{v:.2f}" for v in values],
            textposition="outside",
        )
    fig.add_hline(
        y=JACCARD_LINE,
        line={"color": theme.DECISION.line, "dash": "dash"},
        annotation_text="non-specific above 0.10 (H049)",
        annotation_position="top left",
    )
    fig.update_yaxes(title="Jaccard, approved drug sets", rangemode="tozero")
    fig.update_layout(template=theme.TEMPLATE_NAME, barmode="group", height=380)
    return fig


def pediatric_dots(short: list[dict]) -> go.Figure:
    """For each shortlisted drug: label section 8.4, a study admitting children, or neither."""
    names = [r["drug_name"].title() for r in short]
    label = [1 if "label" in r["pediatric_evidence"] else 0 for r in short]
    study = [1 if "study" in r["pediatric_evidence"] else 0 for r in short]
    fig = go.Figure()
    for column, values, colour, title in (
        (0, label, theme.GOOD.fill, "label section 8.4"),
        (1, study, theme.MACHINE.fill, "study admitting children"),
    ):
        fig.add_scatter(
            x=[column] * len(names),
            y=names,
            mode="markers",
            name=title,
            marker={
                "size": 16,
                "color": [colour if v else theme.PAPER for v in values],
                "line": {"color": theme.INK, "width": 1},
            },
        )
    fig.update_xaxes(tickvals=[0, 1], ticktext=["label 8.4", "child study"], range=[-0.6, 1.6])
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(
        template=theme.TEMPLATE_NAME,
        height=max(300, 24 * len(names) + 100),
        margin={"l": 180},
        showlegend=False,
    )
    return fig


def mechanism_literature(short: list[dict], ladder: list[dict]) -> go.Figure:
    """PubMed records per shortlisted drug: with the mechanism, and with the tumour context."""
    hits = {(r["drug_name"], r["direction_id"]): r for r in ladder}
    names, mech, ctx = [], [], []
    for r in short:
        row = hits.get((r["drug_name"], r["direction_id"]), {})
        names.append(r["drug_name"].title())
        mech.append(int(row.get("mechanism_hits") or 0))
        ctx.append(int(row.get("context_hits") or 0))
    fig = go.Figure()
    fig.add_bar(
        name="drug AND mechanism",
        y=names,
        x=mech,
        orientation="h",
        marker={"color": theme.MACHINE.fill},
    )
    fig.add_bar(
        name="drug AND tumour context",
        y=names,
        x=ctx,
        orientation="h",
        marker={"color": theme.RAW.fill},
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title="PubMed records (descriptive, never a rung)", type="log")
    fig.update_layout(
        template=theme.TEMPLATE_NAME,
        barmode="group",
        height=max(300, 26 * len(names) + 100),
        margin={"l": 180},
    )
    return fig


#: What a transfer comparison plots, in reading order: what the pipeline produced, per case.
#: ``candidate_rows`` is left out on purpose - it is an order of magnitude above every other
#: number, and rescaling the axis for it would flatten the rows the figure exists to compare.
TRANSFER_METRICS = (
    ("targets", "target genes"),
    ("approved_drugs", "approved drugs"),
    ("drugs_rung_5", "drugs at best rung 5"),
    ("drugs_rung_1", "drugs at best rung 1"),
    ("shortlist", "shortlist rows"),
    ("do_not", "do-not rows"),
    ("curated_rows", "curated evidence rows"),
)


def transfer_scalability(rows: list[dict]) -> go.Figure:
    """One bar group per count, one bar per case: the same pipeline on two different cases.

    Linear axis and no normalisation: the point is that both cases produced a table of the
    same shape, and a ratio would hide which one is bigger. ``curated evidence rows`` is
    plotted precisely because it is zero for a transfer card - that zero is the boundary of
    what the comparison may claim, not a gap in the data.
    """
    cases = [str(row.get("case") or "") for row in rows]
    palette = [theme.MACHINE.fill, theme.RAW.fill, theme.MUTED.fill]
    labels = [label for _key, label in TRANSFER_METRICS]
    fig = go.Figure()
    for index, row in enumerate(rows):
        values = [int(row.get(key) or 0) for key, _label in TRANSFER_METRICS]
        fig.add_bar(
            name=cases[index],
            y=labels,
            x=values,
            orientation="h",
            marker={
                "color": palette[index % len(palette)],
                "line": {"color": theme.INK, "width": 0.5},
            },
            text=[str(value) for value in values],
            textposition="outside",
            cliponaxis=False,
        )
    widest = max(
        (int(row.get(key) or 0) for row in rows for key, _l in TRANSFER_METRICS), default=1
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title="rows / genes / drugs", range=[0, widest * 1.22], rangemode="tozero")
    fig.update_layout(
        template=theme.TEMPLATE_NAME,
        barmode="group",
        bargap=0.35,
        height=420,
        margin={"l": 190, "r": 40, "t": 20},
        legend={"orientation": "h", "y": -0.18},
    )
    return fig
