#!/usr/bin/env python3
"""Render step 7's Track 2 figures from the files the pipeline wrote, and nothing else.

Every number on every figure comes from ``build/track2/analysis.json`` (what
``tools/track2_enrich.py`` wrote) or, for the one scalability exhibit, from
``ressources/track2/transfer_comparison.tsv`` (what ``tools/track2_transfer.py`` wrote), so
a figure cannot drift from the entry that quotes it. A figure whose input is absent is
**skipped**, not drawn empty.

Writes ``figures/track2/<slug>.png`` plus one interactive page ``figures/track2-report.html``.
No genomic position exists anywhere in the input: drug names, gene symbols, rungs, counts.

Usage::

    uv run python tools/render_track2_figures.py
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mva.render import theme
from mva.render.figure import Exhibit, Section
from mva.render.report import render
from track2_charts import (
    decoy_overlap,
    ladder_matrix,
    mechanism_literature,
    pediatric_dots,
    rung_funnel,
    transfer_scalability,
)

DEFAULT_IN = Path("build/track2/analysis.json")
DEFAULT_TRANSFER = Path("ressources/track2/transfer_comparison.tsv")
DEFAULT_OUT = Path("figures/track2")
DEFAULT_HTML = Path("figures/track2-report.html")

LEGEND_RUNGS = (
    "**green** = a curated result and rung 4-5; **yellow** = a curated result at rung 2-3, "
    "argued with the model named; **blue** = the automated tests alone (a registered trial "
    "in the tumour plus a paediatric pointer - already being tried, not a mechanism finding); "
    "**red** = set aside (an anti-direction or the standard of care). The number is the rung; "
    "a `*` marks proxy evidence - the cited result is for a same-axis compound, not the drug. "
    "Drugs with a curated result are listed first."
)


def read_transfer(path: Path) -> list[dict]:
    """The transfer comparison as rows, or ``[]`` when the second case has never been run."""
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t", quoting=csv.QUOTE_NONE))


def transfer_exhibit(rows: list[dict]) -> Exhibit:
    """The scalability exhibit: the same pipeline, two different cases, side by side."""
    moved = [row for row in rows if row.get("role") == "transfer case"]
    cost = moved[0] if moved else {}
    reading = (
        f"{cost.get('live_requests', '?')} live requests and "
        f"{cost.get('cached_replies', '?')} cached replies, "
        f"{cost.get('wall_seconds', '?')} s wall clock"
        if cost
        else "no transfer run recorded"
    )
    return Exhibit(
        slug="transfer-scalability",
        title="The same pipeline on a different case, not just a different gene",
        caption=(
            "A transfer card swaps the whole case - a different disease with its own OMIM "
            "and MONDO identifiers, its own HPO terms read out of phenotype.hpoa, its own "
            "tumour context and its own standard of care - and the code runs unchanged. "
            f"Cost of the second case: {reading}. Only the automated rungs (1, 4, 5) are "
            "comparable: a transfer card has no curated evidence.tsv, which is the zero bar "
            "at the bottom and the reason rungs 2-3 cannot appear for it."
        ),
        legend=(
            "**blue** = the real case (the proband's card, the machinery this was built "
            "for); **purple** = the transfer case (a second case supplied as raw public "
            "input). Bars are counts on a linear axis, unnormalised."
        ),
        figure=transfer_scalability(rows),
        height=420,
    )


def build(data: dict, transfer_rows: list[dict] | None = None) -> list[Exhibit]:
    exhibits: list[Exhibit] = []
    ladder = data.get("ladder_top") or []
    short = data.get("shortlist") or []
    do_not = data.get("do_not") or []
    comparison = data.get("decoy_comparison") or []
    by_rung = data.get("ladder_drugs_by_max_rung") or {}
    graded = int(data.get("drugs_graded") or 0)

    if ladder:
        rows = ladder + [r for r in do_not if int(r["rung"]) >= 2]
        directions = sorted({r["direction_id"] for r in rows}, key=lambda d: (d == "pathway", d))
        exhibits.append(
            Exhibit(
                slug="evidence-ladder",
                title="Every drug at rung 2 or higher, on every direction it touches",
                caption=(
                    f"{len({r['drug_name'] for r in rows})} drugs reached rung 2 or higher out of "
                    f"{graded} graded; the shortlist keeps {len(short)} of them. The cell is the "
                    "rung; the colour is what the rung allows."
                ),
                legend=LEGEND_RUNGS,
                figure=ladder_matrix(rows, directions),
                height=max(360, 26 * min(len({r["drug_name"] for r in rows}), 28) + 80),
            )
        )
    if by_rung:
        exhibits.append(
            Exhibit(
                slug="rung-funnel",
                title="From every approved drug to the shortlist",
                caption=(
                    f"{graded} approved (or curated) drugs graded; each counted once at its best "
                    f"rung. {len(short)} survive the shortlist rule: rung 2 or higher, not the "
                    "standard of care, not an anti-direction."
                ),
                legend=(
                    "**green** = argued (rungs 4-5, and the shortlist); **yellow** = rungs 2-3; "
                    "**grey** = rung 1. Bars are counts of drugs, folded to base names."
                ),
                figure=rung_funnel(by_rung, len(short), graded),
                height=320,
            )
        )
    if comparison:
        exhibits.append(
            Exhibit(
                slug="decoy-overlap",
                title="Which directions nominate the same drugs for a decoy gene?",
                caption=(
                    "Jaccard overlap between each real direction's approved drug set and the "
                    "approved set the same pipeline returned for a decoy card (same child, "
                    "different gene). Above the dashed line the direction's automated stage is "
                    "non-specific and only its curated rung counts (H049)."
                ),
                legend=(
                    "**blue / purple** = one bar per decoy card; **yellow dashed** = the "
                    "pre-registered 0.10 line. `all` is every approved drug the real card returned."
                ),
                figure=decoy_overlap(comparison),
                height=380,
            )
        )
    if short:
        exhibits.append(
            Exhibit(
                slug="pediatric-evidence",
                title="Has each shortlisted drug ever been given to children?",
                caption=(
                    "Two pointers per drug: a US label with a section 8.4 Pediatric Use, and a "
                    "registered study admitting children in any indication. A filled dot is a "
                    "pointer to read, never a licence (H050)."
                ),
                legend=(
                    "**green** = label section present; **blue** = a study admitting children; "
                    "empty = neither found."
                ),
                figure=pediatric_dots(short),
                height=max(300, 24 * len(short) + 100),
            )
        )
        exhibits.append(
            Exhibit(
                slug="mechanism-literature",
                title="How much has been written about each shortlisted drug and this mechanism?",
                caption=(
                    "PubMed record counts, log scale: the drug with the gene, protein, pathway or "
                    "disease, and the drug with the tumour context. Descriptive only - a count "
                    "never moves a rung."
                ),
                legend="**blue** = drug AND mechanism; **purple** = drug AND tumour context.",
                figure=mechanism_literature(short, data.get("ladder_top") or []),
                height=max(300, 26 * len(short) + 100),
            )
        )
    if transfer_rows:
        exhibits.append(transfer_exhibit(transfer_rows))
    return exhibits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--analysis", type=Path, default=DEFAULT_IN)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--html", type=Path, default=DEFAULT_HTML)
    parser.add_argument("--transfer", type=Path, default=DEFAULT_TRANSFER)
    args = parser.parse_args()
    if not args.analysis.is_file():
        print(f"{args.analysis} missing - run tools/track2_enrich.py first")
        return 1
    data = json.loads(args.analysis.read_text(encoding="utf-8"))
    theme.install_template()
    exhibits = build(data, read_transfer(args.transfer))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for exhibit in exhibits:
        png = exhibit.write_image(args.out_dir)
        print(f"{exhibit.slug:<24} {'png ' + str(png) if png else 'png: kaleido missing'}")
    section = Section(
        slug="track2-step-7",
        title="Track 2 - step 7: the evidence ladder",
        blurb=(
            "Every approved drug on every direction it touches, placed on one rung of the "
            "pre-registered ladder; the shortlist, the do-not table, and the decoy control."
        ),
        exhibits=exhibits,
    )
    html = render(
        [section],
        title="Track 2 - the evidence ladder",
        subject=(
            f"card v{data.get('card_version')} · {data.get('gene')} · built "
            f"{data.get('built_at', '')[:19]} · {data.get('code_version')}"
        ),
    )
    args.html.write_text(html, encoding="utf-8")
    print(f"html {args.html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
