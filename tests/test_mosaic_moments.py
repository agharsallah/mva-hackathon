"""The closed-form null against the draws it replaced.

:mod:`mva.mosaic.moments` computes what :mod:`mva.mosaic.simulate` used to sample. That is
only safe if the two agree, and agreement is not something the implementations can be
inspected for — one enumerates the beta-binomial's support, the other draws from it, and
they share no code path below ``logpmf``. So it is measured here, at several depths, several
over-dispersions and both statistics.

The second thing under test is the refusal. The Gaussian approximation needs many
independent sites, and a module that quietly approximated an arm with twelve calls would
produce a confident number where there is none.
"""

import numpy as np
import pytest

from mosaic_synthetic import RHO, arm, tally
from mva.mosaic import betabinom, moments, simulate


def margin(depth: int, sites: int) -> tuple[np.ndarray, np.ndarray]:
    return np.array([depth]), np.array([float(sites)])


def drawn_statistic(depth: int, sites: int, centre: float, rho: float, *, folded: bool, draws: int):
    rng = np.random.default_rng(17)
    totals = np.full(sites, depth)
    values = []
    for _ in range(draws):
        baf = betabinom.sample(totals, centre, rho, rng) / totals
        values.append(float(np.mean(np.abs(baf - centre))) if folded else float(np.mean(baf)))
    return np.array(values)


class TestAgainstTheDraws:
    @pytest.mark.parametrize("depth", [20, 44, 100])
    @pytest.mark.parametrize("rho", [0.005, 0.02])
    def test_the_fold_over_moments_match_a_monte_carlo(self, depth, rho):
        computed = moments.fold_moments(
            *margin(depth, 20_000), bands=[(0.5, 1.0)], rho=rho, centre=0.5
        )
        sampled = drawn_statistic(depth, 20_000, 0.5, rho, folded=True, draws=120)
        assert computed.mean == pytest.approx(float(sampled.mean()), rel=0.01)
        assert computed.sd == pytest.approx(float(sampled.std(ddof=1)), rel=0.20)

    def test_the_mean_moments_match_a_monte_carlo(self):
        computed = moments.mean_moments(*margin(44, 20_000), bands=[(0.5, 1.0)], rho=0.02)
        sampled = drawn_statistic(44, 20_000, 0.5, 0.02, folded=False, draws=120)
        assert computed.mean == pytest.approx(float(sampled.mean()), abs=0.001)
        assert computed.sd == pytest.approx(float(sampled.std(ddof=1)), rel=0.20)

    def test_a_percentile_matches_the_sampled_one(self):
        computed = moments.fold_moments(
            *margin(44, 20_000), bands=[(0.5, 1.0)], rho=0.02, centre=0.5
        )
        sampled = drawn_statistic(44, 20_000, 0.5, 0.02, folded=True, draws=200)
        assert computed.percentile(0.95) == pytest.approx(
            float(np.quantile(sampled, 0.95)), rel=0.01
        )


class TestShape:
    def test_a_mosaic_band_split_raises_the_folded_mean_and_not_the_plain_one(self):
        """The whole asymmetry step 8 rests on, in two assertions."""
        null_bands = simulate.bands_at(0.0, 0.5)
        mosaic_bands = simulate.bands_at(0.20, 0.5)
        folded_null = moments.fold_moments(
            *margin(44, 20_000), bands=null_bands, rho=0.02, centre=0.5
        )
        folded_mosaic = moments.fold_moments(
            *margin(44, 20_000), bands=mosaic_bands, rho=0.02, centre=0.5
        )
        plain_null = moments.mean_moments(*margin(44, 20_000), bands=null_bands, rho=0.02)
        plain_mosaic = moments.mean_moments(*margin(44, 20_000), bands=mosaic_bands, rho=0.02)
        assert folded_mosaic.mean > folded_null.mean * 1.1
        assert plain_mosaic.mean == pytest.approx(plain_null.mean, abs=1e-6)

    def test_more_sites_narrow_the_distribution_by_the_square_root(self):
        small = moments.fold_moments(*margin(44, 10_000), bands=[(0.5, 1.0)], rho=0.02, centre=0.5)
        large = moments.fold_moments(*margin(44, 40_000), bands=[(0.5, 1.0)], rho=0.02, centre=0.5)
        assert small.mean == pytest.approx(large.mean, rel=1e-9)
        assert small.sd / large.sd == pytest.approx(2.0, rel=0.01)

    def test_a_mixed_depth_arm_weights_by_how_many_calls_sit_at_each_depth(self):
        depths = np.array([20, 100])
        heavy_shallow = moments.fold_moments(
            depths, np.array([9_000.0, 1_000.0]), bands=[(0.5, 1.0)], rho=0.02, centre=0.5
        )
        heavy_deep = moments.fold_moments(
            depths, np.array([1_000.0, 9_000.0]), bands=[(0.5, 1.0)], rho=0.02, centre=0.5
        )
        # A shallower call scatters further from the centre, so folding it gives a larger mean.
        assert heavy_shallow.mean > heavy_deep.mean


class TestRefusal:
    def test_too_few_sites_is_refused_rather_than_approximated(self):
        computed = moments.fold_moments(
            *margin(44, moments.MIN_SITES_FOR_CLT - 1), bands=[(0.5, 1.0)], rho=0.02, centre=0.5
        )
        assert not computed.usable

    def test_an_empty_arm_is_refused(self):
        empty = tally(np.array([]), np.array([]))
        depths, counts = simulate.depth_margin(empty)
        assert not moments.fold_moments(
            depths, counts, bands=[(0.5, 1.0)], rho=0.02, centre=0.5
        ).usable

    def test_a_real_arm_is_usable(self):
        depths, counts = simulate.depth_margin(arm(sites=5_000, seed=81))
        assert moments.fold_moments(depths, counts, bands=[(0.5, 1.0)], rho=RHO, centre=0.5).usable
