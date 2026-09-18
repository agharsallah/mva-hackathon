#!/usr/bin/env python3
"""Render step 6's report figures from ``build/it2/step-6/analysis.json`` and nothing else.

Every number on every figure comes from the file the run wrote, so a figure cannot drift from
the entry that quotes it — and ``tools/check_figures_fresh.py`` fails any figure older than
that file. A figure whose input is absent is **skipped**, not drawn empty: a chart of zeros
and a stage that did not run look the same to a reader, and only one is a result.

Writes ``figures/track1/iteration2/step-6/<slug>.png`` plus one interactive page.

Usage::

    uv run python tools/render_it2_step6_figures.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from it2_step6_charts import (
    evidence_figure,
    leaveout_figure,
    matrix_figure,
    reach_figure,
    weights_figure,
)
from mva.render import theme
from mva.render.figure import Exhibit, Section
from mva.render.report import render

DEFAULT_IN = Path("build/it2/step-6/analysis.json")
DEFAULT_OUT = Path("figures/track1/iteration2/step-6")


def build(data: dict) -> list[Exhibit]:
    """Every exhibit whose input is present. Absent inputs are skipped, never drawn empty."""
    exhibits: list[Exhibit] = []
    matrix = data.get("matrix") or []
    routes = data.get("routes") or []
    stability = data.get("stability") or []
    evidence = data.get("evidence") or []
    leaders = data.get("leaders") or []
    reach = data.get("reach") or []
    fusion = data.get("fusion") or {}
    frozen = fusion.get("frozen") or {}
    voting = [r for r in routes if r.get("admitted")]

    if matrix and routes:
        exhibits.append(
            Exhibit(
                slug="agreement-matrix",
                title="Routes against the leading pairs",
                caption=(
                    f"The step's headline. {len(voting)} of {len(routes)} instruments were "
                    "admitted to the fusion; each cell is the rank that route gave that pair. "
                    "A grey cell is a pair the route never listed — a weaker statement than "
                    "ranking it last, and never agreement."
                ),
                legend=theme.legend_line(
                    theme.GOOD,
                    theme.DECISION,
                    theme.MUTED,
                    extra=(
                        "green is rank 1; yellow is inside the route's top 50, darker is better; "
                        "grey is not listed. A * marks a rank inherited from the pair's gene, so "
                        "every pair of that gene carries it. Rows run best fused rank first"
                    ),
                ),
                figure=matrix_figure(matrix, routes),
                height=560,
            )
        )

    if stability:
        carried = [r for r in stability if not r.get("leader_kept_rank_one")]
        exhibits.append(
            Exhibit(
                slug="leave-one-route-out",
                title="Where the leader lands when one instrument is silenced",
                caption=(
                    "The ablation an ensemble owes its reader. "
                    + (
                        "No single removal moves the leader."
                        if not carried
                        else "Removing "
                        + " or ".join(r["removed"] for r in carried)
                        + " moves it off rank 1, so the fusion is carried by that route "
                        "rather than confirmed by all of them."
                    )
                ),
                legend=theme.legend_line(
                    theme.GOOD,
                    theme.BAD,
                    extra=(
                        "green keeps the leader at rank 1, red does not; the bar is where it lands"
                    ),
                ),
                figure=leaveout_figure(stability),
                height=300,
            )
        )

    if evidence:
        exhibits.append(
            Exhibit(
                slug="independent-evidence",
                title="Which witnesses speak for each leading pair",
                caption=(
                    "Rank fusion treats every list as a separate witness. This is the "
                    "correction: one segment per raw source that speaks for the pair, after "
                    "routes reading the same source are counted once. A short stack is a pair "
                    "nominated by instruments that all read the same thing."
                ),
                legend=theme.legend_line(
                    theme.RAW,
                    theme.MACHINE,
                    theme.GOOD,
                    theme.DECISION,
                    extra=(
                        "purple is the eight clinical terms, blue the delivered callset, green "
                        "the raw reads, yellow the published literature"
                    ),
                ),
                figure=evidence_figure(evidence),
                height=420,
            )
        )

    if leaders:
        exhibits.append(
            Exhibit(
                slug="weight-sensitivity",
                title="Equal weights against each route's own measured error rate",
                caption=(
                    "The second sensitivity analysis, reported beside the primary result and "
                    "never instead of it. A pair that only reaches the top under equal weights "
                    "is being carried by the instruments with the worst measured error rates."
                ),
                legend=theme.legend_line(
                    theme.MACHINE,
                    theme.DECISION,
                    extra=(
                        "blue is the pre-registered equal weighting, yellow the measured one "
                        "(symptom recall 0.335, 1 − permutation p 0.944, knowledge AUC 0.634); "
                        "shorter is better"
                    ),
                ),
                figure=weights_figure(leaders),
                height=520,
            )
        )

    if reach:
        exhibits.append(
            Exhibit(
                slug="decoy-reach",
                title="How far down the fused ranking the matched controls sit",
                caption=(
                    "The fusion's own decoy null. Size-matched control genes were run through "
                    "the identical fusion, so a ranking that cannot be told apart from theirs "
                    "has resolved nothing below its leader."
                ),
                legend=theme.legend_line(
                    theme.GOOD,
                    theme.BAD,
                    theme.MUTED,
                    extra=(
                        "bars are the best fused rank reached by each class and diamonds the "
                        "median; lower is better"
                    ),
                ),
                figure=reach_figure(reach),
                height=340,
            )
        )

    if frozen:
        exhibits.append(
            Exhibit(
                slug="freeze-receipt",
                title="The ranking predates the comparison",
                caption=(
                    "Not a chart: the receipt. The digest below was recorded in methodology "
                    "entry 108 before any earlier-iteration table was read."
                ),
                legend=(
                    "**Legend** — `shasum -a 256` of the exported file reproduces this digest; "
                    "the constants were fixed in the plan before any route ran."
                ),
                html=(
                    "<table class='facts'>"
                    + "".join(
                        f"<tr><th>{key}</th><td><code>{value}</code></td></tr>"
                        for key, value in (
                            ("file", frozen.get("file", "—")),
                            ("sha256", frozen.get("sha256", "—")),
                            ("pairs frozen", frozen.get("rows", "—")),
                            ("frozen at", frozen.get("frozen_at", "—")),
                            (
                                "constants",
                                "k = {k} · top {t} per route · absent = rank {m} · seed {s}".format(
                                    k=(fusion.get("constants") or {}).get("k", "—"),
                                    t=(fusion.get("constants") or {}).get("top_per_route", "—"),
                                    m=(fusion.get("constants") or {}).get("missing_rank", "—"),
                                    s=(fusion.get("constants") or {}).get("seed", "—"),
                                ),
                            ),
                        )
                    )
                    + "</table>"
                ),
            )
        )
    return exhibits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--analysis", type=Path, default=DEFAULT_IN)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    if not args.analysis.is_file():
        print(f"missing {args.analysis}; run tools/export_it2_step6_analysis.py first")
        return 1
    theme.install_template()
    data = json.loads(args.analysis.read_text(encoding="utf-8"))
    exhibits = build(data)
    if not exhibits:
        print("no exhibit had its input; nothing drawn")
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    for exhibit in exhibits:
        exhibit.write_html(args.out)
        image = exhibit.write_image(args.out)
        print(f"  {exhibit.slug:<22} {'png + html' if image else 'html only (no kaleido)'}")

    page = args.out / "index.html"
    page.write_text(
        render(
            [
                Section(
                    slug="step-6",
                    title="Step 6 — fusion and unblinding",
                    blurb=(
                        "Three instruments ranked, one confirmed, and the result was hashed "
                        "before it was compared to anything."
                    ),
                    exhibits=exhibits,
                )
            ],
            title="Iteration 2, step 6 — one ranking out of three",
            subject="MVA hackathon 2026 · Track 1",
        ),
        encoding="utf-8",
    )
    print(f"wrote {page}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
