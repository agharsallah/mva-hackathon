"""The genotype model: what it reads off the calibration markers, and what it refuses to say.

Counts are simulated from the model's own distribution with a fixed seed, so a test asserts
that the fit recovers parameters it was given — the only check available for an estimator
without a second estimator to disagree with it.
"""

import numpy as np
import pytest
from scipy.stats import nbinom

from mva.kmer.genotype import (
    CLASSES,
    Fit,
    Genotype,
    call_alleles,
    dropout,
    expected,
    fit,
    minimum_count,
    per_probe_agreement,
    posteriors,
)

SEED = 20260913


def draw(mean: float, dispersion: float, size: int, seed: int = SEED) -> np.ndarray:
    """Counts from a negative binomial of a given mean — the model's own emission."""
    probability = dispersion / (dispersion + mean)
    return nbinom.rvs(dispersion, probability, size=size, random_state=np.random.default_rng(seed))


def calibrated(per_copy=22.0, dispersion=30.0, error=0.01, markers=4000) -> Fit:
    """A fit read off simulated markers whose true parameters are known."""
    het_alt = draw(per_copy, dispersion, markers, SEED)
    het_ref = draw(per_copy, dispersion, markers, SEED + 1)
    hom_alt_alt = draw(2 * per_copy, dispersion, markers, SEED + 2)
    hom_alt_ref = draw(2 * per_copy * error, dispersion, markers, SEED + 3)
    return fit(het_ref, het_alt, hom_alt_ref, hom_alt_alt)


def test_the_fit_recovers_the_per_copy_coverage_it_was_shown():
    fitted = calibrated(per_copy=22.0)
    assert 21.0 < fitted.lambda_per_copy < 23.0
    assert 43.0 < fitted.expected_depth < 45.0


def test_both_sides_of_a_heterozygous_marker_give_the_same_per_copy_coverage():
    """They are the same quantity measured on opposite probes of the same markers. A gap is
    a reference-bias or strand effect, not a genotype — which is why it is reported."""
    fitted = calibrated()
    assert fitted.side_disagreement < 0.05


def test_the_fit_recovers_the_dispersion_and_reports_it_as_over_dispersion():
    """Poisson predicts a variance-to-mean ratio of 1. Anything above it is the coverage
    structure a Poisson model has no parameter for."""
    fitted = calibrated(per_copy=22.0, dispersion=30.0)
    assert 15.0 < fitted.dispersion < 60.0
    assert fitted.variance_to_mean > 1.2


def test_the_error_rate_comes_from_the_side_that_should_never_be_seen():
    """A homozygous-alternate marker has no reference copy, so every reference count it
    shows was manufactured."""
    fitted = calibrated(error=0.02)
    assert 0.01 < fitted.error_rate < 0.03


def test_a_fit_with_no_heterozygous_markers_is_refused_rather_than_guessed():
    with pytest.raises(ValueError, match="nothing to fit"):
        fit(np.array([]), np.array([]), np.array([5.0]), np.array([40.0]))


def test_a_balanced_pair_of_counts_reads_as_heterozygous():
    fitted = calibrated(per_copy=22.0)
    weights = posteriors(np.array([22.0]), np.array([21.0]), fitted)
    assert CLASSES[weights.argmax()] is Genotype.HET
    assert weights.max() > 0.95


def test_an_alternate_at_full_depth_with_no_reference_reads_as_homozygous_alternate():
    fitted = calibrated(per_copy=22.0)
    weights = posteriors(np.array([0.0]), np.array([44.0]), fitted)
    assert CLASSES[weights.argmax()] is Genotype.HOM_ALT


def test_a_reference_at_full_depth_with_no_alternate_reads_as_homozygous_reference():
    fitted = calibrated(per_copy=22.0)
    weights = posteriors(np.array([44.0]), np.array([0.0]), fitted)
    assert CLASSES[weights.argmax()] is Genotype.HOM_REF


def test_posteriors_sum_to_one_over_the_three_classes():
    fitted = calibrated()
    weights = posteriors(np.array([22.0, 0.0, 44.0]), np.array([22.0, 44.0, 0.0]), fitted)
    assert np.allclose(weights.sum(axis=-1), 1.0)


def test_a_count_the_model_cannot_choose_between_is_a_no_call_not_its_best_guess():
    """ "The instrument could not say" and "the allele is absent" are different findings and
    only one of them is about the child.

    The counts are shallow on purpose. At the 44x of this sample's baited regions the three
    classes barely overlap and almost nothing is ambiguous; ambiguity is what a thin gene
    looks like, and thin genes are exactly where step 3 must not guess."""
    thin = calibrated(per_copy=1.5)
    ambiguous = call_alleles(np.array([5.0]), np.array([1.0]), np.array([3]), thin)
    assert ambiguous[0].genotype is Genotype.NO_CALL
    assert not ambiguous[0].confident
    assert ambiguous[0].posterior < 0.95


def test_at_this_samples_depth_the_three_classes_barely_overlap():
    """The counterpart of the test above, and the reason a no-call is informative: at 44x a
    balanced pair is heterozygous past any doubt the model can express, so a no-call at that
    depth means something happened to the probes rather than to the statistics."""
    deep = calibrated(per_copy=22.0)
    assert posteriors(np.array([28.0]), np.array([14.0]), deep).max() > 0.999


def test_an_allele_below_the_probe_minimum_is_a_no_call_however_good_its_counts():
    """One probe cannot disagree with itself, so its agreement carries no information."""
    fitted = calibrated(per_copy=22.0)
    calls = call_alleles(
        np.array([22.0]), np.array([22.0]), np.array([1]), fitted, minimum_probes=3
    )
    assert calls[0].genotype is Genotype.NO_CALL
    assert calls[0].probes == 1


def test_the_floor_is_the_parameter_h024_is_written_about():
    thin = calibrated(per_copy=1.5)
    counts = (np.array([4.0]), np.array([1.0]), np.array([3]))
    strict = call_alleles(*counts, thin, floor=0.95)[0]
    loose = call_alleles(*counts, thin, floor=0.50)[0]
    assert strict.genotype is Genotype.NO_CALL
    assert loose.genotype is not Genotype.NO_CALL


def test_each_probe_votes_separately_so_disagreement_stays_visible():
    """Summing an allele's counts first would hide exactly the disagreement a private
    neighbouring variant produces — one probe destroyed, two intact."""
    fitted = calibrated(per_copy=22.0)
    reference = np.array([22.0, 23.0, 44.0])
    alternate = np.array([21.0, 22.0, 0.0])
    votes, strength = per_probe_agreement(reference, alternate, fitted)
    assert [CLASSES[v] for v in votes] == [Genotype.HET, Genotype.HET, Genotype.HOM_REF]
    assert strength.shape == (3,)


def test_expected_counts_put_a_copy_on_its_own_probe_and_a_little_on_the_other():
    fitted = calibrated(per_copy=20.0, error=0.05)
    ref_hom_ref, alt_hom_ref = expected(fitted, 0)
    assert ref_hom_ref == pytest.approx(40.0, rel=0.1)
    assert 0 < alt_hom_ref < ref_hom_ref
    ref_het, alt_het = expected(fitted, 1)
    assert ref_het == pytest.approx(alt_het, rel=0.05)


def test_dropout_is_read_from_the_fitted_model_not_from_a_poisson_tail():
    """Over-dispersion puts far more mass at zero than Poisson does, so the optimistic
    Poisson figure would make every absence look decisive."""
    fitted = calibrated(per_copy=22.0, dispersion=5.0)
    poisson_like = calibrated(per_copy=22.0, dispersion=5000.0)
    assert dropout(fitted, copies=1) > dropout(poisson_like, copies=1)
    assert 0.0 <= dropout(fitted, copies=1) < 1.0


def test_dropout_is_smaller_for_two_copies_than_for_one():
    fitted = calibrated(per_copy=22.0)
    assert dropout(fitted, copies=2) <= dropout(fitted, copies=1)


def test_the_minimum_count_is_a_threshold_an_absent_allele_rarely_reaches():
    """H025's "present" means a count the model would not expect a homozygous-reference
    site to manufacture more often than the stated rate."""
    fitted = calibrated(per_copy=22.0, error=0.01)
    strict = minimum_count(fitted, false_positive=1e-4)
    loose = minimum_count(fitted, false_positive=1e-1)
    assert strict >= loose > 0
    _, absent_mean = expected(fitted, 0)
    assert strict > absent_mean


def test_priors_are_a_stated_parameter_and_change_the_answer():
    """Uniform by default: every allele typed here was already nominated by an aligner and
    a caller, so the question is not "what is a random site"."""
    fitted = calibrated(per_copy=22.0)
    assert fitted.priors == (1 / 3, 1 / 3, 1 / 3)
    skewed = fit(
        draw(22.0, 30.0, 500, SEED),
        draw(22.0, 30.0, 500, SEED + 1),
        draw(0.44, 30.0, 500, SEED + 2),
        draw(44.0, 30.0, 500, SEED + 3),
        priors=(0.98, 0.01, 0.01),
    )
    counts = (np.array([30.0]), np.array([12.0]))
    assert posteriors(*counts, skewed)[0][0] > posteriors(*counts, fitted)[0][0]


def test_the_fit_reports_the_marker_counts_behind_it():
    fitted = calibrated(markers=1234)
    assert fitted.het_markers == 1234 and fitted.hom_alt_markers == 1234
    assert fitted.as_dict()["het_markers"] == 1234
