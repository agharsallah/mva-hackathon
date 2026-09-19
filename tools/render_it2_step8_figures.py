#!/usr/bin/env python3
"""Render step 8's report figures from ``build/it2/step-8/analysis.json`` and nothing else.

Every number on every figure comes from the file the run wrote, so a figure cannot drift
from the entry that quotes it — and ``tools/check_figures_fresh.py`` fails any figure older
than that file. A figure whose input is absent is **skipped**, not drawn empty: a chart of
zeros and a stage that did not run look the same to a reader, and only one is a result.

The headline is deliberately not the chromosome chart. It is the power comparison, because
the step's finding is about the instrument first: entry 037 reported every autosome flat
with a statistic that has no power, and what "flat" is worth cannot be read off a bar chart
of deviations — only off the fraction each chromosome could have detected.

Writes ``figures/track1/iteration2/step-8/<slug>.png`` plus one interactive page.

Usage::

    uv run python tools/render_it2_step8_figures.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from it2_step8_charts import (
    bdev_figure,
    density_figure,
    depth_figure,
    limit_figure,
    model_figure,
    multi_figure,
    power_figure,
)
from it2_step8_dosage_charts import dosage_exhibits, optional_json
from mva.render import theme
from mva.render.figure import Exhibit, Section
from mva.render.report import render

DEFAULT_IN = Path("build/it2/step-8/analysis.json")

#: The dosage route's own files. A counting pass over the raw reads wrote them and they share
#: no input with the callset, which is the whole reason the route exists -- so they are read
#: separately and their exhibits are skipped, not faked, when the pass has not run.
DEFAULT_DOSAGE = Path("build/it2/step-8/dosage.json")
DEFAULT_COMPOSITION = Path("build/it2/step-8/composition.json")
DEFAULT_OUT = Path("figures/track1/iteration2/step-8")


def _limits_exhibits(data: dict) -> list[Exhibit]:
    limits = data.get("limits") or {}
    folded = limits.get("bdev") or []
    mean = limits.get("mean_baf") or []
    if not folded:
        return []
    grid = limits.get("grid") or []
    reached = [row for row in folded if row["f80"] is not None]
    mean_reached = [row for row in mean if row["f80"] is not None]
    worst = max((row["f80"] for row in reached), default=None)

    return [
        Exhibit(
            slug="power-then-and-now",
            title="The same sites, scored two ways",
            caption=(
                "The step's headline, and the reason it exists. Both statistics see the "
                "identical simulated draws from each chromosome's own depths at the same "
                f"seed; the only difference is the line that computes the number. "
                f"Fold-over reaches 80 % power on {len(reached)} of {len(folded)} contigs; "
                f"entry 037's mean B-allele fraction reaches it on {len(mean_reached)}. "
                "A mosaic gain splits heterozygous sites into two bands symmetric about the "
                "centre, so their mean does not move — which is what 037 measured."
            ),
            legend=theme.legend_line(
                theme.GOOD,
                theme.BAD,
                theme.DECISION,
                extra=(
                    "green is the fold-over deviation, red is 037's mean; one line per "
                    "contig, yellow marks the 80 % power the limit is read off"
                ),
            ),
            figure=power_figure(folded, mean, grid),
            height=460,
        ),
        Exhibit(
            slug="detection-limit",
            title="The smallest mosaic fraction each chromosome could have shown",
            caption=(
                "What every negative result on this page has to be quoted with. A bar is "
                "the smallest injected cell fraction reaching 80 % power at that "
                "chromosome's own heterozygous-site count and depth"
                + (f"; the worst is {worst:.1%}." if worst is not None else ".")
                + " A hatched bar is a contig that never reaches 80 % at any fraction "
                "tested, which is a blind spot and not a small limit."
            ),
            legend=theme.legend_line(
                theme.GOOD,
                theme.MUTED,
                extra=(
                    "lower is better; grey hatching is a contig with no limit at all, and "
                    "grey fill marks the hemizygous X and Y, where allele balance cannot see"
                ),
            ),
            figure=limit_figure(folded),
            height=380,
        ),
    ]


def build(data: dict, dosage: dict | None = None, composition: dict | None = None) -> list[Exhibit]:
    """Every exhibit whose input is present. Absent inputs are skipped, never drawn empty."""
    exhibits: list[Exhibit] = _limits_exhibits(data)
    exhibits.extend(dosage_exhibits(dosage or {}, composition or {}))

    bdev = data.get("bdev") or {}
    whole = bdev.get("whole") or []
    if whole:
        flagged = [row["chrom"] for row in whole if row["exceeds_null"]]
        exhibits.append(
            Exhibit(
                slug="bdev-per-chromosome",
                title="Fold-over deviation, against each chromosome's own null",
                caption=(
                    "Every contig's mean |BAF − centre| beside the null its own depths and "
                    "site count generate — not a shared threshold, so a shallow chromosome "
                    "is judged against a wider null rather than flagged for being shallow. "
                    + (
                        "No contig exceeds its null."
                        if not flagged
                        else "Exceeding its null: " + ", ".join(f"chr{c}" for c in flagged) + "."
                    )
                ),
                legend=theme.legend_line(
                    theme.GOOD,
                    theme.BAD,
                    theme.DECISION,
                    theme.MUTED,
                    extra=(
                        "green is inside the null, red is above it, yellow marks the null's "
                        "95th percentile and blue its mean; grey is a hemizygous contig"
                    ),
                ),
                figure=bdev_figure(whole),
                height=400,
            )
        )

    baseline = data.get("baseline") or {}
    if baseline.get("depth_ratio"):
        shifted = baseline.get("shifted") or []
        exhibits.append(
            Exhibit(
                slug="depth-against-baseline",
                title="Each chromosome's depth against a baseline it was left out of",
                caption=(
                    "The denominator every relative route divides by. The baseline is the "
                    "median of the per-chromosome medians with each chromosome held out in "
                    "turn, so no single contig can prop it up. "
                    + (
                        "No chromosome's exclusion moves it beyond its bootstrap interval."
                        if not shifted
                        else "Moved by: " + ", ".join(f"chr{c}" for c in shifted) + "."
                    )
                    + " The dotted lines are the measured spread of the ratio across "
                    "autosomes — the precision floor below which a depth shift is not "
                    "evidence of anything."
                ),
                legend=theme.legend_line(
                    theme.GOOD,
                    theme.DECISION,
                    theme.MACHINE,
                    theme.MUTED,
                    extra=(
                        "yellow dots are the precision floor, blue is the baseline itself, "
                        "grey markers are the hemizygous contigs"
                    ),
                ),
                figure=depth_figure(
                    baseline.get("depth_ratio") or {},
                    baseline.get("sex_chromosome_ratio") or {},
                    float(baseline.get("depth_spread") or 0.02),
                ),
                height=340,
            )
        )

    models = data.get("models") or {}
    if models.get("fits"):
        verdicts = models.get("verdicts") or []
        confident = [row for row in verdicts if row["confident"]]
        exhibits.append(
            Exhibit(
                slug="model-margins",
                title="How far the best model beat the next one, per chromosome",
                caption=(
                    "Five models per chromosome — normal, monosomy, mitotic trisomy, "
                    "meiotic trisomy, copy-neutral loss of heterozygosity — ranked by BIC. "
                    f"{len(confident)} of {len(verdicts)} contigs clear Kong 2018's own "
                    "ΔBIC ≥ 10; the rest are reported as not distinguishable rather than as "
                    "their leader. A bar at the floor is the winning model."
                ),
                legend=theme.legend_line(
                    theme.DECISION,
                    extra=(
                        "one bar per model, log scale; the dashed line is ΔBIC 10, below "
                        "which the ranking is not a call"
                    ),
                ),
                figure=model_figure(models["fits"]),
                height=420,
            )
        )

    multi = data.get("multi") or {}
    if multi.get("designs"):
        exhibits.append(
            Exhibit(
                slug="multi-chromosome",
                title="When several chromosomes are abnormal at once",
                caption=(
                    "Variegated aneuploidy breaks the assumption every relative route makes. "
                    "Two and three chromosomes are injected simultaneously and *every* "
                    "chromosome is rescored on the same draws, so the second bar is measured "
                    "rather than assumed: it is how often an untouched chromosome is flagged "
                    "because the injected ones moved the baseline."
                ),
                legend=theme.legend_line(
                    theme.GOOD,
                    theme.BAD,
                    theme.DECISION,
                    extra=(
                        "green is recovery of the injected chromosomes, red is untouched "
                        "chromosomes wrongly flagged, yellow is the nominal 5 % rate"
                    ),
                ),
                figure=multi_figure(multi["designs"]),
                height=360,
            )
        )

    constants = data.get("constants") or {}
    if constants.get("density"):
        exhibits.append(
            Exhibit(
                slug="heterozygous-density",
                title="Heterozygous calls per PASS call, by arm",
                caption=(
                    "The statistic a monosomy or a copy-neutral loss moves, which allele "
                    "balance cannot see: those events remove heterozygous sites rather than "
                    "shifting them. It is reported beside the models and deliberately kept "
                    "out of the likelihood — in a bulk sample the diploid cells still make a "
                    "site heterozygous, so what actually removes the call is the caller's "
                    "threshold, and that is not a model anyone can write down honestly."
                ),
                legend=theme.legend_line(
                    theme.MACHINE,
                    theme.RAW,
                    extra="blue is the short arm, purple the long arm",
                ),
                figure=density_figure(constants["density"]),
                height=360,
            )
        )
    return exhibits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--analysis", type=Path, default=DEFAULT_IN)
    parser.add_argument("--dosage", type=Path, default=DEFAULT_DOSAGE)
    parser.add_argument("--composition", type=Path, default=DEFAULT_COMPOSITION)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    if not args.analysis.is_file():
        print(f"missing {args.analysis}; run tools/fit_it2_mosaic.py first")
        return 1
    theme.install_template()
    data = json.loads(args.analysis.read_text(encoding="utf-8"))
    exhibits = build(data, optional_json(args.dosage), optional_json(args.composition))
    if not exhibits:
        print("no exhibit had its input; nothing drawn")
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    for exhibit in exhibits:
        exhibit.write_html(args.out)
        image = exhibit.write_image(args.out)
        print(f"  {exhibit.slug:<24} {'png + html' if image else 'html only (no kaleido)'}")

    page = args.out / "index.html"
    page.write_text(
        render(
            [
                Section(
                    slug="step-8",
                    title="Step 8 — the mosaic aneuploidy bound",
                    blurb=(
                        "Entry 037 reported every autosome flat with a statistic that has no "
                        "power for a mosaic gain. This is the re-test, and the limit that "
                        "makes its answer mean something."
                    ),
                    exhibits=exhibits,
                )
            ],
            title="Iteration 2, step 8 — how small an event could we have seen?",
            subject="MVA hackathon 2026 · Track 1",
        ),
        encoding="utf-8",
    )
    print(f"wrote {page}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
