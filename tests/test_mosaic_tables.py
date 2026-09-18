"""The histograms, the arm check and the baseline — the structural half of the package.

Nothing statistical here. What is under test is that the reduction the whole step rests on
is lossless in the ways it claims, that the arm check compares the right two things, and
that the baseline flags a chromosome capable of moving it rather than quietly absorbing it.
"""

import numpy as np
import pytest

from mosaic_synthetic import arm, depths, tally
from mva.mosaic import arms, baseline
from mva.mosaic.tables import AlleleHistogram, allele_histograms, depth_histograms, pool


class TestAlleleHistogram:
    def test_sites_counts_calls_and_not_distinct_pairs(self):
        histogram = tally(np.array([10, 10, 12]), np.array([44, 44, 44]))
        assert histogram.n_sites == 3
        assert histogram.k.size == 2

    def test_the_mean_is_site_weighted_not_row_weighted(self):
        """One pair seen 99 times and another seen once must not count equally."""
        histogram = AlleleHistogram(
            "1", "q", np.array([22, 40]), np.array([44, 44]), np.array([99.0, 1.0])
        )
        assert histogram.weighted(histogram.baf) == pytest.approx((99 * 0.5 + 40 / 44) / 100)

    def test_mismatched_lengths_are_refused(self):
        with pytest.raises(ValueError, match="same length"):
            AlleleHistogram("1", "q", np.array([1]), np.array([2, 3]), np.array([1.0]))

    def test_a_call_with_no_reads_is_refused(self):
        with pytest.raises(ValueError, match="no reads"):
            AlleleHistogram("1", "q", np.array([0]), np.array([0]), np.array([1.0]))

    def test_an_empty_histogram_is_usable(self):
        empty = AlleleHistogram("1", "p", np.array([]), np.array([]), np.array([]))
        assert empty.n_sites == 0
        assert empty.mean_depth == 0.0


class TestPooling:
    def test_adding_arms_is_exact(self):
        """The pooled histogram must be the histogram of the pooled calls, which is true of
        counts and of no summary they could have been reduced to first."""
        left = arm(sites=3_000, seed=71, chrom="1")
        right = arm(sites=2_000, seed=72, chrom="1")
        whole = pool([left, right], chrom="1", arm="")
        assert whole.n_sites == left.n_sites + right.n_sites
        expected = (
            left.weighted(left.baf) * left.n_sites + right.weighted(right.baf) * right.n_sites
        ) / whole.n_sites
        assert whole.weighted(whole.baf) == pytest.approx(expected)

    def test_pooling_nothing_gives_an_empty_histogram(self):
        assert pool([], chrom="1", arm="").n_sites == 0


class TestGrouping:
    def test_rows_group_by_chromosome_and_arm(self):
        rows = [
            {"chrom": "1", "arm": "p", "k": 20, "n": 40, "sites": 5},
            {"chrom": "1", "arm": "q", "k": 20, "n": 40, "sites": 7},
            {"chrom": "2", "arm": "p", "k": 21, "n": 40, "sites": 2},
        ]
        grouped = allele_histograms(rows)
        assert set(grouped) == {("1", "p"), ("1", "q"), ("2", "p")}
        assert grouped[("1", "q")].n_sites == 7

    def test_depth_rows_group_the_same_way(self):
        grouped = depth_histograms([{"chrom": "1", "arm": "q", "depth": 40, "sites": 9}])
        assert grouped[("1", "q")].mean == 40.0


class TestDepthHistogram:
    def test_variance_to_mean_is_one_for_a_poisson_like_spread(self):
        """Real depth is over-dispersed; the ratio is the number that says by how much."""
        histogram = depths(44.0, dispersion=1e6, sites=40_000, seed=73)
        assert histogram.variance_to_mean == pytest.approx(1.0, abs=0.1)

    def test_it_rises_when_the_spread_widens(self):
        tight = depths(44.0, dispersion=1e6, sites=40_000, seed=74)
        wide = depths(44.0, dispersion=5.0, sites=40_000, seed=74)
        assert wide.variance_to_mean > tight.variance_to_mean


class TestArmCheck:
    def test_the_widest_gap_is_found(self):
        present = [0, 1, 2, 10, 11, 12]
        assert arms.centromere_gap(present) == (3_000_000, 10_000_000)

    def test_a_chromosome_with_no_gap_reports_none(self):
        assert arms.centromere_gap([0, 1, 2, 3]) is None

    def test_a_gap_near_the_centromere_agrees(self):
        geometry = {"1": {"cen_start": 5_000_000, "cen_end": 7_000_000, "acrocentric": False}}
        checks = arms.check(geometry, {"1": [0, 1, 2, 3, 4, 8, 9, 10]})
        assert checks[0].agrees

    def test_a_gap_far_from_it_does_not(self):
        geometry = {"1": {"cen_start": 5_000_000, "cen_end": 7_000_000, "acrocentric": False}}
        checks = arms.check(geometry, {"1": [0, 1, 40, 41]})
        assert not checks[0].agrees
        assert arms.disagreements(checks) == checks

    def test_an_acrocentric_is_exempt_because_its_biggest_hole_is_its_short_arm(self):
        geometry = {"21": {"cen_start": 10_000_000, "cen_end": 13_000_000, "acrocentric": True}}
        checks = arms.check(geometry, {"21": [0, 1, 40, 41]})
        assert checks[0].agrees

    def test_a_chromosome_with_no_bins_is_skipped_not_assumed(self):
        geometry = {"1": {"cen_start": 1, "cen_end": 2, "acrocentric": False}}
        assert arms.check(geometry, {}) == []


class TestBaseline:
    def test_a_clean_set_is_stable(self):
        estimates = {str(index): 42.0 + (index % 3) * 0.1 for index in range(22)}
        assert baseline.leave_one_out(estimates, seed=1).stable

    def test_one_outlier_alone_cannot_move_a_median(self):
        """Which is the point of a median baseline, and why the flag needs the LOO form."""
        estimates = {str(index): 42.0 for index in range(22)}
        estimates["7"] = 80.0
        assert baseline.leave_one_out(estimates, seed=1).robust == pytest.approx(42.0)

    def test_the_robust_value_is_the_median_of_the_leave_one_out_medians(self):
        estimates = {"a": 1.0, "b": 2.0, "c": 3.0, "d": 4.0, "e": 5.0}
        fitted = baseline.leave_one_out(estimates, seed=1)
        assert fitted.robust == pytest.approx(np.median(list(fitted.without.values())))

    def test_too_few_chromosomes_to_hold_one_out_is_said_rather_than_faked(self):
        fitted = baseline.leave_one_out({"a": 1.0, "b": 2.0}, seed=1)
        assert fitted.without == {}
        assert fitted.stable

    def test_the_absolute_comparison_only_covers_what_both_sides_have(self):
        shift = baseline.absolute_shift({"1": 1.0, "2": 1.1}, {"1": 0.9, "3": 2.0})
        assert shift == {"1": pytest.approx(0.1)}
