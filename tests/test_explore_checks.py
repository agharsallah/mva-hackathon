"""The verdict engine: bands are stated, reasoning travels with the number."""

from pathlib import Path

from mva.explore import CallsetProfile, Verdict, run_checks
from mva.explore.checks import GENOME_BASES

PROFILE = Path(__file__).parent / "fixtures" / "profile"


def graded():
    return {c.name: c for c in run_checks(CallsetProfile.load(PROFILE))}


def test_every_check_states_the_band_it_was_judged_against():
    # A verdict nobody can argue with is a verdict nobody can trust. Each check has to
    # carry both the expected range and the reasoning behind that range.
    for check in run_checks(CallsetProfile.load(PROFILE)):
        assert check.expected
        assert len(check.basis) > 40


def test_a_healthy_transition_transversion_ratio_passes():
    assert graded()["Transition/transversion ratio"].verdict is Verdict.PASS


def test_multiallelic_sites_fail_until_the_callset_is_normalized():
    # The scorer compares allele strings verbatim, so a record holding two alternate
    # alleles at once can never be matched. This is a blocker, not a warning.
    check = graded()["Multiallelic sites"]
    assert check.verdict is Verdict.FAIL
    assert check.is_actionable


def test_a_chromosome_off_diploid_balance_is_caught():
    check = next(c for c in graded().values() if "allele-balance deviation" in c.name)
    assert "chr20" in check.name
    assert check.verdict in (Verdict.WARN, Verdict.FAIL)


def test_sex_is_inferred_from_sex_chromosome_evidence_and_never_graded():
    check = graded()["Genetic sex from sex-chromosome evidence"]
    assert check.verdict is Verdict.INFO
    assert "male" in check.display


def test_coverage_is_derived_from_sequenced_bases_over_the_genome_length():
    check = graded()["Estimated raw coverage"]
    assert check.value == 2.98e9 / GENOME_BASES
    # Far below the 30x floor for germline calling, so the fixture must fail it.
    assert check.verdict is Verdict.FAIL


def test_checks_degrade_to_the_subset_the_profile_supports(tmp_path):
    (tmp_path / "fastq_qc_L001.tsv").write_text("metric\tvalue\nduplication_rate\t0.05\n")
    names = [c.name for c in run_checks(CallsetProfile.load(tmp_path))]
    assert names == ["Duplication rate"]


def test_an_empty_profile_produces_no_checks_rather_than_failing(tmp_path):
    assert run_checks(CallsetProfile.load(tmp_path)) == []


def test_every_verdict_carries_a_colour_from_the_shared_palette():
    for verdict in Verdict:
        assert verdict.hue.fill.startswith("#")
        assert verdict.hue.label
