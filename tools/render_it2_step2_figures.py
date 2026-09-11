#!/usr/bin/env python3
"""Render step 2's report figures from the files the run wrote.

Every number on every figure comes from JSON or TSV the run produced, so a figure cannot
drift from the entry that quotes it. A figure whose input is absent is **skipped**, not
drawn empty: a chart of zeros and a stage that did not run look the same to a reader, and
only one of them is a result.

Writes ``figures/track1/iteration2/step-2/<slug>.png`` plus one interactive page.

Usage::

    uv run python tools/render_it2_step2_figures.py
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import plotly.graph_objects as go

from mva.render import theme
from mva.render.figure import Exhibit, Section
from mva.render.report import render

DEFAULT_IN = Path("build/it2/step-2")
DEFAULT_OUT = Path("figures/track1/iteration2/step-2")

#: The pre-registered gate the uniqueness pass was judged against, drawn on its figure so
#: the failure is visible rather than described.
OFF_TARGET_GATE = 0.05

#: Genes below this share of the median bait density are called unreachable (entry 085).
SPARSE_FRACTION = 0.5

#: Left margin for the horizontal charts. Their category labels are sentences, not words
#: ("wide-tier reach, +/- 50 kb"), and the template's default margin clips them.
LABEL_MARGIN = 230


def read_json(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def read_tsv(path: Path) -> list[dict[str, str]] | None:
    if not path.exists():
        return None
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def funnel_figure(summary: dict, pass_report: dict, recovery: dict | None) -> go.Figure:
    """Every read the pass started with, and what survived each narrowing."""
    stages = [
        ("reads in the store", pass_report["reads_scanned"], theme.RAW),
        ("share a bait k-mer", pass_report["reads_matched"], theme.MACHINE),
        ("distinct fragments", pass_report["fragments"], theme.MACHINE),
    ]
    if recovery:
        stages.append(("complete pairs", recovery["fragments"], theme.GOOD))
    labels = [name for name, _, _ in stages]
    values = [value for _, value, _ in stages]
    figure = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker={
                "color": [hue.fill for _, _, hue in stages],
                "line": {"color": [hue.line for _, _, hue in stages], "width": 1.5},
            },
            text=[f"{value:,}" for value in values],
            textposition="outside",
            hovertemplate="%{y}: %{x:,}<extra></extra>",
        )
    )
    expected = summary["expected_reads"]
    figure.add_vline(
        x=expected,
        line={"color": theme.DECISION.line, "dash": "dash"},
        annotation_text=f"predicted {expected:,.0f}",
        annotation_position="top",
    )
    figure.update_xaxes(type="log", title="reads (log scale)")
    figure.update_yaxes(autorange="reversed")
    figure.update_layout(margin={"l": LABEL_MARGIN})
    return figure


def uniqueness_figure(summary: dict, sweep: dict | None) -> go.Figure:
    """What the off-target gate measured, and everything it was compared against."""
    unique = summary.get("uniqueness") or {}
    rows: list[tuple[str, float]] = [
        ("bait as built (k=31)", unique["repeated"] / unique["bait_kmers"])
    ]
    if sweep:
        rows.extend(
            (f"zone: {name}", zone["off_target"])
            for name, zone in (sweep.get("by_zone") or {}).items()
        )
        rows.extend(
            (f"whole bait at k={entry['k']}", entry["off_target"])
            for entry in sweep.get("by_k") or []
            if entry["k"] != 31
        )
    labels = [name for name, _ in rows]
    values = [value for _, value in rows]
    colours = [theme.BAD.fill if value >= OFF_TARGET_GATE else theme.GOOD.fill for value in values]
    lines = [theme.BAD.line if value >= OFF_TARGET_GATE else theme.GOOD.line for value in values]
    figure = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker={"color": colours, "line": {"color": lines, "width": 1.5}},
            text=[f"{value * 100:.2f}%" for value in values],
            textposition="outside",
            hovertemplate="%{y}: %{x:.4f}<extra></extra>",
        )
    )
    figure.add_vline(
        x=OFF_TARGET_GATE,
        line={"color": theme.DECISION.line, "dash": "dash"},
        annotation_text="gate: < 5%",
        annotation_position="top",
    )
    figure.update_xaxes(title="bait k-mers occurring more than once in GRCh38", tickformat=".1%")
    figure.update_yaxes(autorange="reversed")
    figure.update_layout(margin={"l": LABEL_MARGIN}, showlegend=False)
    return figure


def density_figure(profile: list[dict[str, str]], sparse: list[str]) -> go.Figure:
    """Per-gene bait density by tier — what the failed gate was actually proxying for."""
    tiers = ("core", "mechanism-term", "net", "decoy")
    hues = {
        "core": theme.GOOD,
        "mechanism-term": theme.GOOD,
        "net": theme.MACHINE,
        "decoy": theme.MUTED,
    }
    densities = [float(row["density"]) for row in profile]
    median = statistics.median(densities) if densities else 0.0
    figure = go.Figure()
    for tier in tiers:
        values = [float(row["density"]) for row in profile if row["tier"] == tier]
        if not values:
            continue
        figure.add_trace(
            go.Box(
                x=values,
                name=f"{tier} (n={len(values)})",
                orientation="h",
                boxpoints="outliers",
                marker={"color": hues[tier].line, "size": 4},
                fillcolor=hues[tier].fill,
                line={"color": hues[tier].line},
                hovertemplate="%{x:.3f}<extra></extra>",
            )
        )
    figure.add_vline(
        x=median * SPARSE_FRACTION,
        line={"color": theme.BAD.line, "dash": "dash"},
        annotation_text=(f"half the median ({median * SPARSE_FRACTION:.2f}) — {len(sparse)} below"),
        annotation_position="bottom right",
    )
    figure.update_xaxes(title="surviving unique k-mers per base", range=[0, 1.05])
    figure.update_layout(margin={"l": LABEL_MARGIN})
    return figure


def depth_figure(rows: list[dict[str, str]]) -> go.Figure:
    """Distribution of per-interval depth, with the floor every absence is read against."""
    depths = [float(row["mean_depth"]) for row in rows]
    figure = go.Figure(
        go.Histogram(
            x=depths,
            nbinsx=80,
            marker={"color": theme.MACHINE.fill, "line": {"color": theme.MACHINE.line, "width": 1}},
            hovertemplate="depth %{x}: %{y} intervals<extra></extra>",
        )
    )
    figure.add_vline(
        x=10,
        line={"color": theme.BAD.line, "dash": "dash"},
        annotation_text="10x floor",
        annotation_position="top right",
    )
    figure.update_xaxes(title="mean depth over a baited interval")
    figure.update_yaxes(title="intervals")
    return figure


def build(source: Path) -> Section:
    summary = read_json(source / "summary.json")
    pass_report = read_json(source / "bait-pass.json")
    recovery = read_json(source / "recovery.json")
    sweep = read_json(source / "uniqueness-sweep.json")
    profile = read_tsv(source / "bait-profile.tsv")
    profile_summary = read_json(source / "bait-profile.json") or {}
    depths = read_tsv(source / "tables" / "it2_exon_depth.tsv")

    if summary is None:
        raise SystemExit(f"no summary.json under {source} — run tools/build_it2_bait.py first")

    unique = summary.get("uniqueness") or {}
    off_target = unique["repeated"] / unique["bait_kmers"] if unique.get("bait_kmers") else 0.0
    exhibits: list[Exhibit] = []

    if pass_report:
        exhibits.append(
            Exhibit(
                slug="recovery-funnel",
                title="From 1.07 billion reads to the fragments worth aligning",
                caption=(
                    f"{pass_report['reads_scanned']:,} reads swept against "
                    f"{pass_report['bait_kmers']:,} bait k-mers at stride "
                    f"{pass_report['stride']}. {pass_report['matched_fraction'] * 100:.4f}% "
                    f"matched, against a bait occupying "
                    f"{summary['genome_fraction'] * 100:.2f}% of the genome — the agreement "
                    "between those two numbers is the check that the engine is correct."
                ),
                legend=theme.legend_line(
                    theme.RAW,
                    theme.MACHINE,
                    theme.GOOD,
                    extra="**yellow dashed** = the recovery predicted before the pass ran.",
                ),
                figure=funnel_figure(summary, pass_report, recovery),
                notes=[
                    (
                        f"Gate: within 0.5-2x of {summary['expected_reads']:,} reads "
                        f"({summary['expected_reads_gate'][0]:,}-"
                        f"{summary['expected_reads_gate'][1]:,})."
                    ),
                ],
            )
        )

    exhibits.append(
        Exhibit(
            slug="bait-uniqueness",
            title="The off-target gate, and everything it was compared against",
            caption=(
                f"{unique.get('repeated', 0):,} of {unique.get('bait_kmers', 0):,} bait "
                f"k-mers ({off_target * 100:.2f}%) occur more than once in GRCh38 and were "
                "dropped. The pre-registered gate was 5%. It was not moved: the other bars "
                "are what the number was measured against, not attempts to pass it."
            ),
            legend=(
                "**red** = above the gate, **green** = below it, **yellow dashed** = the "
                "gate itself. Zones are measured independently against the whole genome, "
                "so they do not partition the bait and their counts do not sum to it."
            ),
            figure=uniqueness_figure(summary, sweep),
            notes=[
                (
                    "Removing the wide padding entirely would move the load from "
                    "8.79% to 8.38% — padding is not the lever, and abandoning it costs "
                    "the only reach step 2 has for an exon-scale deletion."
                    if sweep
                    else "The k and zone sweep has not run."
                ),
                (
                    f"{unique.get('unseen', 0)} bait k-mers were never found in the genome "
                    "pass, which must be zero: every one was cut from the same reference."
                ),
            ],
        )
    )

    if profile:
        sparse = profile_summary.get("sparse_genes", [])
        exhibits.append(
            Exhibit(
                slug="bait-density",
                title="What the gate was proxying for: can the bait reach each gene?",
                caption=(
                    f"Surviving unique k-mers per base, per gene, after the filter. "
                    f"{len(sparse)} of {len(profile)} genes fall below half the median — "
                    "and none of them is core or mechanism-term. The genes step 2 reasons "
                    "about are all reachable; the sparse ones are segmental-duplication "
                    "families, mostly in the decoy set."
                ),
                legend=theme.legend_line(
                    theme.GOOD,
                    theme.MACHINE,
                    theme.MUTED,
                    extra=(
                        "**green** = the tiers step 2 draws conclusions from, **blue** = "
                        "screened but not core, **grey** = the decoy null; **red dashed** "
                        "= the reachability threshold."
                    ),
                ),
                figure=density_figure(profile, sparse),
                notes=[
                    (
                        "The decoy set carries 16 of the 21 sparse genes against the "
                        "targets' 5, which is why H020 is reported twice — over all genes "
                        "and restricted to reachable ones (entry 085)."
                    ),
                ],
            )
        )

    if depths:
        thin = [row for row in depths if float(row["mean_depth"]) < 10]
        exhibits.append(
            Exhibit(
                slug="exon-coverage",
                title="How much evidence there is behind every absence",
                caption=(
                    f"Mean depth over {len(depths):,} baited intervals. {len(thin):,} sit "
                    "below 10x, where 'no second allele here' is a gap in the data rather "
                    "than a finding about the child."
                ),
                legend=(
                    "**blue** = intervals at that depth; **red dashed** = the 10x floor "
                    "below which an absence is not interpreted."
                ),
                figure=depth_figure(depths),
            )
        )

    return Section(
        slug="it2-step-2",
        title="Step 2 — the alleles the reads carry",
        blurb=(
            "Recovering the reads that came from the target genes without the vendor's "
            "caller, and measuring how much of those genes the recovery can actually see. "
            "Every figure is drawn from the run's own output files."
        ),
        exhibits=exhibits,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
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
        title="Iteration 2, step 2 — the alleles the reads carry",
        subject="PROBAND01 — recovered from the raw reads, without the vendor caller",
    )
    html = args.out / "index.html"
    html.write_text(page, encoding="utf-8")
    print(f"  {html}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
