"""The ``panel_het_pairs`` derivation, run against a miniature DuckDB warehouse.

Hermetic: no server, no network. The real SQL runs over a handful of rows chosen to
exercise every branch the derivation has — a phased pair, an unphased record, a ``1/2``
multi-allelic site, a suppressed record, a homozygous record, an out-of-interval record,
and a het allele VEP never annotated.

Positions here are three-digit counters. They are not coordinates and the repo commits
none.
"""

import duckdb
import pytest

from mva.warehouse.analysis import by_name
from mva.warehouse.analysis_pairs import PANEL_HET_PAIRS
from mva.warehouse.derivation import resolve


@pytest.fixture()
def warehouse():
    """One tiny row set per table ``panel_het_pairs`` reads."""
    connection = duckdb.connect()
    connection.execute("CREATE SCHEMA src")
    connection.execute("""
        CREATE TABLE src.mva_panel_grch38 AS SELECT * FROM (VALUES
            ('chr15', 100, 900, 'BUB1B'),
            ('chr5',  100, 900, 'TRIP13'))
        AS t(chrom, start, "end", name);

        CREATE TABLE src.panel_annotations AS SELECT * FROM (VALUES
            ('15', 500, 'G', 'A', 'rs1', 'BUB1B', 'stop_gained', 'HIGH',
             NULL::DOUBLE, NULL::DOUBLE, 'Pathogenic'),
            ('15', 520, 'C', 'T', NULL, 'BUB1B', 'missense_variant', 'MODERATE',
             0.4, 0.5, NULL),
            ('15', 700, 'G', 'A', NULL, 'BUB1B', 'missense_variant', 'MODERATE',
             0.0001, 0.0002, NULL),
            ('15', 700, 'G', 'C', NULL, 'BUB1B', 'frameshift_variant', 'HIGH',
             NULL::DOUBLE, NULL::DOUBLE, NULL))
        AS t(chrom, pos, ref, alt, rsid, gene, consequence, impact,
             gnomad_af, gnomad_af_grpmax, clin_sig);

        CREATE TABLE src.variants_raw AS SELECT * FROM (VALUES
            -- two het records sharing a phase set, opposite PGT: a resolved TRANS pair
            ('15', '500', 'G', 'A',   '900.0', 'PASS',
             'GT:AD:DP:GQ:PGT:PID', '0/1:20,18:38:99:0|1:500_G_A'),
            ('15', '520', 'C', 'T',   '880.0', 'PASS',
             'GT:AD:DP:GQ:PGT:PID', '0/1:22,19:41:99:1|0:500_G_A'),
            -- multi-allelic 1/2: two ALT alleles, three depths, no phase fields
            ('15', '700', 'G', 'A,C', '400.0', 'PASS',
             'GT:AD:DP:GQ',         '1/2:5,7,9:21:99'),
            -- unphased het that VEP never annotated
            ('15', '760', 'T', 'G',   '300.0', 'PASS',
             'GT:AD:DP',            '0/1:12,11:23'),
            -- suppressed het: PASS-only, so it must not appear
            ('15', '800', 'A', 'G',   '40.0',  'LowQual',
             'GT:AD:DP',            '0/1:6,5:11'),
            -- homozygous ALT: not half a pair
            ('15', '820', 'A', 'T',   '900.0', 'PASS',
             'GT:AD:DP',            '1/1:0,30:30'),
            -- FORMAT in a different order: every field is found by name
            ('5',  '300', 'A', 'G',   '500.0', 'PASS',
             'DP:GT:AD:PID:PGT',    '26:0/1:13,13:300_A_G:0|1'),
            -- outside every panel interval
            ('15', '950', 'A', 'G',   '900.0', 'PASS',
             'GT:AD:DP',            '0/1:10,10:20'),
            -- a contig the panel does not name at all
            ('7',  '500', 'A', 'G',   '900.0', 'PASS',
             'GT:AD:DP',            '0/1:10,10:20'))
        AS t(chrom, pos, ref, alt, qual, filter, format, sample_call);
    """)
    yield connection
    connection.close()


def run(connection) -> list[dict]:
    relation = connection.sql(resolve(PANEL_HET_PAIRS.sql, "src"))
    return [dict(zip(relation.columns, row)) for row in relation.fetchall()]


@pytest.fixture()
def rows(warehouse) -> list[dict]:
    return run(warehouse)


def at(rows: list[dict], pos: int, alt: str) -> dict:
    return next(r for r in rows if r["pos"] == pos and r["alt"] == alt)


class TestRegistration:
    def test_the_derivation_is_in_the_one_registry(self):
        assert by_name("panel_het_pairs") is PANEL_HET_PAIRS

    def test_it_declares_every_table_it_reads(self):
        assert set(PANEL_HET_PAIRS.depends_on) == {
            "mva_panel_grch38",
            "variants_raw",
            "panel_annotations",
        }


class TestMembership:
    def test_only_heterozygous_pass_alleles_inside_a_panel_gene_survive(self, rows):
        assert sorted((r["pos"], r["alt"]) for r in rows) == [
            (300, "G"),
            (500, "A"),
            (520, "T"),
            (700, "A"),
            (700, "C"),
            (760, "G"),
        ]

    def test_a_suppressed_het_is_not_evidence(self, rows):
        assert not [r for r in rows if r["pos"] == 800]

    def test_a_homozygous_call_is_not_half_a_pair(self, rows):
        assert not [r for r in rows if r["pos"] == 820]

    def test_a_record_past_the_interval_end_is_excluded(self, rows):
        assert not [r for r in rows if r["pos"] == 950]

    def test_a_contig_the_panel_does_not_name_is_never_read(self, rows):
        assert {r["chrom"] for r in rows} == {"15", "5"}

    def test_the_gene_label_comes_from_the_interval_it_falls_in(self, rows):
        assert at(rows, 300, "G")["gene"] == "TRIP13"
        assert at(rows, 500, "A")["gene"] == "BUB1B"

    def test_the_contig_stays_bare_as_the_callset_spells_it(self, rows):
        assert all(not r["chrom"].startswith("chr") for r in rows)


class TestMultiAllelic:
    def test_a_one_two_record_becomes_two_distinguishable_rows(self, rows):
        both = [r for r in rows if r["pos"] == 700]
        assert [(r["allele_ix"], r["alt"]) for r in both] == [(1, "A"), (2, "C")]
        assert {r["gt"] for r in both} == {"1/2"}

    def test_each_allele_of_a_one_two_site_gets_its_own_fraction(self, rows):
        """`panel_candidates` reports null here because "the" ALT is ambiguous. Once the
        row *is* one allele the fraction is well defined: depth over 5+7+9."""
        assert at(rows, 700, "A")["vaf"] == pytest.approx(7 / 21, abs=1e-4)
        assert at(rows, 700, "C")["vaf"] == pytest.approx(9 / 21, abs=1e-4)

    def test_a_biallelic_row_keeps_the_alt_over_ref_plus_alt_convention(self, rows):
        assert at(rows, 500, "A")["vaf"] == pytest.approx(18 / 38, abs=1e-4)


class TestPhaseFields:
    def test_pgt_and_pid_are_carried_raw_for_the_classifier_to_read(self, rows):
        left, right = at(rows, 500, "A"), at(rows, 520, "T")
        assert left["pid"] == right["pid"] == "500_G_A"
        assert (left["pgt"], right["pgt"]) == ("0|1", "1|0")

    def test_an_unphased_record_carries_nulls_not_empty_strings(self, rows):
        row = at(rows, 700, "A")
        assert row["pgt"] is None and row["pid"] is None

    def test_fields_are_located_by_name_not_by_position(self, rows):
        """The TRIP13 record spells FORMAT as DP:GT:AD:PID:PGT."""
        row = at(rows, 300, "G")
        assert (row["gt"], row["dp"], row["pgt"], row["pid"]) == ("0/1", 26, "0|1", "300_A_G")


class TestAnnotationJoin:
    def test_an_annotated_allele_carries_its_consequence_and_rarity(self, rows):
        row = at(rows, 500, "A")
        assert row["annotated"] is True
        assert (row["consequence"], row["impact"]) == ("stop_gained", "HIGH")
        assert row["clin_sig"] == "Pathogenic"
        assert row["is_protein_altering"] is True

    def test_the_two_alts_of_one_site_join_to_their_own_annotation(self, rows):
        assert at(rows, 700, "A")["consequence"] == "missense_variant"
        assert at(rows, 700, "C")["consequence"] == "frameshift_variant"

    def test_a_common_allele_is_not_rare_at_the_recessive_cutoff(self, rows):
        assert at(rows, 520, "T")["is_rare_recessive"] is False

    def test_an_allele_absent_from_gnomad_is_rare_because_it_was_looked_up(self, rows):
        row = at(rows, 500, "A")
        assert row["gnomad_af"] is None and row["is_rare_recessive"] is True

    def test_an_unannotated_allele_is_null_not_false(self, rows):
        """Absent from VEP is not "measured and common" — the flags must not read as a
        finding."""
        row = at(rows, 760, "G")
        assert row["annotated"] is False
        assert row["is_rare_recessive"] is None
        assert row["is_protein_altering"] is None
        assert row["consequence"] is None and row["gnomad_af"] is None


class TestOrdering:
    def test_rows_arrive_gene_then_position_then_allele(self, rows):
        keys = [(r["gene"], r["pos"], r["allele_ix"]) for r in rows]
        assert keys == sorted(keys)
