#!/usr/bin/env python3
"""Step 9, E5+E6: is each candidate safe *for this child*? Three figures (entry 152).

**a — evidence.** Candidate x source heat map. One column per evidence source (the child's
genome via PharmCAT/CPIC, his own phenotypes via OnSIDES labels) and one column for the
two together. Red = that source raises a question, green = it does not, grey = the source
had nothing to say about this drug. Only drugs at least one source speaks to are drawn.

**b — base rate.** Share of ingredients whose labels carry an adverse effect matching one
of the child's phenotypes: the shortlist against a comparison set matched on how many
distinct effects their labels carry. Wilson 95 % intervals, because several candidates
have single-digit label counts.

**c — coverage.** What the callset could actually answer, per pharmacogene: definition
positions genotyped out of positions PharmCAT needs, beside the regional variant density
that says whether the absent positions are plausibly reference or a hole.

**Sources.** ``ressources/track2/candidate_safety.tsv``, ``build/it4/track2-e56/
{pgx,label}_summary.json``.

Usage::

    uv run python tools/render_step9_e56.py

Outputs ``figures/it4/step9-e56-{evidence,baserate,coverage}.{svg,html}`` +
``.provenance.json``, and prints the legend line to paste under each figure.
"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mva.drugs.patient_safety import wilson_interval

TABLE = Path("ressources/track2/candidate_safety.tsv")
PGX = Path("build/it4/track2-e56/pgx_summary.json")
LABELS = Path("build/it4/track2-e56/label_summary.json")
OUT = Path("figures/it4")
ENTRY = "docs/iteration4/step-9/methodology/152-is-each-candidate-safe-for-this-child.md"


def _save(fig: Any, name: str, width: int, height: int | None = None) -> Path:
    """Write the SVG and the interactive HTML. Height defaults to the figure's own."""
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"step9-e56-{name}.svg"
    fig.write_image(path, format="svg", width=width, height=height or fig.layout.height)
    fig.write_html(path.with_suffix(".html"), include_plotlyjs="cdn", full_html=True)
    return path


def _rows() -> list[dict[str, str]]:
    with TABLE.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def evidence_figure(rows: list[dict[str, str]]) -> Any:
    """Candidate x source heat map: who raises a question about which drug."""
    import plotly.graph_objects as go

    from mva.render.theme import BAD, DECISION, GOOD, MUTED

    drawn = [r for r in rows if r["genome_flag"] == "yes" or r["phenotype_flag"] == "yes"]
    drawn.sort(key=lambda r: (r["combined_flag"], r["drug"]))
    labels = [f"{r['drug']} ({r['direction']})"[:44] for r in drawn]

    def cell(row: dict[str, str], column: str) -> float:
        if column == "genome":
            if not row["pgx_genes"]:
                return 0.0
            return 3.0 if row["genome_flag"] == "yes" else 1.0
        if column == "phenotype":
            if row["labels_total"] == "0":
                return 0.0
            return 3.0 if row["phenotype_flag"] == "yes" else 1.0
        flags = (row["genome_flag"] == "yes") + (row["phenotype_flag"] == "yes")
        return {2: 3.0, 1: 2.0}.get(flags, 0.0)

    columns = ["genome (PharmCAT/CPIC)", "phenotypes (OnSIDES labels)", "both sources"]
    z = [[cell(r, key) for key in ("genome", "phenotype", "both")] for r in drawn]
    text = [
        [
            r["genome_call"].split("[")[0][:38],
            (r["phenotype_matched_effects"] if r["phenotype_matched_effects"] != "none" else "-")[
                :38
            ],
            r["combined_flag"]
            .replace(" flags a question", "")
            .replace("unflagged by these two sources (not evidence of safety)", "unflagged"),
        ]
        for r in drawn
    ]
    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=columns,
            y=labels,
            text=text,
            hovertemplate="%{y}<br>%{x}<br>%{text}<extra></extra>",
            colorscale=[
                (0.000, MUTED.fill),
                (0.2499, MUTED.fill),
                (0.2500, GOOD.fill),
                (0.4999, GOOD.fill),
                (0.5000, DECISION.fill),
                (0.7499, DECISION.fill),
                (0.7500, BAD.fill),
                (1.000, BAD.fill),
            ],
            zmin=-0.5,
            zmax=3.5,
            showscale=False,
            xgap=3,
            ygap=2,
            zsmooth=False,
        )
    )
    fig.update_layout(
        template="plotly_white",
        title=(
            "Which source raises a question about which candidate"
            "<br><sub>only candidates at least one source flags are drawn; "
            "the rest are unflagged, which is not the same as safe</sub>"
        ),
        margin={"l": 250, "r": 30, "t": 130, "b": 40},
        title_y=0.96,
        title_yanchor="top",
        height=max(420, 22 * len(drawn) + 140),
    )
    fig.update_xaxes(side="top")
    fig.update_yaxes(autorange="reversed", tickfont={"size": 10})
    return fig


def baserate_figure(labels: dict[str, Any]) -> Any:
    """Shortlist vs matched comparison set, with Wilson intervals."""
    import plotly.graph_objects as go

    from mva.render.theme import BAD, MACHINE

    groups = [
        ("shortlist candidates", labels["shortlist"], BAD),
        ("matched comparison set", labels["comparison_set"], MACHINE),
    ]
    fig = go.Figure()
    for name, block, hue in groups:
        hit, total = block["ingredients_flagged"], block["ingredients"]
        low, high = wilson_interval(hit, total)
        fig.add_bar(
            x=[name],
            y=[hit / total],
            marker_color=hue.fill,
            marker_line_color=hue.line,
            marker_line_width=1.5,
            width=0.45,
            text=[f"{hit}/{total} = {hit / total:.0%}"],
            textposition="inside",
            insidetextanchor="start",
            textfont={"size": 13},
            error_y={
                "type": "data",
                "symmetric": False,
                "array": [high - hit / total],
                "arrayminus": [hit / total - low],
                "color": hue.line,
                "thickness": 1.6,
                "width": 10,
            },
            showlegend=False,
            hovertemplate=f"{name}<br>%{{y:.1%}} (95 % CI {low:.1%}-{high:.1%})<extra></extra>",
        )
    fig.update_layout(
        template="plotly_white",
        title=(
            "Labels that name one of the child's own phenotypes"
            "<br><sub>share of ingredients with at least one matching adverse effect; "
            "Wilson 95 % intervals</sub>"
        ),
        yaxis={"title": "share of ingredients", "tickformat": ".0%", "range": [0, 0.9]},
        margin={"l": 70, "r": 30, "t": 100, "b": 50},
        height=440,
        bargap=0.5,
    )
    return fig


def coverage_figure(pgx: dict[str, Any]) -> Any:
    """Per pharmacogene: positions genotyped out of positions needed, and regional density."""
    from plotly.subplots import make_subplots

    from mva.render.theme import BAD, DECISION, GOOD, MACHINE

    genes = [(g, b) for g, b in pgx["genes"].items() if b["positions_total"] > 0]
    genes.sort(key=lambda kv: -kv[1]["positions_total"])
    names = [g for g, _ in genes]
    fig = make_subplots(
        rows=1,
        cols=2,
        shared_yaxes=True,
        horizontal_spacing=0.08,
        subplot_titles=(
            "definition positions: genotyped vs needed (log)",
            "regional variant density / genome-wide (1.529 PASS per kb)",
        ),
    )
    fig.add_bar(
        x=[b["positions_total"] for _, b in genes],
        y=names,
        orientation="h",
        marker_color=MACHINE.fill,
        marker_line_color=MACHINE.line,
        name="needed",
        hovertemplate="%{y}: %{x} positions needed<extra></extra>",
        row=1,
        col=1,
    )
    fig.add_bar(
        x=[b["positions_called"] or None for _, b in genes],
        y=names,
        orientation="h",
        marker_color=GOOD.fill,
        marker_line_color=GOOD.line,
        name="genotyped",
        hovertemplate="%{y}: %{x} genotyped<extra></extra>",
        row=1,
        col=1,
    )
    ratios = [b["density_ratio"] for _, b in genes]
    fig.add_bar(
        x=ratios,
        y=names,
        orientation="h",
        marker_color=[
            GOOD.fill if r >= 0.5 else (DECISION.fill if r >= 0.2 else BAD.fill) for r in ratios
        ],
        marker_line_color=[
            GOOD.line if r >= 0.5 else (DECISION.line if r >= 0.2 else BAD.line) for r in ratios
        ],
        name="density ratio",
        showlegend=False,
        hovertemplate="%{y}: %{x:.2f}x genome-wide density<extra></extra>",
        row=1,
        col=2,
    )
    fig.add_vline(x=0.5, line_dash="dash", line_color=GOOD.line, row=1, col=2)
    fig.add_vline(x=0.2, line_dash="dot", line_color=BAD.line, row=1, col=2)
    fig.update_xaxes(type="log", title_text="positions (log)", dtick=1, row=1, col=1)
    fig.update_xaxes(title_text="x genome-wide", row=1, col=2)
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(
        template="plotly_white",
        barmode="overlay",
        title="What the variant-only callset could answer, per pharmacogene",
        height=620,
        margin={"l": 90, "r": 30, "t": 90, "b": 60},
        legend={"orientation": "h", "y": -0.1},
    )
    return fig


def main() -> int:
    from mva.render.theme import BAD, DECISION, GOOD, MACHINE, MUTED

    rows = _rows()
    pgx = json.loads(PGX.read_text())
    labels = json.loads(LABELS.read_text())
    written = [
        _save(evidence_figure(rows), "evidence", 1020),
        _save(baserate_figure(labels), "baserate", 760, 430),
        _save(coverage_figure(pgx), "coverage", 1150, 620),
    ]
    print(
        f"evidence: **Legend** — red = that source raises a question ({BAD.label}); "
        f"green = that source looked and raised none ({GOOD.label}); "
        f"yellow = exactly one of the two sources ({DECISION.label}); "
        f"grey = the source had nothing on this drug ({MUTED.label}). "
        "'Unflagged' is not safe: it means these two sources are silent."
    )
    print(
        f"baserate: **Legend** — red = the shortlist ({BAD.label}); blue = the matched "
        f"comparison set ({MACHINE.label}); bars = Wilson 95 % intervals."
    )
    print(
        f"coverage: **Legend** — blue = positions PharmCAT needs ({MACHINE.label}); "
        f"green = positions this callset genotyped, no green bar = none ({GOOD.label}); "
        "right panel green = "
        f"region called at ≥ 0.5x the genome-wide rate, yellow = 0.2-0.5x ({DECISION.label}), "
        f"red = below 0.2x, where an absent-to-ref assumption is not supported ({BAD.label})."
    )
    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()
    for path in written:
        provenance = {
            "name": path.stem,
            "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "built_by": "tools/render_step9_e56.py",
            "code_version": commit,
            "inputs": [
                {"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                for p in (TABLE, PGX, LABELS)
            ],
            "sources": {
                "genomic": "the child's callset, read only as PharmCAT actionability words",
                "clinical": "the proband's 7 own HPO terms, mapped in hpo_to_adverse_terms.tsv",
            },
            "entry": ENTRY,
        }
        path.with_suffix(".provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
