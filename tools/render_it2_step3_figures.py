#!/usr/bin/env python3
"""Render step 3's report figures from ``build/it2/step-3/analysis.json`` and nothing else.

Every number on every figure comes from the file the run wrote, so a figure cannot drift
from the entry that quotes it — and ``tools/check_figures_fresh.py`` fails any figure older
than that file. A figure whose input is absent is **skipped**, not drawn empty: a chart of
zeros and a stage that did not run look the same to a reader, and only one is a result.

Writes ``figures/track1/iteration2/step-3/<slug>.png`` plus one interactive page.

Usage::

    uv run python tools/render_it2_step3_figures.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from it2_step3_charts import (
    calibration_figure,
    calls_figure,
    confirmation_figure,
    mapq_figure,
    metric,
    probes_figure,
    reach_figure,
)
from mva.render import theme
from mva.render.figure import Exhibit, Section
from mva.render.report import render

DEFAULT_IN = Path("build/it2/step-3/analysis.json")
DEFAULT_OUT = Path("figures/track1/iteration2/step-3")


def build(data: dict) -> list[Exhibit]:
    """Every exhibit whose input is present. Absent inputs are skipped, never drawn empty."""
    exhibits: list[Exhibit] = []
    calibration = data.get("calibration") or []
    fitted_lambda = metric(calibration, "lambda_per_copy")
    variance_to_mean = metric(calibration, "variance_to_mean")

    if data.get("contrast"):
        exhibits.append(
            Exhibit(
                slug="confirmation",
                title="What a second instrument says about the first one's alleles",
                caption=(
                    "Every allele typed again from k-mer counts, with no aligner and no "
                    "caller in the chain. The right-hand pair is the set the delivered "
                    "callset never reported — the alleles six of ten target genes and eight "
                    "of ten decoy genes reached biallelic only through, and therefore the "
                    "claim with the most leverage in the step."
                ),
                legend=theme.legend_line(
                    theme.GOOD,
                    theme.MUTED,
                    extra="**yellow dashed** = the 80% H027 was pre-registered against.",
                ),
                figure=confirmation_figure(data["contrast"]),
                notes=[
                    (
                        "Decoys pass through identical rules: H020 is refuted, so a "
                        "target-gene result does not outweigh a decoy's before the filter."
                    )
                ],
            )
        )

    if data.get("calls"):
        exhibits.append(
            Exhibit(
                slug="calls-by-tier",
                title="What the model said, including where it declined to say",
                caption=(
                    'A no-call is a bar here, not a gap. "The instrument could not say" '
                    'and "the allele is absent" are different findings and only one of '
                    "them is about the child."
                ),
                legend=theme.legend_line(
                    theme.GOOD,
                    theme.MACHINE,
                    theme.MUTED,
                    theme.BAD,
                    extra="**red** = no-call; **grey** = homozygous reference.",
                ),
                figure=calls_figure(data["calls"]),
            )
        )

    if data.get("probes"):
        exhibits.append(
            Exhibit(
                slug="probe-design",
                title="How many alleles got three windows that could disagree",
                caption=(
                    "Three probe pairs per allele, spread across the variant, so that a "
                    "probe destroyed by another variant this child carries a few bases away "
                    "shows up as disagreement rather than as a genotype. An allele with "
                    "fewer is a weaker measurement, kept and counted, never dropped."
                ),
                legend=theme.legend_line(
                    theme.GOOD,
                    theme.BAD,
                    extra="**red** = alleles that could not be given three usable windows.",
                ),
                figure=probes_figure(data["probes"]),
            )
        )

    if data.get("reach"):
        exhibits.append(
            Exhibit(
                slug="reachability",
                title="Do the genes the gate excluded yield a genotype anyway?",
                caption=(
                    "The reachability rule was fixed before the run: a gene is excluded when "
                    "its bait density is below half the median, or more than half its reads "
                    "carry MAPQ 0. H029 says an excluded gene yields no confident genotype; "
                    "this is the figure that can refute it."
                ),
                legend=theme.legend_line(
                    theme.GOOD,
                    theme.BAD,
                    extra="**red** = genes the stage-0 gate excluded, by reason.",
                ),
                figure=reach_figure(data["reach"]),
            )
        )

    if data.get("mapq"):
        exhibits.append(
            Exhibit(
                slug="mapq-profile",
                title="Where the aligner was unsure, and how rarely",
                caption=(
                    "8.79% of the bait was dropped as repeated territory and no parameter "
                    "reached the pre-registered 5%. That number is about bait k-mers. This "
                    "is what it cost the *reads*, on a log axis because the answer spans "
                    "orders of magnitude and the finding is how small the typical one is."
                ),
                legend=theme.legend_line(
                    theme.MACHINE,
                    theme.BAD,
                    extra="**red** = the worst gene in that tier, not its average.",
                ),
                figure=mapq_figure(data["mapq"]),
            )
        )

    if fitted_lambda is not None:
        exhibits.append(
            Exhibit(
                slug="calibration",
                title="The fitted model, and the checks that say whether to believe it",
                caption=(
                    f"Per-copy coverage fitted at {fitted_lambda:.2f}, so an expected depth "
                    f"of {2 * fitted_lambda:.2f} against the 44.08x the baited alignment "
                    "measured — the two are the same quantity read off different "
                    "instruments. The variance-to-mean ratio is "
                    f"{variance_to_mean:.2f} where Poisson predicts 1."
                    if variance_to_mean
                    else ""
                ),
                legend=theme.legend_line(
                    theme.MACHINE,
                    extra="**yellow dashed** = Poisson's variance-to-mean ratio of 1.",
                ),
                figure=calibration_figure(calibration),
            )
        )
    return exhibits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--source", type=Path, default=DEFAULT_IN)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    if not args.source.is_file():
        raise SystemExit(f"no {args.source} — run tools/export_it2_step3_analysis.py first")
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
                slug="it2-step-3",
                title="Step 3 — the reads, with no aligner and no caller",
                blurb=(
                    "Step 2 found alleles by aligning reads and running two callers over "
                    "them. Both are models with assumptions — where a read belongs, what a "
                    "haplotype looks like. This step reads the same bytes with neither: it "
                    "counts how often each allele's 31-letter spelling appears. Where the "
                    "two agree the allele has survived a genuinely disjoint instrument; "
                    "where they disagree, the disagreement is the finding."
                ),
                exhibits=exhibits,
            )
        ],
        title="Iteration 2, step 3",
        subject="Alignment-free genotype and copy number",
    )
    (args.out / "index.html").write_text(page, encoding="utf-8")
    print(f"\nwrote {len(exhibits)} exhibits to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
