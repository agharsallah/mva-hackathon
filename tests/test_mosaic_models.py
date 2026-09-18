"""The five models, their fits, and the two pairs that cannot be told apart.

The value of a five-model comparison is entirely in whether it picks the right one, so the
tests inject each mechanism in turn and check the call. Two of them are expected to fail in
specific, pre-registered ways, and those expectations are asserted rather than hoped for:

* mitotic and meiotic trisomy differ by the balanced tract, which is small or absent at low
  cell fraction -- so at f = 0.05 the comparison must *not* claim to separate them;
* copy-neutral loss of heterozygosity and mitotic trisomy share their bands and differ only
  in depth, so their pairwise margin is exposed as its own number.

A test that asserted "the right model always wins" would be asserting something the data
cannot support, and would fail on real chromosomes for the right reason at the wrong time.
"""

import pytest

from mosaic_synthetic import CENTRE, DEPTH, RHO, arm, depths
from mva.mosaic import madseq, models


def fit(model: str, fraction: float, *, tract: float = 0.0, sites: int = 20_000, seed: int = 41):
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
    def test_a_balanced_chromosome_is_called_normal(self):
        verdict = madseq.best(fit("normal", 0.0))
        assert verdict.best == "normal"

    @pytest.mark.parametrize("fraction", [0.10, 0.20])
    def test_a_mitotic_trisomy_is_called_one(self, fraction):
        assert madseq.best(fit("mitotic_trisomy", fraction)).best == "mitotic_trisomy"

    @pytest.mark.parametrize("fraction", [0.10, 0.20])
    def test_copy_neutral_loh_is_called_one(self, fraction):
        assert madseq.best(fit("cnloh", fraction)).best == "cnloh"

    def test_a_monosomy_is_called_one(self):
        assert madseq.best(fit("monosomy", 0.20)).best == "monosomy"

    def test_the_fitted_fraction_recovers_what_was_injected(self):
        """Unlike the published band estimator, the likelihood fit is not compressed."""
        for fraction in (0.05, 0.10, 0.20):
            verdict = madseq.best(fit("mitotic_trisomy", fraction))
            assert verdict.fraction == pytest.approx(fraction, abs=0.02)


class TestWhatCannotBeSeparated:
    """H057, pre-registered before any of this ran: the mechanism is positional, and the
    band structure that survives a coordinate-free histogram is not enough to recover it."""

    @pytest.mark.parametrize("fraction", [0.05, 0.10, 0.20])
    @pytest.mark.parametrize("tract", [0.3, 0.5])
    def test_meiotic_is_never_separated_from_mitotic_at_kongs_threshold(self, fraction, tract):
        verdict = madseq.best(fit("meiotic_trisomy", fraction, tract=tract))
        assert verdict.best in {"mitotic_trisomy", "meiotic_trisomy"}
        assert not verdict.confident or verdict.best != "meiotic_trisomy"

    def test_the_two_are_nonetheless_the_top_two(self):
        """They are not separable *from each other* -- which is a different statement from
        not being able to see a trisomy at all, and the report must not conflate them."""
        fits = fit("meiotic_trisomy", 0.20, tract=0.5)
        ranked = sorted(fits, key=lambda item: item.bic)
        assert {ranked[0].model, ranked[1].model} == {"mitotic_trisomy", "meiotic_trisomy"}

    def test_the_trisomy_versus_cnloh_margin_is_reported_on_its_own(self):
        """They share their bands and differ only in depth, so a reader must see that
        number without having to subtract two BICs from a table."""
        verdict = madseq.best(fit("mitotic_trisomy", 0.20))
        assert verdict.trisomy_vs_cnloh > 0
        assert "trisomy_vs_cnloh" in verdict.as_dict()


class TestTheLowConfidenceRule:
    def test_a_margin_under_ten_is_not_a_call(self):
        fits = fit("normal", 0.0)
        verdict = madseq.best(fits, delta=1e9)
        assert verdict.call == "not distinguishable"
        assert not verdict.confident

    def test_the_default_threshold_is_kongs(self):
        assert madseq.DELTA_BIC == 10.0
