"""Case-report anchors, derived by script from a gene list and a term list.

*Plain words.* An **anchor** is a published paper that talks about one of our candidate
genes *and* about the child's clinical features. The more of the child's features one
paper covers, the more that paper looks like a description of the same disease.

**Why this is a script and not a reading list.** The first draft of the iteration-2 plan
named five chromosome-instability papers by hand, and those are the discovery papers of
the genes iteration 1 had already found: a hand-written anchor list is a leak through the
blind protocol, dressed as a literature search. So the anchor set is *generated* — one
search per (gene, clinical term) pair, over a gene list this module is handed — and the
methodology entry prints which anchor came out of which gene. A paper that the plan's own
bibliography names enters only if the script produced it.

**The matched-term count falls out of the queries, at no extra cost.** Asking
``gene AND term`` once per term gives, per paper, the set of terms whose query returned
it. A PMID returned by five of the seven searches is a paper that discusses that gene
alongside five of the child's features — and that is a per-*paper* statement, which is
what the claim needs, not a per-gene one.

Case-agnostic: genes in, term labels in, anchor rows out. The child's terms are supplied
by the caller (:mod:`mva.phenotype.terms` owns them); nothing about this case is written
here.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from ..drugs.cache import Fetcher
from . import sources

__all__ = ["Anchor", "GeneAnchors", "for_gene", "for_genes", "rank"]


@dataclass(frozen=True)
class Anchor:
    """One paper, and how much of the child's phenotype it covers alongside one gene."""

    gene: str
    pmid: str
    title: str
    journal: str
    year: str
    #: The clinical term labels whose search returned this paper, in term order.
    matched_terms: tuple[str, ...]
    terms_total: int

    @property
    def terms_matched(self) -> int:
        return len(self.matched_terms)


@dataclass
class GeneAnchors:
    """Every anchor found for one gene, plus the per-term hit counts behind them."""

    gene: str
    anchors: list[Anchor] = field(default_factory=list)
    #: term label -> how many papers PubTator holds for ``gene AND term``, all pages.
    hits_per_term: dict[str, int] = field(default_factory=dict)

    @property
    def best(self) -> int:
        """The highest matched-term count any single paper reached for this gene."""
        return max((anchor.terms_matched for anchor in self.anchors), default=0)

    @property
    def terms_with_any_paper(self) -> int:
        """How many of the child's terms the gene co-occurs with at all."""
        return sum(1 for count in self.hits_per_term.values() if count > 0)


def for_gene(
    fetcher: Fetcher,
    gene: str,
    term_labels: Sequence[str],
) -> GeneAnchors:
    """Search ``gene AND <term>`` once per term and fold the replies into paper rows.

    Every paper the searches surfaced is returned, including the ones matching a single
    term. Filtering to "interesting" papers here would hide the denominator the decoy
    comparison needs: a decoy gene with many one-term papers and no five-term paper is
    precisely the shape the null is measuring.
    """
    found: dict[str, dict[str, Any]] = {}
    matched: dict[str, list[str]] = {}
    hits: dict[str, int] = {}
    for label in term_labels:
        reply = sources.search_papers(fetcher, sources.gene_query(gene, label))
        hits[label] = int(reply["count"])
        for paper in reply["papers"]:
            pmid = paper["pmid"]
            if not pmid:
                continue
            found.setdefault(pmid, paper)
            matched.setdefault(pmid, []).append(label)
    anchors = [
        Anchor(
            gene=gene,
            pmid=pmid,
            title=paper["title"],
            journal=paper["journal"],
            year=paper["year"],
            matched_terms=tuple(matched[pmid]),
            terms_total=len(term_labels),
        )
        for pmid, paper in found.items()
    ]
    anchors.sort(key=lambda anchor: (-anchor.terms_matched, anchor.pmid))
    return GeneAnchors(gene=gene, anchors=anchors, hits_per_term=hits)


def for_genes(
    fetcher: Fetcher,
    genes: Sequence[str],
    term_labels: Sequence[str],
    *,
    on_gene: Callable[[str, int, int], None] | None = None,
) -> list[GeneAnchors]:
    """:func:`for_gene` over a gene list, in order, with an optional progress callback.

    The pass is ``len(genes) x len(term_labels)`` searches and is paced by the fetcher's
    own courtesy interval, so it is minutes rather than seconds; ``on_gene`` exists so a
    caller can say where it has got to without this module knowing what a log looks like.
    """
    results = []
    for index, gene in enumerate(genes, start=1):
        results.append(for_gene(fetcher, gene, term_labels))
        if on_gene is not None:
            on_gene(gene, index, len(genes))
    return results


def rank(results: Sequence[GeneAnchors]) -> list[tuple[str, int, int]]:
    """Genes ordered by their best paper, as ``(gene, best, terms_with_any_paper)``.

    **Citation volume is deliberately not a tie-break.** The whole point of step 5 is to
    find out whether the literature says anything a hit count does not, so the number
    that would settle a tie in favour of the famous gene is kept out of the ordering and
    measured against it instead. Ties break on the gene symbol, which carries nothing.
    """
    rows = [(result.gene, result.best, result.terms_with_any_paper) for result in results]
    rows.sort(key=lambda row: (-row[1], -row[2], row[0]))
    return rows
