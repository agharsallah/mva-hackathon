"""Reading each gene's mode of inheritance out of the same corpus the ranker scores on.

:mod:`mva.pipeline.inheritance` holds the *rule* — recessive genes matter more when the
parents have a history of pregnancy loss, dominant-only genes matter less — and takes a
:class:`~mva.pipeline.inheritance.GeneInheritance` per gene. This module builds those from
``genes_to_phenotype.txt``, which already carries the inheritance terms as ordinary
annotations beside the clinical features.

No new file and no new download: the corpus is the one step 1 ranked on, so the inheritance
prior and the phenotype score cannot disagree about which genes exist.
"""

from __future__ import annotations

from ..pipeline.inheritance import DOMINANT_TERMS, RECESSIVE_TERMS, GeneInheritance
from .associations import Corpus

__all__ = ["MODE_TERMS", "gene_inheritance"]

#: Every term this module reads as a statement about inheritance.
MODE_TERMS = RECESSIVE_TERMS | DOMINANT_TERMS


def gene_inheritance(corpus: Corpus) -> dict[str, GeneInheritance]:
    """One :class:`GeneInheritance` per annotated gene, keyed by symbol.

    A gene with no inheritance term curated against it comes back with an empty ``modes``,
    which the factor reads as *unknown* and leaves at 1.0 — the absence is carried, not
    turned into an assumption.
    """
    return {
        symbol: GeneInheritance(
            symbol=symbol,
            modes=frozenset(annotation.terms & MODE_TERMS),
            disease_terms=annotation.terms,
        )
        for symbol, annotation in corpus.genes.items()
    }
