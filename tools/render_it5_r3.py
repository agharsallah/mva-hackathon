#!/usr/bin/env python3
"""Render route R3's figures from the tables it wrote — never from a database.

Three figures, all built from files the run already produced, so a figure cannot quote a
number the tables do not:

1. **extraction funnel** — papers retrieved → texts cached → sentences screened → rows
   written → rows that passed the quote gate → candidate rows. The point of the figure is
   how much is dropped, and where.
2. **evidence map** — intervention × effect, coloured by whether the reported direction is
   the one a hypomorph (too little protein) wants. Harm rows are kept on the same map: a
   compound that lowers BubR1 is a safety signal, not a missing row.
3. **MVA drug exposures** — what the reported MVA patients were actually given and how it
   went, coloured by outcome, annotated with the proband's overlapping HPO term.

Inputs: ``ressources/track2/it5/litmine_{corpus,interventions,mva_exposures}.tsv``,
``literature_candidates.tsv`` and ``build/it5/r3/screen_stats.json``.
Outputs: ``figures/it5/r3-<slug>.svg`` and ``.html``.

Usage::

    uv run python tools/render_it5_r3.py
"""

from __future__ import annotations

import argparse
import csv
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import plotly.graph_objects as go

from mva.render.theme import BAD, DECISION, GOOD, MACHINE, MUTED, RAW, install_template, legend_line

SCRIPT = "tools/render_it5_r3.py"
TABLES = Path("ressources/track2/it5")
STATS = Path("build/it5/r3/screen_stats.json")
CORPUS_STATS = Path("build/it5/r3/corpus_stats.json")
OUT = Path("figures/it5")

#: For a hypomorph: the direction of each effect that helps. Mirrors the driver's card.
DESIRED = {
    "bubr1_level": "increase",
    "function": "increase",
    "aneuploidy": "decrease",
    "senescence": "decrease",
    "lifespan": "increase",
    "tumour": "decrease",
}
EFFECT_ORDER = [
    "bubr1_level",
    "acetylation",
    "function",
    "aneuploidy",
    "senescence",
    "lifespan",
    "tumour",
    "other",
]
OUTCOME_COLOUR = {
    "tolerated": GOOD,
    "response": DECISION,
    "toxicity": BAD,
    "death": BAD,
    "other": MACHINE,
}


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def polarity(row: Mapping[str, str]) -> str:
    goal = DESIRED.get(row["effect_on"])
    if not goal or row["direction"] == "no_change":
        return "neutral"
    return "benefit" if row["direction"] == goal else "harm"


# ── figures ──────────────────────────────────────────────────────────────────────────────


def funnel(
    corpus: Sequence[Mapping[str, str]],
    kept: Sequence[Mapping[str, str]],
    rejected: Sequence[Mapping[str, str]],
    candidate_rows: Sequence[Mapping[str, str]],
    stats: Mapping[str, Any],
) -> tuple[go.Figure, str, str]:
    papers = int(stats.get("papers_retrieved") or len({r["pmid"] for r in corpus}))
    stages = [
        ("papers retrieved by the 6 queries", papers, RAW),
        ("papers with a cached text", len({r["pmid"] for r in corpus}), RAW),
        ("texts cached (abstract + full)", len(corpus), RAW),
        ("sentences past the screen", int(stats.get("intervention_sentences", 0)), MACHINE),
        ("rows written by the reader", len(kept) + len(rejected), DECISION),
        ("rows past the quote gate", len(kept), GOOD),
        ("approved-drug candidate rows", len(candidate_rows), GOOD),
    ]
    figure = go.Figure(
        go.Bar(
            x=[value for _, value, _ in stages],
            y=[f"{label} ({value})" for label, value, _ in stages],
            orientation="h",
            marker={
                "color": [hue.fill for *_, hue in stages],
                "line": {"color": [hue.line for *_, hue in stages], "width": 1.5},
            },
            hovertemplate="%{y}<extra></extra>",
        )
    )
    figure.update_layout(
        title="R3 extraction funnel: from a query to a quote-verified candidate",
        xaxis={"title": "records (log scale)", "type": "log"},
        yaxis={"autorange": "reversed"},
        height=380,
        showlegend=False,
        meta={"script": SCRIPT, "source": "ressources/track2/it5/litmine_*.tsv"},
    )
    caption = f"{papers} papers → {len(kept)} verified rows → {len(candidate_rows)} candidate rows"
    return (
        figure,
        caption,
        legend_line(
            RAW, MACHINE, DECISION, GOOD, extra="log x-axis, so a short bar is still hundreds"
        ),
    )


def evidence_map(rows: Sequence[Mapping[str, str]]) -> tuple[go.Figure, str, str]:
    interventions = sorted({r["intervention"] for r in rows})
    marks: dict[str, list[Any]] = {
        "x": [],
        "y": [],
        "colour": [],
        "line": [],
        "text": [],
        "size": [],
    }
    counts = {"benefit": 0, "harm": 0, "neutral": 0}
    for row in rows:
        kind = polarity(row)
        counts[kind] += 1
        hue = {"benefit": GOOD, "harm": BAD, "neutral": MUTED}[kind]
        marks["x"].append(row["effect_on"])
        marks["y"].append(row["intervention"])
        marks["colour"].append(hue.fill)
        marks["line"].append(hue.line)
        marks["size"].append(26 if row["model_system"].endswith("in_vivo") else 18)
        marks["text"].append(
            f"{row['intervention']}<br>{row['effect_on']}: {row['direction']}"
            f"<br>{row['model_system']} · PMID {row['pmid']}"
        )
    figure = go.Figure(
        go.Scatter(
            x=marks["x"],
            y=marks["y"],
            mode="markers",
            marker={
                "size": marks["size"],
                "color": marks["colour"],
                "line": {"color": marks["line"], "width": 2},
                "symbol": "square",
            },
            text=marks["text"],
            hovertemplate="%{text}<extra></extra>",
        )
    )
    figure.update_layout(
        title="R3 evidence map: every quote-verified intervention × what it moved",
        xaxis={"categoryorder": "array", "categoryarray": EFFECT_ORDER, "title": "effect measured"},
        yaxis={"title": "", "automargin": True},
        height=max(420, 26 * len(interventions) + 180),
        showlegend=False,
        meta={"script": SCRIPT, "source": "ressources/track2/it5/litmine_interventions.tsv"},
    )
    caption = (
        f"{len(rows)} rows over {len(interventions)} interventions: "
        f"{counts['benefit']} helpful, {counts['harm']} harmful, {counts['neutral']} neither"
    )
    legend = legend_line(
        GOOD,
        BAD,
        MUTED,
        extra="a big square is an animal or a patient, a small one is cells",
    )
    return figure, caption, legend


def exposures(rows: Sequence[Mapping[str, str]]) -> tuple[go.Figure, str, str]:
    labels, colours, lines, text = [], [], [], []
    for row in rows:
        hue = OUTCOME_COLOUR.get(row["outcome_kind"], MACHINE)
        labels.append(f"{row['drug_or_regimen'][:46]}<br><i>{row['patient_gene'][:34]}</i>")
        colours.append(hue.fill)
        lines.append(hue.line)
        text.append(f"{row['outcome']}<br>HPO overlap: {row['hpo_overlap']}<br>PMID {row['pmid']}")
    figure = go.Figure(
        go.Bar(
            x=[1] * len(rows),
            y=labels,
            orientation="h",
            marker={"color": colours, "line": {"color": lines, "width": 1.5}},
            text=[r["outcome_kind"] for r in rows],
            textposition="inside",
            hovertext=text,
            hovertemplate="%{hovertext}<extra></extra>",
        )
    )
    figure.update_layout(
        title="What MVA patients were actually given, and how it went",
        xaxis={"visible": False},
        yaxis={"autorange": "reversed", "automargin": True},
        height=max(380, 46 * len(rows) + 140),
        showlegend=False,
        meta={"script": SCRIPT, "source": "ressources/track2/it5/litmine_mva_exposures.tsv"},
    )
    kinds = {r["outcome_kind"] for r in rows}
    caption = f"{len(rows)} quote-verified exposures across {len(kinds)} outcome kinds"
    legend = legend_line(
        GOOD,
        DECISION,
        BAD,
        MACHINE,
        extra="green tolerated; yellow a response question; red toxicity or death; "
        "blue an advisory statement",
    )
    return figure, caption, legend


# ── driver ───────────────────────────────────────────────────────────────────────────────


def write(figure: go.Figure, out_dir: Path, slug: str) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    try:
        figure.write_image(
            out_dir / f"{slug}.svg", format="svg", width=1000, height=figure.layout.height or 420
        )
        written += 1
    except Exception as error:  # kaleido is optional; report the miss and keep the HTML
        print(f"  {slug}.svg not written ({type(error).__name__}: {error})")
    figure.write_html(out_dir / f"{slug}.html", include_plotlyjs="cdn", full_html=True)
    return written + 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--tables", type=Path, default=TABLES)
    parser.add_argument("--stats", type=Path, default=STATS)
    parser.add_argument("--out-dir", type=Path, default=OUT)
    args = parser.parse_args()
    install_template()
    kept = read_tsv(args.tables / "litmine_interventions.tsv")
    rejected = read_tsv(args.tables / "litmine_rejected.tsv")
    corpus = read_tsv(args.tables / "litmine_corpus.tsv")
    exposure_rows = read_tsv(args.tables / "litmine_mva_exposures.tsv")
    candidate_rows = read_tsv(args.tables / "literature_candidates.tsv")
    stats = json.loads(args.stats.read_text(encoding="utf-8")) if args.stats.exists() else {}
    if CORPUS_STATS.exists():
        stats = {**stats, **json.loads(CORPUS_STATS.read_text(encoding="utf-8"))}
    jobs = [
        ("r3-extraction-funnel", funnel(corpus, kept, rejected, candidate_rows, stats)),
        ("r3-evidence-map", evidence_map(kept)),
        ("r3-mva-exposures", exposures(exposure_rows)),
    ]
    total = 0
    for slug, (figure, caption, legend) in jobs:
        total += write(figure, args.out_dir, slug)
        print(f"{slug:<26} {caption}\n  > {legend}")
    print(f"{total} files in {args.out_dir}")


if __name__ == "__main__":
    main()
