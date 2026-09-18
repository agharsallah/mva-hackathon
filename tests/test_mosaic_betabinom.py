"""The over-dispersed allele-balance model: does it recover what it is given?

Three properties matter and each has a way of being silently wrong.

* **It must reduce to the binomial.** If it does not, every number downstream is off by an
  unknown amount and nothing would say so.
* **It must recover a known rho.** A fit that returns its lower bound on every input would
  look like a clean sample and would be indistinguishable from one.
* **Its sampler and its likelihood must be the same distribution.** They are used in
  opposite directions -- the sampler builds the null, the likelihood scores the data --
  so a mismatch would make a well-calibrated test look powerful.
"""

import numpy as np
import pytest
from scipy.stats import binom

from mosaic_synthetic import tally
from mva.mosaic import betabinom
from mva.mosaic.tables import AlleleHistogram


class TestLogpmf:
    def test_it_reduces_to_the_binomial_as_rho_goes_to_zero(self):
        k = np.arange(0, 45)
        n = np.full(45, 44)
        ours = np.exp(betabinom.logpmf(k, n, 0.5, betabinom.RHO_BOUNDS[0]))
        assert np.abs(ours - binom.pmf(k, 44, 0.5)).max() < 1e-5

    def test_it_is_a_distribution(self):
        k = np.arange(0, 31)
        n = np.full(31, 30)
        assert np.exp(betabinom.logpmf(k, n, 0.42, 0.05)).sum() == pytest.approx(1.0, abs=1e-9)

    def test_over_dispersion_widens_it(self):
        """The variance inflation is 1 + (n-1)*rho, which is the whole point of the model."""
        n = np.array([44])
        _, tight = betabinom.mean_and_variance(n, 0.5, 1e-6)
        _, wide = betabinom.mean_and_variance(n, 0.5, 0.05)
        assert wide[0] / tight[0] == pytest.approx(1.0 + 43 * 0.05, rel=1e-3)


class TestFitRho:
    @pytest.mark.parametrize("truth", [0.005, 0.02, 0.10])
    def test_it_recovers_a_known_over_dispersion(self, truth):
        rng = np.random.default_rng(4)
        n = np.full(40_000, 44)
        histogram = tally(betabinom.sample(n, 0.5, truth, rng), n)
        assert betabinom.fit_rho(histogram) == pytest.approx(truth, rel=0.15)

    def test_an_empty_histogram_returns_the_binomial_not_a_guess(self):
        empty = AlleleHistogram("1", "p", np.array([]), np.array([]), np.array([]))
        assert betabinom.fit_rho(empty) == betabinom.RHO_BOUNDS[0]

    def test_the_fit_is_a_maximum(self):
        """Perturbing the fitted value in either direction must lower the likelihood."""
        rng = np.random.default_rng(6)
        n = np.full(20_000, 44)
        histogram = tally(betabinom.sample(n, 0.5, 0.03, rng), n)
        fitted = betabinom.fit_rho(histogram)
        best = betabinom.log_likelihood(histogram, 0.5, fitted)
        assert best > betabinom.log_likelihood(histogram, 0.5, fitted * 0.5)
        assert best > betabinom.log_likelihood(histogram, 0.5, fitted * 2.0)


class TestSampler:
    def test_the_sampler_matches_the_likelihood(self):
        """Draw from the sampler, fit with the likelihood, recover the sampler's parameter."""
        rng = np.random.default_rng(9)
        n = np.full(30_000, 30)
        histogram = tally(betabinom.sample(n, 0.4, 0.04, rng), n)
        assert histogram.weighted(histogram.baf) == pytest.approx(0.4, abs=0.01)
        assert betabinom.fit_rho(histogram, p=0.4) == pytest.approx(0.04, rel=0.2)
