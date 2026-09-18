#!/usr/bin/env python3
"""Does any single published paper describe a candidate gene alongside this child's features?

*Plain words.* For each gene in the step-5 set, and for each of the child's seven proband
HPO term labels, ask PubTator 3.0 — NCBI's entity-annotated search over PubMed and PMC —
for the papers mentioning both. A paper returned by five of the seven searches discusses
that gene alongside five of the child's clinical features, which is what a **case-report
anchor** is.

**Derived, never typed.** The first draft of the iteration-2 plan listed five
chromosome-instability papers by name — and those are the discovery papers of the genes
iteration 1 had already found. A hand-written anchor list in a blind design is a leak
wearing a citation. So the anchor set is generated from the gene list, and the entry prints
which anchor came out of which gene. A paper in the plan's own bibliography enters only if
these queries produce it.

**The decoys run through the identical loop.** Without them "we found a paper" is a
sentence, not a measurement: the question is whether a symptom-nominated gene finds such a
paper more often than a size-matched control does.

Writes ``build/it2/step-5/tables/it2_anchors.tsv``, ``it2_anchor_terms.tsv`` and
``anchors.json``. Every reply is cached, so a re-run costs no requests.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import it2_step5_common as common
from mva.drugs import provenance
from mva.drugs.cache import Fetcher
from mva.knowledge import anchors as anchor_module
from mva.knowledge import sources
from mva.phenotype.terms import PROBAND_ONLY

ANCHOR_COLUMNS = (
    "gene",
    "pmid",
    "title",
    "journal",
    "year",
    "terms_matched",
    "terms_total",
    "matched_terms",
    "is_target",
    "is_decoy",
    "in_top_leaders",
)

TERM_COLUMNS = ("gene", "term_label", "papers", "is_target", "is_decoy")

#: Seconds between live PubTator calls. NCBI's documented courtesy is 3 requests a second
#: *across its services*, and this run measured HTTP 429 at 0.34 s while another stage was
#: reading LitVar on the same host. Slower is the price of a pass that finishes.
DEFAULT_INTERVAL = 0.7

#: Below this a paper is noise: one shared term between a gene and a feature is what any
#: two biomedical words do. Kept as a write-time cut, not a query-time one, so the per-term
#: denominators in ``it2_anchor_terms`` still carry every count the searches returned.
MIN_TERMS = 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=common.DEFAULT_OUT)
    parser.add_argument("--refresh", action="store_true", help="bypass the cache")
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL,
        help="seconds between live calls; raise it if NCBI answers 429",
    )
    parser.add_argument(
        "--limit", type=int, default=0, help="stop after N genes (a smoke test, never a result)"
    )
    args = parser.parse_args(argv)

    labels = [term.label for term in PROBAND_ONLY.terms]
    gene_rows = common.genes()
    if args.limit:
        gene_rows = gene_rows[: args.limit]
    flags = {row["gene"]: row for row in gene_rows}
    names = [row["gene"] for row in gene_rows]
    searches = len(names) * len(labels)
    print(f"{len(names):,} genes x {len(labels)} proband terms = {searches:,} searches")
    print("terms: " + "; ".join(labels))

    fetcher = Fetcher(source="pubtator3", refresh=args.refresh, min_interval_s=args.interval)

    def progress(gene: str, index: int, total: int) -> None:
        if index % 25 == 0 or index == total:
            print(f"  {index:>4}/{total}  {gene}")

    results = anchor_module.for_genes(fetcher, names, labels, on_gene=progress)

    anchor_rows = []
    term_rows = []
    for result in results:
        flag = flags.get(result.gene, {})
        for anchor in result.anchors:
            if anchor.terms_matched < MIN_TERMS:
                continue
            anchor_rows.append(
                {
                    "gene": anchor.gene,
                    "pmid": anchor.pmid,
                    "title": anchor.title,
                    "journal": anchor.journal,
                    "year": anchor.year,
                    "terms_matched": anchor.terms_matched,
                    "terms_total": anchor.terms_total,
                    "matched_terms": "; ".join(anchor.matched_terms),
                    "is_target": bool(flag.get("is_target")),
                    "is_decoy": bool(flag.get("is_decoy")),
                    "in_top_leaders": bool(flag.get("in_top_leaders")),
                }
            )
        for label, papers in result.hits_per_term.items():
            term_rows.append(
                {
                    "gene": result.gene,
                    "term_label": label,
                    "papers": papers,
                    "is_target": bool(flag.get("is_target")),
                    "is_decoy": bool(flag.get("is_decoy")),
                }
            )

    tables = args.out / "tables"
    written = common.write_tsv(tables / "it2_anchors.tsv", anchor_rows, ANCHOR_COLUMNS)
    common.write_tsv(tables / "it2_anchor_terms.tsv", term_rows, TERM_COLUMNS)

    best = {result.gene: result.best for result in results}
    reaching = sorted(gene for gene, value in best.items() if value >= 5)
    payload = {
        "genes": len(results),
        "terms": labels,
        "searches": len(results) * len(labels),
        "anchor_rows": written,
        "min_terms_written": MIN_TERMS,
        "genes_reaching_five_terms": reaching,
        "best_per_gene": best,
        "source": sources.PUBTATOR,
    }
    common.write_json(args.out / "anchors.json", payload)

    print(f"\n  anchor rows (>= {MIN_TERMS} terms) : {written:,}")
    print(f"  genes with a >= 5-term paper    : {len(reaching)}")
    if reaching:
        print("    " + ", ".join(reaching[:20]))

    manifest = provenance.envelope("it2-step5-anchors", built_by=Path(__file__).name)
    manifest["inputs"] = [
        provenance.api_input(
            "pubtator3",
            sources.PUBTATOR,
            role="entity-annotated literature search",
            fetcher=fetcher,
            queries=[sources.gene_query("<gene>", label) for label in labels],
        )
    ]
    manifest["outputs"] = [
        provenance.output(tables / "it2_anchors.tsv", written),
        provenance.output(tables / "it2_anchor_terms.tsv", len(term_rows)),
    ]
    provenance.write(manifest, args.out / "anchors.provenance.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
