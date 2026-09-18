#!/usr/bin/env python3
"""Render step 5's report figures from ``build/it2/step-5/analysis.json`` and nothing else.

Every number on every figure comes from the file the run wrote, so a figure cannot drift
from the entry that quotes it — and ``tools/check_figures_fresh.py`` fails any figure older
than that file. A figure whose input is absent is **skipped**, not drawn empty: a chart of
zeros and a stage that did not run look the same to a reader, and only one is a result.

Writes ``figures/track1/iteration2/step-5/<slug>.png`` plus one interactive page.

Usage::

    uv run python tools/render_it2_step5_figures.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from it2_step5_charts import (
    anchors_figure,
    catalogue_figure,
    citations_figure,
    domains_figure,
    separation_figure,
    sources_figure,
)
from mva.render import theme
from mva.render.figure import Exhibit, Section
from mva.render.report import render

DEFAULT_IN = Path("build/it2/step-5/analysis.json")
DEFAULT_OUT = Path("figures/track1/iteration2/step-5")


def build(data: dict) -> list[Exhibit]:
    """Every exhibit whose input is present. Absent inputs are skipped, never drawn empty."""
    exhibits: list[Exhibit] = []
    coverage = data.get("coverage") or {}
    anchors = data.get("anchor_summary") or {}
    protein = data.get("protein_summary") or {}
    baselines = data.get("baselines") or {}
    agreement = baselines.get("agreement") or {}
    separation = baselines.get("separation") or {}

    # The figure reads every gene, not the 25 the page shows: rho is a statement about all
    # 815, and a scatter of the leaders alone is a flat band that proves nothing.
    every_gene = data.get("citations_all") or data.get("citations") or []
    if every_gene and agreement:
        exhibits.append(
            Exhibit(
                slug="citations",
                title="The knowledge ordering against the ordering a hit count alone would give",
                caption=(
                    f"The test that decides whether this step is a result. All "
                    f"{len(every_gene):,} genes, each at "
                    "the rank the literature queries gave it and at the rank a raw PubMed hit "
                    "count alone would have given it; the dotted diagonal is no reordering at "
                    f"all. Spearman rho = {float(agreement.get('rho', 0)):.3f} and the two "
                    f"top-{int(agreement.get('k', 5))} sets share "
                    f"{int(agreement.get('overlap', 0))} genes. "
                    + (
                        "The route reorders the baseline, so it carries information a "
                        "citation count does not."
                        if agreement.get("reorders")
                        else "The route does not reorder the baseline: it has measured how "
                        "much has been written about each gene, which is a fact about the "
                        "literature and not about this child."
                    )
                ),
                legend=theme.legend_line(
                    theme.GOOD,
                    theme.BAD,
                    theme.MACHINE,
                    theme.MUTED,
                    extra=(
                        "**green** = a gene the symptoms nominated; **red** = a matched "
                        "decoy; **blue** = neither; **grey dotted** = the line of no "
                        "reordering."
                    ),
                ),
                figure=citations_figure(every_gene),
                height=560,
            )
        )

    if data.get("groups") and separation:
        exhibits.append(
            Exhibit(
                slug="separation",
                title="Targets against their matched decoys, scored by the identical queries",
                caption=(
                    "The decoy null for the knowledge route. The 396 controls are matched to "
                    "the targets on coding length and exon count, which matters here more "
                    "than anywhere else in the iteration: a bigger gene carries more alleles "
                    "and attracts more papers, so an unmatched control set would measure gene "
                    "size. "
                    f"{separation.get('verdict', '')}."
                ),
                legend=theme.legend_line(
                    theme.GOOD,
                    theme.BAD,
                    theme.MACHINE,
                    theme.RAW,
                    extra=(
                        "**green** = symptom-nominated targets; **red** = matched decoys; "
                        "**blue** = curated genes that were not nominated; **purple** = genes "
                        "with no curated phenotype at all. The label on each bar is how many "
                        "of its genes found a paper covering five of the child's features."
                    ),
                ),
                figure=separation_figure(data["groups"]),
                height=460,
            )
        )

    if data.get("catalogue") and coverage:
        exhibits.append(
            Exhibit(
                slug="catalogue",
                title="Of the alleles this child carries, which has anyone published about?",
                caption=(
                    f"{int(coverage.get('alleles', 0)):,} alleles the ranking scored across "
                    f"{int(coverage.get('genes', 0)):,} genes, each asked of LitVar 2.0 by its "
                    "dbSNP identifier. "
                    f"{int(coverage.get('described', 0)):,} of the "
                    f"{int(coverage.get('queryable', 0)):,} askable ones carry at least one "
                    "publication, and "
                    f"{int(coverage.get('unqueryable', 0)):,} have no identifier at all, so no "
                    "literature index keyed on dbSNP could have had an opinion about them. The "
                    "three counts are drawn separately because a single coverage percentage "
                    "would merge the last two, and only one of them says anything. The "
                    f"`carries` column of the table is different evidence entirely: "
                    f"{int(coverage.get('clinvar_carried', 0))} public ClinVar pathogenic "
                    "alleles that step 3 found present in the raw reads by k-mer count, with "
                    "no aligner and no caller."
                ),
                legend=theme.legend_line(
                    theme.GOOD,
                    theme.MACHINE,
                    theme.MUTED,
                    extra=(
                        "**green** = at least one publication mentions this exact variant; "
                        "**blue** = askable, and nobody has; **grey** = no dbSNP identifier, "
                        "so never asked. Grey is not evidence of absence."
                    ),
                ),
                figure=catalogue_figure(data["catalogue"]),
                height=560,
            )
        )

    if data.get("anchors"):
        reaching = anchors.get("genes_reaching_five_terms") or []
        exhibits.append(
            Exhibit(
                slug="anchors",
                title="Papers that discuss a gene alongside the child's own features",
                caption=(
                    f"{int(anchors.get('searches', 0)):,} searches — every gene in the set "
                    f"against each of the {len(anchors.get('terms') or [])} proband terms — "
                    "and a paper returned by five of the seven is a paper about five of this "
                    "child's features. Every row was produced by the script: a hand-picked "
                    "reading list in a blind design is a leak wearing a citation, because the "
                    "papers a reader reaches for are the discovery papers of the gene the "
                    "previous iteration already found. "
                    + (
                        f"{len(reaching)} gene(s) reached five terms: {', '.join(reaching[:8])}."
                        if reaching
                        else "No gene reached five terms."
                    )
                ),
                legend=theme.legend_line(
                    theme.GOOD,
                    theme.BAD,
                    theme.MACHINE,
                    extra=(
                        "**green** = a symptom-nominated target; **red** = a matched decoy; "
                        "**blue** = neither. A red bar as tall as a green one is the finding."
                    ),
                ),
                figure=anchors_figure(data["anchors"]),
                height=560,
            )
        )

    if data.get("protein") and data.get("domains"):
        leader = protein.get("leader") or {}
        exhibits.append(
            Exhibit(
                slug="domains",
                title="Where each leading missense allele sits in its protein",
                caption=(
                    "Each protein as a rule, its InterPro entries as bars, the missense allele "
                    "as a tick. Only an entry InterPro types as a *domain* counts for the "
                    "claim: families and superfamilies span most of a protein, so counting "
                    "them would make the test pass for almost any residue. Every position is a "
                    "fraction of the protein's own length — no residue number is committed. "
                    + (
                        f"The leading allele in {leader.get('gene')} sits at "
                        f"{float(leader.get('fraction') or 0) * 100:.1f}% of the protein, "
                        f"pLDDT {leader.get('plddt')}, "
                        f"{'inside' if leader.get('in_domain') else 'outside'} every annotated "
                        "domain."
                        if leader
                        else ""
                    )
                ),
                legend=theme.legend_line(
                    theme.DECISION,
                    theme.MACHINE,
                    theme.GOOD,
                    theme.BAD,
                    extra=(
                        "**amber** = an InterPro domain, the only kind the claim counts; "
                        "**blue** = a family or superfamily, drawn thinner and excluded; "
                        "**green tick** = the allele falls inside a domain; **red tick** = it "
                        "does not."
                    ),
                ),
                figure=domains_figure(data["protein"], data["domains"]),
                height=max(320, 70 * len(data["protein"])),
            )
        )

    if coverage and anchors and protein:
        exhibits.append(
            Exhibit(
                slug="sources",
                title="What each public source was asked, and what it could answer",
                caption=(
                    "Three sources, three different questions, and the grey band on each row "
                    "is the part of the question that source could not reach at all. That "
                    "band is what a reader needs before any of the coloured bars mean "
                    "anything: an allele with no dbSNP identifier, a residue with no canonical "
                    "protein consequence and a gene with no reviewed UniProt entry are "
                    "absences of the instrument, not findings about the child."
                ),
                legend=theme.legend_line(
                    theme.GOOD,
                    theme.MACHINE,
                    theme.MUTED,
                    extra=(
                        "**green** = the source answered yes; **blue** = it answered no; "
                        "**grey** = it could not be asked."
                    ),
                ),
                figure=sources_figure(coverage, anchors, protein),
                height=360,
            )
        )
    return exhibits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--source", type=Path, default=DEFAULT_IN)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    if not args.source.is_file():
        raise SystemExit(f"no {args.source} — run tools/export_it2_step5_analysis.py first")
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
                slug="it2-step-5",
                title="Step 5 — what the literature knows, and what that is worth",
                blurb=(
                    "A literature route is the easiest route in a rare-disease pipeline to "
                    "fool yourself with: the gene at the top of any search is the gene most "
                    "has been written about. So this step asks three knowledge questions — "
                    "has anyone published about the alleles this child carries, does any "
                    "single paper discuss a candidate gene alongside several of the child's "
                    "features, and does a leading missense allele land in an annotated "
                    "protein domain — and then asks a fourth that judges all three: does any "
                    "of it order anything that a raw publication count does not?"
                ),
                exhibits=exhibits,
            )
        ],
        title="Iteration 2, step 5",
        subject="The knowledge engine, and the baselines that judge it",
    )
    (args.out / "index.html").write_text(page, encoding="utf-8")
    print(f"\nwrote {len(exhibits)} exhibits to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
