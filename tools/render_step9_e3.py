#!/usr/bin/env python3
"""Step 9, E3: LINCS signature reversal in two figures.

(a) ``step9-e3-engines`` — do the two engines agree? Left: every compound both engines
    ranked as a reverser of the BUB1B knockout consensus, SigCom rank against iLINCS rank
    (log axes), with the pre-registered top-100 box. Right: for each approved drug in
    either engine's top 100, in how many of the 20 random decoy signatures' SigCom top 100
    it also sits — the "specifically" clause, with its cut of 1.
(b) ``step9-e3-control`` — the positive control: where the other checkpoint genes'
    knockouts (CRISPR) and knockdowns (shRNA) land among every perturbed gene, for the
    real signature and for each decoy, against the 5 % cut.

**Sources.** ``ressources/track2/it4/lincs_reversal.tsv`` and
``build/it4/track2-e3/summary.json``, both written by ``tools/signature_reversal.py run``.
Entry 153.

    uv run python tools/render_step9_e3.py

Outputs ``figures/it4/step9-e3-{engines,control}.{svg,html}`` plus one ``.provenance.json``
each, and prints each figure's legend line.
"""

from __future__ import annotations

import json
import math
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
import polars as pl
from plotly.subplots import make_subplots

from mva.drugs import provenance
from mva.render.theme import BAD, DECISION, GOOD, MACHINE, MUTED, install_template, legend_line

TABLE = Path("ressources/track2/it4/lincs_reversal.tsv")
SUMMARY = Path("build/it4/track2-e3/summary.json")
OUT = Path("figures/it4")
PREVIEW = Path("build/it4/track2-e3/preview")
ENTRY = "docs/iteration4/step-9/methodology/153-lincs-signature-reversal-of-bub1b-loss.md"
TOP_N = 100
DECOY_CUT = 1
LIBRARY_TITLE = {"l1000_xpr": "CRISPR knockouts (l1000_xpr)", "l1000_shRNA": "shRNA (l1000_shRNA)"}


def _write(
    fig: go.Figure, name: str, width: int, height: int, inputs: list[Path], legend: str
) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    PREVIEW.mkdir(parents=True, exist_ok=True)
    svg = OUT / f"step9-e3-{name}.svg"
    fig.write_image(svg, format="svg", width=width, height=height)
    fig.write_image(PREVIEW / f"{name}.png", format="png", width=width, height=height, scale=2)
    fig.write_html(svg.with_suffix(".html"), include_plotlyjs="cdn", full_html=True)
    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()
    svg.with_suffix(".provenance.json").write_text(
        json.dumps(
            {
                "name": svg.stem,
                "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "built_by": "tools/render_step9_e3.py",
                "code_version": commit,
                "inputs": [
                    {"path": p.as_posix(), "sha256": provenance.digest(p)[0]} for p in inputs
                ],
                "entry": ENTRY,
                "legend": legend,
                "patient_data": (
                    "none. Public LINCS signatures, gene symbols and drug names only; no "
                    "patient-derived value and no genomic position appears on any axis"
                ),
            },
            indent=2,
        )
        + "\n"
    )
    print(f"wrote {svg}\n  {legend}\n")


def _hue(row: dict[str, Any]) -> tuple[Any, str]:
    if row["approved"] and row["top_both"] and row["decoy_top_hits"] <= DECOY_CUT:
        return GOOD, "approved, top 100 in both, specific"
    if row["approved"] and row["top_both"]:
        return BAD, "approved, top 100 in both, not specific (≥ 2 decoys)"
    if row["approved"]:
        return MACHINE, "approved"
    return MUTED, "not approved (tool compound)"


def engines_figure(table: pl.DataFrame, decoys: int) -> None:
    both = table.filter(pl.col("sigcom_rank").is_not_null() & pl.col("ilincs_rank").is_not_null())
    fig = make_subplots(
        rows=1, cols=2, column_widths=[0.62, 0.38], horizontal_spacing=0.12,
        subplot_titles=(
            f"compound reverser rank, both engines ({both.height} compounds)",
            f"approved drugs in either top {TOP_N}: decoys that also rank them",
        ),
    )  # fmt: skip
    groups: dict[str, tuple[Any, list[dict[str, Any]]]] = {}
    for row in both.sort("approved").iter_rows(named=True):
        hue, tag = _hue(row)
        groups.setdefault(tag, (hue, []))[1].append(row)
    for tag, (hue, rows) in groups.items():
        fig.add_trace(
            go.Scatter(
                x=[r["sigcom_rank"] for r in rows], y=[r["ilincs_rank"] for r in rows],
                mode="markers", name=tag, legendgroup=tag,
                hovertext=[r["drug"] for r in rows], hoverinfo="text+x+y",
                marker={"size": 7 if hue is MUTED else 9, "color": hue.fill,
                        "line": {"color": hue.line, "width": 1.2}},
            ),
            row=1, col=1,
        )  # fmt: skip
    listed = both.filter(pl.col("top_both") & pl.col("approved"))
    for k, row in enumerate(listed.sort("sigcom_rank").iter_rows(named=True)):
        fig.add_annotation(
            x=_log(row["sigcom_rank"]), y=_log(row["ilincs_rank"]), text=row["drug"].title(),
            showarrow=True, arrowhead=0, ax=-60 + 45 * k, ay=-28 + 40 * (k % 2),
            font={"size": 10}, row=1, col=1,
        )  # fmt: skip
    for axis in ("x", "y"):
        line = {"color": DECISION.line, "width": 1.5, "dash": "dash"}
        if axis == "x":
            fig.add_vline(x=TOP_N, line=line, row=1, col=1)
        else:
            fig.add_hline(y=TOP_N, line=line, row=1, col=1)
    fig.update_xaxes(
        type="log", title_text="SigCom LINCS rank (1 = strongest reverser)", row=1, col=1
    )
    fig.update_yaxes(type="log", title_text="iLINCS rank", row=1, col=1)

    either = table.filter(
        pl.col("approved") & ((pl.col("sigcom_rank") <= TOP_N) | (pl.col("ilincs_rank") <= TOP_N))
    ).sort(["decoy_top_hits", "drug"], descending=[True, False])
    fig.add_trace(
        go.Bar(
            y=[d.title() for d in either["drug"]], x=either["decoy_top_hits"].to_list(),
            orientation="h", showlegend=False,
            marker={"color": [_hue(r)[0].fill for r in either.iter_rows(named=True)],
                    "line": {"color": [_hue(r)[0].line for r in either.iter_rows(named=True)],
                             "width": 1}},
            hovertext=[f"SigCom {r['sigcom_rank']} · iLINCS {r['ilincs_rank']}"
                       for r in either.iter_rows(named=True)],
        ),
        row=1, col=2,
    )  # fmt: skip
    fig.add_vline(
        x=DECOY_CUT + 0.5, line={"color": DECISION.line, "width": 1.5, "dash": "dash"},
        row=1, col=2,
    )  # fmt: skip
    fig.update_xaxes(title_text=f"decoys (of {decoys}) with this drug in their top {TOP_N}",
                     range=[0, decoys], row=1, col=2)  # fmt: skip
    fig.update_yaxes(autorange="reversed", tickfont={"size": 9}, dtick=1, row=1, col=2)
    fig.update_layout(
        title="E3 — reversers of the BUB1B knockout consensus: do two engines agree, specifically?",
        legend={"orientation": "h", "y": -0.18},
        margin={"l": 70, "r": 30, "t": 90},
    )
    legend = legend_line(
        GOOD, BAD, MACHINE, MUTED, DECISION,
        extra=(f"green = approved, in both engines' top {TOP_N} and in at most {DECOY_CUT} decoy's "
               f"top {TOP_N}; red = the same but in 2 or more decoys' tops (not specific); blue = "
               "approved, outside the double top; grey = tool compounds with no approval; "
               f"yellow dashed = the pre-registered cuts (rank {TOP_N}; {DECOY_CUT} decoy)"),
    )  # fmt: skip
    _write(fig, "engines", 1280, 900, [TABLE, SUMMARY], legend)


def _log(value: float) -> float:
    return math.log10(value)


def control_figure(summary: dict[str, Any]) -> None:
    nulls = summary["control_null"]
    cut = next(iter(summary["verdict_inputs"]["controls"].values()))["cut"]
    libraries = list(nulls)
    fig = make_subplots(
        rows=1, cols=len(libraries), shared_yaxes=True, horizontal_spacing=0.08,
        subplot_titles=[LIBRARY_TITLE.get(lib, lib) for lib in libraries],
    )  # fmt: skip
    for col, lib in enumerate(libraries, start=1):
        null = nulls[lib]
        universe = null["universe_genes"]
        decoy = [r / universe * 100 for r in null["decoy_best_ranks"] if r is not None]
        fig.add_trace(
            go.Box(
                y=decoy, x=["20 decoys: best checkpoint gene"] * len(decoy), boxpoints="all",
                jitter=0.4, pointpos=0, name="decoys", showlegend=col == 1,
                marker={"color": MUTED.line, "size": 6}, line={"color": MUTED.line},
                fillcolor="rgba(0,0,0,0)",
            ),
            row=1, col=col,
        )  # fmt: skip
        for gene, rank in sorted(null["real_ranks"].items()):
            if rank is None:
                continue
            pct = rank / universe * 100
            hue = GOOD if pct <= cut * 100 else BAD
            fig.add_trace(
                go.Scatter(
                    x=[gene], y=[pct], mode="markers+text", text=[f"{rank}"],
                    textposition="middle right", showlegend=False,
                    marker={"size": 11, "color": hue.fill, "line": {"color": hue.line, "width": 2}},
                    hovertext=[f"{gene}: gene rank {rank} of {universe}"], hoverinfo="text",
                ),
                row=1, col=col,
            )  # fmt: skip
        fig.add_hline(
            y=cut * 100, line={"color": DECISION.line, "width": 1.5, "dash": "dash"},
            row=1, col=col,
        )  # fmt: skip
    fig.update_yaxes(type="log")
    fig.update_yaxes(title_text="gene-level mimicker rank, % of perturbed genes", row=1, col=1)
    fig.update_layout(
        title="E3 positive control — does the BUB1B signature find other checkpoint losses?",
        margin={"l": 80, "r": 70, "t": 90},
    )
    legend = legend_line(
        GOOD, BAD, MUTED, DECISION,
        extra=(f"green = a checkpoint gene (BUB1, BUB3, MAD1L1, MAD2L1, TTK) in the top "
               f"{cut:.0%} of perturbed genes as a mimicker of the real signature, red = outside "
               "(number = its rank; a gene beyond the retrieved depth is not drawn); grey dots = "
               "each decoy's best checkpoint gene, the chance rate of the control; yellow dashed "
               f"= the pre-registered {cut:.0%} cut; log axis"),
    )  # fmt: skip
    _write(fig, "control", 1180, 600, [SUMMARY], legend)


def main() -> None:
    install_template()
    table = pl.read_csv(TABLE, separator="\t")
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    decoys = int(str(table["decoys"].max() or 0))
    engines_figure(table, decoys)
    control_figure(summary)


if __name__ == "__main__":
    main()
