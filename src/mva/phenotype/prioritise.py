"""Rank every annotated gene against the child's phenotype.

This is the step the whole package exists for, and the reason it matters is a bias in the
work that came before it. The current lead - two rare protein-altering alleles in one gene
- was found by filtering an **eight-gene candidate panel** chosen by hand from what is
known about the disease. That is a circular prior: the search found MVA genes because it
only looked at MVA genes. ``mva.warehouse.analysis_funnel`` states the gap outright, that
no genome-wide ranking exists in this repository and its table must not imply one.

Ranking here is driven by the child's symptoms alone. It never reads the panel, never reads
the callset, and never reads a variant. It therefore cannot inherit the panel's bias, which
is what makes its verdict on that gene worth having: a gene that surfaces in the top ten of
five thousand, chosen by a scorer that was never told which genes to care about, is
evidence of a different kind from a gene that survived a filter built around it.

**Genes, not variants.** A phenotype says which gene is likely broken; it says nothing
about which allele. Fusing the two would launder a phenotype prior into per-variant
evidence and double-count it. The ranking stops at the gene, and
:mod:`mva.phenotype.prior` hands it to the pair ranker as a prior over genes.
"""

from dataclasses import dataclass

from .associations import Corpus
from .ontology import Ontology
from .similarity import NO_MATCH, Similarity, compare
from .terms import TermSet


@dataclass(frozen=True)
class GeneScore:
    """One gene's standing against the term set, with the arithmetic behind it."""

    symbol: str
    rank: int
    similarity: Similarity
    entrez_id: str | None = None
    #: How many curated phenotype terms the gene carries. Context for the reverse score:
    #: a heavily annotated gene is penalised by it, and the reader has to be able to see that.
    term_count: int = 0

    @property
    def score(self) -> float:
        """The number the ranking is ordered by, in ``0..1``."""
        return self.similarity.normalised

    @property
    def summary(self) -> str:
        """One line naming the strongest feature match - what a table cell should show."""
        best = self.similarity.best
        if best is None or best.common_ancestor is None:
            return "no informative match"
        return f"{best.query_term} via {best.common_ancestor} (IC {best.ic:.2f})"


@dataclass(frozen=True)
class Ranking:
    """A whole ranked list, and enough about its inputs to be reproducible.

    The term set is carried because two rankings that differ by one term are two different
    claims, and a list with no term set attached cannot be told apart from the other one.
    """

    term_set: TermSet
    scores: tuple[GeneScore, ...]
    #: Query terms the ontology release could not place. Reported, never silently dropped.
    unresolved: tuple[str, ...] = ()
    #: How many annotated genes were **scored**, including those that scored zero and are
    #: therefore absent from ``scores``. This is the denominator a rank is quoted against:
    #: "rank 3 of 4,921 genes considered" is the honest sentence, where "of 812 genes that
    #: scored above zero" silently flatters every rank by dropping the genes it beat.
    considered: int = 0

    def __len__(self) -> int:
        return len(self.scores)

    def top(self, limit: int) -> tuple[GeneScore, ...]:
        """The best ``limit`` genes."""
        return self.scores[:limit]

    def rank_of(self, symbol: str) -> int | None:
        """Where a gene placed, or ``None`` if it was never annotated.

        ``None`` is not rank infinity. A gene absent from HPO's curation has no phenotype
        evidence either way, and reporting that as "ranked last" would turn missing
        knowledge into a negative finding.
        """
        wanted = symbol.upper()
        for score in self.scores:
            if score.symbol == wanted:
                return score.rank
        return None

    def by_symbol(self, symbol: str) -> GeneScore | None:
        """One gene's full record, matched case-insensitively."""
        wanted = symbol.upper()
        return next((score for score in self.scores if score.symbol == wanted), None)


def rank_genes(
    term_set: TermSet,
    corpus: Corpus,
    ontology: Ontology,
    *,
    minimum: float = 0.0,
) -> Ranking:
    """Score every annotated gene against ``term_set``, best first.

    ``minimum`` drops genes scoring at or below it. The default drops only genes that
    scored exactly zero - they share no informative ancestor with any query term, so they
    carry no signal and ordering them against each other would be ordering noise. The
    count of genes *considered* is kept on the :class:`Ranking` regardless, so "where did
    this gene place, out of how many" stays answerable, which is the question the whole
    exercise is built to ask.
    """
    resolved: list[str] = []
    unresolved: list[str] = []
    for hpo_id in term_set.ids:
        live = ontology.resolve(hpo_id)
        if live is None:
            unresolved.append(hpo_id)
        else:
            resolved.append(live)

    scored: list[tuple[str, Similarity, str | None, int]] = []
    for symbol in corpus.symbols():
        annotation = corpus.genes[symbol]
        similarity = compare(resolved, sorted(annotation.terms), ontology) if resolved else NO_MATCH
        if similarity.normalised > minimum:
            scored.append((symbol, similarity, annotation.entrez_id, len(annotation.terms)))

    # Sorted by score, then by symbol: ties are broken by name rather than by dict order,
    # so two runs over the same release produce byte-identical output.
    scored.sort(key=lambda row: (-row[1].normalised, row[0]))

    scores = tuple(
        GeneScore(
            symbol=symbol,
            rank=index,
            similarity=similarity,
            entrez_id=entrez_id,
            term_count=term_count,
        )
        for index, (symbol, similarity, entrez_id, term_count) in enumerate(scored, start=1)
    )
    return Ranking(
        term_set=term_set,
        scores=scores,
        unresolved=tuple(unresolved),
        considered=len(corpus),
    )


@dataclass(frozen=True)
class RankDelta:
    """How one gene moved between two rankings."""

    symbol: str
    before: int | None
    after: int | None

    @property
    def moved(self) -> int | None:
        """Places gained (positive) or lost. ``None`` when the gene is missing from one side."""
        if self.before is None or self.after is None:
            return None
        return self.before - self.after


def delta(first: Ranking, second: Ranking, symbols: tuple[str, ...]) -> tuple[RankDelta, ...]:
    """Compare two rankings over a named set of genes.

    Built for the open question the roadmap records: whether the **parental** term
    ``HP:0200067`` belongs in the proband's term set at all. Running with and without it
    and reporting the movement answers that with a number instead of an argument.
    """
    return tuple(
        RankDelta(symbol.upper(), first.rank_of(symbol), second.rank_of(symbol))
        for symbol in symbols
    )
