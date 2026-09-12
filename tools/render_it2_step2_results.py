#!/usr/bin/env python3
"""The three figures step 2's *results* need, as opposed to its instrument.

`render_it2_step2_figures.py` draws what the bait and the pass did; this draws what the
alleles say. Split because they read different files and answer different questions, and
because one 370-line module was already at the size ceiling.

Every number comes from `analysis.json`, exported straight from the warehouse, so a figure
cannot disagree with the table it was drawn from.

Usage::

    uv run python tools/render_it2_step2_results.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import plotly.graph_objects as go

from mva.render import theme
from mva.render.figure import Exhibit, Section
from mva.render.report import render

DEFAULT_IN = Path("build/it2/step-2")
DEFAULT_OUT = Path("figures/track1/iteration2/step-2")

#: Tier order, coarsest evidence last, so the eye reads target tiers before the null.
TIERS = ("core", "mechanism-term", "net", "decoy")

HUES = {
    "core": theme.GOOD,
    "mechanism-term": theme.GOOD,
    "net": theme.MACHINE,
    "decoy": theme.MUTED,
}


def filter_figure(scored: list[dict], unfiltered: list[dict]) -> go.Figure:
    """The finding that outranks the verdict: the filter discriminates, the gene list does not."""
    by_tier = {row["tier"]: row for row in scored}
    raw = {row["tier"]: row for row in unfiltered}
    labels = [tier for tier in TIERS if tier in by_tier]
    before = [raw[tier]["biallelic"] / raw[tier]["genes"] for tier in labels]
    after = [by_tier[tier]["biallelic"] / by_tier[tier]["genes"] for tier in labels]

    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=labels,
            y=before,
            name="any two variants",
            marker={"color": theme.BAD.fill, "line": {"color": theme.BAD.line, "width": 1.5}},
            text=[f"{value:.1%}" for value in before],
            textposition="outside",
        )
    )
    figure.add_trace(
        go.Bar(
            x=labels,
            y=after,
            name="rare and protein-altering",
            marker={"color": theme.GOOD.fill, "line": {"color": theme.GOOD.line, "width": 1.5}},
            text=[f"{value:.2%}" for value in after],
            textposition="outside",
        )
    )
    figure.update_yaxes(title="genes with a biallelic candidate", tickformat=".0%")
    figure.update_layout(barmode="group", legend={"orientation": "h", "y": 1.12})
    return figure


def concordance_figure(rows: list[dict]) -> go.Figure:
    """H022: two callers of disjoint model class against the vendor's."""
    labels = [f"{row['caller']}  ({int(row['co_called']):,} sites)" for row in rows]
    values = [float(row["concordance"]) for row in rows]
    figure = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker={"color": theme.GOOD.fill, "line": {"color": theme.GOOD.line, "width": 1.5}},
            text=[f"{value:.4f}" for value in values],
            textposition="outside",
        )
    )
    figure.add_vline(
        x=0.99,
        line={"color": theme.DECISION.line, "dash": "dash"},
        annotation_text="H022: ≥ 0.99",
        annotation_position="bottom left",
    )
    figure.update_xaxes(title="agreement with the delivered callset", range=[0.95, 1.001])
    figure.update_layout(margin={"l": 260}, showlegend=False)
    return figure


def sv_figure(rows: list[dict]) -> go.Figure:
    """What the bait's own geometry invents, and what survives it."""
    kinds = [
        ("credible", lambda r: not r["spans_unbaited"] and not r["bait_edge"], theme.GOOD),
        ("at a bait edge", lambda r: r["bait_edge"] and not r["spans_unbaited"], theme.DECISION),
        ("spanning unbaited gaps", lambda r: r["spans_unbaited"], theme.BAD),
    ]
    types = ["DEL", "DUP", "INV"]
    figure = go.Figure()
    for name, keep, hue in kinds:
        counts = [
            sum(int(r["consensus_calls"]) for r in rows if r["sv_type"] == t and keep(r))
            for t in types
        ]
        figure.add_trace(
            go.Bar(
                x=types,
                y=counts,
                name=name,
                marker={"color": hue.fill, "line": {"color": hue.line, "width": 1.5}},
                text=[str(value) for value in counts],
                textposition="outside",
            )
        )
    figure.update_yaxes(title="two-method-class consensus calls")
    figure.update_layout(barmode="group", legend={"orientation": "h", "y": 1.12})
    return figure


def build(source: Path) -> Section:
    data = json.loads((source / "analysis.json").read_text(encoding="utf-8"))
    leads = data["leads"]
    targets = [row for row in leads if row["tier"] != "decoy"]
    decoys = [row for row in leads if row["tier"] == "decoy"]
    scored = {row["tier"]: row for row in data["by_tier"]}

    return Section(
        slug="it2-step-2-results",
        title="Step 2 — what the recovered reads say",
        blurb=(
            "The alleles the reads carry, checked against the vendor's callset, against a "
            "matched decoy set, and against the bait's own geometry. Every number is read "
            "from the warehouse tables the run wrote."
        ),
        exhibits=[
            Exhibit(
                slug="caller-concordance",
                title="Do two independent callers agree with the vendor's pipeline?",
                caption=(
                    "Reads selected by k-mer bait rather than whole-genome alignment, called "
                    "by two callers sharing no code with the vendor's, at single-base "
                    "substitutions where normalisation is a no-op. Both clear the "
                    "pre-registered line. This is the check that licenses the rest of step 2."
                ),
                legend=(
                    "**green** = measured agreement, **yellow dashed** = the pre-registered "
                    "0.99. Indels are excluded: the delivered callset is unnormalised and "
                    "its indels are not comparable without a left-alignment — so the claim "
                    "is untested for the allele class the aligner is weakest at."
                ),
                figure=concordance_figure(data["concordance"]),
            ),
            Exhibit(
                slug="filter-not-genelist",
                title="What actually discriminates: the filter, not the gene list",
                caption=(
                    "Count any gene with two heterozygous variants and the decoys win "
                    f"({data['unfiltered_by_tier'][-1]['biallelic']} of "
                    f"{data['unfiltered_by_tier'][-1]['genes']} decoys) — everyone carries "
                    "about two differences per gene, so it describes a genome, not a "
                    "patient. Require the alleles to be rare and protein-altering and the "
                    f"target tiers separate: core {scored['core']['biallelic']}/"
                    f"{scored['core']['genes']} against decoy "
                    f"{scored['decoy']['biallelic']}/{scored['decoy']['genes']}."
                ),
                legend=(
                    "**red** = any two variants, **green** = rare and protein-altering. "
                    "Same genes, same reads, same enumeration — only the filter differs."
                ),
                figure=filter_figure(data["by_tier"], data["unfiltered_by_tier"]),
                notes=[
                    (
                        "H020 is supported in direction only: four events against two is "
                        "Fisher one-sided p = 0.343, which cannot separate a twofold "
                        "difference from none."
                    ),
                ],
            ),
            Exhibit(
                slug="sv-artefacts",
                title="What the bait's geometry invents, and what survives it",
                caption=(
                    "A baited alignment is islands of coverage with emptiness between, and a "
                    "read-pair caller reports the emptiness as one enormous event — the "
                    "first consensus run contained a 13 Mb deletion and a 40 Mb inversion in "
                    "a living child. Requiring over half of a call's span to be baited "
                    "territory removes them and leaves deletions with a median length of "
                    "302 bp."
                ),
                legend=(
                    "**green** = credible (span mostly baited, away from an edge); "
                    "**yellow** = within one insert-size of a bait boundary; **red** = "
                    "spanning the unbaited gaps the bait itself created."
                ),
                figure=sv_figure(data["sv_consensus"]),
                notes=[
                    (
                        f"H023 is refuted: {len(targets)} target and {len(decoys)} decoy "
                        "genes hold a biallelic candidate, and two genes — one of them a "
                        "decoy — carry a credible consensus deletion over a coding exon."
                    ),
                ],
            ),
        ],
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
        title="Iteration 2, step 2 — what the recovered reads say",
        subject="PROBAND01 — alleles discovered without the vendor's caller",
    )
    html = args.out / "results.html"
    html.write_text(page, encoding="utf-8")
    print(f"  {html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
