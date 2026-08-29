"""Assembling a profile directory: optional everywhere, case-agnostic by construction."""
from dataclasses import replace
from pathlib import Path

import pytest

from mva.explore import CallsetProfile, ProfileLayout

PROFILE = Path(__file__).parent / "fixtures" / "profile"


def loaded():
    return CallsetProfile.load(PROFILE)


def test_every_section_present_in_the_directory_is_loaded():
    assert set(loaded().available) == {
        "header", "contigs", "stats", "filters_and_genotypes",
        "balance", "reads", "read_qc", "panel",
    }


def test_a_missing_directory_entry_is_a_gap_not_an_exception(tmp_path):
    # The most common time to want a profile is while the script building it is still
    # being debugged, so a half-written directory has to load.
    (tmp_path / "vcf_contig_counts.tsv").write_text("1\t248956422\t1200\n")
    profile = CallsetProfile.load(tmp_path)
    assert profile.available == ["contigs"]
    assert profile.balance == []
    assert profile.total_records is None


def test_an_empty_directory_loads_and_reports_nothing(tmp_path):
    assert CallsetProfile.load(tmp_path).available == []


def test_a_renamed_artifact_is_a_layout_swap_not_a_code_change(tmp_path):
    (tmp_path / "counts.tsv").write_text("1\t248956422\t1200\n")
    profile = CallsetProfile.load(tmp_path, ProfileLayout(contig_counts="counts.tsv"))
    assert [c.name for c in profile.contigs] == ["1"]


def test_scaffolds_are_separated_from_the_primary_assembly():
    profile = loaded()
    assert [c.name for c in profile.primary_contigs] == ["1", "2", "20", "X", "Y"]
    assert profile.scaffold_records == 7


def test_contigs_are_returned_in_assembly_order_not_file_order():
    assert [c.name for c in loaded().primary_contigs][:3] == ["1", "2", "20"]


def test_allele_balance_deviation_is_signed_from_the_diploid_expectation():
    chrom20 = next(b for b in loaded().balance if b.chrom == "20")
    assert chrom20.deviation == pytest.approx(-0.08)


def test_read_files_are_grouped_by_lane_and_mate():
    reads = loaded().reads
    assert {f.lane for f in reads} == {"L001"}
    assert sorted(f.mate for f in reads) == ["R1", "R2"]


def test_panel_genes_carry_length_normalised_and_suppression_figures():
    genes = {g.symbol: g for g in loaded().panel}
    assert genes["GENEB"].suppressed == 6
    assert genes["GENEB"].suppressed_fraction == 0.6
    assert genes["GENEA"].variants_per_kb == 40 / 50


def test_panel_notes_are_joined_from_the_bed_without_the_caller_asking():
    genes = {g.symbol: g for g in loaded().panel}
    assert genes["GENEA"].note == "a synthetic candidate"


def test_totals_prefer_the_measured_tally_over_the_stats_estimate():
    profile = loaded()
    assert profile.total_records == 2650
    assert profile.phased_records == 400
    assert profile.total_gigabases == 2.98


def test_the_profile_is_immutable_so_a_view_cannot_edit_shared_state():
    profile = loaded()
    assert replace(profile, panel=[]).panel == []
    assert profile.panel != []
