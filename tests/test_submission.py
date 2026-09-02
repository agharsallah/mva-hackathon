"""The submission seam: the CSV contract the scorer parses.

Each team member gets six submissions and the team has eighteen in total. A row that
fails to parse does not cost a row, it costs a whole submission, so every constraint the
scorer enforces is asserted here rather than discovered on the leaderboard.
"""

import csv
import io

import pytest

from mva.pipeline import Row, Variant, write_submission
from mva.pipeline.submission import problems, read_submission

A = Variant("chr15", 40143000, "T", "C")
B = Variant("chr15", 40143500, "G", "T")
C = Variant("chr5", 900000, "A", "AT")

TEMPLATE_HEADER = [
    "proband_id",
    "chrom_1",
    "pos_1",
    "ref_1",
    "alt_1",
    "chrom_2",
    "pos_2",
    "ref_2",
    "alt_2",
    "epcr",
    "finding_type",
    "notes",
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


# --- problems(): the enumerating form, for an interactive builder ------------


def test_problems_lists_every_violation_rather_than_the_first():
    found = problems([Row(A, epcr=1.5), Row(B, epcr=1.6, finding_type="incidental")])
    assert len(found) == 3  # two epcr, one finding_type
    assert all(m.startswith("row ") for m in found)


def test_problems_names_the_offending_row_by_file_position():
    assert problems([Row(A, epcr=0.9), Row(B, epcr=0.8, finding_type="x")])[0].startswith("row 2:")


def test_a_clean_submission_has_no_problems():
    assert problems([Row(A, B, epcr=0.99), Row(C, epcr=0.98)]) == []


def test_descending_is_not_checked_unless_asked_for():
    rows = [Row(A, epcr=0.5), Row(B, epcr=0.9)]
    assert problems(rows) == []
    assert problems(rows, require_descending=True)[0].startswith("row 2:")


def test_descending_rejects_equal_neighbours_as_well_as_ascending_ones():
    # Distinctness already catches this; the ordering rule must not disagree with it.
    assert problems([Row(A, epcr=0.9), Row(B, epcr=0.9)], require_descending=True)


# --- Row.variants(): a row holds a SET of alleles (intel §8.2) ---------------


def test_a_pair_row_holds_both_alleles_regardless_of_order():
    assert Row(A, B, epcr=0.9).variants() == Row(B, A, epcr=0.9).variants()


def test_a_row_whose_two_alleles_are_identical_is_a_single_variant_row():
    assert Row(A, A, epcr=0.9).variants() == frozenset({A})


# --- read_submission(): parse back the way the scorer parses -----------------


def roundtrip(rows):
    out = io.StringIO()
    write_submission(rows, out)
    return read_submission(io.StringIO(out.getvalue()))


def test_a_written_submission_reads_back_identical():
    rows = [
        Row(A, B, epcr=0.99, notes="a note, with a comma"),
        Row(C, epcr=0.5, finding_type="secondary"),
    ]
    assert roundtrip(rows) == sorted(rows, key=lambda r: -r.epcr)


def test_reading_never_normalizes_the_contig():
    # The scorer compares chrom verbatim, so a reader that "helpfully" added chr would
    # hide the exact bug this parser exists to expose.
    text = f"{','.join(TEMPLATE_HEADER)}\nPROBAND01,15,40143000,T,C,,,,,0.9,primary,\n"
    assert read_submission(io.StringIO(text))[0].variant.chrom == "15"


def test_a_wrong_header_is_rejected():
    with pytest.raises(ValueError, match="header"):
        read_submission(io.StringIO("chrom,pos\nchr1,1\n"))


def test_a_wrong_proband_id_is_rejected():
    text = f"{','.join(TEMPLATE_HEADER)}\nPROBAND02,chr15,40143000,T,C,,,,,0.9,primary,\n"
    with pytest.raises(ValueError, match="proband_id"):
        read_submission(io.StringIO(text))


def test_an_empty_file_is_rejected():
    with pytest.raises(ValueError):
        read_submission(io.StringIO(""))
