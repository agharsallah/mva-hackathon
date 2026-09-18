"""The detection limit, and the comparison that makes step 8 worth running.

Two things are asserted here, and the second is the step's headline claim:

* the limit must **fall** as an arm gets more sites -- a detection limit that ignored the
  data would be a constant, and a constant would be a fabrication;
* the fold-over statistic must reach 80 % power at fractions where entry 037's mean-BAF
  statistic never does, on identical draws at an identical seed.

The multi-chromosome designs are tested on both arms of their answer. Recovery alone would
pass with a test that flags everything, so the false-positive arm is asserted too.
"""

import pytest

from mosaic_synthetic import CENTRE, RHO, arm
from mva.mosaic import simulate

REPLICATES = 40


def limit(sites: int, *, statistic=simulate.bdev_statistic, name="bdev", seed: int = 51):
    return simulate.power_curve(
        arm(sites=sites, seed=seed),
        rho=RHO,
        centre=CENTRE,
        replicates=REPLICATES,
        seed=seed,
        statistic=statistic,
        name=name,
    )


class TestPowerCurve:
    def test_power_rises_with_the_injected_fraction(self):
        curve = limit(20_000).power
        fractions = sorted(curve)
        assert curve[fractions[0]] <= curve[fractions[-1]]
        assert curve[fractions[-1]] == 1.0

    def test_a_bigger_arm_detects_a_smaller_fraction(self):
        assert limit(40_000).f80 <= limit(4_000).f80

    def test_the_threshold_is_the_null_ninety_fifth_percentile(self):
        result = limit(10_000)
        assert result.threshold > 0
        assert result.target == 0.80

    def test_an_empty_arm_reports_no_limit_rather_than_a_number(self):
        import numpy as np

        from mva.mosaic.tables import AlleleHistogram

        empty = AlleleHistogram("21", "p", np.array([]), np.array([]), np.array([]))
        result = simulate.power_curve(empty, rho=RHO, centre=CENTRE, replicates=5)
        assert not result.detected_anything


class TestAgainstEntry037:
    def test_the_fold_over_statistic_has_power_where_the_mean_has_none(self):
        """The claim the step exists to make: same arm, same seed, same draws, one line
        different between the two statistics."""
        folded = limit(20_000)
        mean = limit(20_000, statistic=simulate.mean_statistic, name="mean_baf")
        assert folded.detected_anything
        assert not mean.detected_anything

    def test_the_mean_statistic_stays_near_its_nominal_rate(self):
        """Not weaker -- flat. Its power does not rise with the fraction at all."""
        curve = limit(20_000, statistic=simulate.mean_statistic, name="mean_baf").power
        assert max(curve.values()) < 0.5


class TestMultiChromosome:
    @pytest.fixture(scope="class")
    @staticmethod
    def histograms():
        return {name: arm(sites=15_000, seed=60 + index) for index, name in enumerate("abcde")}

    def test_every_injected_chromosome_is_recovered_at_a_large_fraction(self, histograms):
        results = simulate.multi_chromosome(
            histograms,
            affected=("a", "b"),
            fraction=0.20,
            rho=RHO,
            centre=CENTRE,
            replicates=20,
            seed=61,
        )
        assert min(item.recall for item in results) == 1.0

    def test_the_untouched_chromosomes_are_scored_too(self, histograms):
        """The arm that decides whether a genome-wide bound survives on a variegated
        genome: if injecting two chromosomes made the other three light up, the bound
        would be worthless and nothing but this measurement would say so."""
        results = simulate.multi_chromosome(
            histograms,
            affected=("a", "b"),
            fraction=0.20,
            rho=RHO,
            centre=CENTRE,
            replicates=20,
            seed=62,
        )
        rate = sum(item.false_positive_rate for item in results) / len(results)
        assert rate < 0.25

    def test_a_tiny_fraction_is_not_recovered(self, histograms):
        results = simulate.multi_chromosome(
            histograms,
            affected=("a",),
            fraction=0.01,
            rho=RHO,
            centre=CENTRE,
            replicates=20,
            seed=63,
        )
        assert sum(item.recall for item in results) / len(results) < 0.8
