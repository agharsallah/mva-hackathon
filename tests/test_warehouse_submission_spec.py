"""Selectors: how a coordinate-free allele description becomes one warehouse row."""

from __future__ import annotations

import duckdb
import pytest

from mva.warehouse.submission_spec import Selector, SelectorError, resolve, to_sql


@pytest.fixture
def connection():
    con = duckdb.connect()
    con.execute("ATTACH ':memory:' AS pg")
    con.execute("CREATE SCHEMA pg.results")
    con.execute(
        "CREATE TABLE pg.results.coding_candidates ("
        "gene VARCHAR, chrom VARCHAR, pos BIGINT, ref VARCHAR, alt VARCHAR, "
        "consequence VARCHAR, gnomad_af DOUBLE, is_clinvar_plp BOOLEAN, rsid VARCHAR)"
    )
    con.execute(
        "INSERT INTO pg.results.coding_candidates VALUES "
        "('GENEA', '15', 1001, 'T', 'G', 'stop_gained', 3e-5, true, 'rs1'), "
        "('GENEA', '15', 1002, 'T', 'G', 'missense_variant', NULL, false, NULL), "
        "('GENEA', '15', 1002, 'T', 'G', 'missense_variant', NULL, false, NULL), "  # dup row
        "('GENEB', '2', 2001, 'C', 'A', 'missense_variant,splice_region_variant', "
        "0.5, false, 'rs2')"
    )
    return con


def selector(*where):
    return Selector.from_json("x", {"table": "results.coding_candidates", "where": list(where)})


def test_to_sql_binds_values_and_inlines_null_tests():
    sql, params = to_sql(selector(["gene", "=", "GENEA"], ["gnomad_af", "is", None]))
    assert sql.endswith("WHERE gene = ? AND gnomad_af IS NULL")
    assert sql.startswith("SELECT DISTINCT chrom, pos, ref, alt FROM pg.results.coding_candidates")
    assert params == ["GENEA"]


def test_a_selector_resolves_to_one_allele(connection):
    allele = resolve(
        connection, "stop", selector(["gene", "=", "GENEA"], ["consequence", "like", "%stop%"])
    )
    assert (allele.chrom, allele.pos, allele.ref, allele.alt) == ("15", 1001, "T", "G")


def test_duplicate_rows_of_the_same_allele_still_count_as_one(connection):
    allele = resolve(connection, "mis", selector(["gene", "=", "GENEA"], ["gnomad_af", "is", None]))
    assert allele.pos == 1002


def test_zero_or_many_matches_is_an_error_that_names_no_position(connection):
    with pytest.raises(SelectorError, match="matched 0 alleles") as info:
        resolve(connection, "none", selector(["gene", "=", "NOPE"]))
    assert "1001" not in str(info.value)
    with pytest.raises(SelectorError, match="matched 2 alleles") as info:
        resolve(connection, "many", selector(["gene", "=", "GENEA"]))
    assert "1001" not in str(info.value) and "1002" not in str(info.value)


@pytest.mark.parametrize(
    "raw",
    [
        {"table": "results.coding_candidates; DROP TABLE x", "where": [["gene", "=", "A"]]},
        {"table": "results.coding_candidates", "where": [["gene = 'A' OR 1", "=", "A"]]},
        {"table": "results.coding_candidates", "where": [["gene", "in", "A"]]},
        {"table": "results.coding_candidates", "where": [["gnomad_af", "is", 0.0]]},
        {"table": "results.coding_candidates", "where": []},
        {"table": "results.coding_candidates", "where": [["gene", "="]]},
    ],
)
def test_malformed_selectors_are_refused(raw):
    with pytest.raises(SelectorError):
        Selector.from_json("bad", raw)
