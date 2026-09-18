#!/usr/bin/env python3
"""The chart shapes step 8's exhibits are drawn with, separated from what they mean.

One bounded concern: every function takes rows from ``build/it2/step-8/analysis.json`` and
returns a ``plotly`` figure. The captions and the legends live in
``tools/render_it2_step8_figures.py``, because those are claims about the data and these are
only shapes.

Three conventions, each forced by the data rather than chosen:

* **A limit that was never reached is a hole, not a large number.** A chromosome whose
  power never reaches 80 %% has no ``f80``; drawing it at the top of the axis would read as
  "detectable at 30 %%" when the truth is "not detectable at any fraction tested".
* **Chromosomes are ordered as a karyogram is read** — 1 to 22, then X and Y — not by value.
  Sorting by the statistic would put the answer in the axis order and invite the reader to
  see a ranking where there is a genome.
* **A hemizygous contig is drawn, and marked.** X and Y in a male proband carry almost no
  heterozygous calls, so their allele-balance numbers are not comparable with an autosome's.
  Removing them would hide that; colouring them says it.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import plotly.graph_objects as go

from mva.render import theme

#: Karyogram order. Anything not named here is appended in the order it arrives.
ORDER = [*(str(number) for number in range(1, 23)), "X", "Y"]

#: Contigs whose allele balance is not comparable with an autosome's in a male proband.
HEMIZYGOUS = ("X", "Y")


def _ordered(rows: list[dict], key: str = "chrom") -> list[dict]:
    index = {name: position for position, name in enumerate(ORDER)}
    return sorted(rows, key=lambda row: (index.get(str(row[key]), len(ORDER)), str(row[key])))


def _tone(chrom: str, flagged: bool) -> str:
    if chrom in HEMIZYGOUS:
        return theme.MUTED.fill
    return theme.BAD.fill if flagged else theme.GOOD.fill


def bdev_figure(rows: list[dict]) -> go.Figure:
    """Each contig's fold-over deviation against the null its own depths generate."""
    ordered = _ordered(rows)
    chroms = [str(row["chrom"]) for row in ordered]
    observed = [row["bdev"] for row in ordered]
    null_mean = [row["null_mean"] for row in ordered]
    null_p95 = [row["null_p95"] for row in ordered]
    colours = [
        _tone(chrom, bool(row["exceeds_null"])) for chrom, row in zip(chroms, ordered, strict=True)
    ]

    figure = go.Figure()
    figure.add_bar(
        x=chroms,
        y=observed,
        marker_color=colours,
        marker_line_color=theme.MUTED.line,
        marker_line_width=1,
        name="observed",
        hovertemplate="chr%{x}<br>Bdev %{y:.5f}<extra></extra>",
    )
    figure.add_scatter(
        x=chroms,
        y=null_p95,
        mode="markers",
        marker={
            "symbol": "line-ew-open",
            "size": 18,
            "line": {"width": 2, "color": theme.DECISION.line},
        },
        name="null 95th percentile",
        hovertemplate="chr%{x}<br>reject above %{y:.5f}<extra></extra>",
    )
    figure.add_scatter(
        x=chroms,
        y=null_mean,
        mode="markers",
        marker={
            "symbol": "line-ew-open",
            "size": 18,
            "line": {"width": 1, "color": theme.MACHINE.line},
        },
        name="null mean",
        hovertemplate="chr%{x}<br>null mean %{y:.5f}<extra></extra>",
    )
    figure.update_layout(
        xaxis_title="chromosome",
        yaxis_title="mean |BAF − centre|",
        barmode="overlay",
        legend={"orientation": "h", "y": 1.12},
    )
    return figure


def power_figure(folded: list[dict], mean: list[dict], grid: list[float]) -> go.Figure:
    """Power against cell fraction, one line per contig, for both statistics."""
    figure = go.Figure()
    for rows, hue, label in (
        (mean, theme.BAD, "037 mean BAF"),
        (folded, theme.GOOD, "fold-over Bdev"),
    ):
        for index, row in enumerate(_ordered(rows)):
            curve = row["power"]
            figure.add_scatter(
                x=grid,
                y=[curve[str(round(float(point), 4))] for point in grid],
                mode="lines",
                line={"color": hue.fill, "width": 1},
                opacity=0.65,
                name=label,
                legendgroup=label,
                showlegend=index == 0,
                hovertemplate=(
                    f"chr{row['chrom']} · {label}<br>f %{{x}}<br>power %{{y:.2f}}<extra></extra>"
                ),
            )
    figure.add_hline(
        y=0.80,
        line={"color": theme.DECISION.line, "width": 2, "dash": "dash"},
        annotation_text="80 % power",
        annotation_position="bottom right",
    )
    figure.update_layout(
        xaxis_title="injected cell fraction",
        yaxis_title="power",
        yaxis_range=[0, 1.02],
        legend={"orientation": "h", "y": 1.12},
    )
    return figure


def limit_figure(rows: list[dict]) -> go.Figure:
    """The smallest detectable fraction per contig — the number a negative result needs."""
    ordered = _ordered(rows)
    chroms = [str(row["chrom"]) for row in ordered]
    reached = [row for row in ordered if row["f80"] is not None]
    missing = [row for row in ordered if row["f80"] is None]

    figure = go.Figure()
    figure.add_bar(
        x=[str(row["chrom"]) for row in reached],
        y=[row["f80"] for row in reached],
        marker_color=[_tone(str(row["chrom"]), False) for row in reached],
        marker_line_color=theme.MUTED.line,
        marker_line_width=1,
        name="detection limit",
        hovertemplate="chr%{x}<br>detects %{y:.1%} and above<extra></extra>",
    )
    if missing:
        figure.add_bar(
            x=[str(row["chrom"]) for row in missing],
            y=[max((row["f80"] for row in reached), default=0.1)] * len(missing),
            marker_color=theme.MUTED.fill,
            marker_pattern_shape="/",
            name="no limit reached",
            hovertemplate="chr%{x}<br>never reaches 80 % power<extra></extra>",
        )
    figure.update_layout(
        xaxis_title="chromosome",
        yaxis_title="smallest detectable cell fraction",
        yaxis_tickformat=".0%",
        barmode="overlay",
        legend={"orientation": "h", "y": 1.12},
        xaxis={"categoryorder": "array", "categoryarray": chroms},
    )
    return figure


def depth_figure(ratios: dict[str, float], sex: dict[str, float], spread: float) -> go.Figure:
    """Each contig's depth against the leave-one-out baseline, with the precision floor drawn."""
    rows = [{"chrom": chrom, "ratio": value} for chrom, value in {**ratios, **sex}.items()]
    ordered = _ordered(rows)
    chroms = [str(row["chrom"]) for row in ordered]
    figure = go.Figure()
    figure.add_scatter(
        x=chroms,
        y=[row["ratio"] for row in ordered],
        mode="markers",
        marker={
            "size": 11,
            "color": [_tone(chrom, False) for chrom in chroms],
            "line": {"width": 1, "color": theme.MUTED.line},
        },
        name="depth ÷ baseline",
        hovertemplate="chr%{x}<br>%{y:.3f}× baseline<extra></extra>",
    )
    for sign in (1, -1):
        figure.add_hline(
            y=1.0 + sign * spread,
            line={"color": theme.DECISION.line, "width": 1, "dash": "dot"},
        )
    figure.add_hline(y=1.0, line={"color": theme.MACHINE.line, "width": 1})
    figure.update_layout(
        xaxis_title="chromosome",
        yaxis_title="mean depth ÷ leave-one-out baseline",
        showlegend=False,
    )
    return figure


def model_figure(fits: list[dict]) -> go.Figure:
    """ΔBIC of every model against the winner, per contig, with Kong's threshold drawn."""
    by_chrom: dict[str, list[dict]] = {}
    for fit in fits:
        by_chrom.setdefault(str(fit["chrom"]), []).append(fit)

    ordered = _ordered([{"chrom": chrom} for chrom in by_chrom])
    chroms = [str(row["chrom"]) for row in ordered]
    models = [fit["model"] for fit in by_chrom[chroms[0]]]

    figure = go.Figure()
    for model in models:
        deltas = []
        for chrom in chroms:
            rows = {fit["model"]: fit for fit in by_chrom[chrom]}
            floor = min(fit["bic"] for fit in by_chrom[chrom])
            deltas.append(rows[model]["bic"] - floor)
        figure.add_bar(
            x=chroms,
            y=deltas,
            name=model,
            hovertemplate=f"chr%{{x}} · {model}<br>ΔBIC %{{y:.1f}}<extra></extra>",
        )
    figure.add_hline(
        y=10.0,
        line={"color": theme.DECISION.line, "width": 2, "dash": "dash"},
        annotation_text="ΔBIC 10 — below this is not a call",
        annotation_position="top left",
    )
    figure.update_layout(
        xaxis_title="chromosome",
        yaxis_title="ΔBIC against the best model",
        yaxis_type="log",
        barmode="group",
        legend={"orientation": "h", "y": 1.12},
    )
    return figure


def multi_figure(designs: list[dict]) -> go.Figure:
    """Recovery and false positives when several chromosomes are abnormal at once."""
    labels = [f"{row['n_affected']}× at {row['fraction']:.0%}" for row in designs]
    figure = go.Figure()
    figure.add_bar(
        x=labels,
        y=[row["recall"] for row in designs],
        marker_color=theme.GOOD.fill,
        marker_line_color=theme.GOOD.line,
        marker_line_width=1,
        name="injected chromosomes recovered",
        hovertemplate="%{x}<br>recall %{y:.2f}<extra></extra>",
    )
    figure.add_bar(
        x=labels,
        y=[row["false_positive_rate"] for row in designs],
        marker_color=theme.BAD.fill,
        marker_line_color=theme.BAD.line,
        marker_line_width=1,
        name="untouched chromosomes flagged",
        hovertemplate="%{x}<br>false positive rate %{y:.3f}<extra></extra>",
    )
    figure.add_hline(
        y=0.05,
        line={"color": theme.DECISION.line, "width": 1, "dash": "dot"},
        annotation_text="nominal 5 %",
        annotation_position="top right",
    )
    figure.update_layout(
        xaxis_title="design",
        yaxis_title="share",
        barmode="group",
        legend={"orientation": "h", "y": 1.12},
    )
    return figure


def density_figure(rows: list[dict]) -> go.Figure:
    """Heterozygous calls per PASS call, by arm — the statistic a monosomy moves."""
    tested = [row for row in rows if row["arm"] in ("p", "q")]
    ordered = _ordered(tested)
    figure = go.Figure()
    for arm, hue in (("p", theme.MACHINE), ("q", theme.RAW)):
        subset = [row for row in ordered if row["arm"] == arm]
        figure.add_bar(
            x=[str(row["chrom"]) for row in subset],
            y=[row["het_share"] for row in subset],
            name=f"{arm} arm",
            marker_color=hue.fill,
            marker_line_color=hue.line,
            marker_line_width=1,
            hovertemplate=f"chr%{{x}}{arm}<br>%{{y:.3f}} het per PASS call<extra></extra>",
        )
    figure.update_layout(
        xaxis_title="chromosome",
        yaxis_title="heterozygous calls ÷ PASS calls",
        barmode="group",
        legend={"orientation": "h", "y": 1.12},
    )
    return figure
