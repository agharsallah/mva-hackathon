"""The one place a colour is chosen.

Every diagram in this repository speaks the same visual language, fixed in `CLAUDE.md`:
green is good, red is broken, yellow is a decision, blue is neutral machinery, purple is
raw input. The SVGs in ``docs/assets/`` already use it; this module carries the identical
hues into the plotted charts so a reader moving between a hand-drawn anatomy diagram and a
generated figure does not have to relearn what a colour means.

Semantics come first and the hex code second. Call sites ask for ``SEMANTIC.good``, never
for ``"#8fd18f"`` — which is what keeps a later palette change to one edit here.
"""

from dataclasses import dataclass

import plotly.graph_objects as go
import plotly.io as pio


@dataclass(frozen=True)
class Hue:
    """One semantic role, in the two weights a chart needs.

    ``fill`` is the pastel used for areas and bars, matched to ``docs/assets/*.svg``.
    ``line`` is the saturated version for outlines, markers and text on white.
    """

    fill: str
    line: str
    label: str


#: The semantic palette. Adding a role means adding a legend word, so keep it small.
GOOD = Hue("#8fd18f", "#3f8f47", "good / safe / the goal")
BAD = Hue("#ff9999", "#c0392b", "broken / dangerous / lost points")
DECISION = Hue("#ffe9b3", "#c98f1e", "a decision point")
MACHINE = Hue("#cfe8ff", "#3d7ebd", "neutral machinery")
RAW = Hue("#e0d4f7", "#7a5cab", "the raw input")
MUTED = Hue("#e6e6e6", "#888888", "context, not the subject")

#: Ordered sweep for series that carry no semantics of their own (lanes, contigs, genes).
SEQUENCE = [
    "#3d7ebd",
    "#7a5cab",
    "#3f8f47",
    "#c98f1e",
    "#c0392b",
    "#4aa3a3",
    "#a3579b",
    "#6b8f3f",
    "#b5762e",
    "#8a8a8a",
]

INK = "#333333"
SUBTLE_INK = "#666666"
GRID = "#e6e6e6"
PAPER = "#ffffff"

FONT = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "'SF Mono', 'JetBrains Mono', Menlo, Consolas, monospace"

TEMPLATE_NAME = "sepiq"


def install_template() -> None:
    """Register the repository template with Plotly and make it the default.

    Idempotent, and called at import time of :mod:`sepiq.explore`, so every figure built
    anywhere in the package inherits the same axes, fonts and background without each
    view having to remember to ask.
    """
    template = go.layout.Template()
    template.layout = go.Layout(
        font=dict(family=FONT, size=13, color=INK),
        title=dict(font=dict(size=17, color=INK), x=0, xanchor="left", pad=dict(b=12)),
        paper_bgcolor=PAPER,
        plot_bgcolor=PAPER,
        colorway=SEQUENCE,
        margin=dict(l=64, r=28, t=56, b=52),
        xaxis=dict(
            gridcolor=GRID,
            zerolinecolor=GRID,
            linecolor=GRID,
            ticks="outside",
            tickcolor=GRID,
            ticklen=4,
            title=dict(font=dict(size=12, color=SUBTLE_INK)),
        ),
        yaxis=dict(
            gridcolor=GRID,
            zerolinecolor=GRID,
            linecolor=GRID,
            ticks="outside",
            tickcolor=GRID,
            ticklen=4,
            title=dict(font=dict(size=12, color=SUBTLE_INK)),
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            font=dict(size=12),
            bgcolor="rgba(0,0,0,0)",
        ),
        hoverlabel=dict(font=dict(family=MONO, size=12), bgcolor="#ffffff", bordercolor=GRID),
    )
    pio.templates[TEMPLATE_NAME] = template
    pio.templates.default = TEMPLATE_NAME


def legend_line(*hues: Hue, extra: str = "") -> str:
    """Compose the ``> **Legend**`` sentence a figure is required to carry.

    The repository rule is that every visual decodes its own colours immediately beneath
    itself. Generating that line from the same objects the figure was coloured with is
    what stops the caption and the chart from drifting apart.
    """
    parts = [hue.label for hue in hues]
    if extra:
        parts.append(extra)
    return "**Legend** — " + "; ".join(parts) + "."
