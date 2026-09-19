"""What the pair ranking must do, and what it must refuse to do.

Two things are worth more than the rest: an unscored pair is *excluded*, never scored zero,
and the confirmed pair is found by gene symbol with no coordinate anywhere in the path.
"""

from __future__ import annotations

import duckdb
import pytest

from mva.zoo import rank
from mva.zoo.pairs import Pair, pairs_from_alleles, pairs_from_fixture

FIXTURES = "fixtures/it4"


def pair(gene: str, left: str, right: str, *, confirmed: bool = False) -> Pair:
    return Pair(gene=gene, left_id=left, right_id=right, phase="trans", is_confirmed=confirmed)


@pytest.fixture
def three_pairs() -> list[Pair]:
    return [
        pair("GA", "a1", "a2"),
        pair("GB", "b1", "b2", confirmed=True),
        pair("GC", "c1", "c2"),
    ]


# ── pair score ───────────────────────────────────────────────────────────────────────────


def test_pair_score_is_min_then_max():
    assert rank.pair_score({"x": 0.2, "y": 0.9}, pair("G", "x", "y")) == (0.2, 0.9)


def test_pair_score_is_none_when_either_half_is_unscored():
    assert rank.pair_score({"x": 0.2}, pair("G", "x", "y")) is None
    assert rank.pair_score({"y": 0.2}, pair("G", "x", "y")) is None
    assert rank.pair_score({}, pair("G", "x", "y")) is None


# ── ordering ─────────────────────────────────────────────────────────────────────────────


def test_ranking_orders_by_min_then_max(three_pairs):
    scores = {"a1": 0.9, "a2": 0.1, "b1": 0.5, "b2": 0.5, "c1": 0.4, "c2": 0.99}
    table = rank.rank_pairs(three_pairs, scores, model="m")
    assert [row.pair.gene for row in table.ranked] == ["GB", "GC", "GA"]
    assert [row.rank for row in table.ranked] == [1, 2, 3]
    assert table.ranked[0].min_score == 0.5


def test_ties_share_a_rank_and_the_next_rank_skips():
    pairs = [pair("G1", "a", "b"), pair("G2", "c", "d"), pair("G3", "e", "f")]
    scores = {"a": 0.5, "b": 0.5, "c": 0.5, "d": 0.5, "e": 0.1, "f": 0.1}
    table = rank.rank_pairs(pairs, scores, model="m")
    assert [row.rank for row in table.ranked] == [1, 1, 3]


def test_unscored_pairs_leave_the_lane_and_are_counted(three_pairs):
    scores = {"a1": 0.9, "a2": 0.1, "b1": 0.5}  # GB half-scored, GC not at all
    table = rank.rank_pairs(three_pairs, scores, model="m")
    assert table.n_ranked == 1
    assert table.unscored_pairs == 2
    assert table.scored_alleles == 3


# ── the confirmed pair ───────────────────────────────────────────────────────────────────


def test_confirmed_rank_reports_rank_and_percentiles(three_pairs):
    scores = {"a1": 0.9, "a2": 0.1, "b1": 0.5, "b2": 0.5, "c1": 0.4, "c2": 0.99}
    table = rank.rank_pairs(three_pairs, scores, model="m")
    found = rank.confirmed_rank(table, scores)
    assert found is not None
    assert (found.gene, found.rank, found.n_ranked) == ("GB", 1, 3)
    assert found.percentile == pytest.approx(100 * 1 / 3, abs=1e-3)
    # b1 = 0.5: two alleles score higher (0.9, 0.99), so it sits 3rd of 6 → 50 %.
    assert found.left_percentile == pytest.approx(50.0)
    assert found.right_percentile == pytest.approx(50.0)


def test_a_lane_that_cannot_score_the_pair_has_no_opinion_rather_than_a_bad_one(three_pairs):
    scores = {"a1": 0.9, "a2": 0.1, "b1": 0.5}
    table = rank.rank_pairs(three_pairs, scores, model="m")
    found = rank.confirmed_rank(table, scores)
    assert found is not None
    assert found.rank is None and found.percentile is None
    assert found.left_percentile is not None  # one half was scored, and that is reported
    assert found.right_percentile is None


def test_confirmed_rank_is_none_when_no_pair_is_flagged():
    table = rank.rank_pairs([pair("G", "x", "y")], {"x": 1.0, "y": 1.0}, model="m")
    assert rank.confirmed_rank(table, {"x": 1.0, "y": 1.0}) is None


def test_rank_per_model_keeps_every_lane_separate(three_pairs):
    scores = {
        "one": {"a1": 0.9, "a2": 0.8, "b1": 0.1, "b2": 0.1},
        "two": {"b1": 0.9, "b2": 0.9, "c1": 0.2, "c2": 0.2},
    }
    ranks = rank.rank_per_model(three_pairs, scores)
    assert set(ranks) == {"one", "two"}
    assert ranks["one"].confirmed.rank == 2
    assert ranks["two"].confirmed.rank == 1


# ── building pairs from a fixture and from real-shaped rows ──────────────────────────────


def test_pairs_from_fixture_reads_the_flag():
    pairs = pairs_from_fixture(f"{FIXTURES}/pairs.tsv")
    assert len(pairs) == 20
    assert sum(1 for p in pairs if p.is_confirmed) == 1


def test_pair_key_is_order_independent():
    assert pair("G", "x", "y").key == pair("G", "y", "x").key


def test_pairs_from_alleles_uses_the_pipeline_and_flags_the_confirmed_gene():
    # Synthetic rows in the shape of results.coding_alleles. Positions are invented and tiny.
    rows = [
        {"gene": "BUB1B", "chrom": "1", "pos": 101, "ref": "A", "alt": "T", "gt": "0/1"},
        {"gene": "BUB1B", "chrom": "1", "pos": 202, "ref": "C", "alt": "G", "gt": "0/1"},
        {"gene": "OTHER", "chrom": "1", "pos": 303, "ref": "G", "alt": "A", "gt": "0/1"},
        {"gene": "OTHER", "chrom": "1", "pos": 404, "ref": "T", "alt": "C", "gt": "0/1"},
    ]
    built = pairs_from_alleles(rows, confirmed_gene="BUB1B")
    assert built.genes == 2
    assert len(built.pairs) == 2
    confirmed = [p for p in built.pairs if p.is_confirmed]
    assert [p.gene for p in confirmed] == ["BUB1B"]
    assert "flagged confirmed" in built.confirmed_note


def test_a_cis_pair_never_becomes_a_candidate():
    rows = [
        {"gene": "G", "chrom": "1", "pos": 101, "ref": "A", "alt": "T", "gt": "0|1",
         "pgt": "0|1", "pid": "ps1"},
        {"gene": "G", "chrom": "1", "pos": 105, "ref": "C", "alt": "G", "gt": "0|1",
         "pgt": "0|1", "pid": "ps1"},
    ]  # fmt: skip
    assert pairs_from_alleles(rows).pairs == []


def test_two_pairs_in_the_confirmed_gene_are_told_apart_by_consequence():
    from mva.zoo.types import allele_id

    rows = [
        {"gene": "BUB1B", "chrom": "1", "pos": 101, "ref": "A", "alt": "T", "gt": "0/1"},
        {"gene": "BUB1B", "chrom": "1", "pos": 202, "ref": "C", "alt": "G", "gt": "0/1"},
        {"gene": "BUB1B", "chrom": "1", "pos": 303, "ref": "G", "alt": "A", "gt": "0/1"},
    ]
    consequences = {
        allele_id("1", 101, "A", "T"): "stop_gained",
        allele_id("1", 202, "C", "G"): "missense_variant",
        allele_id("1", 303, "G", "A"): "synonymous_variant",
    }
    built = pairs_from_alleles(rows, confirmed_gene="BUB1B", consequences=consequences)
    confirmed = [p for p in built.pairs if p.is_confirmed]
    assert len(confirmed) == 1
    assert set(confirmed[0].key[1:]) == {
        allele_id("1", 101, "A", "T"),
        allele_id("1", 202, "C", "G"),
    }


def test_an_ambiguous_confirmed_gene_flags_them_all_and_says_so():
    rows = [
        {"gene": "BUB1B", "chrom": "1", "pos": 101, "ref": "A", "alt": "T", "gt": "0/1"},
        {"gene": "BUB1B", "chrom": "1", "pos": 202, "ref": "C", "alt": "G", "gt": "0/1"},
        {"gene": "BUB1B", "chrom": "1", "pos": 303, "ref": "G", "alt": "A", "gt": "0/1"},
    ]
    # no consequences → the lof+missense rule cannot single one out
    built = pairs_from_alleles(rows, confirmed_gene="BUB1B")
    assert sum(1 for p in built.pairs if p.is_confirmed) == 3
    assert "all 3 are flagged confirmed" in built.confirmed_note


def test_a_gene_with_too_many_het_calls_is_skipped_and_named():
    rows = [
        {"gene": "BIG", "chrom": "1", "pos": 100 + i, "ref": "A", "alt": "T", "gt": "0/1"}
        for i in range(10)
    ]
    built = pairs_from_alleles(rows, max_calls_per_gene=5)
    assert built.pairs == []
    assert built.skipped_genes == ("BIG",)


# ── the read-only table ──────────────────────────────────────────────────────────────────


def test_read_only_percentiles_cover_only_the_read_only_alleles():
    records = [
        {"allele_id": "r1", "gene": "G", "consequence": "missense", "is_read_only": True},
        {"allele_id": "v1", "gene": "G", "consequence": "missense", "is_read_only": False},
    ]
    rows = rank.read_only_percentiles({"m": {"r1": 0.9, "v1": 0.1}}, records)
    assert [row["allele_id"] for row in rows] == ["r1"]
    assert rows[0]["percentile"] == pytest.approx(50.0)
    assert rows[0]["n_scored"] == 2


# ── the warehouse writer ─────────────────────────────────────────────────────────────────


@pytest.fixture
def connection():
    con = duckdb.connect()
    con.execute("ATTACH ':memory:' AS pg")
    con.execute("CREATE SCHEMA pg.results")
    # The real warehouse has two schemas: `results` holds what a stage writes,
    # `warehouse` holds the append-only data_lineage edge list. Emulating only one
    # let a writer point its lineage at `results` and pass here while failing on the
    # first real run (entry 128).
    con.execute("CREATE SCHEMA pg.warehouse")
    from mva.warehouse.lineage import ensure_lineage_table

    ensure_lineage_table(con, "results")
    return con


def test_write_ranks_appends_rows_and_one_lineage_edge(connection, three_pairs):
    scores = {"a1": 0.9, "a2": 0.1, "b1": 0.5, "b2": 0.5, "c1": 0.4, "c2": 0.99}
    ranks = rank.rank_per_model(three_pairs, {"m": scores})
    written = rank.write_ranks(connection, "results", ranks, run_id="run-1")
    assert written == 3
    rows = connection.execute(
        f"SELECT model, rank, is_confirmed FROM pg.results.{rank.MODEL_RANKS_TABLE} ORDER BY rank"
    ).fetchall()
    assert rows[0] == ("m", 1, True)
    edges = connection.execute(
        "SELECT target_table, target_rows FROM pg.warehouse.data_lineage"
    ).fetchall()
    assert edges == [(rank.MODEL_RANKS_TABLE, 3)]


def test_the_confirmed_pair_is_written_even_below_the_top_cut(connection, three_pairs):
    scores = {"a1": 0.9, "a2": 0.9, "b1": 0.1, "b2": 0.1, "c1": 0.5, "c2": 0.5}
    ranks = rank.rank_per_model(three_pairs, {"m": scores})
    rank.write_ranks(connection, "results", ranks, run_id="run-1", top=1)
    kept = connection.execute(
        f"SELECT gene, rank FROM pg.results.{rank.MODEL_RANKS_TABLE} ORDER BY rank"
    ).fetchall()
    assert kept == [("GA", 1), ("GB", 3)]


def test_no_coordinate_column_exists_in_the_rank_table():
    names = {name for name, _ in rank.MODEL_RANKS_COLUMNS}
    assert not names & {"chrom", "pos", "ref", "alt"}
