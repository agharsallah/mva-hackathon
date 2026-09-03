"""Tests for the similarity rollup, the genome-wide ranking, and the gene prior.

Same synthetic fixtures as ``test_phenotype_ontology.py``: six annotated genes over a
twenty-term graph, small enough that every expected ordering is one a reader can derive by
looking at the fixture rather than by trusting the code that produced it.

The fixture is rigged so BUB1B is the right answer, because the property under test is the
one the real run depends on — a gene named by the query terms outranks a gene that merely
shares an ancestor with them.
"""

import math
from pathlib import Path

import pytest

from mva.phenotype import associations, ontology, prior, prioritise, similarity, terms

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def graph() -> ontology.Ontology:
    scored = ontology.parse_obo(FIXTURES / "mini_hpo.obo")
    corpus = associations.parse_genes_to_phenotype(FIXTURES / "mini_genes_to_phenotype.txt", scored)
    return corpus.apply_to(scored)


@pytest.fixture
def corpus(graph: ontology.Ontology) -> associations.Corpus:
    return associations.parse_genes_to_phenotype(FIXTURES / "mini_genes_to_phenotype.txt", graph)


def a_term_set(name: str, *ids: str) -> terms.TermSet:
    """A term set built from bare ids, for tests that do not need the real labels."""
    return terms.TermSet(name, tuple(terms.Term(i, i, "fixture") for i in ids), "fixture")


# ── one term against one gene ────────────────────────────────────────────────────────


def test_the_best_match_is_the_strongest_pairing_not_the_first(
    graph: ontology.Ontology,
) -> None:
    match = similarity.best_match("HP:0002859", ["HP:0004322", "HP:0002667", "HP:0002859"], graph)
    assert match.gene_term == "HP:0002859"
    assert match.common_ancestor == "HP:0002859"


def test_a_term_with_nothing_informative_in_common_reports_no_match(
    graph: ontology.Ontology,
) -> None:
    """They still share the root, but the root carries no information, so it is not a match."""
    match = similarity.best_match("HP:0001622", ["HP:0002859"], graph)
    assert not match.matched


# ── set against set ──────────────────────────────────────────────────────────────────


def test_an_exact_match_on_every_term_normalises_to_one(graph: ontology.Ontology) -> None:
    """The ceiling is the query set scored against itself, so identity must reach it."""
    query = ["HP:0002859", "HP:0004322"]
    assert similarity.compare(query, query, graph).normalised == pytest.approx(1.0)


def test_an_empty_side_scores_nothing_rather_than_raising(graph: ontology.Ontology) -> None:
    """A genome-wide run reaches genes with no usable annotation; it must not die there."""
    assert similarity.compare([], ["HP:0002859"], graph) is similarity.NO_MATCH
    assert similarity.compare(["HP:0002859"], [], graph) is similarity.NO_MATCH


def test_forward_and_reverse_differ_when_the_gene_is_broadly_annotated(
    graph: ontology.Ontology,
) -> None:
    """Forward asks whether the child is explained; reverse punishes a big annotation list.

    Both are reported because either alone is misleading, and the gap between them is a
    fact about how heavily the gene is curated rather than about the child.
    """
    result = similarity.compare(["HP:0002859"], ["HP:0002859", "HP:0001622"], graph)
    assert result.forward > result.reverse
    assert result.reverse < result.forward
    assert result.symmetric == pytest.approx((result.forward + result.reverse) / 2)


def test_the_normalised_score_is_bounded_at_one(graph: ontology.Ontology) -> None:
    """A gene annotated more rarely than the query can out-score the query's own ceiling."""
    result = similarity.compare(["HP:0002664"], ["HP:0002859"], graph)
    assert 0.0 <= result.normalised <= 1.0


def test_the_breakdown_names_which_term_matched_through_which_ancestor(
    graph: ontology.Ontology,
) -> None:
    """A bare float cannot be argued with, and the register refuses an unarguable number."""
    result = similarity.compare(["HP:0002859", "HP:0001622"], ["HP:0002667"], graph)
    best = result.best
    assert best is not None
    assert best.query_term == "HP:0002859"
    assert best.common_ancestor == "HP:0002664"
    assert result.matched_terms == ("HP:0002859",)


def test_the_optimal_score_is_the_mean_information_content_of_the_query(
    graph: ontology.Ontology,
) -> None:
    query = ["HP:0002859", "HP:0002664"]
    expected = (graph.ic("HP:0002859") + graph.ic("HP:0002664")) / 2
    assert similarity.optimal_score(query, graph) == pytest.approx(expected)


# ── the ranking ──────────────────────────────────────────────────────────────────────


def test_the_gene_named_by_the_query_outranks_one_that_shares_an_ancestor(
    graph: ontology.Ontology, corpus: associations.Corpus
) -> None:
    """The property the whole exercise rests on, on a fixture rigged so the answer is known."""
    ranking = prioritise.rank_genes(a_term_set("t", "HP:0002859", "HP:0004322"), corpus, graph)
    assert ranking.scores[0].symbol == "BUB1B"
    assert ranking.rank_of("BUB1B") == 1
    assert (ranking.rank_of("TP53") or 0) > 1


def test_a_gene_with_no_shared_ancestor_is_left_out_of_the_ranking(
    graph: ontology.Ontology, corpus: associations.Corpus
) -> None:
    """It scored zero. Ordering zeroes against each other would be ordering noise."""
    ranking = prioritise.rank_genes(a_term_set("t", "HP:0002859"), corpus, graph)
    assert ranking.rank_of("WIDEGENE") is None


def test_the_population_a_rank_is_quoted_against_counts_every_gene_considered(
    graph: ontology.Ontology, corpus: associations.Corpus
) -> None:
    """ "Rank 1 of 6" is honest; "rank 1 of 3" silently drops the genes it beat."""
    ranking = prioritise.rank_genes(a_term_set("t", "HP:0002859"), corpus, graph)
    assert ranking.considered == len(corpus) == 6
    assert len(ranking) < ranking.considered


def test_an_unrankable_gene_is_absent_rather_than_ranked_last(
    graph: ontology.Ontology, corpus: associations.Corpus
) -> None:
    """Missing curation is missing knowledge, not evidence against the gene."""
    ranking = prioritise.rank_genes(a_term_set("t", "HP:0002859"), corpus, graph)
    assert ranking.rank_of("NOT_A_GENE") is None
    assert ranking.by_symbol("NOT_A_GENE") is None


def test_ties_are_broken_by_symbol_so_two_runs_agree(
    graph: ontology.Ontology, corpus: associations.Corpus
) -> None:
    ranking = prioritise.rank_genes(a_term_set("t", "HP:0002859"), corpus, graph)
    tied = [s.symbol for s in ranking.scores if s.score == ranking.scores[-1].score]
    assert tied == sorted(tied)


def test_an_unresolvable_query_term_is_reported_not_silently_dropped(
    graph: ontology.Ontology, corpus: associations.Corpus
) -> None:
    """A ranking over seven terms while claiming eight is the failure this prevents."""
    ranking = prioritise.rank_genes(a_term_set("t", "HP:0002859", "HP:9999995"), corpus, graph)
    assert ranking.unresolved == ("HP:9999995",)


def test_a_retired_query_term_is_resolved_and_scores(
    graph: ontology.Ontology, corpus: associations.Corpus
) -> None:
    """Querying the retired id must give the same ranking as querying its replacement."""
    retired = prioritise.rank_genes(a_term_set("t", "HP:9999996"), corpus, graph)
    live = prioritise.rank_genes(a_term_set("t", "HP:0002859"), corpus, graph)
    assert retired.unresolved == ()
    assert [s.symbol for s in retired.scores] == [s.symbol for s in live.scores]


def test_lookup_is_case_insensitive(graph: ontology.Ontology, corpus: associations.Corpus) -> None:
    ranking = prioritise.rank_genes(a_term_set("t", "HP:0002859"), corpus, graph)
    assert ranking.rank_of("bub1b") == ranking.rank_of("BUB1B") is not None


# ── the with/without-parental delta ──────────────────────────────────────────────────


def test_the_delta_reports_movement_between_two_term_sets(
    graph: ontology.Ontology, corpus: associations.Corpus
) -> None:
    """The roadmap's open question about the parental term, answered as a number."""
    with_parental = prioritise.rank_genes(
        a_term_set("with", "HP:0002667", "HP:0200067"), corpus, graph
    )
    without = prioritise.rank_genes(a_term_set("without", "HP:0002667"), corpus, graph)
    moves = prioritise.delta(with_parental, without, ("BUB1B", "TRIP13"))
    assert {move.symbol for move in moves} == {"BUB1B", "TRIP13"}
    assert all(move.before is not None or move.after is not None for move in moves)


def test_a_gene_missing_from_one_side_reports_no_movement(
    graph: ontology.Ontology, corpus: associations.Corpus
) -> None:
    """None is not "moved infinitely far"; it is "this side has nothing to say"."""
    ranking = prioritise.rank_genes(a_term_set("t", "HP:0002859"), corpus, graph)
    moves = prioritise.delta(ranking, ranking, ("WIDEGENE",))
    assert moves[0].moved is None


# ── the gene prior ───────────────────────────────────────────────────────────────────


def test_the_multiplier_is_one_plus_strength_times_the_score(
    graph: ontology.Ontology, corpus: associations.Corpus
) -> None:
    ranking = prioritise.rank_genes(a_term_set("t", "HP:0002859", "HP:0004322"), corpus, graph)
    top = ranking.scores[0]
    assert prior.gene_prior(ranking)[top.symbol] == pytest.approx(
        1.0 + prior.DEFAULT_STRENGTH * top.score
    )


def test_only_a_gene_curated_to_exactly_the_query_reaches_the_full_multiplier(
    graph: ontology.Ontology, corpus: associations.Corpus
) -> None:
    """RETIRED carries one term and the query is that term, so nothing is left unexplained.

    BUB1B carries the same term plus three others, and the reverse direction charges it for
    them - which is the documented behaviour, not a defect. A gene cannot reach the ceiling
    merely by containing the query.
    """
    ranking = prioritise.rank_genes(a_term_set("t", "HP:0002859"), corpus, graph)
    priors = prior.gene_prior(ranking)
    assert priors["RETIRED"] == pytest.approx(1.0 + prior.DEFAULT_STRENGTH)
    assert priors["BUB1B"] < priors["RETIRED"]


def test_a_gene_outside_the_prior_falls_back_to_neutral(
    graph: ontology.Ontology, corpus: associations.Corpus
) -> None:
    """`rank_pairs` defaults a missing gene to 1.0, so absence must mean "no signal"."""
    ranking = prioritise.rank_genes(a_term_set("t", "HP:0002859"), corpus, graph)
    assert "WIDEGENE" not in prior.gene_prior(ranking)


def test_zero_strength_disables_the_mechanism_entirely(
    graph: ontology.Ontology, corpus: associations.Corpus
) -> None:
    """A knob that can be turned off is defensible at N=1; a fitted transform is not."""
    ranking = prioritise.rank_genes(a_term_set("t", "HP:0002859"), corpus, graph)
    assert set(prior.gene_prior(ranking, strength=0.0).values()) == {1.0}


def test_the_prior_is_monotone_in_the_score(
    graph: ontology.Ontology, corpus: associations.Corpus
) -> None:
    """The ordering the phenotype produced has to survive the mapping into a multiplier."""
    ranking = prioritise.rank_genes(a_term_set("t", "HP:0002859", "HP:0004322"), corpus, graph)
    values = [prior.gene_prior(ranking)[s.symbol] for s in ranking.scores]
    assert values == sorted(values, reverse=True)


def test_the_prior_can_be_limited_to_the_top_genes(
    graph: ontology.Ontology, corpus: associations.Corpus
) -> None:
    ranking = prioritise.rank_genes(a_term_set("t", "HP:0002859", "HP:0004322"), corpus, graph)
    assert list(prior.gene_prior(ranking, limit=1)) == ["BUB1B"]


def test_a_negative_strength_is_refused(
    graph: ontology.Ontology, corpus: associations.Corpus
) -> None:
    ranking = prioritise.rank_genes(a_term_set("t", "HP:0002859"), corpus, graph)
    with pytest.raises(ValueError, match="must not be negative"):
        prior.gene_prior(ranking, strength=-1.0)


def test_the_explanation_names_the_rank_the_population_and_the_match(
    graph: ontology.Ontology, corpus: associations.Corpus
) -> None:
    """Written for the evidence register, which refuses an observation with no source."""
    ranking = prioritise.rank_genes(a_term_set("t", "HP:0002859", "HP:0004322"), corpus, graph)
    sentence = prior.explain(ranking, "BUB1B")
    assert "ranks 1 of 6" in sentence
    assert "HP:0002859" in sentence


def test_the_explanation_of_an_uncurated_gene_says_so_rather_than_scoring_it(
    graph: ontology.Ontology, corpus: associations.Corpus
) -> None:
    ranking = prioritise.rank_genes(a_term_set("t", "HP:0002859"), corpus, graph)
    assert "absence of knowledge" in prior.explain(ranking, "WIDEGENE")


# ── the real term sets against the fixture graph ─────────────────────────────────────


def test_every_delivered_term_exists_in_a_release_shaped_like_the_fixture() -> None:
    """The fixture carries all eight real ids, so a typo in `terms.py` fails here."""
    graph = ontology.parse_obo(FIXTURES / "mini_hpo.obo")
    assert [t for t in terms.WITH_PARENTAL.ids if graph.resolve(t) is None] == []


def test_dropping_the_parental_term_changes_the_query_and_nothing_else() -> None:
    assert terms.WITH_PARENTAL.id_set - terms.PROBAND_ONLY.id_set == {terms.PARENTAL_TERM}


def test_information_content_rises_with_specificity_on_the_real_terms(
    graph: ontology.Ontology,
) -> None:
    """Sanity on the shape the ranking depends on, using real ids from the fixture."""
    assert graph.ic("HP:0002859") > graph.ic("HP:0002664")
    assert graph.ic("HP:0002664") > 0.0
    assert math.isfinite(graph.ic("HP:0002859"))
