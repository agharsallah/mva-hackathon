"""Loading iteration 2's step-1 tables, and the lineage that must arrive with them.

The load itself is dull — two TSVs into two tables. The part worth testing is the
provenance rule the project runs on: a table built from the child's symptoms must record
*both* halves of where it came from, the public release and the clinical terms, or a
reader will assume a genomic origin it never had.
"""

import json
from pathlib import Path

import pytest

from mva.warehouse import it2_tables
from test_science_register import FakeConnection

MANIFEST = {
    "hpo_release": "hp/releases/2026-06-23",
    "parameters": {"seed": 20260910, "core_n": 50, "target_n": 300},
    "inputs": [
        {"path": "build/reference-scratch/hp.obo", "sha256": "aaa", "role": "the ontology graph"},
        {
            "path": "build/reference-scratch/genes_to_phenotype.txt",
            "sha256": "bbb",
            "role": "curation",
        },
    ],
    "clinical_input": {
        "source": "ressources/hackathon-rules/Challenge_Clinical_Phenotype_1.md",
        "term_sets": {"proband-only": ["HP:0002859"], "with-parental": ["HP:0002859"]},
    },
}


@pytest.fixture
def build_dir(tmp_path: Path) -> Path:
    (tmp_path / "provenance.json").write_text(json.dumps(MANIFEST), encoding="utf-8")
    (tmp_path / "targets.tsv").write_text(
        "symbol\ttier\tscore_rank\tscore\tentered_by\tterm_sets\nA\tcore\t1\t0.5\tscore\tproband-only\n",
        encoding="utf-8",
    )
    (tmp_path / "decoys.tsv").write_text(
        "symbol\tmatched_to\tcoding_length\texon_count\nZ\tA\t900\t7\n", encoding="utf-8"
    )
    return tmp_path


def _load(build_dir: Path) -> tuple[FakeConnection, list]:
    connection = FakeConnection([[(1,)], [(1,)]])
    loaded = it2_tables.load(
        connection, schema="warehouse", result_schema="results", out_dir=build_dir
    )
    return connection, loaded


def test_both_tables_are_written_into_the_result_schema(build_dir):
    connection, loaded = _load(build_dir)
    assert [item.table for item in loaded] == ["it2_targets", "it2_decoys"]
    for table in ("it2_targets", "it2_decoys"):
        assert f"pg.results.{table}" in connection.sql_text


def test_the_table_is_replaced_rather_than_appended_to(build_dir):
    """A partial old copy left behind would be a silent mixture of two runs."""
    connection, _ = _load(build_dir)
    assert connection.sql_text.count("DROP TABLE IF EXISTS") == 2


def test_every_table_records_both_the_public_release_and_the_clinical_terms(build_dir):
    connection, _ = _load(build_dir)
    lineage_rows = [params for sql, params in connection.inserts() if "data_lineage" in sql]
    kinds = [(row[1], row[3]) for row in lineage_rows]
    for table in ("it2_targets", "it2_decoys"):
        assert (table, "clinical") in kinds, "the child's terms are the case-specific input"
        assert kinds.count((table, "file")) == len(MANIFEST["inputs"])


def test_the_clinical_row_names_the_phenotype_document_and_both_term_sets(build_dir):
    connection, _ = _load(build_dir)
    clinical = next(
        params
        for sql, params in connection.inserts()
        if "data_lineage" in sql and params[3] == "clinical"
    )
    assert clinical[4] == MANIFEST["clinical_input"]["source"]
    assert clinical[5] == "proband-only,with-parental"


def test_the_decoy_lineage_names_the_seed_that_drew_it(build_dir):
    """The draw is reproducible only if the seed travels with the table."""
    connection, _ = _load(build_dir)
    transforms = [
        params[7]
        for sql, params in connection.inserts()
        if "data_lineage" in sql and params[1] == "it2_decoys"
    ]
    assert all("20260910" in transform for transform in transforms)
