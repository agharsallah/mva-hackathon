"""The mechanism card, parsed - and the query strings it produces.

Every assertion runs against ``tests/fixtures/track2/card.json``, an invented case whose
gene, disease, pathway and directions differ from the repository's real card in every
field. A test that passed only because a value was hard-coded would fail here.
"""

from __future__ import annotations

import json

import pytest

from mva.drugs import mechanism
from mva.drugs.queries import literature_queries, trial_queries
from test_drugs_support import FIXTURES

CARD = FIXTURES / "card.json"


@pytest.fixture
def card() -> mechanism.MechanismCard:
    return mechanism.load(CARD)


class TestCard:
    def test_identity_comes_off_the_card(self, card: mechanism.MechanismCard) -> None:
        assert card.version == 7
        assert card.gene_symbol == "GENEA"
        assert card.uniprot == "P00001"
        assert card.ensembl_gene_id == "ENSG00000000001"

    def test_disease_query_drops_the_parenthetical_gloss(
        self, card: mechanism.MechanismCard
    ) -> None:
        assert card.disease_name == "Fictional wobble syndrome 3 (FWS3)"
        assert card.disease_query == "Fictional wobble syndrome 3"

    def test_tumour_context_is_one_searchable_term(self, card: mechanism.MechanismCard) -> None:
        assert card.tumour_context == "testoma"

    def test_pathway_is_trimmed_to_its_head_phrase(self, card: mechanism.MechanismCard) -> None:
        assert card.pathway == "widget assembly checkpoint"

    def test_seed_targets_are_the_union_in_card_order_deduped(
        self, card: mechanism.MechanismCard
    ) -> None:
        assert card.seed_targets == ("GENEA", "GENEB", "GENEC")

    def test_a_symbol_names_every_direction_that_seeded_it(
        self, card: mechanism.MechanismCard
    ) -> None:
        assert card.directions_for("GENEB") == ("X1", "X2")
        assert card.directions_for("GENEA") == ("X1",)
        assert card.directions_for("NOTINCARD") == ()

    def test_cited_pmids_are_kept_in_card_order(self, card: mechanism.MechanismCard) -> None:
        assert card.literature_pmids == ("90000111", "90000222")

    def test_a_non_object_payload_is_refused_not_guessed(self, tmp_path) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        with pytest.raises(TypeError):
            mechanism.load(bad)

    def test_a_card_with_no_directions_yields_no_seeds(self, tmp_path) -> None:
        empty = tmp_path / "empty.json"
        empty.write_text(json.dumps({"version": 1, "gene": {"symbol": "X"}}), encoding="utf-8")
        assert mechanism.load(empty).seed_targets == ()


class TestQueryPhrases:
    def test_a_slash_becomes_an_or(self, card: mechanism.MechanismCard) -> None:
        first, second = card.directions
        assert first.query_phrase == "(widget reinforcement OR wobble reduction)"
        assert second.query_phrase == "(wobble-selective stress)"

    def test_the_anchor_skips_the_generic_disease_noun(self, card: mechanism.MechanismCard) -> None:
        # "Fictional wobble syndrome 3" -> "wobble", not "syndrome" and not "3".
        terms = [q.term for q in literature_queries(card)]
        assert all(term.endswith("wobble") or "AND drug" in term for term in terms[1:])

    def test_three_query_families_come_out_of_one_card(self, card: mechanism.MechanismCard) -> None:
        queries = literature_queries(card)
        assert [q.family for q in queries] == ["gene", "pathway", "direction", "direction"]
        assert queries[0].term == "GENEA AND (repurposing OR inhibitor OR wobble)"
        assert queries[1].term == "widget assembly checkpoint AND drug"

    def test_trial_queries_are_the_disease_plus_one_per_approved_drug(
        self, card: mechanism.MechanismCard
    ) -> None:
        from mva.drugs.candidates import Candidate

        approved = [
            Candidate("WIDGETONE", "CHEMBL0001", "GENEA", "seed", approved=True),
            Candidate("widgetone", "CHEMBL0001", "GENEB", "seed", approved=True),
        ]
        queries = trial_queries(card, approved)
        assert [q.family for q in queries] == ["disease", "candidate", "candidate"]
        assert queries[0].text == "cond=Fictional wobble syndrome 3"
        # Both spellings are asked: the dedup key is case-folded but the *name* is not,
        # and a registry search is case-insensitive anyway.
        assert queries[1].text == "cond=testoma intr=WIDGETONE"
