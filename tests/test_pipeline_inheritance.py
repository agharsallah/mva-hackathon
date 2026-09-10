"""The mode-of-inheritance factor: a pre-registered prior, and its off switch.

The switch is the load-bearing part. The plan promises every ranking that uses the factor
is reported again without it, and that promise is only keepable if turning it off really
returns every gene to 1.0.
"""

import pytest

from mva.pipeline import inheritance as inh


def _gene(**fields) -> inh.GeneInheritance:
    base = dict(symbol="G", modes=frozenset(), disease_terms=frozenset())
    return inh.GeneInheritance(**(base | fields))


def test_a_recessive_gene_with_curated_prenatal_loss_is_up_weighted():
    gene = _gene(
        modes=frozenset({inh.AUTOSOMAL_RECESSIVE}), disease_terms=frozenset({"HP:0005268"})
    )
    assert inh.factor(gene) == inh.RECESSIVE_WITH_LOSS


def test_a_plain_recessive_gene_is_left_alone():
    assert inh.factor(_gene(modes=frozenset({inh.AUTOSOMAL_RECESSIVE}))) == inh.RECESSIVE


def test_a_dominant_only_gene_is_down_weighted():
    assert inh.factor(_gene(modes=frozenset({inh.AUTOSOMAL_DOMINANT}))) == inh.DOMINANT_ONLY


def test_a_gene_with_both_modes_is_not_treated_as_dominant_only():
    gene = _gene(modes=frozenset({inh.AUTOSOMAL_DOMINANT, inh.AUTOSOMAL_RECESSIVE}))
    assert inh.factor(gene) == inh.RECESSIVE


def test_an_uncurated_gene_gets_no_prior_rather_than_a_penalty():
    """Missing knowledge is not negative evidence."""
    assert inh.factor(_gene()) == inh.UNKNOWN


@pytest.mark.parametrize(
    "modes",
    [
        frozenset({inh.AUTOSOMAL_RECESSIVE}),
        frozenset({inh.AUTOSOMAL_DOMINANT}),
        frozenset({inh.X_LINKED_RECESSIVE}),
    ],
)
def test_switching_the_family_history_off_returns_every_gene_to_one(modes):
    gene = _gene(modes=modes, disease_terms=frozenset({"HP:0200067"}))
    assert inh.factor(gene, family_history_of_loss=False) == 1.0


def test_every_factor_carries_a_stated_reason():
    gene = _gene(
        modes=frozenset({inh.AUTOSOMAL_RECESSIVE}), disease_terms=frozenset({"HP:0003826"})
    )
    sentence = inh.explain(gene)
    assert "x1.5" in sentence and "recessive" in sentence and "birth" in sentence


def test_factors_returns_the_mapping_the_pair_ranker_consumes():
    genes = [
        _gene(symbol="A", modes=frozenset({inh.AUTOSOMAL_RECESSIVE})),
        _gene(symbol="B", modes=frozenset({inh.AUTOSOMAL_DOMINANT})),
    ]
    assert inh.factors(genes) == {"A": 1.0, "B": 0.5}
