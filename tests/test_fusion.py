"""Reciprocal rank fusion: the arithmetic, the inheritance rule, and the frozen hash.

Every expected score below is the published formula ``Σ w / (k + rank)`` computed by hand in
the test itself, never a number copied from a previous run of the code under test. That is
the property the ``ranx`` cross-check would have given, obtained without the dependency.
"""

from __future__ import annotations

import pytest

from mva.pipeline import fusion, fusion_freeze
from mva.pipeline.fusion import Confirmation, Pair, Route, RouteRank

LEADER = Pair("GENEA", "a1", "a2")
RUNNER = Pair("GENEB", "b1", "b2")
THIRD = Pair("GENEC", "c1", "")


def route(name: str, **kwargs) -> Route:
    return Route(name=name, unit=kwargs.pop("unit", "pair"), **kwargs)


def ranked(name: str, *pairs: tuple[Pair, int]) -> list[RouteRank]:
    return [RouteRank(route=name, pair=pair, rank=rank) for pair, rank in pairs]


class TestPair:
    def test_id_is_stable_and_carries_the_empty_partner(self):
        assert LEADER.id == "GENEA|a1|a2"
        assert THIRD.id == "GENEC|c1|"

    def test_keys_by_unit(self):
        assert LEADER.keys("pair") == ("GENEA|a1|a2",)
        assert LEADER.keys("gene") == ("GENEA",)
        assert LEADER.keys("allele") == ("a1", "a2")

    def test_single_allele_pair_has_one_allele_key(self):
        assert THIRD.keys("allele") == ("c1",)

    def test_unknown_unit_is_refused(self):
        with pytest.raises(ValueError, match="unit must be one of"):
            LEADER.keys("exon")


class TestRoute:
    def test_unknown_unit_is_refused_at_construction(self):
        with pytest.raises(ValueError, match="unit must be one of"):
            Route(name="bad", unit="exon")

    def test_negative_weight_is_refused(self):
        with pytest.raises(ValueError, match="veto"):
            Route(name="bad", unit="pair", weight=-1.0)

    def test_a_route_at_weight_zero_does_not_vote_but_still_exists(self):
        silent = Route(name="reads", unit="allele", admitted=False, weight=0.0)
        assert silent.votes is False
        assert silent.name == "reads"


class TestInherit:
    def test_a_pair_route_is_used_as_it_stands(self):
        rows = fusion.inherit(route("likelihood"), [LEADER.id, RUNNER.id], [LEADER, RUNNER, THIRD])
        assert [(r.pair.id, r.rank, r.inherited) for r in rows] == [
            ("GENEA|a1|a2", 1, False),
            ("GENEB|b1|b2", 2, False),
        ]

    def test_a_gene_rank_fans_out_to_every_pair_in_the_gene(self):
        other = Pair("GENEA", "a3", "a4")
        rows = fusion.inherit(route("phenotype", unit="gene"), ["GENEA"], [LEADER, other, RUNNER])
        assert {r.pair.id for r in rows} == {LEADER.id, other.id}
        assert all(r.rank == 1 and r.inherited for r in rows)

    def test_an_allele_route_gives_the_pair_its_best_allele_rank(self):
        rows = fusion.inherit(route("reads", unit="allele"), ["a2", "zz", "a1"], [LEADER])
        assert [(r.pair.id, r.rank) for r in rows] == [(LEADER.id, 1)]

    def test_nothing_past_the_cut_is_an_opinion(self):
        rows = fusion.inherit(route("likelihood"), [RUNNER.id, LEADER.id], [LEADER, RUNNER], top=1)
        assert [r.pair.id for r in rows] == [RUNNER.id]


class TestFuse:
    def test_two_routes_agreeing_sum_the_published_formula(self):
        routes = [route("one"), route("two")]
        rows = ranked("one", (LEADER, 1), (RUNNER, 2)) + ranked("two", (LEADER, 1), (RUNNER, 3))
        fused = fusion.fuse(routes, rows)

        leader, runner = fused
        assert leader.pair == LEADER
        assert leader.score == pytest.approx(1 / 61 + 1 / 61)
        assert runner.score == pytest.approx(1 / 62 + 1 / 63)
        assert [row.rank for row in fused] == [1, 2]

    def test_a_pair_a_route_never_listed_scores_at_the_missing_rank(self):
        routes = [route("one"), route("two")]
        rows = ranked("one", (LEADER, 1), (THIRD, 2)) + ranked("two", (LEADER, 1))
        fused = {row.pair.id: row for row in fusion.fuse(routes, rows)}

        assert fused[THIRD.id].score == pytest.approx(1 / 62 + 1 / (60 + fusion.MISSING_RANK))
        assert fused[THIRD.id].per_route["two"] == fusion.MISSING_RANK

    def test_missing_is_one_worse_than_the_last_listed_rank(self):
        assert fusion.MISSING_RANK == fusion.TOP_N + 1

    def test_a_silenced_route_shows_its_opinion_and_adds_nothing(self):
        routes = [route("one"), route("reads", admitted=False, weight=0.0)]
        rows = ranked("one", (LEADER, 2)) + ranked("reads", (LEADER, 1))
        (fused,) = fusion.fuse(routes, rows)

        assert fused.score == pytest.approx(1 / 62)
        assert fused.per_route == {"one": 2, "reads": 1}

    def test_weights_scale_each_contribution(self):
        routes = [route("one", weight=0.5), route("two", weight=2.0)]
        rows = ranked("one", (LEADER, 1)) + ranked("two", (LEADER, 4))
        (fused,) = fusion.fuse(routes, rows)

        assert fused.score == pytest.approx(0.5 / 61 + 2.0 / 64)

    def test_k_is_a_parameter_and_sixty_is_the_default(self):
        routes = [route("one")]
        rows = ranked("one", (LEADER, 1))
        assert fusion.fuse(routes, rows)[0].score == pytest.approx(1 / 61)
        assert fusion.fuse(routes, rows, k=0)[0].score == pytest.approx(1 / 1)

    def test_ties_share_a_rank_and_the_next_rank_skips(self):
        routes = [route("one")]
        rows = ranked("one", (LEADER, 1), (RUNNER, 1), (THIRD, 5))
        fused = fusion.fuse(routes, rows)

        assert [row.rank for row in fused] == [1, 1, 3]

    def test_ties_are_ordered_by_pair_id_so_two_runs_agree(self):
        routes = [route("one")]
        rows = ranked("one", (RUNNER, 1), (LEADER, 1))
        assert [row.pair.id for row in fusion.fuse(routes, rows)] == [LEADER.id, RUNNER.id]

    def test_a_confirmation_for_a_pair_nobody_ranked_is_refused(self):
        with pytest.raises(ValueError, match="which no route ranked"):
            fusion.fuse(
                [route("one")],
                ranked("one", (LEADER, 1)),
                confirmations={RUNNER.id: Confirmation(read_confirmed=True)},
            )


class TestIndependentEvidence:
    def test_two_routes_reading_the_same_source_count_once(self):
        routes = [
            route("phenotype", unit="gene", inputs=("hpo",)),
            route("likelihood", inputs=("vcf", "hpo")),
        ]
        rows = ranked("phenotype", (LEADER, 1)) + ranked("likelihood", (LEADER, 1))
        (fused,) = fusion.fuse(routes, rows)

        assert fused.inputs == ("hpo", "vcf")
        assert fused.independent_evidence == 2

    def test_a_route_that_did_not_list_the_pair_does_not_speak_for_it(self):
        routes = [route("one", inputs=("vcf",)), route("two", inputs=("literature",))]
        rows = ranked("one", (LEADER, 1), (RUNNER, 2)) + ranked("two", (LEADER, 1))
        fused = {row.pair.id: row for row in fusion.fuse(routes, rows)}

        assert fused[LEADER.id].inputs == ("literature", "vcf")
        assert fused[RUNNER.id].inputs == ("vcf",)

    def test_the_confirmation_route_contributes_the_reads_without_a_rank(self):
        routes = [route("likelihood", inputs=("vcf",))]
        rows = ranked("likelihood", (LEADER, 1))
        (fused,) = fusion.fuse(
            routes, rows, confirmations={LEADER.id: Confirmation(read_confirmed=True)}
        )

        assert fused.inputs == ("reads", "vcf")
        assert fused.independent_evidence == 2

    def test_an_unconfirmed_pair_gains_nothing_from_the_reads(self):
        routes = [route("likelihood", inputs=("vcf",))]
        rows = ranked("likelihood", (LEADER, 1))
        (fused,) = fusion.fuse(
            routes,
            rows,
            confirmations={LEADER.id: Confirmation(single_copy=True, no_cn_loss=True)},
        )

        assert fused.inputs == ("vcf",)
        assert fused.confirmation.complete is False


class TestLeaveOneOut:
    def test_each_voting_route_is_dropped_in_turn(self):
        routes = [route("one"), route("two"), route("three")]
        rows = (
            ranked("one", (LEADER, 1), (RUNNER, 2))
            + ranked("two", (LEADER, 1), (RUNNER, 2))
            + ranked("three", (RUNNER, 1), (LEADER, 2))
        )
        out = fusion.leave_one_out(routes, rows)

        assert set(out) == {"one", "two", "three"}
        assert out["three"][0].pair == LEADER
        assert out["one"][0].pair == LEADER

    def test_dropping_the_route_that_carried_it_changes_rank_one(self):
        routes = [route("weak"), route("strong")]
        rows = ranked("weak", (RUNNER, 1), (LEADER, 40)) + ranked("strong", (LEADER, 1))
        assert fusion.fuse(routes, rows)[0].pair == LEADER
        assert fusion.leave_one_out(routes, rows)["strong"][0].pair == RUNNER

    def test_one_voting_route_has_nothing_to_leave_out(self):
        routes = [route("one"), route("reads", admitted=False, weight=0.0)]
        rows = ranked("one", (LEADER, 1))
        assert fusion.leave_one_out(routes, rows) == {}

    def test_the_dropped_route_still_shows_where_it_would_have_put_the_pair(self):
        routes = [route("one"), route("two")]
        rows = ranked("one", (LEADER, 1)) + ranked("two", (LEADER, 7))
        assert fusion.leave_one_out(routes, rows)["two"][0].per_route["two"] == 7


class TestFreeze:
    def test_the_digest_is_of_the_exported_text(self):
        import hashlib

        routes = [route("one")]
        fused = fusion.fuse(routes, ranked("one", (LEADER, 1)))
        frozen = fusion_freeze.freeze(fused, routes=routes)

        assert frozen.rows == 1
        assert frozen.sha256 == hashlib.sha256(frozen.text.encode("utf-8")).hexdigest()

    def test_the_header_names_every_route_after_the_fixed_columns(self):
        routes = [route("one"), route("two")]
        fused = fusion.fuse(routes, ranked("one", (LEADER, 1)))
        header = fusion_freeze.freeze(fused, routes=routes).text.splitlines()[0].split("\t")

        assert header[: len(fusion_freeze.COLUMNS)] == list(fusion_freeze.COLUMNS)
        assert header[len(fusion_freeze.COLUMNS) :] == ["one", "two"]

    def test_the_same_ranking_hashes_the_same_however_the_rows_arrived(self):
        routes = [route("one")]
        forwards = fusion.fuse(routes, ranked("one", (LEADER, 1), (RUNNER, 2)))
        backwards = fusion.fuse(routes, ranked("one", (RUNNER, 2), (LEADER, 1)))

        assert fusion_freeze.freeze(forwards, routes=routes).sha256 == (
            fusion_freeze.freeze(backwards, routes=routes).sha256
        )

    def test_a_different_ordering_hashes_differently(self):
        routes = [route("one")]
        one = fusion.fuse(routes, ranked("one", (LEADER, 1), (RUNNER, 2)))
        other = fusion.fuse(routes, ranked("one", (RUNNER, 1), (LEADER, 2)))

        assert fusion_freeze.freeze(one, routes=routes).sha256 != (
            fusion_freeze.freeze(other, routes=routes).sha256
        )

    def test_the_confirmation_triple_is_written_as_flags(self):
        routes = [route("one")]
        fused = fusion.fuse(
            routes,
            ranked("one", (LEADER, 1), (RUNNER, 2)),
            confirmations={LEADER.id: Confirmation(True, True, True)},
        )
        rows = fusion_freeze.freeze(fused, routes=routes).text.splitlines()[1:]

        assert rows[0].split("\t")[6] == "R1C"
        assert rows[1].split("\t")[6] == "-"
