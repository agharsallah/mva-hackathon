"""Step 3's SQL, executed against tables small enough to reason about by hand.

The derivations in :mod:`mva.warehouse.analysis_it2_kmer` decide three things the step's
verdicts rest on:

* **what "confirmed" means** — the alignment-free model put the posterior floor on the same
  class the caller spelled, with a full probe set, and nothing looser counts (H027);
* **that reachability is carried, not applied** — a gene the stage-0 gate excluded still
  appears, with its flag, so an absence there is never quoted as a finding (H029);
* **filter symmetry** — targets and decoys go through exactly the same SQL, because H020 is
  refuted and a target-gene result does not outweigh a decoy's before the filter.

Each is tested by running the real SQL, unmodified, over a handful of rows in an in-memory
DuckDB. These are fixtures, not the child's data: they prove the rule the SQL implements,
never a number in the report.
"""

import duckdb
import pytest

from mva.warehouse.analysis_it2_kmer import (
    IT2_KMER_CONFIRMATION,
    IT2_KMER_PAIRS,
    IT2_KMER_REACH,
)
from mva.warehouse.derivation import resolve

SCHEMA = """
CREATE TABLE it2_kmer_genotypes (
    symbol VARCHAR, tier VARCHAR, origin VARCHAR, allele_ordinal BIGINT, novel BOOLEAN,
    probes BIGINT, probes_agreeing BIGINT, ref_count BIGINT, alt_count BIGINT,
    call VARCHAR, posterior DOUBLE, caller_genotype VARCHAR, confirms_caller BOOLEAN,
    reachable BOOLEAN
);
CREATE TABLE it2_mapq_profile (
    symbol VARCHAR, tier VARCHAR, reads BIGINT, mapq0 BIGINT, mapq0_fraction DOUBLE,
    median_mapq DOUBLE, mean_mapq DOUBLE, bait_density DOUBLE,
    sparse_bait BOOLEAN, mapq_refused BOOLEAN, reachable BOOLEAN
);
"""


@pytest.fixture
def db():
    connection = duckdb.connect()
    connection.execute(SCHEMA)
    return connection


def run(connection, derivation):
    sql = resolve(derivation.sql, "main", "main")
    cursor = connection.execute(sql)
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def add_gene(connection, symbol, tier, *, reachable=True, sparse=False, refused=False, density=0.9):
    connection.execute(
        "INSERT INTO it2_mapq_profile VALUES (?, ?, 1000, 1, 0.001, 60.0, 58.0, ?, ?, ?, ?)",
        [symbol, tier, density, sparse, refused, reachable],
    )


def add_call(
    connection,
    symbol,
    tier,
    ordinal,
    *,
    novel=False,
    probes=3,
    agreeing=3,
    call="het",
    posterior=0.99,
    caller="0/1",
    confirms=True,
    reachable=True,
    origin="reads",
):
    connection.execute(
        "INSERT INTO it2_kmer_genotypes VALUES (?,?,?,?,?,?,?,20,20,?,?,?,?,?)",
        [
            symbol,
            tier,
            origin,
            ordinal,
            novel,
            probes,
            agreeing,
            call,
            posterior,
            caller,
            confirms,
            reachable,
        ],
    )


def test_confirmation_is_split_by_whether_the_vendor_had_ever_seen_the_allele(db):
    """The 1,199 the delivered callset never reported are the claim with the most leverage
    in the step, so they are counted separately rather than folded into one rate."""
    add_call(db, "A", "core", 1, novel=False, confirms=True)
    add_call(db, "A", "core", 2, novel=True, confirms=True)
    add_call(db, "A", "core", 3, novel=True, confirms=False, call="hom-ref")
    rows = {row["novel"]: row for row in run(db, IT2_KMER_CONFIRMATION)}
    assert rows[False]["confirmed"] == 1 and rows[False]["alleles"] == 1
    assert rows[True]["alleles"] == 2 and rows[True]["confirmed"] == 1
    assert rows[True]["confirmed_fraction"] == pytest.approx(0.5)


def test_an_allele_no_caller_reported_is_not_in_the_confirmation_rate(db):
    """A ClinVar allele nobody called cannot confirm or contradict a caller. Counting it
    would put every absent published allele into the denominator of H027."""
    add_call(db, "A", "core", 1, caller="", confirms=False, origin="clinvar")
    add_call(db, "A", "core", 2, caller="0/1", confirms=True)
    rows = run(db, IT2_KMER_CONFIRMATION)
    assert sum(row["alleles"] for row in rows) == 1


def test_a_no_call_counts_against_confirmation_rather_than_vanishing(db):
    """ "The instrument could not say" is not "the instrument agreed"."""
    add_call(db, "A", "core", 1, call="no-call", confirms=False, posterior=0.4)
    add_call(db, "A", "core", 2, confirms=True)
    row = next(r for r in run(db, IT2_KMER_CONFIRMATION) if not r["novel"])
    assert row["alleles"] == 2 and row["no_call"] == 1
    assert row["confirmed_fraction"] == pytest.approx(0.5)


def test_alleles_without_a_full_probe_set_leave_the_denominator(db):
    """A call made on one probe cannot show disagreement, so it is not evidence either way
    and does not get to dilute the rate."""
    add_call(db, "A", "core", 1, probes=1, confirms=True)
    add_call(db, "A", "core", 2, probes=3, confirms=True)
    row = next(r for r in run(db, IT2_KMER_CONFIRMATION) if not r["novel"])
    assert row["alleles"] == 2 and row["fully_probed"] == 1
    # Both sides of the rate are restricted to fully-probed alleles, so the one-probe call
    # neither dilutes it nor — as it did before this test was written — pushes it above 1.
    assert row["confirmed"] == 1
    assert row["confirmed_fraction"] == pytest.approx(1.0)


def test_decoys_appear_beside_targets_under_the_same_rule(db):
    add_call(db, "A", "core", 1, confirms=True)
    add_call(db, "D", "decoy", 1, confirms=True)
    tiers = {row["tier"] for row in run(db, IT2_KMER_CONFIRMATION)}
    assert tiers == {"core", "decoy"}


def test_an_unreachable_gene_still_appears_with_its_flag(db):
    """Entry 093's gate flags genes; it does not delete them. An absence in an excluded
    gene must be visible as an absence-with-a-reason, not as no row at all."""
    add_gene(db, "THIN", "net", reachable=False, sparse=True)
    rows = run(db, IT2_KMER_REACH)
    assert len(rows) == 1
    assert rows[0]["reachable"] is False and rows[0]["genes"] == 1


def test_a_confident_call_in_an_excluded_gene_is_counted_because_that_would_refute_h029(db):
    add_gene(db, "THIN", "net", reachable=False, sparse=True)
    add_call(db, "THIN", "net", 1, call="het", posterior=0.99, reachable=False)
    row = run(db, IT2_KMER_REACH)[0]
    assert row["alleles"] == 1 and row["confident_calls"] == 1
    assert row["confident_and_unanimous"] == 1
    assert row["confident_fraction"] == pytest.approx(1.0)


def test_reach_separates_the_two_reasons_a_gene_was_excluded(db):
    """Sparse bait and a refusing aligner are different failures with different fixes, and
    entry 093 found they almost never coincide."""
    add_gene(db, "SPARSE", "net", reachable=False, sparse=True, refused=False)
    add_gene(db, "REFUSED", "net", reachable=False, sparse=False, refused=True)
    rows = run(db, IT2_KMER_REACH)
    assert len(rows) == 2
    assert {(r["sparse_bait"], r["mapq_refused"]) for r in rows} == {(True, False), (False, True)}


def test_two_confirmed_heterozygous_alleles_make_a_gene_biallelic(db):
    add_gene(db, "A", "core")
    add_call(db, "A", "core", 1)
    add_call(db, "A", "core", 2)
    row = next(r for r in run(db, IT2_KMER_PAIRS) if r["symbol"] == "A")
    assert row["confirmed_het"] == 2 and row["biallelic_confirmed"] is True


def test_one_confirmed_allele_does_not(db):
    add_gene(db, "A", "core")
    add_call(db, "A", "core", 1)
    row = next(r for r in run(db, IT2_KMER_PAIRS) if r["symbol"] == "A")
    assert row["confirmed_het"] == 1 and row["biallelic_confirmed"] is False


def test_a_call_whose_probes_disagree_does_not_count_towards_a_pair(db):
    """Disagreement between probes is the signal that one of them was destroyed by a
    neighbouring variant, and a genotype built on it is not corroboration."""
    add_gene(db, "A", "core")
    add_call(db, "A", "core", 1, probes=3, agreeing=2)
    add_call(db, "A", "core", 2, probes=3, agreeing=3)
    row = next(r for r in run(db, IT2_KMER_PAIRS) if r["symbol"] == "A")
    assert row["confirmed_het"] == 1 and row["biallelic_confirmed"] is False


def test_a_homozygous_call_is_not_two_heterozygous_ones(db):
    add_gene(db, "A", "core")
    add_call(db, "A", "core", 1, call="hom-alt", caller="1/1")
    row = next(r for r in run(db, IT2_KMER_PAIRS) if r["symbol"] == "A")
    assert row["confirmed_het"] == 0


def test_a_gene_with_no_calls_appears_with_zero_rather_than_disappearing(db):
    """A gene that yielded nothing is a result. Dropping it would make an absence
    indistinguishable from a gene that was never looked at."""
    add_gene(db, "QUIET", "core")
    row = next(r for r in run(db, IT2_KMER_PAIRS) if r["symbol"] == "QUIET")
    assert row["confirmed_het"] == 0 and row["biallelic_confirmed"] is False


def test_the_pair_rule_is_the_same_sql_for_a_decoy(db):
    add_gene(db, "A", "core")
    add_gene(db, "D", "decoy")
    for gene, tier in (("A", "core"), ("D", "decoy")):
        add_call(db, gene, tier, 1)
        add_call(db, gene, tier, 2)
    rows = {row["symbol"]: row for row in run(db, IT2_KMER_PAIRS)}
    assert rows["A"]["biallelic_confirmed"] == rows["D"]["biallelic_confirmed"] is True


def test_every_pair_row_carries_reachability_and_bait_density(db):
    add_gene(db, "A", "core", density=0.42)
    row = next(r for r in run(db, IT2_KMER_PAIRS) if r["symbol"] == "A")
    assert row["reachable"] is True and row["bait_density"] == pytest.approx(0.42)
