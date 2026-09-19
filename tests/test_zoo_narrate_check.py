"""The citation checker: what it counts, and what it refuses to let through.

``P4-7`` is a number this module produces, so these tests pin the three rules separately —
a failure has to say *which* rule broke, otherwise the claim's verdict is a guess.
"""

from __future__ import annotations

import pytest

from mva.zoo.narrate_check import check_narrative, split_sentences

ROWS = [
    {"id": "cov.fraction", "label": "share scored", "text": "27.0% of all allele records"},
    {"id": "dist.p90", "label": "p90", "text": "the p90 quantile of this lane's scores is 0.21"},
    {
        "id": "pair.rank",
        "label": "the confirmed pair's rank",
        "text": "this lane did not score both halves of the confirmed pair",
    },
    {"id": "pair.gene", "label": "gene", "text": "the confirmed pair sits in the gene `BUB1B`"},
]


class TestSplitting:
    def test_an_empty_reply_has_no_sentences(self):
        assert split_sentences("   \n\n ") == []

    def test_a_full_stop_ends_a_sentence_and_the_citation_stays_with_it(self):
        pieces = split_sentences("One thing [cov.fraction]. Another [dist.p90].")
        assert pieces == ["One thing [cov.fraction].", "Another [dist.p90]."]

    def test_a_bulleted_reply_is_flattened_rather_than_rejected(self):
        # A model that answers in a list has still written sentences; the checker's job is to
        # count citations, not to police formatting.
        assert split_sentences("- One [cov.fraction].\n- Two [dist.p90].") == [
            "One [cov.fraction].",
            "Two [dist.p90].",
        ]


class TestCitationRule:
    def test_every_sentence_cited_is_a_zero_uncited_rate(self):
        result = check_narrative(
            "The lane scored about a quarter of the records [cov.fraction]. "
            "Most scores sit well below its p90 [dist.p90].",
            ROWS,
        )
        assert (result.n_sentences, result.cited_sentences, result.uncited_sentences) == (2, 2, 0)
        assert result.uncited_rate == 0.0
        assert result.ok

    def test_an_uncited_sentence_is_counted_not_ignored(self):
        result = check_narrative(
            "The lane scored about a quarter of the records [cov.fraction]. "
            "This one rests on nothing at all.",
            ROWS,
        )
        assert result.uncited_sentences == 1
        assert result.uncited_rate == pytest.approx(0.5)
        assert not result.ok

    def test_a_citation_to_a_row_that_was_never_sent_does_not_count_as_cited(self):
        result = check_narrative("A claim [pair.percentile].", ROWS)
        assert result.unknown_ids == ("pair.percentile",)
        assert result.cited_sentences == 0

    def test_an_empty_reply_is_fully_uncited_rather_than_vacuously_perfect(self):
        result = check_narrative("", ROWS)
        assert result.uncited_rate == 1.0
        assert not result.ok


class TestNewNameRule:
    def test_a_gene_the_rows_name_is_allowed(self):
        result = check_narrative("The pair sits in BUB1B [pair.gene].", ROWS)
        assert result.new_names == ()

    def test_a_gene_the_rows_never_named_is_reported(self):
        # This is risk R3: the model knows the answer from training text. It may not use it.
        result = check_narrative("This looks like CEP57 to me [pair.gene].", ROWS)
        assert result.new_names == ("CEP57",)
        assert not result.ok

    def test_a_disease_the_rows_never_named_is_reported(self):
        result = check_narrative("This is mosaic variegated aneuploidy [pair.rank].", ROWS)
        assert "mosaic variegated aneuploidy" in result.new_names

    def test_a_row_id_is_never_mistaken_for_a_gene_symbol(self):
        result = check_narrative("A point [DIST.P90].", [{"id": "DIST.P90", "text": "x"}])
        assert result.new_names == ()

    def test_common_upper_case_words_are_not_gene_symbols(self):
        result = check_narrative("The HPO terms and the JSON say so [cov.fraction].", ROWS)
        assert result.new_names == ()


class TestLengthRule:
    def test_a_reply_inside_the_budget_passes(self):
        result = check_narrative("Short [cov.fraction].", ROWS, max_words=200)
        assert not result.over_length

    def test_a_reply_over_the_budget_is_flagged(self):
        text = " ".join(["word"] * 210) + " [cov.fraction]."
        result = check_narrative(text, ROWS, max_words=200)
        assert result.over_length
        assert not result.ok

    def test_no_budget_means_no_length_check(self):
        text = " ".join(["word"] * 500) + " [cov.fraction]."
        assert not check_narrative(text, ROWS).over_length


class TestSummary:
    def test_the_summary_is_plain_json(self):
        summary = check_narrative("A [cov.fraction].", ROWS, max_words=200).summary()
        assert summary["sentences"] == 1
        assert summary["uncited_rate"] == 0.0
        assert summary["ok"] is True
        assert isinstance(summary["unknown_ids"], list)

    def test_rows_may_be_given_as_a_plain_mapping(self):
        result = check_narrative("A [x.y].", {"x.y": "some fact"})
        assert result.cited_sentences == 1
