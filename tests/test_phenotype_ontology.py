"""Tests for the HPO graph, the annotation corpus, and the term set.

No test here reaches the network or a real HPO release. The fixtures are a synthetic
twenty-term ontology and eleven annotation rows in ``tests/fixtures/``, sized so every
expected information content is arithmetic a reader can redo on paper — which is the only
way an assertion about ``-log(p)`` is worth anything.
"""

import math
from pathlib import Path

import pytest

from mva.phenotype import associations, ontology, terms

FIXTURES = Path(__file__).parent / "fixtures"
OBO = FIXTURES / "mini_hpo.obo"
GENES = FIXTURES / "mini_genes_to_phenotype.txt"


@pytest.fixture
def graph() -> ontology.Ontology:
    return ontology.parse_obo(OBO)


@pytest.fixture
def corpus(graph: ontology.Ontology) -> associations.Corpus:
    return associations.parse_genes_to_phenotype(GENES, graph)


@pytest.fixture
def scored(graph: ontology.Ontology, corpus: associations.Corpus) -> ontology.Ontology:
    return corpus.apply_to(graph)


# ── parsing ──────────────────────────────────────────────────────────────────────────


def test_typedef_stanzas_do_not_become_phenotype_terms(graph: ontology.Ontology) -> None:
    """A ``[Typedef]`` declares a relation, not a feature; loading it would rank on it."""
    assert "part_of" not in graph
    assert len(graph) == 19


def test_the_is_a_comment_is_stripped_from_the_parent_id(graph: ontology.Ontology) -> None:
    assert graph.parents("HP:0002859") == frozenset({"HP:0002664"})


def test_a_term_with_two_parents_keeps_both(graph: ontology.Ontology) -> None:
    """HPO is a DAG, not a tree. Keeping one parent would silently truncate the closure."""
    assert graph.parents("HP:0003202") == frozenset({"HP:0003011", "HP:0001507"})


def test_a_parent_this_release_does_not_carry_is_dropped_not_invented(tmp_path: Path) -> None:
    stanza = "[Term]\nid: HP:0000042\nname: Orphan\nis_a: HP:0000999 ! Not in this release\n"
    path = tmp_path / "hp.obo"
    path.write_text(stanza, encoding="utf-8")
    graph = ontology.parse_obo(path)
    assert graph.parents("HP:0000042") == frozenset()
    assert graph.ancestors("HP:0000042") == frozenset({"HP:0000042"})


# ── resolution ───────────────────────────────────────────────────────────────────────


def test_an_alt_id_resolves_to_its_live_term(graph: ontology.Ontology) -> None:
    assert graph.resolve("HP:9999997") == "HP:9999998"


def test_a_retired_term_resolves_to_its_replacement(graph: ontology.Ontology) -> None:
    assert graph.resolve("HP:9999996") == "HP:0002859"


def test_a_retired_term_with_no_replacement_resolves_to_nothing(graph: ontology.Ontology) -> None:
    """``None`` rather than the id itself: it cannot be placed, so it cannot be scored."""
    assert graph.resolve("HP:9999995") is None


def test_an_unknown_id_resolves_to_nothing(graph: ontology.Ontology) -> None:
    assert graph.resolve("HP:0000000") is None


# ── closure and depth ────────────────────────────────────────────────────────────────


def test_the_ancestor_closure_includes_the_term_itself(graph: ontology.Ontology) -> None:
    """Reflexive on purpose: an exact match must resolve to the term, not to its parent."""
    assert graph.ancestors("HP:0002859") == frozenset(
        {"HP:0002859", "HP:0002664", "HP:0000118", "HP:0000001"}
    )


def test_the_closure_of_a_multi_parent_term_follows_every_branch(graph: ontology.Ontology) -> None:
    assert graph.ancestors("HP:0003202") == frozenset(
        {"HP:0003202", "HP:0003011", "HP:0001507", "HP:0000118", "HP:0000001"}
    )


def test_depth_counts_the_longest_path_from_the_root(graph: ontology.Ontology) -> None:
    assert graph.depth("HP:0000001") == 0
    assert graph.depth("HP:0000118") == 1
    assert graph.depth("HP:0002664") == 2
    assert graph.depth("HP:0002859") == 3


def test_depth_of_an_unknown_term_is_negative(graph: ontology.Ontology) -> None:
    assert graph.depth("HP:0000000") == -1


# ── information content ──────────────────────────────────────────────────────────────


def test_counts_are_propagated_up_the_graph_before_the_log(scored: ontology.Ontology) -> None:
    """Six genes carry a usable term. Four of them sit under Neoplasm.

    BUB1B and RETIRED via Rhabdomyosarcoma, TRIP13 via Nephroblastoma, and TP53 which
    names Neoplasm outright. So the information content is -log(4/6). Without propagation
    it would be -log(1/6) and every internal node would look far rarer than it is.
    """
    assert scored.ic("HP:0002664") == pytest.approx(-math.log(4 / 6))


def test_a_gene_is_counted_once_per_term_not_once_per_path(
    graph: ontology.Ontology, corpus: associations.Corpus
) -> None:
    """The count is over distinct genes, so no gene may exceed the corpus size anywhere.

    Summing per-term counts up the graph instead would let a gene annotated to both a term
    and its parent contribute twice, and the tell is a closure count above the population.
    """
    counts = corpus.closure_counts(graph)
    assert counts[ontology.ROOT] == len(corpus)
    assert max(counts.values()) <= len(corpus)


def test_the_root_carries_every_gene_and_therefore_no_information(
    scored: ontology.Ontology,
) -> None:
    assert scored.ic("HP:0000001") == 0.0
    assert not math.copysign(1, scored.ic("HP:0000001")) < 0  # never "-0.0" in a report


def test_a_rarer_term_carries_more_information_than_its_parent(
    scored: ontology.Ontology,
) -> None:
    assert scored.ic("HP:0002859") == pytest.approx(-math.log(2 / 6))
    assert scored.ic("HP:0002859") > scored.ic("HP:0002664") > scored.ic(ontology.ROOT)


def test_a_term_no_gene_annotates_scores_zero_rather_than_infinity(
    scored: ontology.Ontology,
) -> None:
    """-log(0) is undefined. Reporting 0.0 cannot inflate a score; guessing would."""
    assert scored.ic("HP:0000121") == 0.0


def test_with_counts_refuses_a_meaningless_total(graph: ontology.Ontology) -> None:
    with pytest.raises(ValueError, match="must be positive"):
        graph.with_frequencies({"HP:0002859": 1}, total=0)


# ── the common ancestor ──────────────────────────────────────────────────────────────


def test_two_cancers_meet_at_neoplasm(scored: ontology.Ontology) -> None:
    term, ic = scored.most_informative_common_ancestor("HP:0002859", "HP:0002667")
    assert term == "HP:0002664"
    assert ic == pytest.approx(-math.log(4 / 6))


def test_a_term_against_itself_meets_at_itself(scored: ontology.Ontology) -> None:
    term, ic = scored.most_informative_common_ancestor("HP:0002859", "HP:0002859")
    assert term == "HP:0002859"
    assert ic == pytest.approx(-math.log(2 / 6))


def test_unrelated_terms_meet_near_the_root_and_score_nothing(scored: ontology.Ontology) -> None:
    _, ic = scored.most_informative_common_ancestor("HP:0002859", "HP:0001622")
    assert ic == 0.0


def test_the_ranked_ancestor_cache_is_cleared_when_the_corpus_changes(
    graph: ontology.Ontology, corpus: associations.Corpus
) -> None:
    """A stale ranking would silently order by the previous corpus's frequencies."""
    graph.with_frequencies({"HP:0002859": 1}, total=1)
    first = graph.ranked_ancestors("HP:0002859")
    corpus.apply_to(graph)
    assert graph.ranked_ancestors("HP:0002859") != first


# ── the annotation corpus ────────────────────────────────────────────────────────────


def test_symbols_are_uppercased_so_the_join_cannot_miss_on_case(
    corpus: associations.Corpus,
) -> None:
    assert corpus.get("bub1b") is not None
    assert "BUB1B" in corpus


def test_the_entrez_id_is_kept_for_the_hosted_cross_checks(corpus: associations.Corpus) -> None:
    annotation = corpus.get("BUB1B")
    assert annotation is not None
    assert annotation.entrez_id == "701"


def test_a_gene_whose_every_term_is_unplaceable_leaves_the_corpus(
    corpus: associations.Corpus,
) -> None:
    """NOWHERE names one retired term with no replacement, so nothing about it is usable.

    It is dropped rather than kept as an empty annotation, because an empty annotation
    still enlarges the denominator every information content is divided by - inflating the
    apparent rarity of every term in the release on the strength of a gene we know nothing
    about.
    """
    assert corpus.get("NOWHERE") is None
    assert "NOWHERE" not in corpus.symbols()


def test_a_retired_term_is_resolved_rather_than_dropped(corpus: associations.Corpus) -> None:
    retired = corpus.get("RETIRED")
    assert retired is not None
    assert retired.terms == frozenset({"HP:0002859"})


def test_the_id_column_is_found_by_shape_not_by_position(tmp_path: Path) -> None:
    """Exomiser's bundled copy swaps the term name and id columns. Both must load."""
    old_layout = (
        "#Format: entrez-gene-id<tab>entrez-gene-symbol<tab>HPO-Term-Name<tab>HPO-Term-ID\n"
        "701\tBUB1B\tRhabdomyosarcoma\tHP:0002859\n"
    )
    path = tmp_path / "g2p.txt"
    path.write_text(old_layout, encoding="utf-8")
    corpus = associations.parse_genes_to_phenotype(path)
    annotation = corpus.get("BUB1B")
    assert annotation is not None
    assert annotation.terms == frozenset({"HP:0002859"})


def test_direct_counts_count_genes_once_per_term(corpus: associations.Corpus) -> None:
    assert corpus.direct_counts["HP:0004322"] == 2  # BUB1B and CEP57
    assert corpus.direct_counts["HP:0002859"] == 2  # BUB1B and the resolved retired term
    assert len(corpus) == 6


def test_counts_from_has_one_implementation(corpus: associations.Corpus) -> None:
    assert associations.counts_from(corpus.genes) == corpus.direct_counts


# ── the declared term set ────────────────────────────────────────────────────────────


def test_the_delivered_set_is_the_eight_terms_from_the_phenotype_document() -> None:
    assert len(terms.WITH_PARENTAL) == 8
    assert terms.PARENTAL_TERM in terms.WITH_PARENTAL.id_set


def test_the_proband_set_drops_the_parental_term_and_only_that() -> None:
    assert len(terms.PROBAND_ONLY) == 7
    assert terms.PARENTAL_TERM not in terms.PROBAND_ONLY.id_set
    assert terms.PROBAND_ONLY.id_set < terms.WITH_PARENTAL.id_set


def test_every_delivered_term_is_a_well_formed_hpo_id() -> None:
    assert all(associations.TERM_PATTERN.match(term.hpo_id) for term in terms.TERMS)


def test_the_ids_are_unique() -> None:
    assert len({term.hpo_id for term in terms.TERMS}) == len(terms.TERMS)


def test_an_unknown_term_names_the_ones_that_exist() -> None:
    with pytest.raises(KeyError, match="HP:0002859"):
        terms.by_id("HP:0000000")


def test_an_unknown_term_set_names_the_ones_that_exist() -> None:
    with pytest.raises(KeyError, match="with-parental"):
        terms.term_set("nonsense")


def test_rows_with_a_placeholder_gene_symbol_are_dropped(tmp_path: Path) -> None:
    """HPO writes ``-`` where it has an NCBI id but no symbol, across several genes.

    Loading them fuses those genes into one fabricated entry whose feature list is the
    union of all of them - and a long enough feature list matches almost any query, so the
    phantom outranks real candidates. Measured in the 2026-06-23 release: 375 such rows
    spanning seven distinct gene ids.
    """
    rows = (
        "ncbi_gene_id\tgene_symbol\thpo_id\thpo_name\n"
        "3653\t-\tHP:0002859\tRhabdomyosarcoma\n"
        "7467\t-\tHP:0004322\tShort stature\n"
        "701\tBUB1B\tHP:0002859\tRhabdomyosarcoma\n"
    )
    path = tmp_path / "g2p.txt"
    path.write_text(rows, encoding="utf-8")
    corpus = associations.parse_genes_to_phenotype(path)
    assert corpus.symbols() == ("BUB1B",)
    assert corpus.get("-") is None
