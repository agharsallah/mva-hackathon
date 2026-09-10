"""The uncurated tier: a gene with no phenotype of its own, scored by its neighbours.

This tier exists to name a blind spot, not to fill it. The tests pin that a curated gene
never enters it, that only edges STRING itself calls high-confidence count, and that a
gene wired to several seeds outranks one wired to a single seed.
"""

from mva.phenotype import network


def _edges(*rows):
    return [network.Edge(a, b, s) for a, b, s in rows]


def test_only_high_confidence_edges_count():
    found = network.neighbours(_edges(("SEED", "WEAK", 300), ("SEED", "STRONG", 900)), ["SEED"])
    assert [n.symbol for n in found] == ["STRONG"]


def test_a_gene_with_a_phenotype_score_never_enters_the_uncurated_tier():
    found = network.neighbours(
        _edges(("SEED", "CURATED", 900), ("SEED", "UNKNOWN", 900)),
        ["SEED"],
        exclude=["CURATED"],
    )
    assert [n.symbol for n in found] == ["UNKNOWN"]


def test_a_seed_is_not_its_own_neighbour():
    found = network.neighbours(_edges(("SEED_A", "SEED_B", 900)), ["SEED_A", "SEED_B"])
    assert found == ()


def test_ties_to_several_seeds_outrank_one_strong_tie():
    found = network.neighbours(
        _edges(
            ("SEED_A", "WIDE", 800),
            ("SEED_B", "WIDE", 800),
            ("SEED_A", "NARROW", 1000),
        ),
        ["SEED_A", "SEED_B"],
    )
    assert [n.symbol for n in found] == ["WIDE", "NARROW"]
    assert found[0].degree == 2
    assert found[0].partners == ("SEED_A", "SEED_B")


def test_proximity_is_scaled_by_the_best_possible_tie_to_every_seed():
    found = network.neighbours(_edges(("SEED", "G", 1000)), ["SEED"])
    assert found[0].proximity == 1.0


def test_string_rows_are_rescaled_to_stringers_own_0_1000_score():
    edges = network.parse_string_network(
        [{"preferredName_A": "A", "preferredName_B": "B", "score": 0.9}]
    )
    assert edges == (network.Edge("A", "B", 900),)


def test_a_self_edge_or_a_nameless_row_is_dropped():
    rows = [
        {"preferredName_A": "A", "preferredName_B": "A", "score": 0.9},
        {"preferredName_A": "", "preferredName_B": "B", "score": 0.9},
        {"preferredName_A": "A", "preferredName_B": "B", "score": "nonsense"},
    ]
    assert network.parse_string_network(rows) == ()


def test_the_request_is_printable_so_the_run_can_be_repeated():
    url = network.network_url(["BUB1B", "CENPE"])
    assert "identifiers=BUB1B%0dCENPE" in url and "species=9606" in url
