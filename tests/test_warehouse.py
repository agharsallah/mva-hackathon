"""Tests for the staging half of the warehouse: shape inference and normalisation.

:mod:`mva.warehouse.catalog` and :mod:`mva.warehouse.stage` are what produce
``build/warehouse/*.parquet``, the input ``pg-ingest`` reads. Everything here runs on a
synthetic profile directory in ``tmp_path`` — no dataset, no network, no services.
"""

from pathlib import Path

import pytest

from mva.warehouse.catalog import OVERRIDES, Dataset, discover, sniff, table_name
from mva.warehouse.stage import normalise, safe_column, safe_columns, stage


@pytest.fixture
def profile(tmp_path: Path) -> Path:
    """A miniature profile directory covering all four source shapes."""
    (tmp_path / "counts.tsv").write_text(
        "gene\tn\tmean_dp\nBUB1B\t80\t44.2\nTP53\t120\t45.1\ntotal\t200\n"
    )
    (tmp_path / "vcf_contig_counts.tsv").write_text("1\t248956422\t383428\n2\t242193529\t388761\n")
    (tmp_path / "vcf_filter_gt_counts.tsv").write_text(
        "## FILTER counts\nPASS\t10\nLowQual\t3\n## GT counts\n0/1\t7\n## total_records\t13\n"
    )
    (tmp_path / "panel.bed").write_text("chr15\t40161060\t40261214\tBUB1B\n")
    (tmp_path / "notes.md").write_text("not stageable\n")
    return tmp_path


class TestCatalog:
    def test_sniffs_each_shape(self, profile: Path):
        assert sniff(profile / "counts.tsv") == "table"
        assert sniff(profile / "vcf_filter_gt_counts.tsv") == "sections"
        assert sniff(profile / "panel.bed") == "bed"

    def test_discover_skips_non_stageable_files(self, profile: Path):
        assert "notes" not in {dataset.table for dataset in discover(profile)}

    def test_overrides_beat_sniffing(self, profile: Path):
        found = {dataset.source: dataset for dataset in discover(profile)}
        assert found["vcf_contig_counts.tsv"] is OVERRIDES["vcf_contig_counts.tsv"]

    def test_table_names_are_sql_safe(self):
        assert table_name("vcf-chrom.allele balance.tsv") == "vcf_chrom_allele_balance"
        assert table_name("1000g.tsv").startswith("t_")


class TestNormalise:
    def test_rollup_lines_become_scalars_not_rows(self, profile: Path):
        dataset = Dataset(table="counts", source="counts.tsv")
        columns, rows, scalars = normalise(dataset, profile)
        assert columns == ("gene", "n", "mean_dp")
        assert len(rows) == 2, "the two-column total must not be read as a record"
        assert scalars == {"total": "200"}

    def test_headerless_source_uses_declared_columns(self, profile: Path):
        columns, rows, _ = normalise(OVERRIDES["vcf_contig_counts.tsv"], profile)
        assert columns == ("chrom", "length", "n_records")
        assert len(rows) == 2, "the first line is a record, not a header"

    def test_sections_flatten_to_long_form(self, profile: Path):
        columns, rows, scalars = normalise(OVERRIDES["vcf_filter_gt_counts.tsv"], profile)
        assert columns == ("section", "label", "count")
        assert ["FILTER counts", "PASS", "10"] in rows
        assert ["GT counts", "0/1", "7"] in rows
        assert scalars == {"total_records": "13"}


class TestSafeColumns:
    def test_punctuation_is_folded(self):
        assert safe_column("pct_in_0.40_0.60") == "pct_in_0_40_0_60"

    def test_leading_digit_is_prefixed(self):
        assert safe_column("5prime") == "c_5prime"

    def test_collisions_are_suffixed(self):
        assert safe_columns(("a.b", "a-b")) == ("a_b", "a_b_2")


class TestStage:
    def test_types_are_inferred_not_left_as_text(self, profile: Path, tmp_path: Path):
        import duckdb

        staged = stage(profile, tmp_path / "out")
        by_table = {item.table: item for item in staged}
        described = duckdb.sql(
            f"DESCRIBE SELECT * FROM read_parquet('{by_table['counts'].parquet}')"
        ).fetchall()
        types = {row[0]: row[1] for row in described}
        assert types["n"] == "BIGINT"
        assert types["mean_dp"] == "DOUBLE"
        assert types["gene"] == "VARCHAR"

    def test_scalars_from_every_source_land_in_one_table(self, profile: Path, tmp_path: Path):
        staged = {item.table: item for item in stage(profile, tmp_path / "out")}
        assert staged["profile_scalars"].rows == 2, "one from counts.tsv, one from the sections"

    def test_catalog_table_describes_every_other_table(self, profile: Path, tmp_path: Path):
        staged = stage(profile, tmp_path / "out")
        catalog = next(item for item in staged if item.table == "warehouse_catalog")
        assert catalog.rows == len(staged) - 1

    def test_intermediate_tsv_is_cleaned_up(self, profile: Path, tmp_path: Path):
        stage(profile, tmp_path / "out")
        assert not list((tmp_path / "out").glob("*.tsv"))
