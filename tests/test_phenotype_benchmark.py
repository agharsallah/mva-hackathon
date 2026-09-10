"""The held-out recall benchmark: what makes the target-set cutoff defensible.

The load-bearing property is the held-out rule. If a disease's own curated annotation of
its gene is still in the corpus when that disease is ranked, the benchmark measures a
lookup and reports a recall near 1.0 — the failure mode that would make the whole curve a
lie. The tests below pin the removal, and the honesty of what it leaves behind.
"""

import random

from mva.phenotype import benchmark as bm
from mva.phenotype.associations import Corpus, GeneAnnotation
from mva.phenotype.ontology import Concept, Ontology

TSV = """ncbi_gene_id\tgene_symbol\thpo_id\thpo_name\tfrequency\tdisease_id
1\tAAA\tHP:0000001\tall\t-\tOMIM:1
1\tAAA\tHP:0000007\tAR\t-\tOMIM:1
2\tBBB\tHP:0000002\ttwo\t-\tOMIM:2
"""


def _ontology() -> Ontology:
    return Ontology(
        concepts={
            "HP:0000001": Concept("HP:0000001", "all"),
            "HP:0000002": Concept("HP:0000002", "two", parents=frozenset({"HP:0000001"})),
            "HP:0000003": Concept("HP:0000003", "three", parents=frozenset({"HP:0000002"})),
        }
    )


def test_diseases_are_grouped_with_their_gene_and_inheritance(tmp_path):
    path = tmp_path / "g2p.txt"
    path.write_text(TSV, encoding="utf-8")
    diseases = {d.disease_id: d for d in bm.read_diseases(path)}
    assert diseases["OMIM:1"].gene_symbol == "AAA"
    assert diseases["OMIM:1"].recessive
    assert not diseases["OMIM:2"].recessive


def test_the_population_excludes_diseases_too_small_to_subsample():
    """A query built by repeating terms would be easier than a real one."""
    small = bm.Disease("OMIM:1", "A", frozenset({"HP:1", bm.RECESSIVE}), recessive=True)
    big = bm.Disease("OMIM:2", "B", frozenset({f"HP:{i}" for i in range(9)}), recessive=True)
    assert bm.population([small, big]) == (big,)


def test_the_inheritance_term_is_not_a_phenotype_and_never_becomes_a_query_term():
    terms = [bm.RECESSIVE, "HP:0000002", "HP:0000003"]
    query = bm.degrade(
        terms, _ontology(), random.Random(1), size=3, imprecision=(0, 0), noise=(0, 0)
    )
    assert bm.RECESSIVE not in query


def test_degradation_blurs_a_term_upward_and_adds_noise():
    query = bm.degrade(
        ["HP:0000003"],
        _ontology(),
        random.Random(2),
        size=1,
        imprecision=(1, 1),
        noise=(1, 1),
        vocabulary=("HP:0000001",),
    )
    assert "HP:0000003" not in query, "the term should have been replaced by its parent"
    assert "HP:0000002" in query
    assert len(query) == 2, "one blurred term plus one noise term"


def test_holding_out_a_disease_removes_only_its_own_contribution():
    corpus = Corpus(
        genes={"AAA": GeneAnnotation("AAA", frozenset({"HP:1", "HP:2", "HP:3"}))},
        direct_counts={},
    )
    disease = bm.Disease("OMIM:1", "AAA", frozenset({"HP:1", "HP:2"}), recessive=True)
    held = bm._held_out(corpus, disease)
    assert held.genes["AAA"].terms == frozenset({"HP:3"})
    assert corpus.genes["AAA"].terms == frozenset({"HP:1", "HP:2", "HP:3"}), "input untouched"


def test_a_gene_described_only_by_the_held_out_disease_leaves_the_corpus():
    """Recorded as a miss, not hidden: a curation-driven ranker really cannot find it."""
    corpus = Corpus(genes={"AAA": GeneAnnotation("AAA", frozenset({"HP:1"}))}, direct_counts={})
    disease = bm.Disease("OMIM:1", "AAA", frozenset({"HP:1"}), recessive=True)
    assert "AAA" not in bm._held_out(corpus, disease).genes


def test_recall_counts_a_missing_rank_as_a_miss_at_every_n():
    result = bm.Result(
        outcomes=(
            bm.Outcome("OMIM:1", "A", rank=3, query=()),
            bm.Outcome("OMIM:2", "B", rank=None, query=()),
        ),
        seed=1,
    )
    assert result.recall_at(1) == 0.0
    assert result.recall_at(10) == 0.5
    assert result.unrankable == 1
    assert result.median_rank == 3


def test_the_bootstrap_interval_brackets_the_estimate_and_is_reproducible():
    result = bm.Result(
        outcomes=tuple(
            bm.Outcome(f"D{i}", "G", rank=1 if i % 2 else 500, query=()) for i in range(40)
        ),
        seed=5,
    )
    low, high = result.interval(10, resamples=200)
    assert low <= result.recall_at(10) <= high
    assert (low, high) == result.interval(10, resamples=200)


def test_a_run_is_reproducible_from_its_seed():
    ontology = _ontology()
    corpus = Corpus(
        genes={
            "AAA": GeneAnnotation("AAA", frozenset({"HP:0000002", "HP:0000003"})),
            "BBB": GeneAnnotation("BBB", frozenset({"HP:0000001"})),
        },
        direct_counts={},
    )
    ontology = corpus.apply_to(ontology)
    diseases = [
        bm.Disease("OMIM:1", "AAA", frozenset({"HP:0000002", "HP:0000003"}), recessive=True)
    ]
    first = bm.run(diseases, corpus, ontology, seed=3, size=2, imprecision=(0, 0), noise=(0, 0))
    second = bm.run(diseases, corpus, ontology, seed=3, size=2, imprecision=(0, 0), noise=(0, 0))
    assert first.outcomes == second.outcomes
