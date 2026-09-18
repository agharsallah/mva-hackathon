"""The likelihood-ratio machinery: the ladder, the combiner, the rank curve, and the nulls.

Every number in here is either published (the ACMG ladder), derived in the test from first
principles (the AUC of two separated distributions), or a property that must hold whatever
the inputs are (nothing is ever filtered; a damped lane is still in the record). None is a
value copied out of a run, because a test that asserts what the code currently prints
cannot fail when the code is wrong.
"""

import math

import pytest

from mva.pipeline.acmg import PRIOR, VERY_STRONG, Strength, cap, likelihood_ratio
from mva.pipeline.likelihood import Lane, combine, strongest
from mva.pipeline.nulls import auc, permutation, separation
from mva.pipeline.rank_lr import MIN_LR, RankLikelihood, RecallPoint, from_benchmark


class TestTheLadder:
    def test_the_rungs_are_the_published_numbers(self):
        # Tavtigian 2018's table, to the two decimals the paper prints.
        assert likelihood_ratio(Strength.VERY_STRONG) == 350.0
        assert round(likelihood_ratio(Strength.STRONG), 1) == 18.7
        assert round(likelihood_ratio(Strength.MODERATE), 2) == 4.33
        assert round(likelihood_ratio(Strength.SUPPORTING), 2) == 2.08

    def test_the_ladder_is_geometric(self):
        # Each rung is the square root of the one above it. Stated as the relation rather
        # than as four constants, because the relation is what the paper derives.
        assert likelihood_ratio(Strength.STRONG) ** 2 == pytest.approx(VERY_STRONG)
        assert likelihood_ratio(Strength.MODERATE) ** 4 == pytest.approx(VERY_STRONG)
        assert likelihood_ratio(Strength.SUPPORTING) ** 8 == pytest.approx(VERY_STRONG)

    def test_benign_evidence_divides_where_pathogenic_multiplies(self):
        for name in ("SUPPORTING", "MODERATE", "STRONG", "VERY_STRONG"):
            pathogenic = likelihood_ratio(Strength[name])
            benign = likelihood_ratio(Strength[f"{name}_BENIGN"])
            assert pathogenic * benign == pytest.approx(1.0)

    def test_saying_nothing_multiplies_by_one(self):
        assert likelihood_ratio(Strength.NONE) == 1.0

    def test_the_prior_is_the_papers(self):
        assert PRIOR == 0.10

    def test_a_cap_lowers_but_never_raises(self):
        assert cap(Strength.VERY_STRONG, Strength.MODERATE) is Strength.MODERATE
        assert cap(Strength.SUPPORTING, Strength.MODERATE) is Strength.SUPPORTING

    def test_a_pathogenic_cap_does_not_touch_benign_evidence(self):
        # A ceiling on how far a tool may argue *for* pathogenicity says nothing about how
        # far it may argue against it; conflating the two would silently mute one side.
        assert cap(Strength.STRONG_BENIGN, Strength.MODERATE) is Strength.STRONG_BENIGN


class TestCombining:
    def test_lanes_multiply_onto_the_prior(self):
        result = combine(
            [Lane("a", 10.0, "src"), Lane("b", 3.0, "src")],
            prior=0.001,
        )
        assert result.combined_lr == pytest.approx(30.0)
        assert result.posterior_odds == pytest.approx((0.001 / 0.999) * 30.0)

    def test_a_lane_below_one_lowers_the_posterior_and_stays_in_the_record(self):
        result = combine([Lane("against", 0.25, "src")], prior=0.5)
        assert result.probability < 0.5
        assert ("against", 0.25) in result.terms

    def test_a_correlation_group_contributes_only_its_strongest_member(self):
        result = combine(
            [
                Lane("clinvar", 18.7, "src", group="allele-effect"),
                Lane("predictor", 4.33, "src", group="allele-effect"),
                Lane("frequency", 2.08, "src"),
            ],
            prior=0.01,
        )
        assert result.combined_lr == pytest.approx(18.7 * 2.08)
        assert result.damped == ("predictor",)

    def test_a_damped_lane_keeps_its_name_and_says_why(self):
        result = combine(
            [
                Lane("clinvar", 18.7, "src", group="g"),
                Lane("predictor", 4.33, "src", group="g"),
            ],
            prior=0.01,
        )
        suppressed = next(lane for lane in result.applied if lane.name == "predictor")
        assert suppressed.likelihood_ratio == 1.0
        assert "damped" in suppressed.note
        assert "clinvar" in suppressed.note

    def test_the_strongest_member_can_be_the_one_arguing_against(self):
        # Furthest from 1 in *either* direction: a strong benign lane must not lose to a
        # supporting pathogenic one just because the latter is above 1.
        result = combine(
            [
                Lane("benign", 1 / 18.7, "src", group="g"),
                Lane("pathogenic", 2.08, "src", group="g"),
            ],
            prior=0.01,
        )
        assert result.combined_lr == pytest.approx(1 / 18.7)

    def test_a_lane_without_a_source_is_refused(self):
        with pytest.raises(ValueError, match="source"):
            Lane("nameless", 2.0, "")

    def test_a_ratio_of_zero_is_refused(self):
        # Zero is a hard filter wearing a multiplier's clothes: nothing recovers from it.
        with pytest.raises(ValueError, match="positive"):
            Lane("absolute", 0.0, "src")

    def test_a_term_cannot_be_applied_twice(self):
        with pytest.raises(ValueError, match="applied once"):
            combine([Lane("x", 2.0, "src"), Lane("x", 3.0, "src")], prior=0.5)

    def test_a_prior_outside_the_open_interval_is_refused(self):
        for bad in (0.0, 1.0, -0.5, 2.0):
            with pytest.raises(ValueError, match="prior"):
                combine([Lane("x", 2.0, "src")], prior=bad)

    def test_strongest_of_nothing_is_nothing(self):
        assert strongest([]) is None


class TestRankLikelihood:
    def curve(self) -> RankLikelihood:
        # A deliberately simple curve: half the causal genes land in the first ten ranks.
        return RankLikelihood(
            curve=(RecallPoint(10, 0.5),),
            ranked=100,
            universe=1000,
            unrankable=0.1,
            source="test",
        )

    def test_the_first_bin_is_the_measured_mass_over_the_uniform_mass(self):
        # 0.5 of causal genes in 10 of 1,000 positions: 0.5 / (10/1000) = 50.
        assert self.curve().lr(1) == pytest.approx(50.0)

    def test_the_tail_bin_covers_the_ranks_past_the_last_measured_point(self):
        # (1 - 0.1) - 0.5 = 0.4 of causal mass over (100-10)/1000 = 0.09.
        assert self.curve().lr(50) == pytest.approx(0.4 / 0.09)

    def test_an_unranked_gene_is_down_weighted_and_never_zero(self):
        # 0.1 of causal genes are unrankable; 900 of 1,000 genes are outside the ranking.
        value = self.curve().lr(None)
        assert value == pytest.approx(0.1 / 0.9)
        assert value > 0

    def test_a_rank_past_the_ranked_population_falls_back_to_unranked(self):
        assert self.curve().lr(5_000) == pytest.approx(self.curve().lr(None))

    def test_the_masses_of_both_distributions_close(self):
        likelihood = self.curve()
        causal = sum(b.causal_mass for b in likelihood.bins()) + likelihood.unrankable
        null = sum(b.null_mass for b in likelihood.bins()) + (
            (likelihood.universe - likelihood.ranked) / likelihood.universe
        )
        assert causal == pytest.approx(1.0)
        assert null == pytest.approx(1.0)

    def test_an_empty_bin_is_clamped_rather_than_called_impossible(self):
        flat = RankLikelihood(
            curve=(RecallPoint(10, 0.0),), ranked=100, universe=1000, unrankable=0.1, source="t"
        )
        assert flat.lr(1) == MIN_LR

    def test_ranks_are_one_based(self):
        with pytest.raises(ValueError, match="1-based"):
            self.curve().lr(0)

    def test_a_curve_must_increase(self):
        with pytest.raises(ValueError, match="increasing"):
            RankLikelihood(
                curve=(RecallPoint(10, 0.5), RecallPoint(5, 0.6)),
                ranked=100,
                universe=1000,
                unrankable=0.0,
                source="t",
            )

    def test_from_benchmark_reads_the_json_a_run_writes(self):
        built = from_benchmark(
            [{"n": 10, "recall": 0.5}],
            ranked=100,
            universe=1000,
            unrankable=0.1,
            source="t",
        )
        assert built.lr(1) == pytest.approx(50.0)


class TestNulls:
    def test_perfect_separation_is_one_and_no_separation_is_a_half(self):
        assert auc([3, 4, 5], [0, 1, 2]) == 1.0
        assert auc([0, 1, 2], [3, 4, 5]) == 0.0
        assert auc([1, 2, 3], [1, 2, 3]) == 0.5

    def test_ties_count_as_half(self):
        assert auc([1, 1], [1, 1]) == 0.5

    def test_an_empty_side_is_not_measurable(self):
        result = separation([], [1.0], seed=1)
        assert result.positives == 0
        assert "not measurable" in result.verdict

    def test_an_interval_covering_a_half_is_reported_as_no_separation(self):
        result = separation([1.0, 2.0], [1.0, 2.0], seed=1, resamples=200)
        assert not result.separates
        assert "covers 0.5" in result.verdict

    def test_a_clear_separation_excludes_a_half(self):
        result = separation(list(range(50, 100)), list(range(50)), seed=1, resamples=200)
        assert result.separates
        assert result.low > 0.5

    def test_the_p_value_is_never_zero(self):
        # A finite null cannot prove p = 0, so the (+1)/(+1) form is used rather than a
        # bare count, which would print 0.000 from a hundred draws and mean nothing.
        result = permutation(100.0, [1.0, 2.0, 3.0])
        assert result.exceeded == 0
        assert result.p_value == pytest.approx(1 / 4)

    def test_a_draw_that_ties_the_observation_counts_against_it(self):
        result = permutation(10.0, [10.0, 1.0])
        assert result.exceeded == 1
        assert result.p_value == pytest.approx(2 / 3)

    def test_the_expected_false_lead_count_is_the_mean_over_draws(self):
        result = permutation(10.0, [1.0, 2.0], beaten=[0, 4])
        assert result.expected_false_leads == pytest.approx(2.0)

    def test_the_null_median_of_no_draws_is_nothing(self):
        assert permutation(1.0, []).null_median is None


class TestTheyComposeAsOneRanking:
    def test_no_candidate_can_be_removed_by_any_lane(self):
        # The property the whole design rests on: whatever a lane says, the posterior stays
        # a positive number, so an ordering exists for every candidate and nothing is lost.
        for ratio in (1e-9, 0.5, 1.0, 2.0, 1e9):
            result = combine([Lane("x", ratio, "src")], prior=1e-5)
            assert result.probability > 0
            assert math.isfinite(result.log10_lr)
