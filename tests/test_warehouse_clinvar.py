"""The ClinVar presence cross-check, against a miniature warehouse.

Hermetic: no database, no network. The real derivation SQL runs over a DuckDB schema
holding one tiny row set per table it reads, so a broken join, a mistyped column or a
wrong NULL convention is caught without a server.

The cases are chosen from what the *committed* extract actually contains — a row with
``alt = '.'``, a 7 kb reference allele, a comma-packed callset ALT, a FORMAT that is not
GT-first — because those are the shapes that break an exact-string join quietly.
"""

import duckdb
import pytest

from mva.warehouse.analysis import DERIVATIONS, by_name
from mva.warehouse.analysis_clinvar import CLINVAR_DERIVATIONS, COMPARABLE, REVIEW_STARS
from mva.warehouse.analysis_reference import PLP_PREDICATE
from mva.warehouse.derivation import resolve

#: A reference allele too long for any callset record to equal — the committed extract's
#: longest is 7,027 characters. Shortened here; the property under test is the same.
HUGE_REF = "A" * 400


@pytest.fixture()
def warehouse():
    """One P/LP row per case the join has to survive, plus the callset they join to."""
    connection = duckdb.connect()
    connection.execute("CREATE SCHEMA src")
    connection.execute(f"""
        CREATE TABLE src.mva_panel_grch38 AS SELECT * FROM (VALUES
            ('chr15', 100, 900, 'BUB1B'),
            ('chr18', 100, 900, 'CEP192'))
        AS t(chrom, start, "end", name);

        CREATE TABLE src.clinvar_panel AS SELECT * FROM (VALUES
            -- present, PASS, heterozygous: the direct-lead shape
            ('15', 500, 'G', 'A', 'rs1', 11, 'Pathogenic',
             'reviewed_by_expert_panel', 'Mosaic_variegated_aneuploidy_syndrome_1',
             'BUB1B'),
            -- present but the caller suppressed the site
            ('15', 800, 'T', 'C', NULL, 12, 'Likely_pathogenic',
             'criteria_provided,_single_submitter', 'Some_condition', 'BUB1B'),
            -- present as the SECOND allele of a comma-packed record
            ('15', 700, 'G', 'C', NULL, 13, 'Pathogenic/Likely_pathogenic',
             'criteria_provided,_multiple_submitters,_no_conflicts', 'Other', 'BUB1B'),
            -- present as a record, but the genotype carries the *other* alternate
            ('15', 750, 'G', 'C', NULL, 14, 'Pathogenic',
             'no_assertion_criteria_provided', 'Other', 'BUB1B'),
            -- absent: nothing was called at this site
            ('15', 600, 'C', 'T', 'rs2', 15, 'Pathogenic',
             'practice_guideline', 'Other', 'BUB1B'),
            -- uncomparable: ClinVar states no alternate allele
            ('15', 650, 'A', '.', NULL, 16, 'Pathogenic', '', 'Other', 'BUB1B'),
            -- unmatchable in practice: a reference allele no VCF record can equal
            ('15', 660, '{HUGE_REF}', 'A', NULL, 17, 'Pathogenic',
             'no_classification_provided', 'Other', 'BUB1B'),
            -- substring trap: the callset spells the ALT `AT` at this exact site
            ('15', 670, 'G', 'A', NULL, 21, 'Pathogenic',
             'criteria_provided,_single_submitter', 'Other', 'BUB1B'),
            -- excluded by the shared predicate, not by a local rule
            ('15', 550, 'G', 'T', NULL, 18,
             'Conflicting_classifications_of_pathogenicity',
             'criteria_provided,_conflicting_classifications', 'Other', 'BUB1B'),
            ('15', 560, 'G', 'T', NULL, 19, 'Uncertain_significance',
             'criteria_provided,_single_submitter', 'Other', 'BUB1B'),
            -- a P/LP row in a gene the 20 kb padding leaked in: not a panel gene
            ('15', 500, 'G', 'A', NULL, 20, 'Pathogenic',
             'reviewed_by_expert_panel', 'Other', 'WRAP53'))
        AS t(chrom, pos, ref, alt, rsid, variation_id, clnsig, clnrevstat, condition,
             gene);

        CREATE TABLE src.variants_raw AS SELECT * FROM (VALUES
            ('15', '500', 'rs1', 'G', 'A',   '812.5', 'PASS',
             'GT:AD:DP:GQ', '0/1:20,18:38:99'),
            -- comma-packed ALT: the ClinVar allele is the second element
            ('15', '700', '.',   'G', 'A,C', '400.0', 'PASS',
             'GT:AD:DP:GQ', '1/2:5,7,9:21:99'),
            -- comma-packed ALT, but the genotype carries allele 1 (A), not C
            ('15', '750', '.',   'G', 'A,C', '300.0', 'PASS',
             'GT:AD:DP:GQ', '0/1:10,10,0:20:99'),
            -- FORMAT is not GT-first
            ('15', '800', '.',   'T', 'C',   '100.0', 'LowQual',
             'DP:GT:AD',    '30:1/1:2,28'),
            -- a callset record with no ClinVar counterpart
            ('15', '900', '.',   'A', 'G',   '50.0',  'PASS',
             'GT:AD:DP',    '0/1:5,5:10'),
            -- same position as an absent P/LP row but a different ALT: must not match
            ('15', '600', '.',   'C', 'G',   '90.0',  'PASS',
             'GT:AD:DP',    '0/1:4,6:10'),
            -- the huge-ref site IS called, with a reference allele of one base
            ('15', '660', '.',   'A', 'G',   '90.0',  'PASS',
             'GT:AD:DP',    '0/1:4,6:10'),
            -- substring trap: `A` must not match the packed ALT string `AT`
            ('15', '670', '.',   'G', 'AT',  '90.0',  'PASS',
             'GT:AD:DP',    '0/1:4,6:10'),
            -- another contig entirely
            ('18', '400', '.',   'C', 'T',   '90.0',  'PASS',
             'GT:AD:DP',    '0/1:4,6:10'))
        AS t(chrom, pos, id, ref, alt, qual, filter, format, sample_call);
    """)
    yield connection
    connection.close()


def run(connection, name: str) -> list[dict]:
    relation = connection.sql(resolve(by_name(name).sql, "src"))
    columns = relation.columns
    return [dict(zip(columns, row)) for row in relation.fetchall()]


@pytest.fixture()
def sites(warehouse) -> dict[int, dict]:
    """The derivation's rows, keyed by ClinVar's stable ``variation_id``."""
    return {row["variation_id"]: row for row in run(warehouse, "clinvar_presence")}


# ── which rows the table is about ────────────────────────────────────────────────────

class TestScope:
    def test_only_pathogenic_and_likely_pathogenic_rows_appear(self, sites):
        """VUS and conflicting rows are not assertions of pathogenicity."""
        assert 18 not in sites, "Conflicting_classifications_of_pathogenicity"
        assert 19 not in sites, "Uncertain_significance"

    def test_the_significance_predicate_is_the_shared_one_not_a_copy(self):
        """One owner for the P/LP rule. A second spelling would drift from it."""
        assert PLP_PREDICATE in by_name("clinvar_presence").sql

    def test_a_gene_the_padding_leaked_in_is_not_a_panel_gene(self, sites):
        """The BED's 20 kb padding pulls ~10 flanking genes into the extract."""
        assert 20 not in sites
        assert {row["gene"] for row in sites.values()} == {"BUB1B"}

    def test_the_panel_is_named_from_the_bed_not_hardcoded(self):
        assert "mva_panel_grch38" in by_name("clinvar_presence").depends_on

    def test_every_plp_panel_row_gets_a_row_present_or_not(self, sites):
        """An absence is a result, so the row is emitted rather than filtered away."""
        assert set(sites) == {11, 12, 13, 14, 15, 16, 17, 21}


# ── the join ─────────────────────────────────────────────────────────────────────────

class TestPresence:
    def test_a_called_site_is_present_with_its_genotype_and_filter(self, sites):
        row = sites[11]
        assert row["present"] is True
        assert (row["gt"], row["filter"]) == ("0/1", "PASS")
        assert row["dp"] == 38 and row["qual"] == pytest.approx(812.5)
        assert row["vaf"] == pytest.approx(18 / 38, abs=1e-4)

    def test_a_present_site_the_caller_suppressed_keeps_its_filter_label(self, sites):
        """Present is not the same as trustworthy — the FILTER travels with the row."""
        row = sites[12]
        assert row["present"] is True and row["filter"] == "LowQual"

    def test_gt_is_read_from_the_records_own_format_keys(self, sites):
        """At the suppressed site FORMAT is `DP:GT:AD`; assuming GT first yields 30."""
        assert sites[12]["gt"] == "1/1" and sites[12]["dp"] == 30

    def test_a_packed_alt_matches_by_membership_and_reports_its_index(self, sites):
        """`G -> A,C` in one record; ClinVar asks about `C`, the second allele."""
        row = sites[13]
        assert row["present"] is True and row["allele_ix"] == 2
        assert row["gt"] == "1/2"
        assert row["vaf"] == pytest.approx(9 / 21, abs=1e-4)

    def test_membership_is_not_a_substring_test(self, sites):
        """`A` is a substring of the callset's ALT `AT` but not an element of it. Chrom,
        pos and ref all agree at this site, so only the ALT rule can reject it."""
        assert sites[21]["present"] is False

    def test_a_site_called_with_a_different_alt_is_absent_not_present(self, sites):
        """Same chrom and pos, different allele. Position alone is not identity."""
        row = sites[15]
        assert row["present"] is False
        assert row["gt"] is None and row["filter"] is None and row["vaf"] is None

    def test_an_absent_site_carries_nulls_never_zeros(self, sites):
        row = sites[15]
        assert row["dp"] is None and row["qual"] is None
        assert row["carries_alt"] is None and row["is_het"] is None


class TestUncomparableRows:
    def test_a_row_with_no_alternate_allele_is_marked_uncomparable(self, sites):
        assert sites[16]["comparable"] is False

    def test_an_uncomparable_row_is_null_rather_than_absent(self, sites):
        """`present = false` is a measurement. A row that could never match is not one."""
        assert sites[16]["present"] is None

    def test_a_comparable_row_says_so(self, sites):
        assert all(sites[key]["comparable"] is True
                   for key in (11, 12, 13, 14, 15, 17, 21))

    def test_a_huge_reference_allele_does_not_crash_the_join(self, sites):
        """The committed extract's longest `ref` is 7,027 characters. The site IS called
        here, with a one-base reference allele, so only the ref rule can reject it."""
        assert sites[17]["comparable"] is True and sites[17]["present"] is False

    def test_the_comparability_rule_is_declared_once(self):
        assert COMPARABLE in by_name("clinvar_presence").sql


class TestGenotypeReading:
    def test_a_het_call_carrying_the_allele_is_the_direct_lead_shape(self, sites):
        row = sites[11]
        assert row["carries_alt"] is True and row["is_het"] is True

    def test_a_homozygous_call_carries_the_allele_but_is_not_het(self, sites):
        assert sites[12]["carries_alt"] is True and sites[12]["is_het"] is False

    def test_a_multiallelic_call_is_het_for_each_of_its_two_alleles(self, sites):
        assert sites[13]["carries_alt"] is True and sites[13]["is_het"] is True

    def test_a_record_listing_the_allele_is_not_a_genotype_carrying_it(self, sites):
        """`0/1` on a `G -> A,C` record carries `A`. Conflating the two invents a carrier."""
        row = sites[14]
        assert row["present"] is True and row["allele_ix"] == 2
        assert row["carries_alt"] is False and row["is_het"] is False


# ── the assertion-quality tier ───────────────────────────────────────────────────────

class TestReviewStars:
    @pytest.mark.parametrize("variation_id,stars", [
        (15, 4),   # practice_guideline
        (11, 3),   # reviewed_by_expert_panel
        (13, 2),   # criteria_provided,_multiple_submitters,_no_conflicts
        (12, 1),   # criteria_provided,_single_submitter
        (14, 0),   # no_assertion_criteria_provided
        (17, 0),   # no_classification_provided
    ])
    def test_each_review_status_maps_to_its_ncbi_gold_star_count(
            self, sites, variation_id, stars):
        assert sites[variation_id]["review_stars"] == stars

    def test_an_unknown_review_status_is_null_rather_than_zero(self, warehouse):
        """Zero stars is an NCBI tier. "Not stated" is a different thing."""
        got = warehouse.sql(
            f"SELECT ({REVIEW_STARS}) FROM (SELECT '' AS clnrevstat)").fetchone()[0]
        assert got is None

    def test_the_raw_status_string_travels_with_the_stars(self, sites):
        assert sites[11]["clnrevstat"] == "reviewed_by_expert_panel"


# ── the registry ─────────────────────────────────────────────────────────────────────

class TestRegistry:
    def test_the_derivation_is_in_the_one_registry(self):
        assert {item.name for item in CLINVAR_DERIVATIONS} <= {
            item.name for item in DERIVATIONS}

    def test_the_registry_has_no_duplicate_names(self):
        names = [item.name for item in DERIVATIONS]
        assert len(names) == len(set(names))

    def test_the_question_states_the_lower_bound_caveat(self):
        """Exact-string matching misses a differently spelled indel. Whoever reads the
        table's own question has to be told that before quoting the number."""
        question = by_name("clinvar_presence").question.lower()
        assert "lower bound" in question and "exact" in question

    def test_the_derivation_reads_the_ingest_schema_only(self):
        """`pg-derive` has no ordering guarantee, so a result table is not an input."""
        assert "results." not in by_name("clinvar_presence").sql
