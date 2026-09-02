"""The `panel_gene_background` derivation, run against a miniature DuckDB warehouse.

Hermetic in the style of `tests/test_warehouse_karyogram.py`: the real SQL, the real
registry lookup, a callset built in memory. No network, no database.

The mini-callset is generated from a bin spec — `(chrom, mb, n, pass_n)` expanded into one
row per record — because the derivation's whole point is a *distribution* over 1 Mb
windows, and a distribution cannot be exercised with a handful of hand-written rows. Every
number is a fabricated shape chosen to make one arithmetic assertion checkable by hand.

The four contigs each carry one property under test:

* ``1`` — an ordinary contig with spread on both axes. The gene sits exactly on the mean,
  so both z-scores must be 0.
* ``5`` — every window identical. Zero spread must yield NULL, never a z of 0.
* ``7`` — hosts the outlier gene: a tenth of the background density, half its PASS share.
* ``9`` — carries one four-record window, which must be excluded from the PASS-share
  background (a ratio of tiny counts) while still counting toward the density background.
"""

import duckdb
import pytest

from mva.warehouse.analysis import DERIVATIONS, by_name
from mva.warehouse.analysis_background import (
    BACKGROUND_DERIVATIONS,
    BIN_BP,
    MIN_BIN_N_FOR_PASS,
    Z_NOTABLE,
)
from mva.warehouse.derivation import resolve

#: ``(chrom, mb, n, pass_n)`` — the window distribution the whole test rests on.
BINS = [
    # contig 1: density mean 1000, sd 163.3; PASS share mean 98.5 %, sd 0.577
    ("1", 0, 1000, 990),
    ("1", 1, 1200, 1176),
    ("1", 2, 800, 792),
    ("1", 3, 1000, 980),
    # contig 5: three identical windows, so neither axis has any spread at all
    ("5", 0, 1000, 990),
    ("5", 1, 1000, 990),
    ("5", 2, 1000, 990),
    # contig 7: density mean 1000, sd 100; PASS share mean 98.0 %, sd 1.0
    ("7", 0, 900, 891),
    ("7", 1, 1000, 970),
    ("7", 2, 1100, 1078),
    # contig 9: two well-covered windows (98.0 % ± 1.0) plus one four-record window whose
    # 0 % PASS share must not reach the PASS background
    ("9", 0, 1000, 990),
    ("9", 1, 1000, 970),
    ("9", 2, 4, 0),
]

#: ``(chrom, length, n_records)`` for the delivered per-contig counts.
CONTIGS = [
    ("1", 4_000_000, 4000),
    ("5", 3_000_000, 3000),
    ("7", 3_000_000, 3000),
    ("9", 3_000_000, 2004),
    # A non-canonical contig, which the canonical predicate must drop everywhere.
    ("GL000009.2", 20_000, 1),
]

#: ``(gene, n_all, n_pass)`` and ``(chrom, start, end, name)`` — the panel side.
GENES = [("ORDINARY", 1000, 985), ("FLAT", 500, 495), ("OUTLIER", 12, 6), ("SMALLBIN", 1000, 980)]
PANEL_BED = [
    ("chr1", 0, 1_000_000, "ORDINARY"),
    ("chr5", 0, 1_000_000, "FLAT"),
    ("chr7", 0, 100_000, "OUTLIER"),
    ("chr9", 0, 1_000_000, "SMALLBIN"),
]


def values(rows) -> str:
    return ", ".join("(" + ", ".join(repr(v) for v in row) + ")" for row in rows)


@pytest.fixture()
def warehouse():
    connection = duckdb.connect()
    connection.execute("CREATE SCHEMA src")
    # `pos` is text: the raw layer is lossless all-text, and the derivation has to cast it
    # itself. A numeric column here would hide a missing CAST.
    connection.execute(f"""
        CREATE TABLE src.variants_raw AS
        SELECT row_number() OVER ()                                    AS line_no,
               s.chrom,
               CAST(s.mb * {BIN_BP} + t.i AS VARCHAR)                  AS pos,
               CASE WHEN t.i < s.pass_n THEN 'PASS' ELSE 'MQ40' END    AS filter
        FROM (VALUES {values(BINS)}) AS s(chrom, mb, n, pass_n),
             range(0, 2000) AS t(i)
        WHERE t.i < s.n
    """)
    # One record on a non-canonical contig, which must never reach a background.
    connection.execute("INSERT INTO src.variants_raw VALUES (999999, 'GL000009.2', '100', 'PASS')")
    connection.execute(
        f"CREATE TABLE src.contig_counts AS SELECT * FROM (VALUES {values(CONTIGS)}) "
        f"AS t(chrom, length, n_records)"
    )
    connection.execute(
        f"CREATE TABLE src.panel_variant_counts AS SELECT * FROM (VALUES {values(GENES)}) "
        f"AS t(gene, n_all, n_pass)"
    )
    connection.execute(
        f"CREATE TABLE src.mva_panel_grch38 AS SELECT * FROM (VALUES {values(PANEL_BED)}) "
        f'AS t(chrom, start, "end", name)'
    )
    yield connection
    connection.close()


def run(connection, name: str) -> list[dict]:
    relation = connection.sql(resolve(by_name(name).sql, "src"))
    columns = relation.columns
    return [dict(zip(columns, row, strict=True)) for row in relation.fetchall()]


@pytest.fixture()
def genes(warehouse) -> dict[str, dict]:
    return {row["gene"]: row for row in run(warehouse, "panel_gene_background")}


def approx(value, expected):
    return float(value) == pytest.approx(expected, abs=0.011)


class TestTheJoin:
    def test_every_panel_gene_gets_a_row(self, genes):
        assert set(genes) == {"ORDINARY", "FLAT", "OUTLIER", "SMALLBIN"}

    def test_the_emitted_contig_stays_chr_prefixed_as_the_panel_spells_it(self, genes):
        assert genes["OUTLIER"]["chrom"] == "chr7"

    def test_the_chr_prefix_is_stripped_only_to_reach_the_bare_callset_side(self, genes):
        """A failed bridge shows up as a NULL background, not as a wrong number."""
        assert genes["OUTLIER"]["contig_n_bins"] == 3
        assert approx(genes["OUTLIER"]["contig_bin_mean_density"], 1000.0)

    def test_a_non_canonical_contig_never_reaches_a_background(self, genes):
        """13 canonical windows exist; the GL contig's record must not add a 14th."""
        assert genes["ORDINARY"]["genome_n_bins"] == len(BINS)


class TestTheGeneNumbers:
    def test_density_is_records_over_the_interval_in_megabases(self, genes):
        assert approx(genes["OUTLIER"]["gene_variants_per_mb"], 120.0)

    def test_pass_share_is_the_genes_own_pass_over_all(self, genes):
        assert approx(genes["OUTLIER"]["gene_pct_pass"], 50.0)

    def test_the_contig_density_divides_by_the_reference_length(self, genes):
        """From `contig_counts`, not from the windows: unsequenced stretches must count."""
        assert approx(genes["SMALLBIN"]["contig_variants_per_mb"], 668.0)

    def test_the_genome_density_pools_every_canonical_contig(self, genes):
        assert approx(genes["ORDINARY"]["genome_variants_per_mb"], 923.4)


class TestTheBackground:
    def test_the_window_mean_and_spread_are_the_ones_computed_by_hand(self, genes):
        row = genes["ORDINARY"]
        assert approx(row["contig_bin_mean_density"], 1000.0)
        assert approx(row["contig_bin_sd_density"], 163.3)
        assert approx(row["contig_bin_mean_pct_pass"], 98.5)
        assert approx(row["contig_bin_sd_pct_pass"], 0.58)

    def test_one_window_is_one_megabase_so_a_window_count_is_a_density(self, genes):
        """The comparison is only valid because the bin width is exactly 1 Mb."""
        assert BIN_BP == 1_000_000
        assert f"// {BIN_BP}" in by_name("panel_gene_background").sql

    def test_a_thin_window_is_kept_in_the_density_background(self, genes):
        """An empty stretch is a real property of the reference, never a missing row."""
        assert genes["SMALLBIN"]["contig_n_bins"] == 3
        assert approx(genes["SMALLBIN"]["contig_bin_mean_density"], 668.0)

    def test_a_thin_window_is_dropped_from_the_pass_share_background(self, genes):
        """Including the 0 %-of-four window would drag the mean from 98.0 to 65.3."""
        assert MIN_BIN_N_FOR_PASS == 100
        assert approx(genes["SMALLBIN"]["contig_bin_mean_pct_pass"], 98.0)
        assert approx(genes["SMALLBIN"]["contig_bin_sd_pct_pass"], 1.41)


class TestTheZScores:
    def test_a_gene_sitting_on_the_mean_scores_zero_on_both_axes(self, genes):
        row = genes["ORDINARY"]
        assert approx(row["z_density_vs_contig"], 0.0)
        assert approx(row["z_pass_vs_contig"], 0.0)

    def test_the_density_z_is_the_distance_in_window_standard_deviations(self, genes):
        """(120 - 1000) / 100."""
        assert approx(genes["OUTLIER"]["z_density_vs_contig"], -8.8)

    def test_the_pass_z_is_the_same_arithmetic_on_the_pass_share(self, genes):
        """(50 - 98) / 1."""
        assert approx(genes["OUTLIER"]["z_pass_vs_contig"], -48.0)

    def test_the_genome_z_is_measured_against_every_window_not_just_the_contigs(self, genes):
        contig = float(genes["OUTLIER"]["z_density_vs_contig"])
        genome = float(genes["OUTLIER"]["z_density_vs_genome"])
        assert genome != contig
        assert genome < -Z_NOTABLE

    def test_a_background_with_no_spread_yields_null_rather_than_zero(self, genes):
        """Contig 5's windows are identical; dividing by that spread is not a z of 0."""
        row = genes["FLAT"]
        assert row["contig_bin_sd_density"] == 0
        assert row["z_density_vs_contig"] is None
        assert row["z_pass_vs_contig"] is None

    def test_the_genome_axis_still_scores_a_gene_whose_contig_is_flat(self, genes):
        assert genes["FLAT"]["z_density_vs_genome"] is not None

    def test_the_most_deviant_gene_is_ordered_first(self, warehouse):
        rows = run(warehouse, "panel_gene_background")
        assert rows[0]["gene"] == "OUTLIER"


class TestRegistry:
    def test_the_background_derivation_is_in_the_one_registry(self):
        names = {item.name for item in DERIVATIONS}
        assert {item.name for item in BACKGROUND_DERIVATIONS} <= names

    def test_it_reads_the_ingest_schema_only(self):
        """A derivation may not read `results`: `pg-derive` has no ordering guarantee, so
        the window aggregate is recomputed here rather than read from
        `results.variant_density_bins`."""
        assert "results." not in by_name("panel_gene_background").sql

    def test_it_bins_the_same_way_variant_density_bins_does(self):
        """The duplicated aggregate is only defensible while the two agree."""
        mine = by_name("panel_gene_background").sql
        theirs = by_name("variant_density_bins").sql
        for fragment in (
            f"CAST(pos AS BIGINT) // {BIN_BP}",
            "length(chrom) <= 2",
            "count(*) FILTER (WHERE filter = 'PASS')",
        ):
            assert fragment in mine, fragment
            assert fragment.replace(str(BIN_BP), "1000000") in theirs, fragment

    def test_it_declares_what_it_depends_on(self):
        assert by_name("panel_gene_background").depends_on == (
            "variants_raw",
            "contig_counts",
            "panel_variant_counts",
            "mva_panel_grch38",
        )

    def test_the_question_says_a_pass_z_is_about_callability_not_pathogenicity(self):
        """The caveat travels with the table, not only with the chart that draws it."""
        question = by_name("panel_gene_background").question
        assert "callability" in question and "pathogenicity" in question
