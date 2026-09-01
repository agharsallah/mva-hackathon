"""The second wave of observed-vs-expected comparisons.

Two halves, both hermetic — no network, no database.

* **The committed norms table** is read straight off disk, because the thing worth
  asserting about a hand-curated citation file is that it stays a citation file: unique
  metric ids, a low ≤ high band, and a PMID or DOI on every single row. A norm that
  arrives without a source is the one failure mode this repository cannot tolerate.
* **The new observations** run their real SQL — the fragments in
  :mod:`mva.warehouse.analysis_reference_qc`, spliced into the real
  ``qc_observed_expected`` derivation — against a miniature DuckDB warehouse whose numbers
  are chosen so every arithmetic mistake changes an answer.

The miniature warehouse is deliberately *not* the one in ``tests/test_warehouse_reference``:
these observations need an SN multiallelic row, a ``1/2`` genotype bucket, an indel
histogram wider than two bins and a non-PASS record carrying an rsID, none of which that
fixture has.
"""

import csv
import re
from pathlib import Path

import duckdb
import pytest

from mva.warehouse.analysis import by_name
from mva.warehouse.analysis_reference_qc import EXTRA_OBSERVED
from mva.warehouse.derivation import resolve

#: The committed, hand-curated norms table this wave extends.
NORMS = Path(__file__).resolve().parents[1] / "ressources" / "reference" / "qc_norms.tsv"

#: A citation is only a citation if it can be followed. Every row must carry one of these.
CITATION = re.compile(r"PMID\s*\d{6,9}|DOI\s*10\.\d{4,9}/", re.IGNORECASE)


@pytest.fixture(scope="module")
def norms() -> list[dict[str, str]]:
    with NORMS.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


class TestTheCommittedNormsTable:
    def test_every_row_carries_a_pmid_or_a_doi(self, norms):
        for row in norms:
            assert CITATION.search(row["source"]), row["metric"]

    def test_every_row_says_which_sentence_the_number_came_from(self, norms):
        for row in norms:
            assert len(row["basis"]) > 40, row["metric"]
            assert row["url"].startswith("http"), row["metric"]

    def test_a_metric_id_is_a_key(self, norms):
        ids = [row["metric"] for row in norms]
        assert len(ids) == len(set(ids))

    def test_the_band_is_never_inverted(self, norms):
        for row in norms:
            low, high = float(row["expected_low"]), float(row["expected_high"])
            assert low <= high, row["metric"]

    def test_every_row_names_the_assay_it_applies_to(self, norms):
        # A Ts/Tv measured genome-wide and one measured in coding regions are different
        # numbers; a row that does not say which is a trap, not a norm.
        for row in norms:
            assert row["applies_to"].strip(), row["metric"]
            assert row["unit"].strip(), row["metric"]


@pytest.fixture(scope="module")
def warehouse():
    """A DuckDB schema shaped for the *new* observations, with adversarial numbers.

    Counts are picked so that no two derived quantities collide: the IDD histogram totals
    100 alleles while SN reports 40 indel *records*, so a 1–2 bp share computed against
    the wrong denominator is off by a factor of 2.5 and cannot pass by luck.
    """
    connection = duckdb.connect()
    connection.execute("CREATE SCHEMA src")
    connection.execute("""
        CREATE TABLE src.stats_summary AS SELECT * FROM (VALUES
            (1, 'SN' || chr(9) || '0' || chr(9) || 'number of records:'
                || chr(9) || '200'),
            (2, 'SN' || chr(9) || '0' || chr(9) || 'number of SNPs:' || chr(9) || '160'),
            (3, 'SN' || chr(9) || '0' || chr(9) || 'number of indels:' || chr(9) || '40'),
            (4, 'SN' || chr(9) || '0' || chr(9) || 'number of multiallelic sites:'
                || chr(9) || '10'),
            (5, 'TSTV' || chr(9) || '0' || chr(9) || '6' || chr(9) || '3'
                || chr(9) || '2.00'),
            -- 100 indel alleles: 30 + 20 at |1|, 10 + 5 at |2|, the rest longer.
            (6, 'IDD' || chr(9) || '0' || chr(9) || '1'  || chr(9) || '30'),
            (7, 'IDD' || chr(9) || '0' || chr(9) || '-1' || chr(9) || '20'),
            (8, 'IDD' || chr(9) || '0' || chr(9) || '2'  || chr(9) || '10'),
            (9, 'IDD' || chr(9) || '0' || chr(9) || '-2' || chr(9) || '5'),
            (10, 'IDD' || chr(9) || '0' || chr(9) || '3' || chr(9) || '25'),
            (11, 'IDD' || chr(9) || '0' || chr(9) || '-9' || chr(9) || '10'))
        AS t(line_no, line);

        CREATE TABLE src.filter_gt_counts AS SELECT * FROM (VALUES
            ('genotype counts', '0/1', 120),
            ('genotype counts', '1/1', 70),
            ('genotype counts', '1/2', 10),
            ('FILTER counts',   'PASS', 150))
        AS t(section, label, count);

        CREATE TABLE src.profile_scalars AS SELECT * FROM (VALUES
            ('est_raw_coverage_x', '40.0'))
        AS t(key, value);

        -- Ten records, arranged so all three dbSNP rates differ:
        --   every record        6 of 10 carry an rsID  = 60.00%
        --   PASS only           5 of  8                = 62.50%
        --   PASS biallelic SNV  5 of  6                = 83.33%
        -- The 1 bp insertion and the comma-packed multi-allelic ALT are the two records
        -- the SNV rate must exclude, and both are rsID-less PASS records so excluding
        -- them moves the answer.
        CREATE TABLE src.variants_raw AS SELECT * FROM (VALUES
            ('1', '10', 'rs1', 'A', 'G',   '9', 'PASS',    'GT', '0/1'),
            ('1', '20', 'rs2', 'A', 'G',   '9', 'PASS',    'GT', '0/1'),
            ('1', '30', 'rs3', 'A', 'G',   '9', 'PASS',    'GT', '1/1'),
            ('1', '40', 'rs4', 'A', 'G',   '9', 'PASS',    'GT', '0/1'),
            ('1', '50', 'rs5', 'A', 'G',   '9', 'PASS',    'GT', '0/1'),
            ('1', '60', '.',   'A', 'G',   '9', 'PASS',    'GT', '0/1'),
            ('1', '65', '.',   'A', 'AT',  '9', 'PASS',    'GT', '0/1'),
            ('1', '68', '.',   'A', 'G,T', '9', 'PASS',    'GT', '1/2'),
            ('1', '70', 'rs7', 'A', 'G',   '9', 'LowQual', 'GT', '0/1'),
            ('1', '80', '.',   'A', 'G',   '9', 'MQ40',    'GT', '0/1'))
        AS t(chrom, pos, id, ref, alt, qual, filter, format, sample_call);
    """)
    return connection


def rows(warehouse, norms_sql: str) -> dict[str, dict]:
    """Run the real derivation against a norms table built row by row for one test."""
    warehouse.execute("DROP TABLE IF EXISTS src.qc_norms")
    warehouse.execute(f"CREATE TABLE src.qc_norms AS {norms_sql}")
    sql = resolve(by_name("qc_observed_expected").sql, "src")
    found = warehouse.sql(sql)
    columns = [name for name in found.columns]
    return {row[0]: dict(zip(columns, row)) for row in found.fetchall()}


def norm(metric: str, low: float, high: float) -> str:
    return (f"SELECT '{metric}' AS metric, {low} AS expected_low, {high} AS expected_high,"
            f" 'unit' AS unit, 'WGS' AS applies_to, 'src PMID 12345678' AS source")


ALL_NEW = " UNION ALL ".join([
    norm("snv_to_indel_ratio", 4.0, 4.5),
    norm("het_count_per_genome", 100, 200),
    norm("multiallelic_site_fraction", 1.0, 2.0),
    norm("indel_length_1_2bp_share", 60.0, 70.0),
    norm("dbsnp_membership_rate_pass_only", 99.0, 99.9),
    norm("dbsnp_membership_rate_pass_snv", 89.89, 89.89),
    norm("dbsnp_membership_rate_per_genome", 99.0, 99.9),
])


@pytest.fixture(scope="module")
def found(warehouse) -> dict[str, dict]:
    """Every new metric graded at once, against bands chosen to exercise both verdicts."""
    return rows(warehouse, ALL_NEW)


class TestTheNewObservations:
    def test_snvs_per_indel_divides_the_two_sn_counts(self, found):
        assert found["snv_to_indel_ratio"]["observed"] == pytest.approx(160 / 40)
        assert found["snv_to_indel_ratio"]["verdict"] == "within"

    def test_a_multiallelic_call_counts_as_heterozygous(self, found):
        # 120 (0/1) + 10 (1/2). Both copies of a 1/2 site carry a different variant, so
        # the site is a heterozygote — dropping it undercounts by the multiallelic count.
        assert found["het_count_per_genome"]["observed"] == pytest.approx(130)

    def test_the_multiallelic_fraction_is_of_records_not_of_snps(self, found):
        assert found["multiallelic_site_fraction"]["observed"] == pytest.approx(5.0)
        assert found["multiallelic_site_fraction"]["verdict"] == "above"

    def test_the_short_indel_share_uses_the_histogram_total_not_the_sn_count(self, found):
        # (30 + 20 + 10 + 5) / 100 = 65%. Against SN's 40 indel records it would be 162%.
        assert found["indel_length_1_2bp_share"]["observed"] == pytest.approx(65.0)
        assert found["indel_length_1_2bp_share"]["verdict"] == "within"

    def test_the_short_indel_share_counts_both_directions_of_the_histogram(self, warehouse):
        # An insertion-only reading would give (30 + 10) / 100 = 40%, not 65%.
        assert rows(warehouse, norm("indel_length_1_2bp_share", 0, 100)
                    )["indel_length_1_2bp_share"]["observed"] != pytest.approx(40.0)

    def test_pass_only_dbsnp_membership_ignores_the_vetoed_records(self, found):
        assert found["dbsnp_membership_rate_pass_only"]["observed"] == \
            pytest.approx(62.5)             # 5 of 8 PASS records carry an rsID
        assert found["dbsnp_membership_rate_per_genome"]["observed"] == \
            pytest.approx(60.0)             # 6 of 10 records overall

    def test_the_snv_rate_drops_the_indel_and_the_multiallelic_record(self, found):
        # 5 of 6 PASS biallelic SNVs. The 1 bp insertion and the comma-packed ALT are
        # both PASS and both rsID-less, so counting either would pull the rate down.
        assert found["dbsnp_membership_rate_pass_snv"]["observed"] == \
            pytest.approx(500 / 6)
        assert found["dbsnp_membership_rate_pass_snv"]["verdict"] == "below"

    def test_the_three_dbsnp_rates_are_separate_measurements(self, found):
        rates = {found[m]["observed"] for m in (
            "dbsnp_membership_rate_per_genome", "dbsnp_membership_rate_pass_only",
            "dbsnp_membership_rate_pass_snv")}
        assert len(rates) == 3

    def test_every_new_row_says_where_its_observation_came_from(self, found):
        for metric in ("snv_to_indel_ratio", "het_count_per_genome",
                       "multiallelic_site_fraction", "indel_length_1_2bp_share",
                       "dbsnp_membership_rate_pass_only",
                       "dbsnp_membership_rate_pass_snv"):
            assert found[metric]["observed_from"], metric
            assert found[metric]["label"], metric


class TestTheSqlAndTheTsvAgreeOnSpelling:
    """A metric id is the join key. A typo on either side is a silently missing row."""

    def measured(self) -> set[str]:
        return set(re.findall(r"UNION ALL SELECT '([a-z0-9_]+)'", EXTRA_OBSERVED))

    def test_the_new_observations_are_the_ones_this_wave_declared(self):
        assert self.measured() == {
            "snv_to_indel_ratio", "het_count_per_genome", "multiallelic_site_fraction",
            "indel_length_1_2bp_share", "dbsnp_membership_rate_pass_only",
            "dbsnp_membership_rate_pass_snv"}

    def test_each_observation_meant_to_be_graded_has_a_row_in_the_committed_tsv(self, norms):
        committed = {row["metric"] for row in norms}
        assert {"snv_to_indel_ratio", "het_count_per_genome",
                "dbsnp_membership_rate_pass_only",
                "dbsnp_membership_rate_pass_snv"} <= committed

    def test_the_deliberately_ungraded_observations_have_no_norm(self, norms):
        # Measurable, unnormed: no citable single-sample range was found for either, so
        # neither is graded. Adding one here is what would turn it into a table row.
        committed = {row["metric"] for row in norms}
        assert "multiallelic_site_fraction" not in committed
        assert "indel_length_1_2bp_share" not in committed

    def test_a_cohort_scale_norm_is_present_but_deliberately_unjoinable(self, norms):
        # The 3,202-sample multiallelic fraction is cited so nobody grades a one-sample
        # figure against it. Its id must therefore NOT match the observation's id.
        committed = {row["metric"] for row in norms}
        assert "multiallelic_locus_fraction_cohort" in committed
        assert "multiallelic_locus_fraction_cohort" not in self.measured()


class TestMeasurableButUnnormed:
    def test_an_observation_with_no_citable_range_emits_no_row(self, warehouse):
        # The whole discipline of the table: the measurement exists in the SQL, and the
        # row appears only once a citable band is committed. Nothing is graded against a
        # band nobody published.
        found = rows(warehouse, norm("snv_to_indel_ratio", 4.0, 4.5))
        assert set(found) == {"snv_to_indel_ratio"}
        assert "indel_length_1_2bp_share" not in found

    def test_adding_only_the_norm_is_what_turns_a_measurement_into_a_row(self, warehouse):
        before = rows(warehouse, norm("snv_to_indel_ratio", 4.0, 4.5))
        after = rows(warehouse, norm("snv_to_indel_ratio", 4.0, 4.5) + " UNION ALL "
                     + norm("multiallelic_site_fraction", 1.0, 2.0))
        assert set(after) - set(before) == {"multiallelic_site_fraction"}


class TestTheOldObservationsStillWork:
    def test_splicing_the_new_fragments_did_not_disturb_the_original_rows(self, warehouse):
        found = rows(warehouse, " UNION ALL ".join([
            norm("tstv_genome_wide", 2.0, 2.1),
            norm("mean_coverage_wgs", 35.0, 35.0),
            norm("het_hom_ratio_eur", 1.5, 1.6),
        ]))
        assert found["tstv_genome_wide"]["observed"] == pytest.approx(2.00)
        assert found["tstv_genome_wide"]["verdict"] == "within"
        assert found["mean_coverage_wgs"]["observed"] == pytest.approx(40.0)
        assert found["mean_coverage_wgs"]["verdict"] == "above"
        # The *ratio* rows stay 0/1-over-1/1, matching how the literature defines them —
        # only the new *count* row folds 1/2 in.
        assert found["het_hom_ratio_eur"]["observed"] == pytest.approx(120 / 70)
