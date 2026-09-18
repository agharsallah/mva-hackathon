#!/usr/bin/env python3
"""Does the knowledge route order anything that a publication count does not?

This is the stage that decides whether step 5 is a result or a list of famous genes.

**The knowledge score, fixed before the run.** Per gene, lexicographically:
``(best paper's matched-term count, alleles of this gene that anyone has published about)``.
Citation volume is deliberately **not** in it and not a tie-break — the whole question is
whether the literature says something a hit count does not, and a score that quietly
contained the hit count could not answer it.

**Two measurements, both pre-registered:**

* **the decoy null (H038)** — the 396 size-matched control genes ran through the identical
  queries; AUC with a bootstrap interval, by the same code step 4 used. An interval
  covering 0.5 means the route has no measured ranking power.
* **the citation baseline (H039)** — Spearman rho and top-5 overlap against ranking the
  same genes by PubMed hit count alone. Agreement means the route *is* citation volume.

Both have to pass before step 6 may treat this as a ranking route. Writes
``build/it2/step-5/tables/it2_knowledge_ranks.tsv`` and ``baselines.json``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import it2_step5_common as common
from mva.drugs import provenance
from mva.drugs.cache import Fetcher
from mva.drugs.sources import pubmed
from mva.knowledge import baselines

COLUMNS = (
    "gene",
    "knowledge_rank",
    "knowledge_score",
    "best_terms_matched",
    "terms_with_any_paper",
    "described_alleles",
    "pubmed_count",
    "citation_rank",
    "lr_rank",
    "is_target",
    "is_decoy",
    "curated",
)

#: How the two components of the knowledge score combine into one number the AUC can read.
#: The term count dominates by construction (it is worth 100 published alleles) so the
#: ordering is lexicographic, and the second component only ever breaks a tie.
TERM_WEIGHT = 100.0


def pubmed_query(gene: str) -> str:
    """The citation baseline's query. One spelling, so the cache key is stable."""
    return f"{gene}[Title/Abstract]"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=common.DEFAULT_OUT)
    parser.add_argument("--refresh", action="store_true", help="bypass the cache")
    args = parser.parse_args(argv)

    anchors_path = args.out / "anchors.json"
    catalogue_path = args.out / "catalogue.json"
    for path in (anchors_path, catalogue_path):
        if not path.exists():
            print(f"missing {path}; run the catalogue and anchor stages first")
            return 1
    anchors = json.loads(anchors_path.read_text(encoding="utf-8"))
    best = {gene: int(value) for gene, value in (anchors.get("best_per_gene") or {}).items()}
    terms_any = _terms_with_any_paper(args.out)
    described = _described_alleles(args.out)

    gene_rows = common.genes()
    fetcher = Fetcher(source="pubmed", refresh=args.refresh)
    counts: dict[str, int] = {}
    for index, row in enumerate(gene_rows, start=1):
        counts[row["gene"]] = pubmed.count(fetcher, pubmed_query(row["gene"]))
        if index % 100 == 0 or index == len(gene_rows):
            print(f"  {index:>4}/{len(gene_rows)} PubMed counts")

    scored = []
    for row in gene_rows:
        gene = row["gene"]
        score = TERM_WEIGHT * best.get(gene, 0) + min(described.get(gene, 0), 99)
        scored.append(
            {
                "gene": gene,
                "knowledge_score": score,
                "best_terms_matched": best.get(gene, 0),
                "terms_with_any_paper": terms_any.get(gene, 0),
                "described_alleles": described.get(gene, 0),
                "pubmed_count": counts[gene],
                "lr_rank": row["lr_rank"],
                "is_target": bool(row["is_target"]),
                "is_decoy": bool(row["is_decoy"]),
                "curated": bool(row["curated"]),
            }
        )

    knowledge = [(row["gene"], row["knowledge_score"]) for row in scored]
    citations = [(row["gene"], float(row["pubmed_count"])) for row in scored]
    weight = baselines.weigh(
        target_scores=[r["knowledge_score"] for r in scored if r["is_target"]],
        decoy_scores=[r["knowledge_score"] for r in scored if r["is_decoy"]],
        knowledge=knowledge,
        citations=citations,
    )

    knowledge_rank = _dense_rank(knowledge)
    citation_rank = _dense_rank(citations)
    for row in scored:
        row["knowledge_rank"] = knowledge_rank[row["gene"]]
        row["citation_rank"] = citation_rank[row["gene"]]
    scored.sort(key=lambda row: (row["knowledge_rank"], row["gene"]))

    written = common.write_tsv(args.out / "tables" / "it2_knowledge_ranks.tsv", scored, COLUMNS)
    payload = {
        "genes": len(scored),
        "term_weight": TERM_WEIGHT,
        "pubmed_query": pubmed_query("<gene>"),
        "separation": {
            "auc": weight.separation.auc,
            "low": weight.separation.low,
            "high": weight.separation.high,
            "targets": weight.separation.positives,
            "decoys": weight.separation.negatives,
            "separates": weight.separation.separates,
            "verdict": weight.separation.verdict,
        },
        "agreement": {
            "rho": weight.agreement.rho,
            "overlap": weight.agreement.overlap,
            "k": weight.agreement.k,
            "knowledge_top": list(weight.agreement.left_top),
            "citation_top": list(weight.agreement.right_top),
            "tied_at_k": weight.agreement.tied_at_k,
            "reorders": weight.agreement.reorders,
            "verdict": weight.agreement.verdict,
        },
        "route": {
            "ranking_route": weight.ranking_route,
            "verdict": weight.verdict,
        },
        "leaders": scored[:10],
    }
    common.write_json(args.out / "baselines.json", payload)

    print(f"\n  {weight.separation.verdict}")
    print(f"  {weight.agreement.verdict}")
    print(f"  -> {weight.verdict}")
    print(f"\n  wrote {written:,} rows")

    manifest = provenance.envelope("it2-step5-baselines", built_by=Path(__file__).name)
    manifest["inputs"] = [
        provenance.api_input(
            "pubmed",
            pubmed.BASE,
            role="citation-volume baseline",
            fetcher=fetcher,
            queries=[pubmed_query("<gene>")],
        )
    ]
    manifest["outputs"] = [
        provenance.output(args.out / "tables" / "it2_knowledge_ranks.tsv", written)
    ]
    provenance.write(manifest, args.out / "baselines.provenance.json")
    return 0


def _dense_rank(scores: list[tuple[str, float]]) -> dict[str, int]:
    """Position in the ordering, highest score first, ties broken by name for stability."""
    ordered = sorted(scores, key=lambda row: (-row[1], row[0]))
    return {name: index for index, (name, _) in enumerate(ordered, start=1)}


def _terms_with_any_paper(out: Path) -> dict[str, int]:
    """Per gene, how many clinical terms it co-occurs with at all, from the anchor stage."""
    path = out / "tables" / "it2_anchor_terms.tsv"
    counts: dict[str, int] = {}
    if not path.exists():
        return counts
    with path.open(encoding="utf-8") as handle:
        header = handle.readline().rstrip("\n").split("\t")
        gene_at, papers_at = header.index("gene"), header.index("papers")
        for line in handle:
            cells = line.rstrip("\n").split("\t")
            if int(cells[papers_at] or 0) > 0:
                counts[cells[gene_at]] = counts.get(cells[gene_at], 0) + 1
    return counts


def _described_alleles(out: Path) -> dict[str, int]:
    """Per gene, how many of this child's alleles anyone has published about."""
    path = out / "tables" / "it2_pub_alleles.tsv"
    counts: dict[str, int] = {}
    if not path.exists():
        return counts
    with path.open(encoding="utf-8") as handle:
        header = handle.readline().rstrip("\n").split("\t")
        gene_at, count_at = header.index("gene"), header.index("pmid_count")
        for line in handle:
            cells = line.rstrip("\n").split("\t")
            if int(cells[count_at] or 0) > 0:
                counts[cells[gene_at]] = counts.get(cells[gene_at], 0) + 1
    return counts


if __name__ == "__main__":
    raise SystemExit(main())
