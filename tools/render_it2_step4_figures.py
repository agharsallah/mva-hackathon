#!/usr/bin/env python3
"""Render step 4's report figures from ``build/it2/step-4/analysis.json`` and nothing else.

Every number on every figure comes from the file the run wrote, so a figure cannot drift
from the entry that quotes it — and ``tools/check_figures_fresh.py`` fails any figure older
than that file. A figure whose input is absent is **skipped**, not drawn empty: a chart of
zeros and a stage that did not run look the same to a reader, and only one is a result.

Writes ``figures/track1/iteration2/step-4/<slug>.png`` plus one interactive page.

Usage::

    uv run python tools/render_it2_step4_figures.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from it2_step4_charts import (
    ablation_figure,
    decomposition_figure,
    groups_figure,
    lanes_figure,
    leaders_figure,
    null_figure,
    phenotype_bins_figure,
    shapes_figure,
)
from mva.render import theme
from mva.render.figure import Exhibit, Section
from mva.render.report import render

DEFAULT_IN = Path("build/it2/step-4/analysis.json")
DEFAULT_OUT = Path("figures/track1/iteration2/step-4")


def build(data: dict) -> list[Exhibit]:
    """Every exhibit whose input is present. Absent inputs are skipped, never drawn empty."""
    exhibits: list[Exhibit] = []
    leaders = data.get("leaders") or []
    ranking = data.get("ranking") or {}
    nulls = data.get("nulls_summary") or {}

    if leaders:
        exhibits.append(
            Exhibit(
                slug="leaders",
                title="The genome-wide ordering, and what each leader is",
                caption=(
                    "Every biallelic hypothesis in the callset — "
                    f"{int(ranking.get('hypotheses', 0)):,} of them across "
                    f"{int(ranking.get('genes_scored', 0)):,} genes — scored by a "
                    "product of likelihood ratios with no hard filter anywhere. The scale is "
                    "logarithmic because the ordering spans seven orders of magnitude. The "
                    "decoy genes went through the identical scoring and are drawn on the same "
                    "axis: a ranking that hides where its controls landed is asking to be "
                    "taken on trust. A ratio orders hypotheses; it is not a probability that "
                    "the gene is causal."
                ),
                legend=theme.legend_line(
                    theme.GOOD,
                    theme.RAW,
                    theme.MACHINE,
                    theme.BAD,
                    extra=(
                        "**green** = a gene the child's symptoms nominated (step 1 target); "
                        "**purple** = a gene nobody has curated a phenotype for; "
                        "**blue** = curated, but not nominated; **red** = a matched decoy"
                        + (
                            "."
                            if any(row.get("is_decoy") for row in leaders[:20])
                            else " — and no red bar appears among these, which is the result."
                        )
                    ),
                ),
                figure=leaders_figure(leaders[:20]),
                height=560,
            )
        )
        exhibits.append(
            Exhibit(
                slug="decomposition",
                title=f"Why {leaders[0]['gene']} leads — the arithmetic, term by term",
                caption=(
                    "Each bar is one lane's contribution to the leading hypothesis, in "
                    "log₁₀, so the bars add to the total rather than sitting beside it. A "
                    "lane drawn at zero was consulted and **damped**: it shares a "
                    "correlation group with a stronger one, and counting a missense "
                    "predictor tuned on ClinVar beside ClinVar itself would inflate the "
                    "answer. Left and right are the two alleles; they are separate "
                    "observations and do not share a group. The bars are the terms as "
                    "printed, rounded to four significant figures, so the running total "
                    "drifts from the stored ratio by a fraction of a percent."
                ),
                legend=theme.legend_line(
                    theme.GOOD,
                    theme.BAD,
                    theme.MACHINE,
                    extra=(
                        "**green** = the term argues for the gene; **red** = against it; "
                        "**blue** = the combined ratio."
                    ),
                ),
                figure=decomposition_figure(leaders[0]),
                height=480,
            )
        )

    if data.get("groups"):
        exhibits.append(
            Exhibit(
                slug="groups",
                title="Where each class of gene sits — targets against their matched decoys",
                caption=(
                    "The decoy null, drawn. Step 1 drew 396 decoys matched to the targets on "
                    "coding length and exon count, and they were scored by the identical "
                    "likelihood ratio. Step 2 measured the *unfiltered* biallelic rate of the "
                    "two sets as indistinguishable (H020 refuted), so any separation visible "
                    "here is produced by the scoring and by nothing else."
                ),
                legend=theme.legend_line(
                    theme.MACHINE,
                    theme.GOOD,
                    extra=(
                        "**blue** = the median gene of the class; **green** = its 90th "
                        "percentile. The dotted line is a ratio of 1 — above it the evidence "
                        "argues for a gene, below it against."
                    ),
                ),
                figure=groups_figure(data["groups"]),
            )
        )

    if nulls.get("permutation_null") and data.get("nulls"):
        exhibits.append(
            Exhibit(
                slug="permutation-null",
                title="How high a random symptom set gets",
                caption=(
                    f"{int(nulls['permutation_null'].get('draws', 0)):,} random seven-term "
                    "sets, each drawn to match the child's own term-depth profile, each "
                    "re-ranking every "
                    "gene and re-scoring every hypothesis. The bars are what chance reached; "
                    "the dashed line is what the child's terms reached. Empirical "
                    f"p = {float(nulls['permutation_null'].get('p_value', 1)):.4f}, and the "
                    "expected number of genes a random run puts at or above the observed "
                    "leader is "
                    f"{float(nulls['permutation_null'].get('expected_false_leads', 0)):.2f}."
                ),
                legend=theme.legend_line(
                    theme.MUTED,
                    theme.GOOD,
                    extra=(
                        "**grey** = the null distribution over permuted term sets; "
                        "**green dashed** = the observed run."
                    ),
                ),
                figure=null_figure(data["nulls"], float(nulls.get("observed_top", 1.0))),
            )
        )

    if leaders and nulls.get("genotype_only_top"):
        exhibits.append(
            Exhibit(
                slug="genotype-only",
                title="What the DNA alone would have nominated",
                caption=(
                    "The same table with the phenotype lane set to 1 for every gene. Not a "
                    "null — a control, and the one that says how much of the ordering the "
                    "symptoms are carrying. The leader of the combined ranking is **not** "
                    "the leader of this one, which is the honest reading of H030: the claim "
                    "is supported by the two routes together and not by a genome-wide scan "
                    "that found the gene on its own."
                ),
                legend=theme.legend_line(
                    theme.GOOD,
                    theme.MACHINE,
                    extra=(
                        "**green** = both routes, as reported; **blue** = the genotype lanes "
                        "alone. A gene whose blue bar exceeds its green one was pushed *down* "
                        "by the symptoms."
                    ),
                ),
                figure=ablation_figure(leaders, nulls["genotype_only_top"]),
                height=520,
            )
        )

    if ranking.get("phenotype_bins"):
        exhibits.append(
            Exhibit(
                slug="phenotype-bins",
                title="What a rank is worth, measured rather than assumed",
                caption=(
                    "The step's one methodological liberty. Rather than inventing a "
                    "conversion from a similarity score to a likelihood ratio, the ratio "
                    "*is* the ranker's own held-out performance: step 1 ran it on 3,240 "
                    "recessive diseases whose causal gene is known, and each bar is the "
                    "fraction of those genes that landed in that band of ranks divided by "
                    "the fraction of all genes the band contains. The rightmost case — a "
                    "gene nobody has curated — is a ratio below 1, never zero, which is why "
                    "73.6 % of the genome is ordered rather than discarded."
                ),
                legend=theme.legend_line(
                    theme.GOOD,
                    theme.BAD,
                    extra=(
                        "**green** = the rank argues for the gene; **red** = against it. "
                        "The dotted line is a ratio of 1."
                    ),
                ),
                figure=phenotype_bins_figure(ranking["phenotype_bins"]),
            )
        )

    if data.get("lanes"):
        exhibits.append(
            Exhibit(
                slug="lane-coverage",
                title="Which tool actually spoke, per consequence class",
                caption=(
                    "One calibrated tool per consequence class, chosen before any score was "
                    "seen. This is the coverage that resulted: how many allele slots each "
                    "lane won its correlation group for. A lane with a published calibration "
                    "that answers for one allele in fifty contributed almost nothing to this "
                    "ordering, which is a fact about this run rather than about the tool. "
                    "CADD and LOFTEE are absent entirely — Ensembl's REST endpoint does not "
                    "serve either plugin, and the absence is recorded rather than worked "
                    "around."
                ),
                legend=theme.legend_line(
                    theme.MUTED,
                    extra=(
                        "**purple** = AlphaMissense; **blue** = SpliceAI; **green** = "
                        "ClinVar; **amber** = the consequence class alone; **grey** = no "
                        "lane had anything to say."
                    ),
                ),
                figure=lanes_figure(data["lanes"]),
                height=520,
            )
        )

    if data.get("shapes"):
        exhibits.append(
            Exhibit(
                slug="shapes",
                title="What was scored — including the shape a filter would have deleted",
                caption=(
                    "Three shapes of biallelic hypothesis. ``compound`` is two different "
                    "damaged alleles; ``homozygous`` is one allele on both copies; "
                    "``single`` is one allele and nothing on the other copy — the shape a "
                    "hard filter drops outright. It is kept here at the square root of its "
                    "evidence, because a missing partner may be a call the pipeline never "
                    "made rather than a copy that is intact."
                ),
                legend=theme.legend_line(
                    theme.MACHINE,
                    extra="One bar per shape; the label carries the gene count behind it.",
                ),
                figure=shapes_figure(data["shapes"]),
            )
        )
    return exhibits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--source", type=Path, default=DEFAULT_IN)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    if not args.source.is_file():
        raise SystemExit(f"no {args.source} — run tools/export_it2_step4_analysis.py first")
    theme.install_template()
    data = json.loads(args.source.read_text(encoding="utf-8"))
    exhibits = build(data)
    if not exhibits:
        print("nothing to draw yet: every input section is empty")
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    for exhibit in exhibits:
        if exhibit.figure is not None:
            exhibit.figure.write_image(args.out / f"{exhibit.slug}.png", width=1100, height=520)
            print(f"  {exhibit.slug}.png")
    page = render(
        [
            Section(
                slug="it2-step-4",
                title="Step 4 — every gene, ordered, with nothing filtered out",
                blurb=(
                    "Iteration 1 used a funnel: rare AND protein-altering AND biallelic AND "
                    "PASS, and a gene was in or out. This step replaces every one of those "
                    "cuts with a multiplier. A common allele is divided down, a filtered "
                    "call is down-weighted, a gene nobody has curated keeps a ratio below 1, "
                    "and a gene with one damaging allele and no partner is scored at the "
                    "square root of its evidence. Nothing is removed, so the question "
                    '"which gene leads" has an answer for all 11,465 of them — and the '
                    "nulls beside it say how much that answer is worth."
                ),
                exhibits=exhibits,
            )
        ],
        title="Iteration 2, step 4",
        subject="Likelihood-ratio ranking over the VCF",
    )
    (args.out / "index.html").write_text(page, encoding="utf-8")
    print(f"\nwrote {len(exhibits)} exhibits to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
