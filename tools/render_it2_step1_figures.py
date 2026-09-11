#!/usr/bin/env python3
"""Render step 1's report figures — the recall curve, the tiers, the two blind spots.

Reads what the step actually produced (``build/it2/step-1/``) and writes
``figures/track1/iteration2/step-1/<slug>.png`` plus one interactive HTML page. Nothing is
typed: every number on every figure comes from the JSON the run wrote, so a figure cannot
drift from the entry that quotes it.

The four figures are the ones the plan asks step 1 to produce, plus the two its refutations
made necessary:

``recall-at-n``      the curve H012 was tested against, with N = 300 marked and the
                     bootstrap band drawn — the figure that shows *why* the claim failed.
``target-tiers``     what the target set is made of, and how much of it the symptom
                     ranking earned versus the mechanism-term rule.
``ranker-overlap``   how much two independent rankers agree (H014).
``curation-coverage`` how much of the protein-coding genome HPO curation can see at all
                     (H015) — the iteration's largest blind spot.

Usage::

    uv run python tools/render_it2_step1_figures.py
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import csv

import plotly.graph_objects as go

from mva.render import theme
from mva.render.figure import Exhibit, Section
from mva.render.report import render

DEFAULT_IN = Path("build/it2/step-1")
DEFAULT_OUT = Path("figures/track1/iteration2/step-1")

#: The cutoff the target set was fixed at, marked on the curve so the reading is visible.
CHOSEN_N = 300


def recall_figure(curve: dict) -> go.Figure:
    xs = [point["n"] for point in curve["curve"]]
    recalls = [point["recall"] for point in curve["curve"]]
    low = [point["interval"][0] for point in curve["curve"]]
    high = [point["interval"][1] for point in curve["curve"]]

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=xs + xs[::-1],
            y=high + low[::-1],
            # Lines only: the default markers would draw the band's own corner points as
            # data, and a reader would take them for measurements.
            mode="lines",
            fill="toself",
            fillcolor="rgba(61,126,189,0.18)",
            line={"width": 0},
            hoverinfo="skip",
            name="95% bootstrap interval",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=xs,
            y=recalls,
            mode="lines+markers",
            line={"color": theme.MACHINE.line, "width": 2},
            marker={"size": 8},
            name="measured recall",
            hovertemplate="top %{x}: %{y:.3f}<extra></extra>",
        )
    )
    figure.add_hline(
        y=0.90,
        line={"color": theme.GOOD.line, "dash": "dash"},
        annotation_text="H012 predicted ≥ 0.90",
        annotation_position="top left",
    )
    at_n = next(p for p in curve["curve"] if p["n"] == CHOSEN_N)
    figure.add_trace(
        go.Scatter(
            x=[CHOSEN_N],
            y=[at_n["recall"]],
            mode="markers+text",
            marker={"size": 14, "color": theme.BAD.line, "symbol": "x"},
            text=[f"  N = {CHOSEN_N}: {at_n['recall']:.2f}"],
            textposition="middle right",
            name="the chosen cutoff",
        )
    )
    figure.update_xaxes(type="log", title="top N of the ranking")
    figure.update_yaxes(title="share of held-out genes found", range=[0, 1])
    return figure


def tier_figure(targets: list[dict]) -> go.Figure:
    tiers = Counter(row["tier"] for row in targets)
    earned = sum(1 for row in targets if row["entered_by"] == "score")
    colours = {
        "core": theme.GOOD.fill,
        "net": theme.MACHINE.fill,
        "mechanism-term": theme.DECISION.fill,
    }
    figure = go.Figure(
        go.Bar(
            x=[tiers.get(t, 0) for t in ("core", "net", "mechanism-term")],
            y=["core", "net", "mechanism-term"],
            orientation="h",
            marker={
                "color": [colours[t] for t in ("core", "net", "mechanism-term")],
                "line": {"color": theme.INK, "width": 1},
            },
            text=[tiers.get(t, 0) for t in ("core", "net", "mechanism-term")],
            textposition="outside",
        )
    )
    figure.add_annotation(
        x=0,
        y=-0.6,
        xref="x",
        yref="y",
        showarrow=False,
        xanchor="left",
        text=(
            f"{earned} of {len(targets)} rows earned their place by symptom score; "
            f"{len(targets) - earned} entered by the mechanism-term rule alone"
        ),
    )
    figure.update_xaxes(title="genes")
    return figure


def overlap_figure(shared: int, window: int) -> go.Figure:
    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=[shared],
            y=["top 300"],
            orientation="h",
            marker={"color": theme.GOOD.fill, "line": {"color": theme.INK, "width": 1}},
            name="both rankers",
            text=[f"{shared} shared ({shared / window:.0%})"],
            textposition="inside",
        )
    )
    figure.add_trace(
        go.Bar(
            x=[window - shared],
            y=["top 300"],
            orientation="h",
            marker={"color": theme.MUTED.fill, "line": {"color": theme.INK, "width": 1}},
            name="one ranker only",
            text=[f"{window - shared} unique"],
            textposition="inside",
        )
    )
    figure.add_vline(
        x=window / 2,
        line={"color": theme.BAD.line, "dash": "dash"},
        annotation_text="H014 predicted ≥ 50%",
    )
    figure.update_layout(barmode="stack")
    figure.update_yaxes(showticklabels=False)
    figure.update_xaxes(title="genes in the top 300")
    return figure


def coverage_figure(uncurated: int, total: int) -> go.Figure:
    curated = total - uncurated
    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=[curated],
            y=["protein-coding genes"],
            orientation="h",
            marker={"color": theme.GOOD.fill, "line": {"color": theme.INK, "width": 1}},
            name="curated in HPO — rankable",
            text=[f"{curated:,} rankable"],
            textposition="inside",
        )
    )
    figure.add_trace(
        go.Bar(
            x=[uncurated],
            y=["protein-coding genes"],
            orientation="h",
            marker={"color": theme.BAD.fill, "line": {"color": theme.INK, "width": 1}},
            name="no HPO curation — invisible to this ranker",
            text=[f"{uncurated:,} invisible ({uncurated / total:.0%})"],
            textposition="inside",
        )
    )
    figure.update_layout(barmode="stack")
    figure.update_yaxes(showticklabels=False)
    figure.update_xaxes(title="protein-coding genes")
    return figure


def build(source: Path) -> Section:
    curve = json.loads((source / "benchmark.json").read_text(encoding="utf-8"))
    summary = json.loads((source / "summary.json").read_text(encoding="utf-8"))
    with (source / "targets.tsv").open(encoding="utf-8", newline="") as handle:
        targets = list(csv.DictReader(handle, delimiter="\t"))
    overlap = json.loads((source / "agreement.json").read_text(encoding="utf-8"))

    at_n = next(p for p in curve["curve"] if p["n"] == CHOSEN_N)
    return Section(
        slug="it2-step-1",
        title="Step 1 — the blind target set",
        blurb=(
            "Which genes the child's symptoms alone nominate, and how much of the answer "
            "that can be expected to contain. Every figure is drawn from the run's own "
            "output files."
        ),
        exhibits=[
            Exhibit(
                slug="recall-at-n",
                title="How often the symptom ranker finds the causal gene",
                caption=(
                    f"Held-out recall over {curve['diseases_run']} recessive diseases of "
                    f"{curve['diseases_eligible']} eligible, degraded the way Exomiser's own "
                    "benchmark degraded its queries. The cutoff the target set was fixed at "
                    f"is marked: recall there is {at_n['recall']:.2f}, not the 0.90 H012 "
                    "predicted."
                ),
                legend=(
                    "**blue line** = measured recall, **blue band** = its 95% bootstrap "
                    "interval; **green dashed** = the prediction; **red cross** = the "
                    "chosen N. An internal consistency check, not an external validation: "
                    "ground truth and scoring database share curators, and there is no "
                    "genomic background."
                ),
                figure=recall_figure(curve),
                notes=[
                    (
                        f"Median rank {curve['median_rank']}; {curve['unrankable']} of "
                        f"{curve['diseases_run']} genes were unrankable at any N, because "
                        "the withheld disease is the only one curating them."
                    ),
                    (
                        "Raising N does not rescue the claim, which is why the recorded "
                        "decision was to keep N = 300 and describe the target set as an "
                        "enrichment rather than coverage."
                    ),
                ],
            ),
            Exhibit(
                slug="target-tiers",
                title="What the target set is made of",
                caption=(
                    f"{summary['targets']} genes in three tiers. Steps 2-3 read every tier; "
                    "the tier says where human review starts, not what is looked at."
                ),
                legend=(
                    "**green** = core, the top 50 by symptom score · **blue** = net, ranks "
                    "51-300 · **amber** = mechanism-term, admitted by the "
                    "chromosome-instability rule regardless of rank. An amber row is prior "
                    "knowledge, not evidence, and a rediscovery claim may only be made on "
                    "the pure symptom-score ranking."
                ),
                figure=tier_figure(targets),
            ),
            Exhibit(
                slug="ranker-overlap",
                title="How much two independent rankers agree",
                caption=(
                    f"Phen2Gene and the local Resnik ranker share {overlap['shared']} of "
                    f"their top {overlap['window']} genes on the same terms "
                    f"({overlap['shared'] / overlap['window']:.0%}), against the 50% H014 "
                    "predicted."
                ),
                legend=(
                    "**green** = nominated by both methods · **grey** = nominated by one. "
                    "**red dashed** = the prediction. Two good rankers are expected to "
                    "disagree substantially (Yuan 2022), so this refutes the threshold "
                    "rather than either ranker — but it does mean the target set is one "
                    "ranker's opinion, not a converged nomination."
                ),
                figure=overlap_figure(overlap["shared"], overlap["window"]),
            ),
            Exhibit(
                slug="curation-coverage",
                title="How much of the genome this ranker can see at all",
                caption=(
                    f"{summary['uncurated_protein_coding']:,} of "
                    f"{summary['protein_coding_total']:,} protein-coding genes "
                    f"({summary['uncurated_fraction']:.1%}) have no HPO curation, so the "
                    "symptom ranker cannot score them at any N."
                ),
                legend=(
                    "**green** = curated, and therefore rankable · **red** = invisible to "
                    "a curation-driven ranker. H015 predicted under 20% red. This is the "
                    "iteration's largest blind spot, and the reason the `uncurated` tier "
                    "and step 4's genome-wide ranking exist."
                ),
                figure=coverage_figure(
                    summary["uncurated_protein_coding"], summary["protein_coding_total"]
                ),
            ),
        ],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--source", type=Path, default=DEFAULT_IN)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    theme.install_template()
    section = build(args.source)
    args.out.mkdir(parents=True, exist_ok=True)
    for exhibit in section.exhibits:
        written = exhibit.write_image(args.out)
        print(f"  {written if written else f'{exhibit.slug}: no static exporter installed'}")
    page = render(
        [section],
        title="Iteration 2, step 1 — the blind target set",
        subject="PROBAND01 — symptoms only, no genomic data read",
    )
    html = args.out / "index.html"
    html.write_text(page, encoding="utf-8")
    print(f"  {html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
