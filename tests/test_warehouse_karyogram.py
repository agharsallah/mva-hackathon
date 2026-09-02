"""The `baf_bins` derivation, run against a miniature DuckDB warehouse.

Hermetic in the style of `tests/test_warehouse_reference.py`: the real SQL, the real
registry lookup, a handful of rows built in memory. No network, no database.

Positions here are fabricated and chosen to exercise a rule each — they are shapes, not
measurements.
"""

import duckdb
import pytest

from mva.warehouse.analysis import DERIVATIONS, by_name
from mva.warehouse.analysis_karyogram import BIN_BP, KARYOGRAM_DERIVATIONS, LOW_CONFIDENCE_N_HET
from mva.warehouse.derivation import resolve


@pytest.fixture()
def warehouse():
    """One `variants_raw` covering every branch the derivation has to take."""
    connection = duckdb.connect()
    connection.execute("CREATE SCHEMA src")
    connection.execute("""
        CREATE TABLE src.variants_raw AS SELECT * FROM (VALUES
            -- chrom 1, bin 0: two clean heterozygous PASS calls, 0.50 and 0.50
            (1, '1', '100',     '.', 'A', 'G', '900', 'PASS',
             'GT:AD:DP:GQ', '0/1:20,20:40:99'),
            (2, '1', '200',     '.', 'C', 'T', '900', 'PASS',
             'GT:AD:DP:GQ', '0/1:15,15:30:99'),
            -- same bin: not PASS, must not count
            (3, '1', '300',     '.', 'A', 'T', '30',  'LowQual',
             'GT:AD:DP',    '0/1:5,25:30'),
            -- same bin: homozygous ALT, must not count
            (4, '1', '400',     '.', 'A', 'C', '900', 'PASS',
             'GT:AD:DP',    '1/1:0,40:40'),
            -- same bin: multi-allelic, three depths, no single ALT -> skipped
            (5, '1', '500',     '.', 'G', 'A,C', '900', 'PASS',
             'GT:AD:DP',    '1/2:5,7,9:21'),
            -- same bin: AD absent from FORMAT altogether -> skipped
            (6, '1', '600',     '.', 'A', 'G', '900', 'PASS',
             'GT:DP',       '0/1:44'),
            -- same bin: AD present but unparsable -> skipped
            (7, '1', '700',     '.', 'A', 'G', '900', 'PASS',
             'GT:AD:DP',    '0/1:.,.:12'),
            -- chrom 1, bin 2: FORMAT in a different order, so GT is not first
            (8, '1', '2000100', '.', 'A', 'G', '900', 'PASS',
             'DP:GT:AD',    '80:0/1:24,56'),
            -- chrom 1, bin 2: no DP key at all -> depth falls back to AD ref+alt
            (9, '1', '2000200', '.', 'A', 'G', '900', 'PASS',
             'GT:AD',       '0/1:30,70'),
            -- a non-canonical contig, longer than two characters -> excluded
            (10, 'GL000009.2', '100', '.', 'A', 'G', '900', 'PASS',
             'GT:AD:DP',    '0/1:10,10:20'),
            -- chrom X, bin 0: one call only, so the bin is low confidence
            (11, 'X', '900',    '.', 'A', 'G', '900', 'PASS',
             'GT:AD:DP',    '0/1:9,11:20'))
        AS t(line_no, chrom, pos, id, ref, alt, qual, filter, format, sample_call);
    """)
    yield connection
    connection.close()


def run(connection, name: str) -> list[dict]:
    relation = connection.sql(resolve(by_name(name).sql, "src"))
    columns = relation.columns
    return [dict(zip(columns, row, strict=True)) for row in relation.fetchall()]


@pytest.fixture()
def bins(warehouse) -> dict[tuple[str, int], dict]:
    return {(row["chrom"], row["mb"]): row for row in run(warehouse, "baf_bins")}


class TestSelection:
    def test_only_heterozygous_pass_calls_with_a_usable_ad_are_counted(self, bins):
        """Of the seven records in chr1 bin 0, five fail a rule and two survive."""
        assert bins[("1", 0)]["n_het"] == 2

    def test_a_non_canonical_contig_never_produces_a_bin(self, bins):
        assert not any(chrom.startswith("GL") for chrom, _ in bins)

    def test_the_canonical_contigs_that_do_have_calls_all_appear(self, bins):
        assert set(bins) == {("1", 0), ("1", 2), ("X", 0)}


class TestBinning:
    def test_the_bin_is_integer_megabases_not_a_fraction(self, bins):
        """Float division would give one group per position instead of one per Mb."""
        assert all(float(mb).is_integer() for _, mb in bins)

    def test_a_position_past_the_first_megabase_lands_in_its_own_bin(self, bins):
        assert bins[("1", 2)]["n_het"] == 2
        assert BIN_BP == 1_000_000


class TestTheNumbers:
    def test_mean_vaf_is_alt_over_ref_plus_alt(self, bins):
        """chr1 bin 2 holds 56/80 = 0.70 and 70/100 = 0.70."""
        assert float(bins[("1", 2)]["mean_vaf"]) == pytest.approx(0.70)

    def test_vaf_deviation_is_signed_distance_from_the_half(self, bins):
        assert float(bins[("1", 2)]["vaf_deviation"]) == pytest.approx(0.20)
        assert float(bins[("1", 0)]["vaf_deviation"]) == pytest.approx(0.0)

    def test_the_pct_in_band_counts_only_the_calls_inside_0_40_to_0_60(self, bins):
        assert float(bins[("1", 0)]["pct_in_0_40_0_60"]) == pytest.approx(100.0)
        assert float(bins[("1", 2)]["pct_in_0_40_0_60"]) == pytest.approx(0.0)

    def test_the_median_is_reported_next_to_the_mean(self, bins):
        assert float(bins[("1", 0)]["median_vaf"]) == pytest.approx(0.5)

    def test_a_single_call_bin_has_no_sample_spread_rather_than_zero(self, bins):
        """stddev_samp of one value is undefined; reporting 0.0 would claim tightness."""
        assert bins[("X", 0)]["sd_vaf"] is None

    def test_mean_depth_prefers_the_records_own_dp_field(self, bins):
        """chr1 bin 0 carries DP 40 and 30 — the AD sums are the same here, so bin 2
        is the discriminating case."""
        assert float(bins[("1", 0)]["mean_dp"]) == pytest.approx(35.0)

    def test_depth_falls_back_to_the_allele_depths_when_dp_is_absent(self, bins):
        """chr1 bin 2: one record has DP 80, the other has no DP key and AD 30,70."""
        assert float(bins[("1", 2)]["mean_dp"]) == pytest.approx(90.0)


class TestLowConfidence:
    def test_a_thin_bin_is_flagged_rather_than_dropped(self, bins):
        assert bins[("X", 0)]["low_confidence"] is True
        assert bins[("X", 0)]["n_het"] == 1

    def test_the_threshold_is_the_declared_constant(self, warehouse):
        assert LOW_CONFIDENCE_N_HET == 20
        assert f"< {LOW_CONFIDENCE_N_HET}" in by_name("baf_bins").sql


class TestFormatParsing:
    def test_gt_is_read_from_the_records_own_keys_not_by_position(self, bins):
        """Record 8 is `DP:GT:AD`. Assuming GT is first would read the depth as a
        genotype and drop the call entirely."""
        assert bins[("1", 2)]["n_het"] == 2

    def test_the_phased_spelling_is_deliberately_not_admitted(self, warehouse):
        """This callset is single-sample and unphased, so `0|1` never occurs. Widening
        the predicate silently would be a change no data justifies."""
        assert "'0/1'" in by_name("baf_bins").sql
        assert "0|1" not in by_name("baf_bins").sql


class TestRegistry:
    def test_the_karyogram_derivation_is_in_the_one_registry(self):
        names = {item.name for item in DERIVATIONS}
        assert {item.name for item in KARYOGRAM_DERIVATIONS} <= names

    def test_it_reads_the_ingest_schema_only(self):
        """A derivation may not read `results`: `pg-derive` has no ordering guarantee."""
        assert "results." not in by_name("baf_bins").sql

    def test_it_declares_what_it_depends_on(self):
        assert by_name("baf_bins").depends_on == ("variants_raw",)
