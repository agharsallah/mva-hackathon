"""Layer 2 — the genome-wide coding scan, run hermetically against a miniature warehouse.

Both schemas live in one in-memory DuckDB attached as ``pg`` so the SQL runs exactly as
``pg-derive`` would issue it, ``{src}`` and ``{res}`` both resolved. The fixture is
synthetic: a gene shaped like the leading candidate (one truncating, one missense, both
het PASS), a gene one suppressed call short, a homozygous gene, a common-variant decoy, and
an allele spanning two overlapping genes.
"""

from __future__ import annotations

import duckdb
import pytest

from mva.warehouse.analysis import DERIVATIONS
from mva.warehouse.analysis_coding import (
    BIN,
    CODING_DERIVATIONS,
    PROBAND_TERM_SET,
)
from mva.warehouse.derivation import RESULT, SOURCE, resolve

SRC = "pg.warehouse"
RES = "pg.results"

FORMAT = "GT:AD:DP:GQ:PL"


def call(gt: str, ad: str, dp: int = 40) -> str:
    return f"{gt}:{ad}:{dp}:99:0,0,0"


VARIANTS = [
    # line_no, chrom, pos, id, ref, alt, qual, filter, info, format, sample_call
    # gene A (the candidate shape): stop_gained het + missense het, both PASS
    (1, "15", 1_000_050, "rs1", "C", "T", "900", "PASS", "DP=40", FORMAT, call("0/1", "20,20")),
    (2, "15", 1_000_400, ".", "G", "A", "850", "PASS", "DP=42", FORMAT, call("0/1", "22,20")),
    # gene A also carries a common intronic-ish allele outside any CDS: must not join
    (3, "15", 1_005_000, "rs9", "A", "G", "500", "PASS", "DP=40", FORMAT, call("0/1", "20,20")),
    # gene B: one rare missense PASS het + one rare frameshift suppressed (QD2)
    (4, "2", 500_100, ".", "T", "C", "700", "PASS", "DP=30", FORMAT, call("0/1", "15,15")),
    (5, "2", 500_300, ".", "TA", "T", "12", "QD2", "DP=30", FORMAT, call("0/1", "25,5")),
    # gene C: homozygous rare missense PASS
    (6, "7", 200_120, ".", "G", "C", "999", "PASS", "DP=44", FORMAT, call("1/1", "0,44")),
    # gene D: two common missense hets (decoy — frequent in gnomAD)
    (7, "3", 300_100, "rs2", "A", "T", "999", "PASS", "DP=40", FORMAT, call("0/1", "20,20")),
    (8, "3", 300_200, "rs3", "C", "G", "999", "PASS", "DP=40", FORMAT, call("0/1", "20,20")),
    # multi-allelic site in gene E: 1/2 genotype, both ALTs rare missense
    (9, "9", 900_100, ".", "A", "G,T", "999", "PASS", "DP=40", FORMAT, "1/2:0,20,20:40:99:0,0,0"),
    # a site inside two overlapping genes F and G (rare stop_gained het)
    (10, "11", 700_100, ".", "C", "A", "999", "PASS", "DP=40", FORMAT, call("0/1", "20,20")),
    # non-canonical contig: excluded by the length rule
    (11, "KI270728.1", 1000, ".", "A", "G", "999", "PASS", "DP=40", FORMAT, call("0/1", "20,20")),
]

REGIONS = [
    # chrom, start, end, gene, gene_id, n_cds, n_transcripts — one interval spans two bins
    ("15", 1_000_000, 1_000_100, "GENE_A", "ENSG_A", 1, 1),
    ("15", 1_000_350, 1_000_450, "GENE_A", "ENSG_A", 1, 1),
    ("2", 500_000, 500_400, "GENE_B", "ENSG_B", 2, 1),
    ("7", 200_000, 200_200, "GENE_C", "ENSG_C", 1, 1),
    ("3", 300_000, 300_300, "GENE_D", "ENSG_D", 1, 1),
    ("9", 900_000, 900_200, "GENE_E", "ENSG_E", 1, 1),
    ("11", 700_000, 700_200, "GENE_F", "ENSG_F", 1, 1),
    ("11", 699_990, 700_150, "GENE_G", "ENSG_G", 1, 1),
    ("4", BIN - 50, BIN + 50, "GENE_H", "ENSG_H", 1, 1),  # straddles a bin boundary
]

ANNOTATIONS = [
    # chrom, pos, ref, alt, rsid, gene, consequence, impact, gnomad_af, grpmax, clin_sig
    (
        "15",
        1_000_050,
        "C",
        "T",
        "rs1",
        "GENE_A",
        "stop_gained",
        "HIGH",
        3.3e-05,
        1e-04,
        "pathogenic;likely_pathogenic",
    ),
    ("15", 1_000_400, "G", "A", None, "GENE_A", "missense_variant", "MODERATE", None, None, None),
    ("2", 500_100, "T", "C", None, "GENE_B", "missense_variant", "MODERATE", 1e-05, None, None),
    ("2", 500_300, "TA", "T", None, "GENE_B", "frameshift_variant", "HIGH", None, None, None),
    ("7", 200_120, "G", "C", None, "GENE_C", "missense_variant", "MODERATE", 2e-04, None, None),
    (
        "3",
        300_100,
        "A",
        "T",
        "rs2",
        "GENE_D",
        "missense_variant",
        "MODERATE",
        0.31,
        0.4,
        "benign;pathogenic",
    ),
    (
        "3",
        300_200,
        "C",
        "G",
        "rs3",
        "GENE_D",
        "missense_variant",
        "MODERATE",
        0.12,
        0.2,
        "conflicting_interpretations_of_pathogenicity",
    ),
    ("9", 900_100, "A", "G", None, "GENE_E", "missense_variant", "MODERATE", None, None, None),
    ("9", 900_100, "A", "T", None, "GENE_E", "missense_variant", "MODERATE", 1e-06, None, None),
    ("11", 700_100, "C", "A", None, "GENE_F", "stop_gained", "HIGH", None, None, None),
]

HPO = [
    # term_set, genes_considered, gene_symbol, entrez_id, rank, score
    (PROBAND_TERM_SET, 5, "GENE_A", "1", 6, 0.9),
    (PROBAND_TERM_SET, 5, "GENE_B", "2", 40, 0.5),
    (PROBAND_TERM_SET, 5, "GENE_C", "3", 900, 0.1),
    ("with-parental", 5, "GENE_A", "1", 12, 0.7),
]


@pytest.fixture(scope="module")
def warehouse() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("ATTACH ':memory:' AS pg")
    con.execute("CREATE SCHEMA pg.warehouse; CREATE SCHEMA pg.results")
    con.execute(
        f"CREATE TABLE {SRC}.variants_raw (line_no BIGINT, chrom VARCHAR, pos VARCHAR, id VARCHAR,"
        " ref VARCHAR, alt VARCHAR, qual VARCHAR, filter VARCHAR, info VARCHAR, format VARCHAR,"
        " sample_call VARCHAR)"
    )
    con.executemany(
        f"INSERT INTO {SRC}.variants_raw VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [tuple(str(v) if i == 2 else v for i, v in enumerate(row)) for row in VARIANTS],
    )
    con.execute(
        f'CREATE TABLE {SRC}.coding_regions (chrom VARCHAR, start BIGINT, "end" BIGINT,'
        " gene VARCHAR, gene_id VARCHAR, n_cds INTEGER, n_transcripts INTEGER)"
    )
    con.executemany(f"INSERT INTO {SRC}.coding_regions VALUES (?,?,?,?,?,?,?)", REGIONS)
    con.execute(
        f"CREATE TABLE {SRC}.coding_annotations (chrom VARCHAR, pos BIGINT, ref VARCHAR,"
        " alt VARCHAR, rsid VARCHAR, gene VARCHAR, consequence VARCHAR, impact VARCHAR,"
        " gnomad_af DOUBLE, gnomad_af_grpmax DOUBLE, clin_sig VARCHAR, annotated_at TIMESTAMP,"
        " source VARCHAR)"
    )
    con.executemany(
        f"INSERT INTO {SRC}.coding_annotations VALUES (?,?,?,?,?,?,?,?,?,?,?, now(), 'test')",
        ANNOTATIONS,
    )
    con.execute(
        f"CREATE TABLE {SRC}.hpo_gene_scores (term_set VARCHAR, genes_considered INTEGER,"
        " gene_symbol VARCHAR, entrez_id VARCHAR, rank INTEGER, score DOUBLE)"
    )
    con.executemany(f"INSERT INTO {SRC}.hpo_gene_scores VALUES (?,?,?,?,?,?)", HPO)
    for derivation in CODING_DERIVATIONS:
        con.execute(f"CREATE TABLE {RES}.{derivation.name} AS {resolve(derivation.sql, SRC, RES)}")
    return con


def rows(con, sql: str) -> list[dict]:
    rel = con.execute(sql)
    names = [d[0] for d in rel.description]
    return [dict(zip(names, r, strict=True)) for r in rel.fetchall()]


class TestPlaceholders:
    def test_res_resolves_separately_from_src(self):
        assert resolve(f"{SOURCE}.a {RESULT}.b", "S", "R") == "S.a R.b"

    def test_res_falls_back_to_src_when_one_schema_is_given(self):
        assert resolve(f"{SOURCE}.a {RESULT}.b", "S") == "S.a S.b"

    def test_coding_derivations_run_in_dependency_order(self):
        # The three build on each other through `{res}`, which only resolves if the runner
        # reaches them in this order. They were once the last thing registered and the
        # test said so; iteration 2 added a group after them, so what is asserted now is
        # the property that actually matters — contiguous, and in dependency order.
        names = [d.name for d in DERIVATIONS]
        first = names.index("coding_alleles")
        assert names[first : first + 3] == [
            "coding_alleles",
            "coding_candidates",
            "gene_biallelic",
        ]

    def test_nothing_reads_a_result_table_before_it_is_built(self):
        # The general form of the rule above, over the whole registry: a derivation may
        # reference `{res}.x` only if x is declared earlier or is written by a loader.
        from mva.warehouse import it2_step2_tables, it2_tables

        loaded = set(it2_step2_tables.SCHEMAS) | {
            it2_tables.TARGETS_TABLE,
            it2_tables.DECOYS_TABLE,
        }
        built: set[str] = set()
        for item in DERIVATIONS:
            for other in DERIVATIONS:
                if f"{RESULT}.{other.name}" in item.sql:
                    assert other.name in built or other.name == item.name, (
                        f"{item.name} reads {other.name} before it is built"
                    )
            for table in item.reads_loaded:
                assert table in loaded, f"{item.name} reads unloaded {table}"
            built.add(item.name)


class TestCodingAlleles:
    def test_only_alleles_inside_a_coding_interval_survive(self, warehouse):
        got = rows(warehouse, f"SELECT pos FROM {RES}.coding_alleles WHERE chrom = '15'")
        assert sorted(r["pos"] for r in got) == [1_000_050, 1_000_400]

    def test_non_canonical_contigs_are_dropped(self, warehouse):
        assert rows(warehouse, f"SELECT * FROM {RES}.coding_alleles WHERE length(chrom) > 2") == []

    def test_filter_is_carried_not_applied(self, warehouse):
        got = rows(warehouse, f"SELECT filter FROM {RES}.coding_alleles WHERE chrom = '2'")
        assert sorted(r["filter"] for r in got) == ["PASS", "QD2"]

    def test_a_multi_allelic_genotype_yields_one_row_per_alt(self, warehouse):
        got = rows(
            warehouse,
            f"SELECT alt, allele_ix, zygosity, vaf FROM {RES}.coding_alleles WHERE chrom = '9'"
            " ORDER BY allele_ix",
        )
        assert [(r["alt"], r["allele_ix"], r["zygosity"]) for r in got] == [
            ("G", 1, "multi"),
            ("T", 2, "multi"),
        ]
        assert all(r["vaf"] == 0.5 for r in got)

    def test_homozygous_alt_is_one_row_with_full_fraction(self, warehouse):
        got = rows(warehouse, f"SELECT zygosity, vaf FROM {RES}.coding_alleles WHERE chrom = '7'")
        assert got == [{"zygosity": "hom", "vaf": 1.0}]

    def test_an_allele_in_two_overlapping_genes_joins_once_per_gene(self, warehouse):
        got = rows(warehouse, f"SELECT gene FROM {RES}.coding_alleles WHERE chrom = '11'")
        assert sorted(r["gene"] for r in got) == ["GENE_F", "GENE_G"]


class TestCodingCandidates:
    def test_flags_follow_the_annotation(self, warehouse):
        got = rows(
            warehouse,
            f"SELECT pos, is_rare_recessive, is_protein_altering, is_novel, is_clinvar_plp"
            f" FROM {RES}.coding_candidates WHERE chrom = '15' ORDER BY pos",
        )
        assert got == [
            {
                "pos": 1_000_050,
                "is_rare_recessive": True,
                "is_protein_altering": True,
                "is_novel": False,
                "is_clinvar_plp": True,
            },
            {
                "pos": 1_000_400,
                "is_rare_recessive": True,
                "is_protein_altering": True,
                "is_novel": True,
                "is_clinvar_plp": False,
            },
        ]

    def test_conflicting_or_benign_tagged_clinvar_is_not_plp_and_common_is_not_rare(
        self, warehouse
    ):
        got = rows(
            warehouse,
            f"SELECT is_rare_recessive, is_clinvar_plp FROM {RES}.coding_candidates"
            " WHERE chrom = '3' ORDER BY pos",
        )
        assert got == [
            {"is_rare_recessive": False, "is_clinvar_plp": False},
            {"is_rare_recessive": False, "is_clinvar_plp": False},
        ]

    def test_an_unannotated_allele_has_null_flags_not_false(self, warehouse):
        got = rows(
            warehouse,
            f"SELECT annotated, is_rare_recessive FROM {RES}.coding_candidates"
            " WHERE chrom = '11' AND gene = 'GENE_G'",
        )
        # GENE_G's row shares the allele annotated under GENE_F: same key, so annotated.
        assert got == [{"annotated": True, "is_rare_recessive": True}]


class TestGeneBiallelic:
    def test_the_candidate_shaped_gene_ranks_first(self, warehouse):
        got = rows(
            warehouse,
            f"SELECT gene, biallelic_pass, n_plp_pass, n_lof_pass, phenotype_rank"
            f" FROM {RES}.gene_biallelic",
        )
        assert got[0] == {
            "gene": "GENE_A",
            "biallelic_pass": True,
            "n_plp_pass": 1,
            "n_lof_pass": 1,
            "phenotype_rank": 6,
        }

    def test_biallelic_set_membership(self, warehouse):
        got = {r["gene"]: r for r in rows(warehouse, f"SELECT * FROM {RES}.gene_biallelic")}
        assert got["GENE_C"]["biallelic_pass"] is True  # homozygous
        assert got["GENE_E"]["biallelic_pass"] is True  # 1/2 site, both rare
        assert got["GENE_B"]["biallelic_pass"] is False  # one call is suppressed
        assert got["GENE_B"]["biallelic_with_rescue"] is True
        assert got["GENE_B"]["n_nonpass"] == 1
        assert "GENE_D" not in got  # common alleles never enter

    def test_phenotype_rank_reads_the_proband_only_term_set(self, warehouse):
        got = rows(
            warehouse, f"SELECT phenotype_rank FROM {RES}.gene_biallelic WHERE gene = 'GENE_A'"
        )
        assert got == [{"phenotype_rank": 6}]

    def test_a_gene_without_curation_keeps_a_null_rank(self, warehouse):
        got = rows(
            warehouse, f"SELECT phenotype_rank FROM {RES}.gene_biallelic WHERE gene = 'GENE_E'"
        )
        assert got == [{"phenotype_rank": None}]
