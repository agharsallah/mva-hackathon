"""The chart shapes step 3's exhibits are drawn with, separated from what they mean.

One bounded concern: every function here takes rows from ``analysis.json`` and returns a
``plotly`` figure. The captions, legends and the decisions about which exhibits exist live
in ``tools/render_it2_step3_figures.py``, because those are claims about the data and these
are only shapes.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import plotly.graph_objects as go

from mva.render import theme

#: The claim's threshold, drawn on the confirmation figure so it is visible, not described.
H027_THRESHOLD = 0.80

#: Poisson's variance-to-mean ratio. The line over-dispersion is measured against.
POISSON = 1.0

#: Left margin for the horizontal charts. Their category labels are sentences, not words.
LABEL_MARGIN = 240


def metric(rows: list[dict], name: str) -> float | None:
    for row in rows:
        if row.get("metric") == name:
            return float(row["value"])
    return None


def confirmation_figure(contrast: list[dict]) -> go.Figure:
    """Targets against decoys, for the alleles the vendor reported and the ones it did not.

    Four bars rather than one rate, because H020 is refuted: a target-gene result does not
    outweigh a decoy's before the filter, and a single number invites exactly that reading.
    """
    labels = [row["allele_set"] for row in contrast]
    figure = go.Figure(
        [
            go.Bar(
                name="target genes",
                x=labels,
                y=[row["target_rate"] for row in contrast],
                marker_color=theme.GOOD.fill,
                marker_line_color=theme.GOOD.line,
                text=[f"{row['target_confirmed']:,}/{row['target_alleles']:,}" for row in contrast],
                textposition="outside",
            ),
            go.Bar(
                name="decoy genes",
                x=labels,
                y=[row["decoy_rate"] for row in contrast],
                marker_color=theme.MUTED.fill,
                marker_line_color=theme.MUTED.line,
                text=[f"{row['decoy_confirmed']:,}/{row['decoy_alleles']:,}" for row in contrast],
                textposition="outside",
            ),
        ]
    )
    figure.add_hline(
        y=H027_THRESHOLD,
        line_dash="dash",
        line_color=theme.DECISION.line,
        annotation_text="H027: 80%",
    )
    figure.update_layout(
        barmode="group",
        yaxis_title="confirmed by k-mer genotype",
        yaxis_tickformat=".0%",
        yaxis_range=[0, 1.08],
    )
    return figure


def calls_figure(calls: list[dict]) -> go.Figure:
    """What the second instrument said, per tier. A no-call is a bar, not a gap."""
    classes = ["het", "hom-alt", "hom-ref", "no-call"]
    colours = {
        "het": theme.GOOD,
        "hom-alt": theme.MACHINE,
        "hom-ref": theme.MUTED,
        "no-call": theme.BAD,
    }
    tiers = sorted({row["tier"] for row in calls})
    figure = go.Figure(
        [
            go.Bar(
                name=label,
                x=tiers,
                y=[
                    sum(
                        int(row["alleles"])
                        for row in calls
                        if row["tier"] == tier and row["call"] == label
                    )
                    for tier in tiers
                ],
                marker_color=colours[label].fill,
                marker_line_color=colours[label].line,
            )
            for label in classes
        ]
    )
    figure.update_layout(barmode="stack", yaxis_title="alleles", xaxis_title="tier")
    return figure


def probes_figure(probes: list[dict]) -> go.Figure:
    """How many alleles got their three windows, by where the allele came from."""
    rows = sorted(probes, key=lambda row: -int(row["alleles"]))
    figure = go.Figure(
        [
            go.Bar(
                name="all three probes",
                y=[row["origin"] for row in rows],
                x=[int(row["alleles_fully_probed"]) for row in rows],
                orientation="h",
                marker_color=theme.GOOD.fill,
                marker_line_color=theme.GOOD.line,
            ),
            go.Bar(
                name="fewer, or none",
                y=[row["origin"] for row in rows],
                x=[int(row["alleles"]) - int(row["alleles_fully_probed"]) for row in rows],
                orientation="h",
                marker_color=theme.BAD.fill,
                marker_line_color=theme.BAD.line,
            ),
        ]
    )
    figure.update_layout(barmode="stack", xaxis_title="alleles", margin={"l": LABEL_MARGIN})
    return figure


def reach_figure(reach: list[dict]) -> go.Figure:
    """Do genes the gate excluded yield confident calls anyway? (H029)"""

    def label(row: dict) -> str:
        if row["reachable"]:
            return "reachable"
        reasons = []
        if row["sparse_bait"]:
            reasons.append("sparse bait")
        if row["mapq_refused"]:
            reasons.append("aligner refused")
        return "excluded: " + " + ".join(reasons or ["unknown"])

    rows = sorted(reach, key=lambda row: not row["reachable"])
    figure = go.Figure(
        go.Bar(
            x=[label(row) for row in rows],
            y=[float(row["confident_fraction"] or 0.0) for row in rows],
            marker_color=[theme.GOOD.fill if row["reachable"] else theme.BAD.fill for row in rows],
            marker_line_color=[
                theme.GOOD.line if row["reachable"] else theme.BAD.line for row in rows
            ],
            text=[f"{int(row['genes']):,} genes" for row in rows],
            textposition="outside",
        )
    )
    figure.update_layout(
        yaxis_title="alleles called confidently", yaxis_tickformat=".0%", yaxis_range=[0, 1.1]
    )
    return figure


def mapq_figure(mapq: list[dict]) -> go.Figure:
    """Where the aligner was unsure, per tier — the finding being that it mostly was not."""
    rows = sorted(mapq, key=lambda row: row["tier"])
    figure = go.Figure(
        [
            go.Bar(
                name="median gene",
                x=[row["tier"] for row in rows],
                y=[float(row["median_mapq0_fraction"] or 0.0) for row in rows],
                marker_color=theme.MACHINE.fill,
                marker_line_color=theme.MACHINE.line,
            ),
            go.Bar(
                name="worst gene",
                x=[row["tier"] for row in rows],
                y=[float(row["max_mapq0_fraction"] or 0.0) for row in rows],
                marker_color=theme.BAD.fill,
                marker_line_color=theme.BAD.line,
            ),
        ]
    )
    figure.update_layout(
        barmode="group", yaxis_title="reads at MAPQ 0", yaxis_type="log", xaxis_title="tier"
    )
    return figure


def calibration_figure(calibration: list[dict]) -> go.Figure:
    """The fit's parameters as a labelled bar, with Poisson drawn where it belongs."""
    wanted = [
        ("lambda_per_copy", "per-copy coverage (alternate side)"),
        ("lambda_from_reference", "per-copy coverage (reference side)"),
        ("variance_to_mean", "variance-to-mean ratio"),
        ("dispersion", "dispersion"),
        ("minimum_count", "minimum count for 'present'"),
    ]
    rows = [(label, metric(calibration, name)) for name, label in wanted]
    rows = [(label, value) for label, value in rows if value is not None]
    figure = go.Figure(
        go.Bar(
            y=[label for label, _ in rows],
            x=[value for _, value in rows],
            orientation="h",
            marker_color=theme.MACHINE.fill,
            marker_line_color=theme.MACHINE.line,
            text=[f"{value:,.2f}" for _, value in rows],
            textposition="outside",
        )
    )
    figure.add_vline(
        x=POISSON, line_dash="dash", line_color=theme.DECISION.line, annotation_text="Poisson = 1"
    )
    figure.update_layout(xaxis_type="log", margin={"l": LABEL_MARGIN})
    return figure


def copy_number_figure(rows: list[dict], band: list[dict]) -> go.Figure:
    """Copy number per tier against the band measured on the decoys.

    The band is drawn rather than described, because "low" is only meaningful against it —
    and it was measured on this sample at this depth through this bait, not imported.
    """
    ordered = sorted(rows, key=lambda row: str(row["tier"]))
    figure = go.Figure(
        go.Bar(
            x=[row["tier"] for row in ordered],
            y=[float(row["median_copy_number"] or 0.0) for row in ordered],
            marker_color=[
                theme.MUTED.fill if row["tier"] == "decoy" else theme.GOOD.fill for row in ordered
            ],
            marker_line_color=[
                theme.MUTED.line if row["tier"] == "decoy" else theme.GOOD.line for row in ordered
            ],
            text=[f"{int(row['below_null_band']):,} below band" for row in ordered],
            textposition="outside",
        )
    )
    if band:
        low, high = float(band[0]["low"]), float(band[0]["high"])
        figure.add_hrect(y0=low, y1=high, fillcolor=theme.MACHINE.fill, opacity=0.25, line_width=0)
        figure.add_hline(
            y=low,
            line_dash="dash",
            line_color=theme.DECISION.line,
            annotation_text=f"null band, {low:.2f}",
        )
    figure.add_hline(y=2.0, line_color=theme.MUTED.line, annotation_text="diploid = 2.0")
    figure.update_layout(yaxis_title="median copy number", yaxis_range=[0, 3.2])
    return figure
