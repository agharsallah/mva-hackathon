"""The blind target set and its decoy null.

The three properties worth pinning are the plan's three bias fixes: a mechanism-term gene
is tagged rather than hidden, the pure symptom-score rank survives beside it, and a decoy
is matched on gene shape while sharing none of the case's phenotype.
"""

import pytest

from mva.phenotype import targets
from mva.phenotype.associations import Corpus, GeneAnnotation
from mva.phenotype.ontology import Concept, Ontology
from mva.phenotype.prioritise import GeneScore, Ranking
from mva.phenotype.terms import TermSet


def _ranking(term_set: str, pairs) -> Ranking:
    return Ranking(
        term_set=TermSet(name=term_set, terms=(), rationale="a test set"),
        scores=tuple(
            GeneScore(symbol=symbol, rank=rank, similarity=sim, term_count=1)
            for symbol, rank, sim in pairs
        ),
        unresolved=(),
        considered=len(pairs),
    )


class _Sim:
    def __init__(self, value):
        self.normalised = value


def _score(symbol, rank, value):
    return (symbol, rank, _Sim(value))


def test_top_ranks_are_core_and_the_rest_of_the_set_is_net():
    ranking = _ranking("proband-only", [_score(f"G{i}", i, 1.0 / i) for i in range(1, 11)])
    rows = targets.build([ranking], core_n=3, target_n=6)
    assert [r.symbol for r in rows] == ["G1", "G2", "G3", "G4", "G5", "G6"]
    assert [r.tier for r in rows[:3]] == [targets.CORE] * 3
    assert [r.tier for r in rows[3:]] == [targets.NET] * 3


def test_a_mechanism_term_gene_enters_core_tagged_and_keeps_its_pure_rank():
    """The disease name may buy a seat; it may not buy a rediscovery claim."""
    ranking = _ranking("proband-only", [_score(f"G{i}", i, 1.0 / i) for i in range(1, 11)])
    rows = targets.build([ranking], mechanism={"G9"}, core_n=3, target_n=6)
    tagged = next(r for r in rows if r.symbol == "G9")
    assert tagged.tier == targets.MECHANISM
    assert tagged.score_rank == 9
    assert not tagged.earned_its_place


def test_a_mechanism_gene_the_ranker_never_scored_is_carried_with_no_rank():
    rows = targets.build([_ranking("proband-only", [_score("G1", 1, 0.9)])], mechanism={"XYZ"})
    unscored = next(r for r in rows if r.symbol == "XYZ")
    assert unscored.score_rank is None
    assert unscored.tier == targets.MECHANISM
    assert rows[-1].symbol == "XYZ", "unscored rows sort last, so the table reads as a ranking"


def test_the_two_term_sets_are_unioned_and_the_best_rank_wins():
    """Co-primary term sets: neither reading of the family-history term may hide a gene."""
    proband = _ranking("proband-only", [_score("A", 1, 0.9), _score("B", 40, 0.2)])
    parental = _ranking("with-parental", [_score("B", 2, 0.8), _score("C", 3, 0.7)])
    rows = {r.symbol: r for r in targets.build([proband, parental], core_n=3, target_n=50)}
    assert set(rows) == {"A", "B", "C"}
    assert rows["B"].score_rank == 2
    assert rows["B"].term_sets == ("proband-only", "with-parental")


def test_mechanism_genes_are_found_through_the_ancestor_closure():
    """Term-driven, not a gene list: a child term is picked up by its root."""
    ontology = Ontology(
        concepts={
            "HP:0002916": Concept("HP:0002916", "segregation"),
            "HP:0200024": Concept("HP:0200024", "PCS", parents=frozenset({"HP:0002916"})),
            "HP:0000001": Concept("HP:0000001", "all"),
        }
    )
    corpus = Corpus(
        genes={
            "BUB": GeneAnnotation("BUB", frozenset({"HP:0200024"})),
            "OTHER": GeneAnnotation("OTHER", frozenset({"HP:0000001"})),
        },
        direct_counts={},
    )
    found = targets.mechanism_genes(corpus, ontology, roots=("HP:0002916",))
    assert found == frozenset({"BUB"})


def test_the_uncurated_blind_spot_is_counted_not_assumed():
    corpus = Corpus(genes={"A": GeneAnnotation("A", frozenset())}, direct_counts={})
    assert targets.uncurated_count(corpus, ["A", "B", "C"]) == (2, 3)


# --- the decoy null -------------------------------------------------------------------

FEATURES = [
    targets.GeneFeature(f"D{i}", coding_length=500 * (i % 4), exon_count=i % 8)
    for i in range(1, 60)
]


def test_a_decoy_is_never_a_target_and_never_drawn_twice():
    rows = targets.build([_ranking("proband-only", [_score("D1", 1, 0.9), _score("D2", 2, 0.8)])])
    decoys = targets.draw_decoys(rows, FEATURES, seed=7)
    names = [d.symbol for d in decoys]
    assert len(names) == len(set(names))
    assert not set(names) & {"D1", "D2"}


def test_a_decoy_sharing_the_phenotype_is_excluded():
    rows = targets.build([_ranking("proband-only", [_score("D1", 1, 0.9)])])
    decoys = targets.draw_decoys(rows, FEATURES, seed=7, excluded=["D5", "D6", "D7"])
    assert not {d.symbol for d in decoys} & {"D5", "D6", "D7"}


def test_the_draw_is_reproducible_from_its_seed_and_only_from_it():
    rows = targets.build(
        [_ranking("proband-only", [_score(f"D{i}", i, 1.0 / i) for i in range(1, 6)])]
    )
    first = targets.draw_decoys(rows, FEATURES, seed=11)
    assert first == targets.draw_decoys(rows, FEATURES, seed=11)
    assert first != targets.draw_decoys(rows, FEATURES, seed=12)


def test_a_decoy_is_matched_on_gene_shape():
    rows = targets.build([_ranking("proband-only", [_score("D8", 1, 0.9)])])
    shape = next(f for f in FEATURES if f.symbol == "D8")
    decoy = targets.draw_decoys(rows, FEATURES, seed=3)[0]
    assert abs(decoy.coding_length - shape.coding_length) <= 500
    assert abs(decoy.exon_count - shape.exon_count) <= 5


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_every_target_with_a_known_shape_gets_a_decoy(seed):
    rows = targets.build(
        [_ranking("proband-only", [_score(f"D{i}", i, 1.0 / i) for i in range(1, 21)])]
    )
    assert len(targets.draw_decoys(rows, FEATURES, seed=seed)) == len(rows)
