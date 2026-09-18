"""What a ranking of five fits is allowed to say, and the three ways it is refused.

Every rule here exists because the real callset produced a number this repository would
otherwise have printed as a result. The tests construct verdicts directly rather than
fitting anything: these are decisions about already-fitted numbers, and mixing an
hour-long optimisation into a test of a rule would make the rule hard to read and the
test slow for no reason.
"""

import math

import pytest

from mva.mosaic import betabinom, madseq, models
from mva.mosaic import verdict as verdict_module

OBSERVATIONS = 20_000


def fit(
    model: str,
    *,
    bic: float,
    rho: float = 0.01,
    tract: float = 0.0,
    noise: float = 0.02,
    fraction: float = 0.0,
) -> madseq.ModelFit:
    spec = models.by_name(model)
    # ModelFit.bic adds the penalty k log N, so the likelihood is solved backwards from the
    # target rather than set to it -- otherwise a test that asks for a margin of five gets
    # whatever the difference in parameter counts happens to add.
    penalty = spec.parameters * math.log(OBSERVATIONS + 1)
    return madseq.ModelFit(
        chrom="1",
        model=model,
        fraction=fraction,
        tract=tract,
        rho=rho,
        noise_share=noise,
        depth_dispersion=50.0,
        allele_log_likelihood=-(bic - penalty) / 2,
        depth_log_likelihood=0.0,
        parameters=spec.parameters,
        observations=OBSERVATIONS,
    )


def ranking(**overrides) -> tuple[madseq.ModelFit, ...]:
    """Five fits with `normal` leading by a wide margin unless a caller says otherwise."""
    defaults = {
        "normal": 100.0,
        "monosomy": 200.0,
        "mitotic_trisomy": 300.0,
        "meiotic_trisomy": 400.0,
        "cnloh": 500.0,
    }
    return tuple(
        fit(name, bic=overrides.pop(f"{name}_bic", score), **overrides.get(name, {}))
        for name, score in defaults.items()
    )


class TestTheMargin:
    def test_a_wide_margin_names_the_model(self):
        assert verdict_module.best(ranking()).call == "normal"

    def test_a_narrow_margin_is_not_a_call(self):
        fits = ranking(normal_bic=100.0, monosomy_bic=105.0)
        found = verdict_module.best(fits)
        assert found.best == "normal"
        assert found.call == "not distinguishable"

    def test_the_threshold_is_kongs_and_is_a_parameter(self):
        assert madseq.DELTA_BIC == 10.0
        assert verdict_module.best(ranking(), delta=1e9).call == "not distinguishable"


class TestTheTailBurden:
    def test_a_contig_past_the_ceiling_is_not_measurable(self):
        """Read off `normal`'s noise share, never the leader's: a degenerate fit can hide the
        tails inside its extra bands and report almost none."""
        fits = ranking(normal={"noise": 0.24})
        assert verdict_module.best(fits).call == "not measurable"

    def test_the_ceiling_is_an_order_of_magnitude_above_a_clean_autosome(self):
        assert models.NOISE_CEILING == 0.10

    def test_it_outranks_every_other_refusal(self):
        """A contig with no band structure left has nothing for a mechanism to be about."""
        fits = ranking(
            normal={"noise": 0.3}, meiotic_trisomy={"tract": 0.9}, meiotic_trisomy_bic=1.0
        )
        assert verdict_module.best(fits).call == "not measurable"


class TestTheBoundary:
    def test_a_tract_at_its_bound_is_refused(self):
        fits = ranking(
            meiotic_trisomy_bic=1.0, meiotic_trisomy={"tract": verdict_module.TRACT_BOUND}
        )
        found = verdict_module.best(fits)
        assert found.best == "meiotic_trisomy"
        assert found.degenerate
        assert found.call == "model family not usable"

    def test_an_over_dispersion_driven_to_zero_is_refused(self):
        fits = ranking(cnloh_bic=1.0, cnloh={"rho": betabinom.RHO_BOUNDS[0], "fraction": 0.2})
        assert verdict_module.best(fits).call == "model family not usable"

    def test_a_fraction_at_either_bound_is_refused(self):
        for edge in madseq.FRACTION_BOUNDS:
            fits = ranking(monosomy_bic=1.0, monosomy={"fraction": edge})
            assert verdict_module.best(fits).call == "model family not usable"

    def test_a_model_is_only_judged_on_parameters_it_fits(self):
        """`normal` has no tract and no fraction, so neither can be pinned. Without this the
        gate would condemn every clean contig, because their tract is zero by construction."""
        found = verdict_module.best(ranking())
        assert not found.degenerate
        assert found.call == "normal"

    def test_zero_noise_is_not_a_boundary_failure(self):
        """It is the right answer for data with no tails, and every simulated arm fits it."""
        fits = ranking(cnloh_bic=1.0, cnloh={"noise": 0.0, "fraction": 0.2})
        assert not verdict_module.best(fits).degenerate

    def test_an_interior_fit_is_allowed_to_name_its_model(self):
        fits = ranking(cnloh_bic=1.0, cnloh={"rho": 0.02, "fraction": 0.2, "noise": 0.01})
        assert verdict_module.best(fits).call == "cnloh"


class TestWhatTravelsWithTheVerdict:
    def test_the_leader_parameters_are_reported_so_the_refusal_can_be_checked(self):
        fits = ranking(meiotic_trisomy_bic=1.0, meiotic_trisomy={"tract": 0.9, "rho": 0.004})
        row = verdict_module.best(fits).as_dict()
        assert row["leader_tract"] == pytest.approx(0.9)
        assert row["leader_rho"] == pytest.approx(0.004)
        assert row["degenerate"] is True

    def test_the_trisomy_versus_cnloh_margin_is_its_own_column(self):
        """They share their bands and differ only in depth, so a reader must see that number
        without subtracting two BICs from a table."""
        row = verdict_module.best(ranking()).as_dict()
        assert "trisomy_vs_cnloh" in row
