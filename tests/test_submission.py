"""The submission seam: the CSV contract the scorer parses.

Each team member gets six submissions and the team has eighteen in total. A row that
fails to parse does not cost a row, it costs a whole submission, so every constraint the
scorer enforces is asserted here rather than discovered on the leaderboard.
"""
import csv
import io

import pytest

from mva.pipeline import Row, Variant, write_submission

A = Variant("chr15", 40143000, "T", "C")
B = Variant("chr15", 40143500, "G", "T")
C = Variant("chr5", 900000, "A", "AT")

TEMPLATE_HEADER = [
    "proband_id", "chrom_1", "pos_1", "ref_1", "alt_1",
    "chrom_2", "pos_2", "ref_2", "alt_2", "epcr", "finding_type", "notes",
]


def render(rows):
    out = io.StringIO()
    write_submission(rows, out)
    return list(csv.reader(io.StringIO(out.getvalue())))


def test_header_matches_the_official_template_exactly():
    assert render([Row(A, epcr=1.0)])[0] == TEMPLATE_HEADER


def test_pair_row_carries_both_variants_in_one_row():
    # A full match requires both true variants in a single row; two separate rows
    # score only partial credit however they are ranked.
    row = render([Row(A, B, epcr=1.0)])[1]
    assert row[:5] == ["PROBAND01", "chr15", "40143000", "T", "C"]
    assert row[5:9] == ["chr15", "40143500", "G", "T"]


def test_single_variant_row_leaves_the_second_variant_blank():
    # Blank chrom_2/pos_2 is how the scorer recognises a single-variant probe row.
    assert render([Row(A, epcr=0.9)])[1][5:9] == ["", "", "", ""]


def test_finding_type_defaults_to_primary_and_notes_are_carried():
    row = render([Row(C, epcr=0.4, finding_type="secondary", notes="ACMG SF v3.2")])[1]
    assert row[10] == "secondary"
    assert row[11] == "ACMG SF v3.2"


def test_rows_are_written_in_descending_epcr_order():
    # Rank is assigned by descending epcr, and ties break by file order. Writing in
    # rank order makes what we submit match what we think we submitted.
    rendered = render([Row(A, epcr=0.5), Row(B, epcr=0.95), Row(C, epcr=0.7)])
    assert [r[9] for r in rendered[1:]] == ["0.95", "0.7", "0.5"]


def test_duplicate_epcr_is_rejected():
    # Equal epcr leaves rank order decided by file position — an ambiguity that would
    # corrupt the decode of an oracle probe.
    with pytest.raises(ValueError, match="distinct"):
        write_submission([Row(A, epcr=0.5), Row(B, epcr=0.5)], io.StringIO())


@pytest.mark.parametrize("bad", [0.0, -0.1, 1.5])
def test_epcr_outside_the_zero_to_one_interval_is_rejected(bad):
    with pytest.raises(ValueError, match="epcr"):
        write_submission([Row(A, epcr=bad)], io.StringIO())


def test_more_than_ten_rows_is_rejected():
    rows = [Row(A, epcr=1.0 - i / 100) for i in range(11)]
    with pytest.raises(ValueError, match="10"):
        write_submission(rows, io.StringIO())


def test_unknown_finding_type_is_rejected():
    with pytest.raises(ValueError, match="finding_type"):
        write_submission([Row(A, epcr=0.5, finding_type="incidental")], io.StringIO())


def test_empty_submission_is_rejected():
    with pytest.raises(ValueError):
        write_submission([], io.StringIO())
