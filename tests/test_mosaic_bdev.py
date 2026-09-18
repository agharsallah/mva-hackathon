"""Fold-over B-deviation: does it find what a mean cannot, and stay quiet when it should?

The step's whole argument is that entry 037 used a statistic with no power, so the two
properties under test are exactly those two halves:

* on a balanced arm the statistic must **not** exceed its own null -- otherwise every
  chromosome would be reported mosaic and the negative result would be meaningless;
* on an injected mosaic it must, at fractions small enough to matter.

The DANFIP fraction is tested for the thing that actually goes wrong with it at this depth:
it is biased upward, badly, and the correction has to remove that bias at f = 0 without
removing the signal above it.
"""

import numpy as np
import pytest

from mosaic_synthetic import CENTRE, RHO, arm
from mva.mosaic import bdev
from mva.mosaic.tables import AlleleHistogram


class TestCentre:
    def test_it_measures_reference_bias_rather_than_assuming_half(self):
        shifted = arm(sites=20_000, centre=0.47, seed=12)
        assert bdev.centre(shifted) == pytest.approx(0.47, abs=0.005)

    def test_a_mosaic_does_not_move_it(self):
        """The bands are symmetric about the centre, which is why a mean cannot detect them
        and why a mean is the right thing to centre on."""
        balanced = arm(sites=20_000, seed=13)
        mosaic = arm(sites=20_000, fraction=0.20, seed=13)
        assert bdev.centre(mosaic) == pytest.approx(bdev.centre(balanced), abs=0.004)


class TestBdev:
    def test_a_balanced_arm_does_not_exceed_its_null(self):
        result = bdev.bdev(arm(sites=20_000, seed=21), rho=RHO, around=CENTRE, draws=60)
        assert not result.exceeds_null
        assert result.p_value > 0.05

    @pytest.mark.parametrize("fraction", [0.05, 0.10, 0.20])
    def test_an_injected_mosaic_does(self, fraction):
        result = bdev.bdev(
            arm(sites=20_000, fraction=fraction, seed=22), rho=RHO, around=CENTRE, draws=60
        )
        assert result.exceeds_null
        assert result.z > 3.0

    def test_the_statistic_grows_with_the_fraction(self):
        values = [
            bdev.statistic(arm(sites=20_000, fraction=f, seed=23), around=CENTRE)
            for f in (0.0, 0.05, 0.10, 0.20)
        ]
        assert values == sorted(values)

    def test_a_thin_arm_is_reported_unmeasurable_rather_than_flat(self):
        thin = arm(sites=5, seed=24)
        assert not bdev.bdev(thin, rho=RHO, around=CENTRE, draws=20).measurable

    def test_an_empty_arm_does_not_raise(self):
        empty = AlleleHistogram("21", "p", np.array([]), np.array([]), np.array([]))
        result = bdev.bdev(empty, rho=RHO, around=CENTRE, draws=10)
        assert not result.measurable
        assert not result.exceeds_null

    def test_the_p_value_is_never_zero(self):
        """(exceeded + 1) / (draws + 1) -- the project's convention, so a figure can log it."""
        result = bdev.bdev(
            arm(sites=20_000, fraction=0.30, seed=25), rho=RHO, around=CENTRE, draws=40
        )
        assert result.p_value > 0.0


class TestDanfip:
    def test_the_published_estimator_is_badly_biased_at_this_depth(self):
        """The finding the correction exists for: at f = 0 the raw number is far from zero."""
        result = bdev.danfip(arm(sites=20_000, seed=31), around=CENTRE, rho=RHO, draws=40)
        assert result.f_raw > 0.3

    def test_the_correction_removes_that_bias(self):
        result = bdev.danfip(arm(sites=20_000, seed=31), around=CENTRE, rho=RHO, draws=40)
        assert result.f_hat == pytest.approx(0.0, abs=0.02)

    def test_it_still_rises_with_a_real_fraction(self):
        values = [
            bdev.danfip(
                arm(sites=20_000, fraction=f, seed=32), around=CENTRE, rho=RHO, draws=40
            ).f_hat
            for f in (0.0, 0.10, 0.20, 0.30)
        ]
        assert values == sorted(values)
        assert values[-1] > values[0] + 0.1

    def test_it_is_compressed_at_the_low_end_and_says_so_by_being_low(self):
        """Not a bug: at f = 0.05 the bands are inside the noise, and the estimate is a
        floor rather than a measurement. The simulation is what states the limit."""
        result = bdev.danfip(
            arm(sites=20_000, fraction=0.05, seed=33), around=CENTRE, rho=RHO, draws=40
        )
        assert 0.0 <= result.f_hat < 0.05
