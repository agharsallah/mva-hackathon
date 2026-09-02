"""The `stats_af` derivation, run against a miniature DuckDB warehouse.

Hermetic in the style of `tests/test_warehouse_karyogram.py`: the real SQL out of the real
registry, a handful of `bcftools stats` lines built in memory. No network, no database.

The lines below are the **delivered** file's AF, SiS and SN lines, copied verbatim — they
are the measurement this derivation was written against, so a test that changed them would
stop testing the thing that matters. Everything else in the fixture is shaped, not
measured, and is there to prove a rule.
"""

import duckdb
import pytest

from mva.warehouse.analysis import DERIVATIONS, by_name
from mva.warehouse.analysis_stats import STATS_DERIVATIONS
from mva.warehouse.derivation import resolve

#: The delivered file's own lines for the three sections this derivation touches, verbatim.
#: Section codes measured in `pg.warehouse.stats_summary`: IDD 120, DP 55, ST 12, SN 9,
#: AF 2, SiS 1, TSTV 1 — 200 lines, no QUAL section anywhere.
DELIVERED = [
    (1, "SN\t0\tnumber of samples:\t1"),
    (2, "SN\t0\tnumber of records:\t5012204"),
    (11, "SiS\t0\t1\t2536505\t1665690\t870815\t644292\t0\t0\t644292"),
    (12, "AF\t0\t0.000000\t2536505\t1665690\t870815\t644292\t0\t0\t644292"),
    (13, "AF\t0\t0.990000\t1552121\t1032666\t519455\t346146\t0\t0\t346146"),
]

#: What the delivered genotype counter says, independently of the AF section. `1/2` is one
#: record carrying **two** different alternate alleles, so it contributes two.
GT_HET, GT_HOM, GT_TWO_ALT = 3_047_077, 1_898_267, 66_860


def build(connection, lines):
    connection.execute("CREATE SCHEMA IF NOT EXISTS src")
    connection.execute("DROP TABLE IF EXISTS src.stats_summary")
    values = ", ".join("(?, ?)" for _ in lines)
    connection.execute(
        f"CREATE TABLE src.stats_summary AS SELECT * FROM (VALUES {values}) AS t(line_no, line)",
        [item for row in lines for item in row],
    )
    return connection


def run(connection, name: str = "stats_af") -> list[dict]:
    relation = connection.sql(resolve(by_name(name).sql, "src"))
    return [dict(zip(relation.columns, row)) for row in relation.fetchall()]


@pytest.fixture()
def delivered():
    connection = build(duckdb.connect(), DELIVERED)
    yield connection
    connection.close()


# ── the registry wiring ──────────────────────────────────────────────────────────────


def test_the_derivation_is_in_the_one_registry_the_runner_reads():
    """A derivation nobody collected is a file, not an analysis."""
    assert STATS_DERIVATIONS
    for item in STATS_DERIVATIONS:
        assert item in DERIVATIONS
    assert by_name("stats_af").depends_on == ("stats_summary",)


def test_it_reads_only_the_ingest_schema():
    """A result table is not an input: `pg-derive` orders nothing between derivations."""
    sql = by_name("stats_af").sql
    assert "stats_sn" not in sql and "results." not in sql


# ── the parse ────────────────────────────────────────────────────────────────────────


def test_the_delivered_af_section_parses_to_exactly_two_rows(delivered):
    rows = run(delivered)
    assert [row["af_bin"] for row in rows] == [0.0, 0.99]


def test_the_counters_are_read_out_of_the_right_columns(delivered):
    """Off-by-one on `split_part` is the failure mode this table has; pin every field."""
    het, hom = run(delivered)
    assert (het["n_snps"], het["n_ts"], het["n_tv"], het["n_indels"]) == (
        2_536_505,
        1_665_690,
        870_815,
        644_292,
    )
    assert (hom["n_snps"], hom["n_ts"], hom["n_tv"], hom["n_indels"]) == (
        1_552_121,
        1_032_666,
        519_455,
        346_146,
    )


def test_transitions_and_transversions_account_for_every_snp(delivered):
    """bcftools' own invariant. If it fails, two columns were swapped."""
    for row in run(delivered):
        assert row["n_ts"] + row["n_tv"] == row["n_snps"]


def test_alleles_are_snps_plus_indels_and_the_shares_sum_to_a_hundred(delivered):
    rows = run(delivered)
    for row in rows:
        assert row["n_alleles"] == row["n_snps"] + row["n_indels"]
    assert round(sum(row["pct_of_alleles"] for row in rows), 2) == 100.00


def test_tstv_is_computed_per_bin_not_over_the_whole_callset(delivered):
    het, hom = run(delivered)
    assert het["ts_tv"] == round(1_665_690 / 870_815, 3) == 1.913
    assert hom["ts_tv"] == round(1_032_666 / 519_455, 3) == 1.988
    assert het["ts_tv"] < hom["ts_tv"]


# ── the reading, and the assumption it rests on ──────────────────────────────────────


def test_the_af_bins_are_the_genotype_counter_measured_a_second_way(delivered):
    """The whole zygosity reading stands on this identity, so it is asserted, not assumed.

    `bcftools` computed the AF section from AC/AN; the genotype counter counted GT strings.
    With one sample AN is 2, so AC=1 is a heterozygous allele and AC=2 a homozygous one —
    and the two independent counts agree exactly on the delivered file.
    """
    het, hom = run(delivered)
    assert het["n_alleles"] == GT_HET + 2 * GT_TWO_ALT
    assert hom["n_alleles"] == GT_HOM


def test_a_single_sample_callset_gets_the_zygosity_reading(delivered):
    het, hom = run(delivered)
    assert het["zygosity"] == "heterozygous"
    assert hom["zygosity"] == "homozygous alternate"


def test_more_than_one_sample_leaves_zygosity_null_rather_than_wrong():
    """With two samples AN is 4 and the bins are real frequencies; neither word applies."""
    lines = [(1, "SN\t0\tnumber of samples:\t2")] + DELIVERED[2:]
    connection = build(duckdb.connect(), lines)
    try:
        assert [row["zygosity"] for row in run(connection)] == [None, None]
    finally:
        connection.close()


def test_no_sn_line_at_all_also_leaves_zygosity_null():
    """A stats file without SN cannot license the reading either. `IS DISTINCT FROM`
    makes the empty scalar subquery behave, where `<> 1` would yield NULL and fall
    through to the ELSE branch."""
    connection = build(duckdb.connect(), DELIVERED[2:])
    try:
        assert [row["zygosity"] for row in run(connection)] == [None, None]
    finally:
        connection.close()


# ── what is deliberately not derived ─────────────────────────────────────────────────


def test_sis_is_the_af_singleton_bin_and_therefore_gets_no_table_of_its_own():
    """Measured on the delivery: the two lines carry identical counters."""
    sis = DELIVERED[2][1].split("\t")
    singleton = DELIVERED[3][1].split("\t")
    assert sis[3:7] == singleton[3:7]
    assert "stats_sis" not in {item.name for item in DERIVATIONS}


def test_no_derivation_claims_a_section_the_delivered_file_does_not_have():
    """QUAL, HWE, PSC and friends are absent from the delivery; nothing may parse them."""
    absent = ("QUAL", "HWE", "PSC", "PSI", "ICS", "GCsAF")
    for item in DERIVATIONS:
        for code in absent:
            assert f"'{code}' || chr(9)" not in item.sql


def test_the_repeat_columns_are_not_derived_because_the_flag_was_not_used():
    """Columns 8-10 need `bcftools stats -f <fasta>`; without it they are 0/0/everything."""
    for _, line in DELIVERED[3:]:
        fields = line.split("\t")
        assert (fields[7], fields[8], fields[9]) == ("0", "0", fields[6])
    assert "repeat" not in by_name("stats_af").sql.lower()


# ── the question is the catalogue entry, so it has to carry the warning ──────────────


def test_the_question_warns_that_af_here_is_not_a_population_frequency():
    """`catalog_semantics` shows this string as the table's `why`; it is the only place a
    reader of the catalogue meets the trap."""
    question = by_name("stats_af").question
    assert "NOT a population frequency" in question
    assert "zygosity" in question
