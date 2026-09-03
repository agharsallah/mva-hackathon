"""How alike are two lists of symptoms, measured on the graph rather than the words.

The child has eight features. A gene has a curated list of features its patients show.
Neither list will contain the same strings, so the comparison has to run over the
ontology: two terms are alike to the extent that the **most specific thing they have in
common** is itself rare. That is Resnik similarity, and the rarity measure is the
information content computed in :mod:`mva.phenotype.ontology`.

One term against one term is Resnik. Two *sets* against each other needs a rollup, and the
choice of rollup is where these methods actually differ:

**Best-match-average.** For each term on one side, take its single best partner on the
other and average those bests. Taking the best is what makes a match survive the six other
features that have nothing to do with the gene; averaging is what stops one lucky pairing
carrying the whole score. This is the shape PhenoDigm - and therefore hiPHIVE, and
therefore Exomiser - is built on.

**The direction matters, and both directions are wrong on their own.**

* *Forward* (query to gene) asks "is each of the child's features explained by this gene?"
  It ignores everything else the gene does, so a gene with three hundred curated features
  can score highly on the strength of eight.
* *Reverse* (gene to query) asks "is each of the gene's features present in the child?"
  That punishes exactly the well-studied pleiotropic genes a rare-disease case cares about,
  and rewards sparsely annotated ones for having little to be wrong about.

So both are computed and the symmetric mean is the default, with the forward score carried
alongside. Where the two disagree sharply, the disagreement is a fact about how heavily
the gene is annotated, not about the child, and the report says so.

**Normalisation.** A raw Resnik average is in nats and has no ceiling, which makes it
unreadable and incomparable across term sets of different sizes. Dividing by the score the
query set achieves against *itself* - the best any gene could possibly do - puts it on
``0..1``. Exomiser normalises the same way before scaling to 100.

**What this is not.** Exomiser's published hiPHIVE additionally walks mouse and zebrafish
models and a STRING protein-interaction matrix. Those are switched off deliberately: on
the UDN cohort, ``prioritiser-params=human`` scores 82.8% top-10 against 66.6% for the
all-species default (Genome Medicine vol 17 art 127, 2025). This module is the human-only path,
and every result it produces must be described that way.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .ontology import Ontology


@dataclass(frozen=True)
class TermMatch:
    """One query term, its best partner in a gene's term list, and where they meet."""

    query_term: str
    gene_term: str | None
    #: The most informative term both descend from. ``None`` when nothing is shared.
    common_ancestor: str | None
    #: Resnik similarity: the information content of that common ancestor, in nats.
    ic: float

    @property
    def matched(self) -> bool:
        """Whether the query term found any informative partner at all."""
        return self.gene_term is not None and self.ic > 0.0


@dataclass(frozen=True)
class Similarity:
    """One term set scored against one gene's term set, with the arithmetic kept.

    ``matches`` is the per-term breakdown, and it is the reason this is a record rather
    than a float: "why did this gene rank here" is answered by naming which feature matched
    which curated feature through which shared ancestor. A bare score cannot be argued with,
    and an unarguable number has no place in the evidence register.
    """

    forward: float
    reverse: float
    symmetric: float
    #: :attr:`symmetric` divided by the best score this query set could achieve, in ``0..1``.
    normalised: float
    matches: tuple[TermMatch, ...]

    @property
    def best(self) -> TermMatch | None:
        """The single strongest feature match - what a one-line summary should quote."""
        informative = [match for match in self.matches if match.matched]
        return max(informative, key=lambda m: m.ic) if informative else None

    @property
    def matched_terms(self) -> tuple[str, ...]:
        """Query terms that found an informative partner, strongest first."""
        informative = sorted(
            (m for m in self.matches if m.matched), key=lambda m: m.ic, reverse=True
        )
        return tuple(match.query_term for match in informative)


#: An empty result, returned rather than raising when a gene has no usable annotation.
NO_MATCH = Similarity(0.0, 0.0, 0.0, 0.0, ())


def best_match(query_term: str, gene_terms: Iterable[str], ontology: Ontology) -> TermMatch:
    """The strongest Resnik pairing between one query term and a gene's terms."""
    best_term: str | None = None
    best_ancestor: str | None = None
    best_ic = 0.0
    for gene_term in gene_terms:
        ancestor, ic = ontology.most_informative_common_ancestor(query_term, gene_term)
        if ancestor is not None and (best_term is None or ic > best_ic):
            best_term, best_ancestor, best_ic = gene_term, ancestor, ic
    return TermMatch(query_term, best_term, best_ancestor, best_ic)


def compare(
    query_terms: Sequence[str], gene_terms: Sequence[str], ontology: Ontology
) -> Similarity:
    """Score a query term set against one gene's term set.

    Returns :data:`NO_MATCH` rather than raising on an empty side, because a genome-wide
    run reaches genes with no usable annotation and losing the whole run to one of them
    would be the same failure the annotator port is written to avoid.
    """
    if not query_terms or not gene_terms:
        return NO_MATCH

    matches = tuple(best_match(term, gene_terms, ontology) for term in query_terms)
    forward = _mean(match.ic for match in matches)
    reverse = _mean(best_match(term, query_terms, ontology).ic for term in gene_terms)
    symmetric = (forward + reverse) / 2.0

    optimal = optimal_score(query_terms, ontology)
    normalised = symmetric / optimal if optimal > 0 else 0.0
    return Similarity(
        forward=forward,
        reverse=reverse,
        symmetric=symmetric,
        # Clamped: the reverse direction is measured over the gene's terms, so a gene whose
        # own annotations are rarer than the query's can exceed the query's self-score. The
        # ceiling is what makes the number readable as a share of the achievable best.
        normalised=min(normalised, 1.0),
        matches=matches,
    )


def optimal_score(query_terms: Sequence[str], ontology: Ontology) -> float:
    """The score the query set achieves against itself - the ceiling for normalisation.

    Every term's best partner is itself, so this is the mean information content of the
    query terms, and it is identical in both directions.
    """
    if not query_terms:
        return 0.0
    return _mean(ontology.ic(term) for term in query_terms)


def _mean(values: Iterable[float]) -> float:
    collected = list(values)
    return sum(collected) / len(collected) if collected else 0.0
