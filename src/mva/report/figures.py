"""The report's exhibits: the funnel, the genome-wide gene table, the decode table.

Each function takes plain data from :mod:`mva.report.data` and returns one
:class:`~mva.render.figure.Exhibit`, caption and legend included, in the repository palette:
green is the goal, red is lost, yellow a decision, blue machinery, purple the raw input.
"""

from __future__ import annotations

import math

import plotly.graph_objects as go

from ..pipeline.probe_design import Design
from ..render.figure import Exhibit, sized
from ..render.theme import BAD, DECISION, GOOD, MACHINE, MUTED, RAW, legend_line
from .data import Funnel, GeneRow

__all__ = ["decode_table", "funnel_chart", "gene_scatter"]


def funnel_chart(counts: Funnel) -> Exhibit:
    """Every filter with its survivor count, on a log axis so the last stages stay visible."""
    stages = counts.stages()
    labels = [label for label, _ in stages]
    values = [max(value, 1) for _, value in stages]
    colours = [RAW.fill] + [MACHINE.fill] * (len(stages) - 2) + [GOOD.fill]
    lines = [RAW.line] + [MACHINE.line] * (len(stages) - 2) + [GOOD.line]
    figure = go.Figure(
        go.Bar(
            y=labels[::-1],
            x=values[::-1],
            orientation="h",
            marker=dict(color=colours[::-1], line=dict(color=lines[::-1], width=1)),
            text=[f"{value:,}" for _, value in stages][::-1],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>%{x:,} survive<extra></extra>",
        )
    )
    figure.update_layout(
        xaxis=dict(type="log", title="survivors (log scale)", range=[-0.3, 7.2]),
        yaxis=dict(automargin=True),
        margin=dict(l=10, r=80, t=30, b=40),
        showlegend=False,
    )
    return Exhibit(
        slug="track1-funnel",
        title="From five million records to one gene",
        caption=(
            "Each bar is what survives one more filter. The first two cuts are geometry "
            "(is the allele where a protein is encoded?), the next three are annotation "
            "(is it rare, does it change the protein, did the caller trust it?), and the "
            "last four move from alleles to **genes**: which genes hold two such alleles, "
            "which of those carry an allele ClinVar already calls pathogenic, and which "
            "of those the child's symptoms point at. The axis is logarithmic — on a linear "
            "one every bar after the first would be invisible."
        ),
        legend=legend_line(RAW, MACHINE, GOOD, extra="the last bar is the answer the scan gives"),
        figure=sized(figure, 520),
    )


def gene_scatter(rows: list[GeneRow], highlight: str) -> Exhibit:
    """Every gene with a candidate biallelic set, placed by phenotype rank and allele count."""
    shown = [r for r in rows if r.biallelic_pass or r.biallelic_with_rescue]
    uncurated_rank = 1.6 * max((r.phenotype_rank or 0 for r in shown), default=1000)

    def colour(row: GeneRow) -> tuple[str, str]:
        if row.gene == highlight:
            return GOOD.fill, GOOD.line
        if row.n_plp_pass:
            return DECISION.fill, DECISION.line
        if not row.biallelic_pass:
            return MUTED.fill, MUTED.line
        return MACHINE.fill, MACHINE.line

    figure = go.Figure()
    for group, name in ((True, "biallelic on PASS calls"), (False, "only with a rescued call")):
        members = [r for r in shown if r.biallelic_pass is group]
        if not members:
            continue
        figure.add_trace(
            go.Scatter(
                x=[
                    r.phenotype_rank if r.phenotype_rank is not None else uncurated_rank
                    for r in members
                ],
                y=[r.n_pass + r.n_nonpass for r in members],
                mode="markers+text",
                name=name,
                text=[
                    r.gene
                    if (
                        r.gene == highlight
                        or r.n_plp_pass
                        or r.n_lof_pass
                        or (r.phenotype_rank or 10**6) <= 60
                    )
                    else ""
                    for r in members
                ],
                textposition="top center",
                textfont=dict(size=10),
                marker=dict(
                    size=[14 if r.gene == highlight else 9 for r in members],
                    color=[colour(r)[0] for r in members],
                    line=dict(color=[colour(r)[1] for r in members], width=1.2),
                    symbol="circle" if group else "circle-open",
                ),
                customdata=[
                    (r.gene, r.n_pass, r.n_nonpass, r.n_lof_pass, r.n_plp_pass, r.consequences)
                    for r in members
                ],
                hovertemplate="<b>%{customdata[0]}</b><br>phenotype rank %{x}<br>"
                "%{customdata[1]} PASS + %{customdata[2]} filtered candidate alleles<br>"
                "LoF %{customdata[3]} · ClinVar P/LP %{customdata[4]}<br>"
                "%{customdata[5]}<extra></extra>",
            )
        )
    # Shapes and annotations on a log axis take log10 coordinates, not data values.
    figure.add_vline(x=math.log10(30), line=dict(color=DECISION.line, dash="dot", width=1))
    figure.add_annotation(
        x=math.log10(30),
        y=1.02,
        yref="paper",
        text="top 30 by symptoms",
        showarrow=False,
        font=dict(size=10, color=DECISION.line),
        xanchor="left",
    )
    figure.add_annotation(
        x=math.log10(uncurated_rank),
        y=1.02,
        yref="paper",
        text="no HPO curation",
        showarrow=False,
        font=dict(size=10, color=MUTED.line),
        xanchor="center",
    )
    figure.update_layout(
        xaxis=dict(
            type="log",
            title="phenotype rank on the child's own HPO terms (log; uncurated genes parked right)",
        ),
        yaxis=dict(title="rare protein-altering alleles in the gene", rangemode="tozero"),
        legend=dict(orientation="h", y=-0.2),
        margin=dict(l=10, r=20, t=30, b=40),
    )
    return Exhibit(
        slug="track1-gene-scatter",
        title="Every gene that could be recessive, against what the symptoms say",
        caption=(
            "One point per gene that holds two rare protein-altering alleles (or one homozygous). "
            "Left is better on the symptom axis; higher means more candidate alleles. The "
            f"genome-wide scan and the panel-blind phenotype ranking are independent "
            f"instruments — DNA on one axis, HPO on the other — and **{highlight}** is where "
            "they agree. Genes with no HPO curation are parked at the far right."
        ),
        legend=legend_line(
            GOOD,
            DECISION,
            MACHINE,
            MUTED,
            extra="filled = biallelic on PASS calls · hollow = only if a filtered call is rescued",
        ),
        figure=sized(figure, 520),
    )


def decode_table(found: Design, labels: list[str]) -> Exhibit:
    """The submission read as a measurement: one row per distinguishable reply."""
    header = [
        "full match rank",
        "partial match rank",
        "F-max",
        "at epcr",
        "prior mass",
        "what survives",
    ]
    cells: list[list[str]] = [[] for _ in header]
    fills: list[str] = []
    for outcome in found.outcomes:
        full, partial, f_max, threshold = outcome.key
        cells[0].append("—" if full is None else str(full))
        cells[1].append("—" if partial is None else str(partial))
        cells[2].append(f"{f_max:.3f}")
        cells[3].append("—" if threshold is None else f"{threshold:g}")
        cells[4].append(f"{outcome.mass:.2f}")
        cells[5].append(", ".join(h.label for h in outcome.hypotheses))
        fills.append(
            GOOD.fill
            if full == 1
            else DECISION.fill
            if len(outcome.hypotheses) > 1
            else BAD.fill
            if full is None and partial is None
            else MACHINE.fill
        )
    figure = go.Figure(
        go.Table(
            header=dict(
                values=[f"<b>{h}</b>" for h in header], fill_color=MUTED.fill, align="left"
            ),
            cells=dict(values=cells, fill_color=[fills] * len(header), align="left", height=26),
        )
    )
    figure.update_layout(margin=dict(l=10, r=10, t=10, b=10))
    # header row, one line per outcome, plus a second line for replies that leave two
    # hypotheses standing (their label wraps)
    wrapped = sum(1 for o in found.outcomes if len(o.hypotheses) > 1)
    table_height = 70 + 30 * len(found.outcomes) + 18 * wrapped
    return Exhibit(
        slug="track1-decode-table",
        title="What each possible reply would tell us",
        caption=(
            "Rows in rank order: "
            + "; ".join(f"{i + 1}. {label}" for i, label in enumerate(labels))
            + ". Every answer key still considered possible was scored against the written "
            "CSV with the local scorer replica; keys producing the same reply share a row. "
            f"Prior entropy {found.prior_entropy:.2f} bits, expected information gain "
            f"**{found.expected_information_gain:.2f} bits**; the largest set one reply "
            f"leaves standing is {found.max_ambiguity}."
        ),
        legend=legend_line(
            GOOD,
            DECISION,
            BAD,
            MACHINE,
            extra="green = the pair confirmed at rank 1 · yellow = a reply that needs a "
            "follow-up probe · red = nothing matched",
        ),
        # The PNG is written at the exhibit's own height, so pass it there as well: a table
        # sized to its rows must not be printed on a 420 px canvas half full of white.
        height=table_height,
        figure=sized(figure, table_height),
    )
