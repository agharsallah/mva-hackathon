#!/usr/bin/env python3
"""Step 8's dosage figures: the second instrument, and the correction that decides it.

Kept out of ``it2_step8_charts`` because that module was already near the 400-line limit and
because these read a different file. The allele-route charts are drawn from
``analysis.json``; these are drawn from ``composition.json`` and ``dosage.json``, which a
counting pass over the raw reads wrote and which share no input with the callset.

Three figures, in the order a reader needs them:

1. **The positive control first.** X and Y at half, which is the answer a male proband should
   give and the only check this route has that does not depend on the child being normal.
2. **The trend.** Dosage against chromosome GC, because most of what looks like signal is
   composition and a reader should see that before seeing any residual.
3. **What is left.** The residual in units of its own spread, with the multiple-testing
   threshold drawn rather than described.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import plotly.graph_objects as go

from mva.render import theme
from mva.render.figure import Exhibit

ORDER = [*(str(number) for number in range(1, 23)), "X", "Y"]
HEMIZYGOUS = ("X", "Y")

#: Where a single pre-specified chromosome starts to be worth a second look. It is *not* a
#: genome-wide threshold, and the caption says so: with 22 autosomes read at once, roughly
#: one clears two sigma on a genome with nothing wrong with it.
SIGMA = 2.0


def _ordered(rows: list[dict]) -> list[dict]:
    index = {name: position for position, name in enumerate(ORDER)}
    return sorted(
        rows, key=lambda row: (index.get(str(row["chrom"]), len(ORDER)), str(row["chrom"]))
    )


def dosage_figure(rows: list[dict]) -> go.Figure:
    """Both denominators per contig, with the sex chromosomes left in as the control."""
    ordered = _ordered(rows)
    chroms = [str(row["chrom"]) for row in ordered]
    figure = go.Figure()
    figure.add_scatter(
        x=chroms,
        y=[row["relative"] for row in ordered],
        mode="markers",
        marker={
            "size": 10,
            "color": [
                theme.MUTED.fill if name in HEMIZYGOUS else theme.GOOD.fill for name in chroms
            ],
        },
        error_y={
            "type": "data",
            "symmetric": False,
            "array": [row["high"] - row["relative"] for row in ordered],
            "arrayminus": [row["relative"] - row["low"] for row in ordered],
            "color": theme.MUTED.line,
            "thickness": 1,
        },
        name="against the autosomal median",
        hovertemplate="chr%{x}<br>%{y:.4f}x median<extra></extra>",
    )
    figure.add_scatter(
        x=chroms,
        y=[row["absolute"] for row in ordered],
        mode="markers",
        marker={"size": 8, "color": theme.MACHINE.fill, "symbol": "diamond-open"},
        name="against total k-mer mass",
        hovertemplate="chr%{x}<br>%{y:.4f}x absolute<extra></extra>",
    )
    figure.add_hrect(y0=0.97, y1=1.03, fillcolor=theme.MUTED.fill, opacity=0.18, line_width=0)
    figure.update_layout(
        xaxis={
            "title": {"text": "chromosome"},
            "type": "category",
            "categoryorder": "array",
            "categoryarray": chroms,
        },
        yaxis_title="dosage (1 = one copy per copy expected)",
        legend={"orientation": "h", "y": 1.12},
    )
    return figure


def composition_figure(rows: list[dict], slope: float, intercept: float) -> go.Figure:
    """Dosage against chromosome GC, with the fitted trend drawn through it."""
    gcs = [row["gc"] for row in rows]
    span = [min(gcs), max(gcs)]
    figure = go.Figure()
    figure.add_scatter(
        x=gcs,
        y=[row["relative"] for row in rows],
        text=[f"chr{row['chrom']}" for row in rows],
        mode="markers+text",
        textposition="top center",
        textfont={"size": 9},
        marker={"size": 9, "color": theme.GOOD.fill},
        name="measured",
        hovertemplate="%{text}<br>GC %{x:.4f}<br>dosage %{y:.4f}<extra></extra>",
    )
    figure.add_scatter(
        x=span,
        y=[slope * value + intercept for value in span],
        mode="lines",
        line={"color": theme.MACHINE.line, "width": 2},
        name="fitted composition trend",
        hoverinfo="skip",
    )
    figure.update_layout(
        xaxis_title="chromosome GC fraction",
        yaxis_title="dosage against the autosomal median",
        legend={"orientation": "h", "y": 1.12},
    )
    return figure


def residual_figure(rows: list[dict]) -> go.Figure:
    """What survives the trend, in units of its own spread, with the two-sigma lines drawn."""
    ordered = _ordered(rows)
    chroms = [str(row["chrom"]) for row in ordered]
    figure = go.Figure()
    figure.add_bar(
        x=chroms,
        y=[row["z"] for row in ordered],
        marker_color=[
            theme.DECISION.fill if abs(row["z"]) > SIGMA else theme.GOOD.fill for row in ordered
        ],
        customdata=[row["implied_fraction"] * 100 for row in ordered],
        name="residual",
        hovertemplate=(
            "chr%{x}<br>%{y:.2f} sigma<br>implied %{customdata:.2f}% of cells<extra></extra>"
        ),
    )
    for level in (SIGMA, -SIGMA):
        figure.add_hline(y=level, line={"color": theme.DECISION.line, "width": 1, "dash": "dot"})
    figure.add_hline(y=0, line={"color": theme.MACHINE.line, "width": 1})
    figure.update_layout(
        xaxis={
            "title": {"text": "chromosome"},
            "type": "category",
            "categoryorder": "array",
            "categoryarray": chroms,
        },
        yaxis_title="residual / residual spread (sigma)",
        showlegend=False,
    )
    return figure


def optional_json(path: Path) -> dict:
    """A JSON file if the stage that writes it has run, and an empty object if it has not."""
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def dosage_exhibits(dosage: dict, composition: dict) -> list[Exhibit]:
    """The second instrument. Its control first, then the trend, then what survives it."""
    rows = dosage.get("dosage") or []
    fit = composition.get("reported") or {}
    residuals = composition.get("rows") or []
    if not rows:
        return []

    sex = {str(row["chrom"]): row["relative"] for row in rows if str(row["chrom"]) in ("X", "Y")}
    exhibits = [
        Exhibit(
            slug="dosage-per-chromosome",
            title="Sequence contributed per chromosome, against two denominators",
            caption=(
                "The second instrument, sharing nothing with allele balance past the FASTQ: "
                "reference-unique 31-mers are assigned one chromosome each and counted in the "
                "raw reads, so a chromosome present in more copies is hit more often, in "
                "proportion. Read X and Y first — they are the control. One copy of each is "
                "what a male proband should give, and this route reads "
                + ", ".join(f"chr{name} {value:.4f}" for name, value in sorted(sex.items()))
                + " against an expected 0.5. The two denominators differ by a near-constant "
                "factor, which is what says no single chromosome is dragging the median."
            ),
            legend=theme.legend_line(
                theme.GOOD,
                theme.MACHINE,
                theme.MUTED,
                extra=(
                    "green is the ratio to the autosomal median with its probe bootstrap, "
                    "blue the ratio to the genome-wide calibration set, grey the one-copy "
                    "band and the hemizygous contigs"
                ),
            ),
            figure=dosage_figure(rows),
            height=400,
        )
    ]
    if not residuals or not fit:
        return exhibits

    explained = (fit.get("correlation") or 0.0) ** 2
    exhibits.append(
        Exhibit(
            slug="dosage-composition",
            title="Most of what looks like signal is composition",
            caption=(
                "The correction that decides whether any dosage above is evidence. A "
                "bootstrap over probes measures counting noise and is blind to a bias every "
                "probe on a chromosome shares — and GC is exactly that, worth a few per cent "
                f"across a whole chromosome. It explains {explained:.0%} of the spread "
                "between chromosomes. The regressor is the chromosome's own GC from the "
                "reference and not its probes': GC bias acts on fragments of a few hundred "
                "bases, and a probe set is what the uniqueness filter left rather than a fair "
                "sample of the sequence it was cut from."
            ),
            legend=theme.legend_line(
                theme.GOOD,
                theme.MACHINE,
                extra=(
                    "green is one autosome's measured dosage, blue the fitted trend; "
                    "vertical distance from the line is what is left to explain"
                ),
            ),
            figure=composition_figure(
                residuals, float(fit.get("slope") or 0.0), float(fit.get("intercept") or 1.0)
            ),
            height=420,
        )
    )
    worst = max(residuals, key=lambda row: abs(row["z"]))
    tested = composition.get("autosomes_tested") or len(residuals)
    exhibits.append(
        Exhibit(
            slug="dosage-residual",
            title="What is left after composition, in units of the residual spread",
            caption=(
                f"The largest residual is chr{worst['chrom']} at {worst['z']:.2f} sigma, an "
                f"implied {worst['implied_fraction'] * 100:.1f}% of cells. With {tested} "
                "autosomes read at once that is not a finding: roughly one clears two sigma "
                "on a genome with nothing wrong with it. The spread of these residuals — not "
                "the bootstrap width — is this route's precision floor."
            ),
            legend=theme.legend_line(
                theme.GOOD,
                theme.DECISION,
                theme.MACHINE,
                extra=(
                    "yellow dotted lines are plus and minus two sigma, where a single "
                    "pre-specified chromosome would start to be interesting and a set of "
                    f"{tested} is still noise; blue is one copy per copy expected"
                ),
            ),
            figure=residual_figure(residuals),
            height=380,
        )
    )
    return exhibits
