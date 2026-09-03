"""Phenotype-driven gene ranking, in Python, with no JVM.

The child's clinical features arrive as eight HPO terms. This package turns them into a
ranking over every gene HPO curates - roughly five thousand - without reading the callset,
the candidate panel, or a single variant. That independence is the point: the existing
candidate list came from a hand-chosen eight-gene panel, and a prior chosen because of what
the disease is cannot also be evidence about which gene it is.

Why it is a reimplementation rather than a wrapper: Exomiser is a Java application whose
data ships as H2 MVStore databases and Java-serialised objects, with no Python reader and
a 31.5 GB unpacked footprint. Its **phenotype** inputs, though, are plain text. And the
published optimisation study (Genome Medicine 17:127, 2025) measures the human-only
configuration at 82.8% top-10 against 66.6% for the cross-species default - so the two
components that are genuinely hard to reproduce, the protein-interaction random walk and
the mouse and zebrafish models, are the ones the evidence says to leave out.

**Everything here is the human-only path, and no result may be described as "Exomiser".**

The flow, and one module per step:

``terms``          the eight HPO terms, declared once, with and without the parental one
``ontology``       ``hp.obo`` as a DAG: ancestor closure and information content
``associations``   ``genes_to_phenotype.txt``: which genes cause which features
``similarity``     Resnik similarity rolled up by best-match-average, both directions
``prioritise``     every gene scored and ranked against a term set
``prior``          the ranking as a ``gene_prior`` dict for the existing pair ranker
``remote``         Monarch semsim and Phen2Gene as independent second opinions

Nothing in :mod:`mva.pipeline` changes to accommodate any of it. ``rank_pairs`` already
takes a ``gene_prior`` dict; :func:`mva.phenotype.prior.gene_prior` produces one.
"""

from .associations import Corpus, GeneAnnotation, counts_from, parse_genes_to_phenotype
from .ontology import ROOT, Concept, Ontology, parse_obo
from .prior import DEFAULT_STRENGTH, explain, gene_prior
from .prioritise import GeneScore, RankDelta, Ranking, delta, rank_genes
from .similarity import NO_MATCH, Similarity, TermMatch, best_match, compare, optimal_score
from .terms import (
    NOTABLY_ABSENT,
    PARENTAL_TERM,
    PROBAND_ONLY,
    TERM_SETS,
    TERMS,
    WITH_PARENTAL,
    Term,
    TermSet,
    by_id,
    term_set,
)

__all__ = [
    "DEFAULT_STRENGTH",
    "NOTABLY_ABSENT",
    "NO_MATCH",
    "PARENTAL_TERM",
    "PROBAND_ONLY",
    "ROOT",
    "TERMS",
    "TERM_SETS",
    "WITH_PARENTAL",
    "Concept",
    "Corpus",
    "GeneAnnotation",
    "GeneScore",
    "Ontology",
    "RankDelta",
    "Ranking",
    "Similarity",
    "Term",
    "TermMatch",
    "TermSet",
    "best_match",
    "by_id",
    "compare",
    "counts_from",
    "delta",
    "explain",
    "gene_prior",
    "optimal_score",
    "parse_genes_to_phenotype",
    "parse_obo",
    "rank_genes",
    "term_set",
]
