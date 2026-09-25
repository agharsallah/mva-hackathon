#!/usr/bin/env python3
"""Step 11, T1: the chain on a second case, in three figures (entry 156).

(a) ``step11-t1-stages`` - one row per stage of iteration 4's Track 2 chain, one column per
    case (MVA, then the transfer case): did it run, what it took to run (configuration
    alone, configuration with mislabelled text, or a code change), and how many rows it wrote.
(b) ``step11-t1-overlap`` - the two cases' generator unions: drugs per generator and case,
    and the drugs both unions share, with the Jaccard index against H096's two bars.
(c) ``step11-t1-twin`` - where the transfer gene's best mouse genotype ranks among every MGI
    genotype, against the IC-matched null of the same size, per rollup; the case's
    within-pathway genes beside it.

**Sources.** Counts from the files the stages wrote (``--case-dir``, MVA's step-9/10 tables),
runtimes from the build logs, the null from ``twin.json``; classes from transfer_stages.tsv.

    uv run python tools/render_step11_t1.py

Outputs ``figures/it4/step11-t1-{stages,overlap,twin}.{svg,html}`` + ``.provenance.json``.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from mva.drugs import provenance
from mva.drugs.convergence_tables import read_generator
from mva.render.theme import BAD, DECISION, GOOD, MACHINE, MUTED, install_template, legend_line

ENTRY = "docs/iteration4/step-11/methodology/156-the-chain-on-bloom-syndrome.md"
BUILD = Path("build/it4/track2-t1")
MVA = Path("ressources/track2/it4")
GENERATORS = ("walk", "twin", "prism", "lincs")

#: The stage table (entry 156's static survey, fixed before the run) lives beside the case:
#: ``transfer_stages.tsv`` - stage, case_file, mva_file, class, gaps, log. Class:
#: ``config`` = CLI + flags + data files; ``mislabelled`` = ran from flags but wrote MVA
#: text; ``code`` = needed tools/transfer_it4.py.
CLASS_HUE = {"config": GOOD, "mislabelled": DECISION, "code": BAD}
CLASS_WORD = {
    "config": "configuration alone",
    "mislabelled": "configuration; MVA text relabelled",
    "code": "needed new code",
}


def _rows(path: Path) -> int | None:
    if not path.is_file():
        return None
    with path.open(encoding="utf-8", newline="") as handle:
        return max(sum(1 for _ in csv.reader(handle, delimiter="\t")) - 1, 0)


def _runtime(log: Path) -> float | None:
    if not log.is_file():
        return None
    found = re.findall(r"^real\s+([0-9.]+)", log.read_text(encoding="utf-8"), re.M)
    return float(found[-1]) if found else None


def _write(
    fig: go.Figure, name: str, size: tuple[int, int], inputs: list[Path], legend: str
) -> None:
    out, preview = Path("figures/it4"), BUILD / "preview"
    out.mkdir(parents=True, exist_ok=True)
    preview.mkdir(parents=True, exist_ok=True)
    svg = out / f"step11-t1-{name}.svg"
    fig.write_image(svg, format="svg", width=size[0], height=size[1])
    fig.write_image(preview / f"{name}.png", format="png", width=size[0], height=size[1], scale=2)
    fig.write_html(svg.with_suffix(".html"), include_plotlyjs="cdn", full_html=True)
    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()
    manifest = {
        "name": svg.stem,
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "built_by": "tools/render_step11_t1.py",
        "code_version": commit,
        "inputs": [
            {"path": p.as_posix(), "sha256": provenance.digest(p)[0]} for p in inputs if p.is_file()
        ],
        "entry": ENTRY,
        "legend": legend,
        "patient_data": (
            "none. Public screens, graphs, signatures and annotations; MVA's generator lists "
            "are drug names only; no genomic position appears"
        ),
    }
    svg.with_suffix(".provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {svg}\n  {legend}\n")


def _stages(home: Path) -> list[tuple[str, str, str, str, str, str]]:
    with (home / "transfer_stages.tsv").open(encoding="utf-8", newline="") as handle:
        return [
            (r["stage"], r["case_file"], r["mva_file"], r["class"], r["gaps"], r["log"])
            for r in csv.DictReader(handle, delimiter="\t")
        ]


def stages_figure(home: Path) -> None:
    """A stage x case matrix: coloured by what running it took, labelled with rows written."""
    stages = _stages(home)
    names = [s[0] for s in stages][::-1]
    fig = go.Figure()
    inputs: list[Path] = []
    for column in (0, 1):
        for stage, own, mva, klass, gaps, log in stages:
            path = Path(mva) if column == 0 else home / own
            inputs.append(path)
            rows = _rows(path)
            if column == 0:
                hue, text = MACHINE, f"{rows:,} rows" if rows is not None else "missing"
            else:
                hue = CLASS_HUE[klass] if rows is not None else MUTED
                secs = _runtime(BUILD / log) if log else None
                text = (f"{rows:,} rows" if rows is not None else "not written") + (
                    f" · {secs:.0f} s" if secs is not None else ""
                )
                text += f"<br><span style='font-size:10px'>{CLASS_WORD[klass]} (gap {gaps})</span>"
            fig.add_trace(
                go.Scatter(
                    x=[column],
                    y=[stage],
                    mode="markers+text",
                    marker=dict(
                        symbol="square",
                        size=64,
                        color=hue.fill,
                        line=dict(color=hue.line, width=1.5),
                    ),
                    text=[text],
                    textposition="middle right" if column else "middle center",
                    textfont=dict(size=11),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )
    fig.update_layout(
        title="The chain on a second case: which stages ran by configuration alone",
        xaxis=dict(
            tickvals=[0, 1],
            ticktext=["MVA (entries 150-155)", "Bloom syndrome (entry 156)"],
            range=[-0.5, 2.4],
            showgrid=False,
            zeroline=False,
        ),
        yaxis=dict(categoryorder="array", categoryarray=names, showgrid=False),
        margin=dict(l=190, r=30, t=70, b=50),
    )
    legend = legend_line(
        MACHINE,
        extra=(
            "blue = the MVA run, built for that case; Bloom column: green = configuration "
            "alone, yellow = ran from flags but wrote MVA-case text that tools/transfer_it4.py "
            "relabel had to correct, red = needed new code (tools/transfer_it4.py), grey = not "
            "written; 'gap' = entry 156's static-survey row; seconds = wall time from the log"
        ),
    )
    _write(fig, "stages", (980, 560), inputs, legend)


def _union(directory: Path) -> tuple[dict[str, frozenset[str]], set[str]]:
    lists = {g: read_generator(directory, g).drugs for g in GENERATORS}
    return lists, set().union(*lists.values())


def overlap_figure(home: Path) -> dict[str, Any]:
    """Drugs per generator for both cases, the shared drugs, and the Jaccard index."""
    mva, mva_all = _union(MVA / "generators")
    blm, blm_all = _union(home / "generators")
    shared = sorted(mva_all & blm_all)
    jaccard = len(shared) / len(mva_all | blm_all) if mva_all | blm_all else 0.0
    fig = make_subplots(
        rows=1,
        cols=2,
        column_widths=[0.55, 0.45],
        horizontal_spacing=0.14,
        subplot_titles=("approved drugs listed, per generator", "the two unions"),
    )
    for name, lists, hue in (("MVA", mva, MACHINE), ("Bloom", blm, DECISION)):
        fig.add_trace(
            go.Bar(
                name=name,
                x=list(GENERATORS),
                y=[len(lists[g]) for g in GENERATORS],
                marker=dict(color=hue.fill, line=dict(color=hue.line, width=1)),
                text=[len(lists[g]) for g in GENERATORS],
                textposition="outside",
            ),
            row=1,
            col=1,
        )
    only_mva, only_blm = len(mva_all - blm_all), len(blm_all - mva_all)
    hue_j = GOOD if jaccard <= 0.20 else BAD if jaccard > 0.50 else DECISION
    fig.add_trace(
        go.Bar(
            x=["MVA only", "shared", "Bloom only"],
            y=[only_mva, len(shared), only_blm],
            marker=dict(
                color=[MACHINE.fill, hue_j.fill, DECISION.fill],
                line=dict(color=[MACHINE.line, hue_j.line, DECISION.line], width=1),
            ),
            text=[only_mva, len(shared), only_blm],
            textposition="outside",
            showlegend=False,
        ),
        row=1,
        col=2,
    )
    fig.add_annotation(
        xref="x2 domain",
        yref="y2 domain",
        x=0.5,
        y=1.0,
        showarrow=False,
        text=(
            f"Jaccard {jaccard:.3f} (H096: ≤ 0.20 met, > 0.50 refuted)<br>shared: "
            + (
                "<br>".join(
                    ", ".join(x.title() for x in shared[i : i + 4])
                    for i in range(0, len(shared), 4)
                )
                if shared
                else "none"
            )
        ),
        font=dict(size=11),
    )
    fig.update_layout(
        barmode="group",
        title="Different disease, different drugs?",
        margin=dict(t=120, b=110),
        legend=dict(orientation="h", x=0, y=-0.2),
    )
    fig.update_yaxes(range=[0, 70], row=1, col=2)
    legend = legend_line(
        MACHINE,
        DECISION,
        extra=(
            "blue = MVA's lists, yellow = Bloom's lists; the shared bar is green when the "
            "Jaccard index is ≤ 0.20 (H096 clause c met), red above 0.50 (refuted), yellow "
            "between; counts are approved listed drugs by mva.drugs.convergence_tables."
            "read_generator (join key base_name)"
        ),
    )
    inputs = [MVA / "generators" / f"{g}.tsv" for g in GENERATORS]
    inputs += [home / "generators" / f"{g}.tsv" for g in GENERATORS]
    _write(fig, "overlap", (1000, 500), inputs, legend)
    return {
        "mva_union": len(mva_all),
        "bloom_union": len(blm_all),
        "shared": shared,
        "jaccard": jaccard,
        "per_generator": {g: {"mva": len(mva[g]), "bloom": len(blm[g])} for g in GENERATORS},
    }


def twin_figure(twin: Path) -> None:
    """The best genotype's percentile against its null, per rollup, and the pathway genes."""
    data = json.loads(twin.read_text(encoding="utf-8"))
    study = next(iter(data["studies"].values()))
    gene = study["gene"]
    metrics = ("symmetric", "phenodigm")
    fig = make_subplots(
        rows=1,
        cols=3,
        horizontal_spacing=0.08,
        subplot_titles=(
            f"{metrics[0]}: best {gene} genotype vs null",
            f"{metrics[1]}: best {gene} genotype vs null",
            "best genotype per gene (symmetric)",
        ),
    )
    for col, metric in enumerate(metrics, start=1):
        null = study["null"]["percentiles"][metric]
        fig.add_trace(
            go.Histogram(
                x=null,
                nbinsx=40,
                marker=dict(color=MACHINE.fill, line=dict(color=MACHINE.line, width=0.5)),
                showlegend=False,
            ),
            row=1,
            col=col,
        )
        best = study["best"][metric]["percentile"]
        hue = GOOD if best <= 5 else BAD if best > 25 else DECISION
        fig.add_vline(x=best, line=dict(color=hue.line, width=3), row=1, col=col)
        fig.add_vline(x=5, line=dict(color=DECISION.line, dash="dash"), row=1, col=col)
        fig.add_annotation(
            x=best,
            y=1,
            yref=f"y{col} domain" if col > 1 else "y domain",
            xref=f"x{col}" if col > 1 else "x",
            text=f"{best:.2f} %<br>p {study['null']['empirical_p'][metric]:.3f}",
            showarrow=False,
            xanchor="left",
            font=dict(size=11, color=hue.line),
        )
        fig.update_xaxes(
            title_text="percentile among 76,699 genotypes (lower = closer)", row=1, col=col
        )
    rows = [(gene, study["best"]["symmetric"]["percentile"])]
    rows += [
        (p["gene"], p["symmetric"]["percentile"])
        for p in next(iter(data["pathway"].values()))
        if p.get("symmetric")
    ]
    rows.sort(key=lambda r: r[1])
    fig.add_trace(
        go.Bar(
            x=[r[1] for r in rows],
            y=[r[0] for r in rows],
            orientation="h",
            marker=dict(
                color=[DECISION.fill if r[0] == gene else MUTED.fill for r in rows],
                line=dict(
                    color=[DECISION.line if r[0] == gene else MUTED.line for r in rows], width=1
                ),
            ),
            text=[f"{r[1]:.2f} %" for r in rows],
            textposition="outside",
            showlegend=False,
            cliponaxis=False,
        ),
        row=1,
        col=3,
    )
    fig.update_xaxes(type="log", title_text="percentile (log)", row=1, col=3)
    fig.update_yaxes(title_text="null sets", row=1, col=1)
    fig.update_layout(
        title=f"The {gene} phenotype twin (retrospective: entry 150's control)", bargap=0.05
    )
    legend = legend_line(
        MACHINE,
        extra=(
            "blue bars = the best-genotype percentile for 1,000 IC-matched random term sets of "
            "the same size; solid line = the real query's best genotype, green when ≤ 5 % "
            "(H096 clause b), red above 25 %, yellow between; dashed yellow = the 5 % bar; "
            f"right: yellow = {gene}, grey = the case's within-pathway genes (context)"
        ),
    )
    _write(fig, "twin", (1250, 430), [twin], legend)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--case-dir", type=Path, default=Path("ressources/track2/transfer-it4/BLM"))
    parser.add_argument("--twin", type=Path, default=BUILD / "twin" / "twin.json")
    args = parser.parse_args()
    install_template()
    stages_figure(args.case_dir)
    summary = overlap_figure(args.case_dir)
    twin_figure(args.twin)
    (BUILD / "overlap.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
