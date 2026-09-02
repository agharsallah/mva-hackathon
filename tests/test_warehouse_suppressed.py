"""The suppressed-call derivations, run against a miniature DuckDB warehouse.

Hermetic: no server, no network. The real SQL runs over a handful of rows chosen to
exercise every branch — a ``;``-joined FILTER value, a multi-allelic non-PASS record, a
record VEP never annotated, a homozygous suppressed record, a record outside every panel
interval, and a contig the panel does not name.

Positions here are three-digit counters. They are not coordinates and the repo commits
none.
"""

import duckdb
import pytest

from mva.warehouse.analysis import by_name
from mva.warehouse.analysis_suppressed import PANEL_FILTER_CENSUS, PANEL_SUPPRESSED
from mva.warehouse.derivation import resolve


@pytest.fixture()
def warehouse():
    """One tiny row set per table the two derivations read."""
    connection = duckdb.connect()
    connection.execute("CREATE SCHEMA src")
    connection.execute("""
        CREATE TABLE src.mva_panel_grch38 AS SELECT * FROM (VALUES
            ('chr15', 100, 900, 'BUB1B'),
            ('chr5',  100, 900, 'TRIP13'))
        AS t(chrom, start, "end", name);

        CREATE TABLE src.panel_annotations AS SELECT * FROM (VALUES
            ('15', 500, 'G', 'A', 'rs1', 'BUB1B', 'intron_variant', 'MODIFIER',
             0.22, 0.31, NULL),
            -- the two ALTs of the multi-allelic record: MODERATE must win the pick
            ('15', 700, 'G', 'A', NULL, 'BUB1B', 'intron_variant', 'MODIFIER',
             0.4, 0.5, NULL),
            ('15', 700, 'G', 'C', NULL, 'BUB1B', 'missense_variant', 'MODERATE',
             NULL::DOUBLE, NULL::DOUBLE, 'Uncertain_significance'),
            ('5',  300, 'A', 'G', NULL, 'TRIP13', 'missense_variant', 'MODERATE',
             0.0001, 0.0002, NULL))
        AS t(chrom, pos, ref, alt, rsid, gene, consequence, impact,
             gnomad_af, gnomad_af_grpmax, clin_sig);

        CREATE TABLE src.variants_raw AS SELECT * FROM (VALUES
            -- suppressed het, annotated, FORMAT in the usual order
            ('15', '500', 'G', 'A',   '19.8',  'LowQual;QD2',
             'GT:AD:DP:GQ', '0/1:8,5:13:57'),
            -- suppressed multi-allelic: three depths, so vaf is undefined
            ('15', '700', 'G', 'A,C', '52.8',  'MQ40',
             'GT:AD:DP:GQ', '1/2:5,7,9:21:80'),
            -- suppressed homozygous ALT: kept, but it is not half a compound het
            ('15', '760', 'T', 'G',   '11.2',  'LowQual',
             'GT:AD:DP',    '1/1:1,3:4'),
            -- PASS: counted by the census, absent from the record table
            ('15', '800', 'A', 'G',   '900.0', 'PASS',
             'GT:AD:DP',    '0/1:20,18:38'),
            -- suppressed het VEP never saw
            ('15', '820', 'C', 'T',   '25.7',  'MQ40',
             'GT:AD:DP',    '0/1:15,2:17'),
            -- FORMAT in a different order: every field is found by name
            ('5',  '300', 'A', 'G',   '62.8',  'MQ40',
             'DP:GT:GQ:AD', '24:0/1:91:18,6'),
            ('5',  '310', 'A', 'T',   '900.0', 'PASS',
             'GT:AD:DP',    '0/1:10,10:20'),
            -- outside every panel interval
            ('15', '950', 'A', 'G',   '20.0',  'MQ40',
             'GT:AD:DP',    '0/1:10,10:20'),
            -- a contig the panel does not name at all
            ('7',  '500', 'A', 'G',   '20.0',  'MQ40',
             'GT:AD:DP',    '0/1:10,10:20'))
        AS t(chrom, pos, ref, alt, qual, filter, format, sample_call);
    """)
    yield connection
    connection.close()


def run(connection, derivation) -> list[dict]:
    relation = connection.sql(resolve(derivation.sql, "src"))
    return [dict(zip(relation.columns, row)) for row in relation.fetchall()]


@pytest.fixture()
def rows(warehouse) -> list[dict]:
    return run(warehouse, PANEL_SUPPRESSED)


@pytest.fixture()
def census(warehouse) -> list[dict]:
    return run(warehouse, PANEL_FILTER_CENSUS)


def at(rows: list[dict], pos: int) -> dict:
    return next(r for r in rows if r["pos"] == pos)


class TestRegistration:
    def test_both_derivations_are_in_the_one_registry(self):
        assert by_name("panel_suppressed") is PANEL_SUPPRESSED
        assert by_name("panel_filter_census") is PANEL_FILTER_CENSUS

    def test_each_declares_every_table_it_reads(self):
        assert set(PANEL_SUPPRESSED.depends_on) == {
            "mva_panel_grch38",
            "variants_raw",
            "panel_annotations",
        }
        assert set(PANEL_FILTER_CENSUS.depends_on) == {"mva_panel_grch38", "variants_raw"}


class TestMembership:
    def test_only_non_pass_records_inside_a_panel_gene_survive(self, rows):
        assert sorted(r["pos"] for r in rows) == [300, 500, 700, 760, 820]

    def test_a_pass_record_is_not_a_suppressed_one(self, rows):
        assert not [r for r in rows if r["pos"] == 800]

    def test_a_record_past_the_interval_end_is_excluded(self, rows):
        assert not [r for r in rows if r["pos"] == 950]

    def test_a_contig_the_panel_does_not_name_is_never_read(self, rows):
        assert {r["chrom"] for r in rows} == {"15", "5"}

    def test_the_gene_label_comes_from_the_interval_it_falls_in(self, rows):
        assert at(rows, 300)["gene"] == "TRIP13"
        assert at(rows, 500)["gene"] == "BUB1B"

    def test_the_contig_stays_bare_as_the_callset_spells_it(self, rows):
        assert all(not r["chrom"].startswith("chr") for r in rows)

    def test_a_suppressed_homozygous_record_is_kept_and_marked_not_het(self, rows):
        """It is still evidence about the locus; it is simply not half a pair."""
        row = at(rows, 760)
        assert row["gt"] == "1/1" and row["is_het"] is False


class TestFilterValue:
    def test_a_semicolon_joined_value_is_carried_verbatim(self, rows):
        """Splitting it would turn one record that failed two tests into two records."""
        assert at(rows, 500)["filter"] == "LowQual;QD2"

    def test_the_filter_string_is_never_normalised_into_reasons(self, rows):
        assert sorted(r["filter"] for r in rows) == [
            "LowQual",
            "LowQual;QD2",
            "MQ40",
            "MQ40",
            "MQ40",
        ]


class TestGenotypeEvidence:
    def test_fields_are_located_by_name_not_by_position(self, rows):
        """The TRIP13 record spells FORMAT as DP:GT:GQ:AD."""
        row = at(rows, 300)
        assert (row["gt"], row["dp"], row["gq"]) == ("0/1", 24, 91)
        assert (row["ad_ref"], row["ad_alt"]) == (18, 6)

    def test_a_biallelic_record_reports_alt_over_ref_plus_alt(self, rows):
        assert at(rows, 500)["vaf"] == pytest.approx(5 / 13, abs=1e-4)

    def test_a_multiallelic_record_has_no_single_alternate_so_vaf_is_null(self, rows):
        row = at(rows, 700)
        assert row["ad_ref"] is None and row["ad_alt"] is None and row["vaf"] is None

    def test_qual_is_a_number_not_the_text_the_raw_layer_stores(self, rows):
        assert at(rows, 500)["qual"] == pytest.approx(19.8)


class TestAnnotationJoin:
    def test_an_annotated_record_carries_its_consequence_and_frequency(self, rows):
        row = at(rows, 500)
        assert row["annotated"] is True
        assert (row["consequence"], row["impact"]) == ("intron_variant", "MODIFIER")
        assert row["gnomad_af"] == pytest.approx(0.22)
        assert row["rsid"] == "rs1"

    def test_a_multiallelic_record_stays_one_row_and_picks_its_worst_allele(self, rows):
        """Joining every ALT would double the suppressed count this table exists to
        report, so the record joins once — to the most severe allele VEP covered."""
        both = [r for r in rows if r["pos"] == 700]
        assert len(both) == 1
        assert both[0]["alt"] == "A,C", "the record's ALT stays comma-packed"
        assert both[0]["annotated_alt"] == "C"
        assert both[0]["consequence"] == "missense_variant"
        assert both[0]["clin_sig"] == "Uncertain_significance"

    def test_an_unannotated_record_is_null_everywhere_not_false(self, rows):
        """Absent from VEP is not "looked up and harmless"."""
        row = at(rows, 820)
        assert row["annotated"] is False
        assert row["consequence"] is None and row["impact"] is None
        assert row["gnomad_af"] is None and row["annotated_alt"] is None


class TestCensus:
    def test_pass_is_a_row_like_any_other(self, census):
        assert [(r["gene"], r["filter"], r["n"]) for r in census] == [
            ("BUB1B", "PASS", 1),
            ("BUB1B", "MQ40", 2),
            ("BUB1B", "LowQual", 1),
            ("BUB1B", "LowQual;QD2", 1),
            ("TRIP13", "PASS", 1),
            ("TRIP13", "MQ40", 1),
        ]

    def test_a_genes_rows_stack_to_its_whole_record_count(self, census):
        for gene, total in (("BUB1B", 5), ("TRIP13", 2)):
            rows = [r for r in census if r["gene"] == gene]
            assert sum(r["n"] for r in rows) == total
            assert {r["n_gene_all"] for r in rows} == {total}

    def test_the_percentages_of_one_gene_sum_to_a_hundred(self, census):
        for gene in ("BUB1B", "TRIP13"):
            share = sum(r["pct_of_gene"] for r in census if r["gene"] == gene)
            assert share == pytest.approx(100.0, abs=0.02)

    def test_pass_sorts_first_then_the_heaviest_reason(self, census):
        bub1b = [r for r in census if r["gene"] == "BUB1B"]
        assert bub1b[0]["is_pass"] is True
        assert all(r["is_pass"] is False for r in bub1b[1:])
        assert [r["n"] for r in bub1b[1:]] == sorted((r["n"] for r in bub1b[1:]), reverse=True)

    def test_the_census_and_the_record_table_agree_on_what_is_suppressed(self, census, rows):
        counted = sum(r["n"] for r in census if not r["is_pass"])
        assert counted == len(rows)

    def test_a_record_outside_the_panel_is_counted_by_neither(self, census):
        assert sum(r["n"] for r in census) == 7, "9 raw records, 2 outside the panel"
