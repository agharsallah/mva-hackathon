"""The five models, their fits, and the three things they cannot do.

The value of a five-model comparison is entirely in whether it picks the right one, so the
tests inject each mechanism in turn and check the call. Three failures are expected in
specific, pre-registered ways, and those expectations are asserted rather than hoped for:

* **below about 15 % cell fraction the mixture is absorbed by ``normal``.** With the
  over-dispersion fitted per chromosome, a two-band mixture and a single wider band are
  nearly the same distribution, and the simpler one wins on the BIC penalty. That is the
  identifiability floor of allele balance, and it is why the detection limit in
  :mod:`mva.mosaic.simulate` -- which compares against a null fitted *elsewhere* -- is the
  instrument that reaches 2 to 3 %.
* **mitotic and meiotic trisomy are never separated at Kong's threshold.** They are nested:
  the meiotic model is the mitotic one plus a balanced tract, so when the tract buys nothing
  it sits exactly one BIC penalty behind, and when it buys something the margin is small.
* **a trisomy is therefore never *confidently* called**, only led. The honest output is
  "not distinguishable, leading model mitotic trisomy", which is what ``call`` says.

A test asserting "the right model always wins confidently" would be asserting something the
data cannot support, and would fail on real chromosomes for the right reason at the wrong
time.

Eight thousand sites per arm rather than the twenty thousand the other modules use: the fit
is a nested optimisation and the behaviours under test are structural, not marginal.
"""

import pytest

from mosaic_synthetic import CENTRE, DEPTH, RHO, arm, depths
from mva.mosaic import madseq, models
from mva.mosaic import verdict as verdict_module

SITES = 8_000


def fit(model: str, fraction: float, *, tract: float = 0.0, sites: int = SITES, seed: int = 41):
    spec = models.by_name(model)
    alleles = arm(sites=sites, fraction=fraction, model=model, tract=tract, seed=seed)
    depth = depths(DEPTH * models.depth_ratio(spec, fraction), seed=seed + 1)
    return madseq.fit_models(alleles, depth, rho=RHO, centre=CENTRE, baseline_depth=float(DEPTH))


class TestParameterCounting:
    def test_every_model_counts_the_shared_nuisance_parameter(self):
        assert all(model.parameters >= models.NUISANCE for model in models.MODELS)

    def test_the_tract_model_has_one_more_than_the_band_models(self):
        assert models.MEIOTIC_TRISOMY.parameters == models.MITOTIC_TRISOMY.parameters + 1

    def test_normal_is_the_simplest(self):
        assert models.NORMAL.parameters == min(model.parameters for model in models.MODELS)


class TestBands:
    def test_a_trisomy_splits_the_sites_in_two_equal_bands(self):
        bands = models.bands_for(models.MITOTIC_TRISOMY, 0.2, 0.5)
        assert [band.weight for band in bands] == [0.5, 0.5]
        assert sum(band.centre for band in bands) == pytest.approx(1.0)

    def test_the_trisomy_offset_uses_three_copies_and_cnloh_uses_two(self):
        """f/(2+f) against f/2 -- the arithmetic that makes them different models."""
        assert models.offset(models.MITOTIC_TRISOMY, 0.2) == pytest.approx(0.2 / 2.2)
        assert models.offset(models.CNLOH, 0.2) == pytest.approx(0.1)

    def test_depth_moves_up_for_a_gain_down_for_a_loss_and_not_at_all_for_cnloh(self):
        assert models.depth_ratio(models.MITOTIC_TRISOMY, 0.2) == pytest.approx(1.1)
        assert models.depth_ratio(models.MONOSOMY, 0.2) == pytest.approx(0.9)
        assert models.depth_ratio(models.CNLOH, 0.2) == pytest.approx(1.0)

    def test_a_zero_fraction_collapses_every_model_to_one_band(self):
        for model in models.MODELS:
            assert len(models.bands_for(model, 0.0, 0.5)) == 1


class TestCalls:
    def test_a_balanced_chromosome_leads_with_normal(self):
        assert verdict_module.best(fit("normal", 0.0)).best == "normal"

    def test_a_mitotic_trisomy_leads_with_one(self):
        assert verdict_module.best(fit("mitotic_trisomy", 0.20)).best == "mitotic_trisomy"

    def test_copy_neutral_loh_is_called_outright(self):
        """It beats the trisomy that shares its bands on depth, which is a real margin."""
        verdict = verdict_module.best(fit("cnloh", 0.20))
        assert verdict.call == "cnloh"
        assert verdict.confident

    def test_a_monosomy_is_called_outright(self):
        verdict = verdict_module.best(fit("monosomy", 0.20))
        assert verdict.call == "monosomy"
        assert verdict.confident

    def test_the_fitted_fraction_recovers_what_was_injected_where_it_is_identifiable(self):
        """Unlike the published band estimator, the likelihood fit is not compressed."""
        for fraction in (0.20, 0.30):
            verdict = verdict_module.best(fit("mitotic_trisomy", fraction))
            assert verdict.fraction == pytest.approx(fraction, abs=0.02)


class TestTheIdentifiabilityFloor:
    """A mixture below ~15 % is absorbed by a single wider band. Measured, not assumed."""

    @pytest.mark.parametrize("model", ["mitotic_trisomy", "cnloh", "monosomy"])
    def test_a_ten_per_cent_event_is_absorbed_by_normal(self, model):
        assert verdict_module.best(fit(model, 0.10)).best == "normal"

    def test_and_the_absorbing_fit_reports_a_wider_spread_than_the_truth(self):
        """The mechanism of the absorption, so a reader can check it rather than trust it."""
        clean = {row.model: row for row in fit("normal", 0.0)}["normal"]
        absorbed = {row.model: row for row in fit("mitotic_trisomy", 0.10)}["normal"]
        assert absorbed.rho > clean.rho


class TestWhatCannotBeSeparated:
    """H057, pre-registered before any of this ran: the mechanism is positional, and the
    band structure that survives a coordinate-free histogram is not enough to recover it."""

    @pytest.mark.parametrize("fraction", [0.20, 0.30])
    def test_meiotic_is_never_separated_from_mitotic_at_kongs_threshold(self, fraction):
        verdict = verdict_module.best(fit("meiotic_trisomy", fraction, tract=0.5))
        assert verdict.best in {"mitotic_trisomy", "meiotic_trisomy"}
        assert not verdict.confident

    def test_the_two_are_nonetheless_the_top_two(self):
        """They are not separable *from each other* -- which is a different statement from
        not being able to see a trisomy at all, and the report must not conflate them."""
        fits = fit("meiotic_trisomy", 0.30, tract=0.5)
        ranked = sorted(fits, key=lambda item: item.bic)
        assert {ranked[0].model, ranked[1].model} == {"mitotic_trisomy", "meiotic_trisomy"}

    def test_a_trisomy_is_led_but_never_confidently_called(self):
        """Nested models bound the margin below by one BIC penalty, so "confident" is
        unreachable for the pair by construction -- and the page must say "leading" rather
        than "called"."""
        verdict = verdict_module.best(fit("mitotic_trisomy", 0.30))
        assert verdict.best == "mitotic_trisomy"
        assert not verdict.confident
        assert verdict.call == "not distinguishable"

    def test_the_trisomy_versus_cnloh_margin_is_reported_on_its_own(self):
        """They share their bands and differ only in depth, so a reader must see that
        number without having to subtract two BICs from a table."""
        verdict = verdict_module.best(fit("mitotic_trisomy", 0.20))
        assert verdict.trisomy_vs_cnloh > 0
        assert "trisomy_vs_cnloh" in verdict.as_dict()


class TestTheLowConfidenceRule:
    def test_a_margin_under_ten_is_not_a_call(self):
        verdict = verdict_module.best(fit("normal", 0.0), delta=1e9)
        assert verdict.call == "not distinguishable"
        assert not verdict.confident

    def test_the_default_threshold_is_kongs(self):
        assert madseq.DELTA_BIC == 10.0


class TestTheNoiseComponent:
    """Without it the richest model wins everywhere. With it the comparison is about bands."""

    def test_a_clean_arm_needs_almost_no_noise(self):
        assert verdict_module.best(fit("normal", 0.0)).noise_share < 0.02

    def test_an_arm_whose_tails_swallow_it_is_not_measurable(self):
        verdict = verdict_module.Verdict(
            chrom="21",
            best="meiotic_trisomy",
            runner_up="normal",
            delta_bic=4_971.0,
            fraction=0.74,
            trisomy_vs_cnloh=0.0,
            confident=True,
            noise_share=0.24,
        )
        assert not verdict.measurable
        assert verdict.call == "not measurable"

    def test_the_gate_is_an_order_of_magnitude_above_a_clean_autosome(self):
        assert models.NOISE_CEILING == 0.10
