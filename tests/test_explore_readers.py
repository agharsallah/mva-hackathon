"""The parsing seam: real file shapes in, plain records out, never an exception."""
from pathlib import Path

import pytest

from mva.io import readers

PROFILE = Path(__file__).parent / "fixtures" / "profile"


def test_table_separates_rows_from_trailing_rollup_scalars():
    # Profiling scripts append totals underneath the table. Those lines are two fields
    # wide against a five-column header, so parsing them as rows would corrupt the table.
    table = readers.read_table(PROFILE / "fastq_profile.tsv")
    assert len(table.rows) == 2
    assert table.scalars["est_total_gbases"] == "2.98"
    assert table.columns[0] == "file"


def test_table_keeps_comments_so_a_figure_can_cite_its_own_sampling():
    table = readers.read_table(PROFILE / "fastq_qc_L001.tsv")
    assert table.comments == ["synthetic fixture, not sampled from any run"]


def test_sections_distinguish_a_block_header_from_a_single_stated_figure():
    # `## genotype counts` opens a block; `## total_records<tab>2650` states one number.
    sections = readers.read_sections(PROFILE / "vcf_filter_gt_counts.tsv")
    assert set(sections.blocks) == {"FILTER counts", "genotype counts"}
    assert sections.scalars["total_records"] == "2650"
    assert sections.counts("genotype counts")["0/1"] == 1600


def test_bcftools_stats_sections_drop_the_file_index_column():
    stats = readers.read_bcftools_stats(PROFILE / "vcf_stats_summary.txt")
    assert readers.summary_numbers(stats)["SNPs"] == 2200
    assert stats["ST"][0] == ["A>C", "80"]
    assert stats["TSTV"][0][2] == "1.96"


def test_bed_keeps_columns_beyond_the_name_as_extras():
    regions = readers.read_bed(PROFILE / "mva_panel_grch38.bed")
    assert [r.name for r in regions] == ["GENEA", "GENEB"]
    assert regions[0].length == 50000
    assert regions[0].extras[-1] == "a synthetic candidate"


def test_vcf_header_records_contigs_fields_and_the_sample_column():
    header = readers.read_vcf_header(PROFILE / "vcf_header.txt")
    assert header.sample == "WGS_TEST0001"
    assert ("15", 101991189) in header.contigs
    assert "AD" in header.fields["FORMAT"]
    assert header.fields["FILTER"]["MQ40"] == "MQ < 40.0"


def test_a_description_containing_a_comma_is_not_split_on_it():
    # `Description="Allelic depths for the ref and alt alleles in the order listed"` is
    # quoted; a naive split on commas would truncate every field description in the file.
    header = readers.read_vcf_header(PROFILE / "vcf_header.txt")
    assert header.fields["FORMAT"]["AD"].endswith("in the order listed")


@pytest.mark.parametrize("value", ["", None, "n/a", ".", "1.5"])
def test_as_int_never_raises(value):
    assert readers.as_int(value) in (None, 1) or isinstance(readers.as_int(value), int)


def test_numeric_coercion_returns_none_rather_than_raising():
    assert readers.as_float("not a number") is None
    assert readers.as_int("42") == 42
    assert readers.as_float("0.5") == 0.5
