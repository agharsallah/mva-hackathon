"""The reference tables: how they are typed on the way in, and what they derive into.

Two halves, both hermetic.

* **Staging** runs against the *real committed* TSVs in ``ressources/reference/``, because
  the thing worth asserting is that the declared transform matches the file that is
  actually on disk — a header rename upstream must fail here, not in production. No
  network, no database: the specs are staged into ``tmp_path``.
* **Derivations** run their real SQL against a miniature DuckDB warehouse built in memory,
  so a broken join or a mistyped column name is caught without a server.
"""

from pathlib import Path

import duckdb
import pytest

from mva.warehouse import reference
from mva.warehouse.analysis import DERIVATIONS, by_name
from mva.warehouse.analysis_reference import (BENIGN_PREDICATE, PLP_PREDICATE,
                                              REFERENCE_DERIVATIONS, VUS_PREDICATE)
from mva.warehouse.derivation import resolve
from mva.warehouse.stage import stage

#: The committed reference directory, relative to the repository root.
ROOT = Path(__file__).resolve().parents[1] / "ressources" / "reference"


@pytest.fixture(scope="module")
def staged(tmp_path_factory) -> dict[str, Path]:
    """Stage the three real reference TSVs once, and hand back their Parquet paths."""
    outdir = tmp_path_factory.mktemp("reference")
    written = stage(ROOT, outdir, reference.datasets(ROOT))
    return {item.table: item.parquet for item in written}


def types(parquet: Path) -> dict[str, str]:
    described = duckdb.sql(f"DESCRIBE SELECT * FROM read_parquet('{parquet}')").fetchall()
    return {row[0]: row[1] for row in described}


def one(parquet: Path, expression: str):
    return duckdb.sql(
        f"SELECT {expression} FROM read_parquet('{parquet}')").fetchone()[0]


class TestSpecs:
    def test_every_reference_file_is_declared(self):
        declared = {dataset.source for dataset in reference.datasets()}
        assert declared == {path.name for path in ROOT.glob("*.tsv")}

    def test_each_spec_pins_its_own_root(self, tmp_path: Path):
        for dataset in reference.datasets(tmp_path):
            assert dataset.path(Path("ignored")) == tmp_path / dataset.source

    def test_every_reference_table_declares_its_lineage(self):
        for dataset in reference.datasets():
            assert dataset.table in reference.LINEAGE, dataset.table

    def test_each_lineage_note_cites_its_upstream(self):
        for table, spec in reference.LINEAGE.items():
            assert spec["source_version"] and spec["transform"], table
        assert "gnomad" in reference.LINEAGE["gnomad_constraint"]["notes"]
        assert "clinvar" in reference.LINEAGE["clinvar_panel"]["notes"]


class TestGnomadStaging:
    def test_the_committed_header_is_the_one_the_transform_names(self, staged):
        columns = set(types(staged["gnomad_constraint"]))
        assert {"gene", "ensembl_gene_id", "transcript", "chrom", "loeuf", "pli",
                "mis_z", "oe_lof", "lof_obs", "lof_exp", "constraint_flags"} <= columns

    def test_numeric_columns_are_numbers_not_text(self, staged):
        found = types(staged["gnomad_constraint"])
        assert found["loeuf"] == "DOUBLE" and found["pli"] == "DOUBLE"
        assert found["lof_obs"] == "BIGINT" and found["cds_length"] == "BIGINT"
        assert found["mane_select"] == "BOOLEAN"

    def test_na_becomes_null_rather_than_the_string(self, staged):
        parquet = staged["gnomad_constraint"]
        assert one(parquet, "count(*) FILTER (WHERE gene = 'NA')") == 0
        assert one(parquet, "count(*) FILTER (WHERE gene IS NULL)") > 0

    def test_the_chr_prefix_is_stripped_on_the_way_in(self, staged):
        parquet = staged["gnomad_constraint"]
        assert one(parquet, "count(*) FILTER (WHERE chrom LIKE 'chr%')") == 0
        assert one(parquet, "count(DISTINCT chrom)") == 22, "autosomes only"

    def test_the_panel_genes_are_all_present(self, staged):
        panel = "'BUB1B','CEP57','CENPE','CEP192','TRIP13','SMC5','TP53','DICER1'"
        assert one(staged["gnomad_constraint"],
                   f"count(DISTINCT gene) FILTER (WHERE gene IN ({panel}))") == 8


class TestClinvarStaging:
    def test_positions_and_the_stable_key_are_integers(self, staged):
        found = types(staged["clinvar_panel"])
        assert found["pos"] == "BIGINT" and found["variation_id"] == "BIGINT"

    def test_text_columns_are_unbounded(self, staged):
        found = types(staged["clinvar_panel"])
        assert found["ref"] == "VARCHAR" and found["condition"] == "VARCHAR"
        assert one(staged["clinvar_panel"], "max(length(ref))") > 1000

    def test_an_empty_classification_is_null_not_an_empty_string(self, staged):
        parquet = staged["clinvar_panel"]
        assert one(parquet, "count(*) FILTER (WHERE clnsig = '')") == 0
        assert one(parquet, "count(*) FILTER (WHERE clnsig IS NULL)") > 0

    def test_contigs_arrive_bare_and_stay_bare(self, staged):
        assert one(staged["clinvar_panel"],
                   "count(*) FILTER (WHERE chrom LIKE 'chr%')") == 0


class TestQcNormsStaging:
    def test_the_bounds_are_numbers(self, staged):
        found = types(staged["qc_norms"])
        assert found["expected_low"] == "DOUBLE" and found["expected_high"] == "DOUBLE"

    def test_the_recessive_threshold_is_one_percent_not_one_per_mille(self, staged):
        """1e-3 is the *dominant* cutoff. Filtering a compound-het search at it drops
        real alleles — the derivation's threshold has to come from this row."""
        assert one(staged["qc_norms"],
                   "max(expected_high) FILTER "
                   "(WHERE metric = 'rare_af_threshold_recessive')") == 0.01

    def test_every_norm_carries_a_citation(self, staged):
        assert one(staged["qc_norms"], "count(*) FILTER (WHERE source IS NULL)") == 0


# ── the ClinVar significance predicate ───────────────────────────────────────────────

#: Every distinct ``clnsig`` value in the committed extract, with what it should count as.
CLNSIG_CASES = [
    ("Pathogenic", "plp"),
    ("Likely_pathogenic", "plp"),
    ("Pathogenic/Likely_pathogenic", "plp"),
    ("Pathogenic|Affects", "plp"),
    ("Pathogenic/Likely_pathogenic/Pathogenic,_low_penetrance", "plp"),
    ("Conflicting_classifications_of_pathogenicity", "none"),
    ("Uncertain_significance", "vus"),
    ("Benign", "benign"),
    ("Likely_benign", "benign"),
    ("Benign/Likely_benign", "benign"),
    ("not_provided", "none"),
    ("drug_response", "none"),
    (None, "none"),
]


@pytest.mark.parametrize("clnsig,expected", CLNSIG_CASES)
def test_the_clinvar_predicates_bucket_every_real_value(clnsig, expected):
    """`Pathogenic` and `Conflicting_classifications_of_pathogenicity` share a substring.
    Only the first is an assertion, so the exclusion is load-bearing."""
    got = duckdb.sql(f"""
        SELECT CASE WHEN {PLP_PREDICATE}    THEN 'plp'
                    WHEN {VUS_PREDICATE}    THEN 'vus'
                    WHEN {BENIGN_PREDICATE} THEN 'benign'
                    ELSE 'none' END
        FROM (SELECT ? AS clnsig)
    """, params=[clnsig]).fetchone()[0]
    assert got == expected


# ── the derivations, against a miniature warehouse ───────────────────────────────────

@pytest.fixture()
def warehouse():
    """A DuckDB schema holding one tiny row set per table the new derivations read."""
    connection = duckdb.connect()
    connection.execute("CREATE SCHEMA src")
    connection.execute("""
        CREATE TABLE src.mva_panel_grch38 AS SELECT * FROM (VALUES
            ('chr15', 100, 900, 'BUB1B'),
            ('chrX',  100, 900, 'XGENE'))
        AS t(chrom, start, "end", name);

        CREATE TABLE src.panel_variant_counts AS SELECT * FROM (VALUES
            ('BUB1B', 'chr15', 100, 900, 4, 3),
            ('XGENE', 'chrX',  100, 900, 1, 1))
        AS t(gene, chrom, start, "end", n_all, n_pass);

        -- Two canonical transcripts for one symbol: the MANE Select one must win.
        CREATE TABLE src.gnomad_constraint AS SELECT * FROM (VALUES
            ('BUB1B', 'ENST00000287598', true,  0.707, 0.0, 1.78, 0.588, 81, 137.83),
            ('BUB1B', 'ENST00000999999', false, 9.999, 1.0, 0.00, 9.999,  1,   1.00))
        AS t(gene, transcript, mane_select, loeuf, pli, mis_z, oe_lof, lof_obs, lof_exp);

        CREATE TABLE src.clinvar_panel AS SELECT * FROM (VALUES
            ('BUB1B', 'Pathogenic'),
            ('BUB1B', 'Pathogenic/Likely_pathogenic'),
            ('BUB1B', 'Conflicting_classifications_of_pathogenicity'),
            ('BUB1B', 'Uncertain_significance'),
            ('BUB1B', 'Benign/Likely_benign'))
        AS t(gene, clnsig);

        CREATE TABLE src.panel_annotations AS SELECT * FROM (VALUES
            ('15', 500, 'G', 'A', 'rs1', 'BUB1B', 'stop_gained', 'HIGH',
             NULL::DOUBLE, NULL::DOUBLE, 'pathogenic'),
            ('15', 700, 'G', 'C', NULL, 'BUB1B', 'missense_variant', 'MODERATE',
             0.4, 0.5, NULL),
            ('15', 800, 'T', 'C', NULL, 'BUB1B', 'intron_variant', 'MODIFIER',
             0.001, 0.002, NULL))
        AS t(chrom, pos, ref, alt, rsid, gene, consequence, impact,
             gnomad_af, gnomad_af_grpmax, clin_sig);

        CREATE TABLE src.variants_raw AS SELECT * FROM (VALUES
            ('15', '500', 'rs1', 'G', 'A',   '812.5', 'PASS',
             'GT:AD:DP:GQ', '0/1:20,18:38:99'),
            -- multi-allelic: ALT is comma-packed and AD carries three depths
            ('15', '700', '.',   'G', 'A,C', '400.0', 'PASS',
             'GT:AD:DP:GQ', '1/2:5,7,9:21:99'),
            -- FORMAT in a different order: GT is not first
            ('15', '800', '.',   'T', 'C',   '100.0', 'LowQual',
             'DP:GT:AD',    '30:1/1:2,28'),
            ('15', '900', '.',   'A', 'G',   '50.0',  'PASS',
             'GT:AD:DP',    '0/1:5,5:10'))
        AS t(chrom, pos, id, ref, alt, qual, filter, format, sample_call);

        CREATE TABLE src.qc_norms AS SELECT * FROM (VALUES
            ('tstv_genome_wide', 2.0, 2.1, 'ratio', 'WGS', 'Betschart 2024'),
            ('snv_per_genome', 10.0, 20.0, 'SNPs', 'WGS', '1000G 2015'),
            ('insertion_deletion_ratio', 0.924, 0.936, 'ratio', 'WGS', 'Byrska 2022'),
            ('het_hom_ratio_eur', 1.5, 1.6, 'ratio', 'WGS EUR', 'Betschart 2024'),
            ('mean_coverage_wgs', 35.0, 35.0, 'x', 'WGS', 'Betschart 2024'),
            ('dbsnp_membership_rate_per_genome', 99.2, 99.2, 'percent', 'WGS',
             'Taliun 2021'),
            ('de_novo_snv_indel_per_genome', 70.0, 70.0, 'variants', 'trio',
             'Pedersen 2021'))
        AS t(metric, expected_low, expected_high, unit, applies_to, source);

        CREATE TABLE src.stats_summary AS SELECT * FROM (VALUES
            (1, 'SN' || chr(9) || '0' || chr(9) || 'number of records:' || chr(9) || '9'),
            (2, 'SN' || chr(9) || '0' || chr(9) || 'number of SNPs:' || chr(9) || '5'),
            (3, 'SN' || chr(9) || '0' || chr(9) || 'number of indels:' || chr(9) || '4'),
            (4, 'TSTV' || chr(9) || '0' || chr(9) || '6' || chr(9) || '3'
                || chr(9) || '2.00'),
            (5, 'IDD' || chr(9) || '0' || chr(9) || '1' || chr(9) || '9'),
            (6, 'IDD' || chr(9) || '0' || chr(9) || '-1' || chr(9) || '10'))
        AS t(line_no, line);

        CREATE TABLE src.filter_gt_counts AS SELECT * FROM (VALUES
            ('genotype counts', '0/1', 30),
            ('genotype counts', '1/1', 20),
            ('FILTER counts',   'PASS', 99))
        AS t(section, label, count);

        CREATE TABLE src.profile_scalars AS SELECT * FROM (VALUES
            ('fastq_profile.tsv', 'est_raw_coverage_x', '51.9'))
        AS t(source, key, value);
    """)
    yield connection
    connection.close()


def run(connection, name: str) -> list[dict]:
    relation = connection.sql(resolve(by_name(name).sql, "src"))
    columns = relation.columns
    return [dict(zip(columns, row)) for row in relation.fetchall()]


class TestPanelGeneConstraint:
    def test_the_mane_transcript_wins_when_a_symbol_has_two(self, warehouse):
        row = next(r for r in run(warehouse, "panel_gene_constraint")
                   if r["gene"] == "BUB1B")
        assert row["gnomad_transcript"] == "ENST00000287598"
        assert float(row["loeuf"]) == pytest.approx(0.707)

    def test_a_gene_absent_from_gnomad_gets_nulls_not_zeros(self, warehouse):
        """gnomAD constraint is autosomes-only. An X-linked gene must not read as
        unconstrained."""
        row = next(r for r in run(warehouse, "panel_gene_constraint")
                   if r["gene"] == "XGENE")
        assert row["loeuf"] is None and row["pli"] is None and row["lof_obs"] is None

    def test_conflicting_is_excluded_from_the_pathogenic_count(self, warehouse):
        row = next(r for r in run(warehouse, "panel_gene_constraint")
                   if r["gene"] == "BUB1B")
        assert (row["clinvar_plp"], row["clinvar_vus"], row["clinvar_benign"]) == (2, 1, 1)

    def test_the_contig_stays_chr_prefixed_as_the_panel_delivers_it(self, warehouse):
        assert all(r["chrom"].startswith("chr")
                   for r in run(warehouse, "panel_gene_constraint"))


class TestPanelCandidates:
    def rows(self, warehouse) -> dict[int, dict]:
        return {row["pos"]: row for row in run(warehouse, "panel_candidates")}

    def test_every_annotation_gets_a_row_and_no_extra_variant_does(self, warehouse):
        found = self.rows(warehouse)
        assert set(found) == {500, 700, 800}, "the un-annotated variant must not appear"

    def test_a_packed_alt_matches_by_membership_not_substring(self, warehouse):
        """`700` is `G -> A,C` in one record; the annotation asks about `C` alone."""
        assert self.rows(warehouse)[700]["gt"] == "1/2"

    def test_gt_is_read_from_the_records_own_format_keys(self, warehouse):
        """At `800` the FORMAT is `DP:GT:AD` — assuming GT is first yields the depth."""
        row = self.rows(warehouse)[800]
        assert row["gt"] == "1/1" and row["dp"] == 30

    def test_vaf_is_the_alt_fraction_of_ref_plus_alt(self, warehouse):
        assert self.rows(warehouse)[500]["vaf"] == pytest.approx(18 / 38, abs=1e-4)

    def test_a_multiallelic_site_reports_no_vaf_rather_than_a_wrong_one(self, warehouse):
        assert self.rows(warehouse)[700]["vaf"] is None

    def test_rarity_uses_the_recessive_threshold_not_the_dominant_one(self, warehouse):
        found = self.rows(warehouse)
        assert found[500]["is_rare_recessive"] is True, "unknown AF counts as rare"
        assert found[700]["is_rare_recessive"] is False, "0.4 is common"
        # 0.001 is *not* rare under the dominant cutoff but is under the recessive one.
        assert found[800]["is_rare_recessive"] is True

    def test_protein_altering_is_the_two_severe_impact_buckets(self, warehouse):
        found = self.rows(warehouse)
        assert [found[p]["is_protein_altering"] for p in (500, 700, 800)] == \
               [True, True, False]


class TestQcObservedExpected:
    def rows(self, warehouse) -> dict[str, dict]:
        return {row["metric"]: row for row in run(warehouse, "qc_observed_expected")}

    def test_a_norm_with_no_measurable_counterpart_is_skipped_not_guessed(self, warehouse):
        assert "de_novo_snv_indel_per_genome" not in self.rows(warehouse)

    def test_the_verdict_names_which_side_of_the_range_the_value_falls(self, warehouse):
        found = self.rows(warehouse)
        assert found["tstv_genome_wide"]["verdict"] == "within"       # 2.00 in 2.0-2.1
        assert found["snv_per_genome"]["verdict"] == "below"          # 5 under 10
        assert found["insertion_deletion_ratio"]["verdict"] == "below"  # 9/10 = 0.9
        assert found["mean_coverage_wgs"]["verdict"] == "above"       # 51.9 over 35

    def test_the_het_hom_ratio_comes_from_the_genotype_section_only(self, warehouse):
        assert self.rows(warehouse)["het_hom_ratio_eur"]["observed"] == \
               pytest.approx(30 / 20)

    def test_dbsnp_membership_counts_records_with_an_rsid(self, warehouse):
        assert self.rows(warehouse)["dbsnp_membership_rate_per_genome"]["observed"] == \
               pytest.approx(25.0)

    def test_every_row_says_where_its_observation_came_from(self, warehouse):
        for row in self.rows(warehouse).values():
            assert row["observed_from"] and row["source"]


class TestRegistry:
    def test_the_reference_derivations_are_in_the_one_registry(self):
        names = {item.name for item in DERIVATIONS}
        assert {item.name for item in REFERENCE_DERIVATIONS} <= names

    def test_the_registry_has_no_duplicate_names(self):
        names = [item.name for item in DERIVATIONS]
        assert len(names) == len(set(names))
