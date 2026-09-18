"""The score cache: what lands, what is skipped, and what the second run costs.

An in-memory DuckDB stands in for the hosted PostgreSQL. The production connection *is*
DuckDB with the server attached as ``pg``, so attaching an in-memory database under the
same alias exercises the real SQL rather than a mock of it.

Every value here is invented — fake allele ids, a fake model, fake numbers. No coordinate
appears: the cache is keyed on ``allele_id`` and never sees one.
"""

from __future__ import annotations

import duckdb
import pytest

from mva.zoo import cache
from mva.zoo.types import ALLELE_SCORES_COLUMNS, ALLELE_SCORES_TABLE, ScoreRow

SCHEMA = "warehouse"


@pytest.fixture
def connection():
    con = duckdb.connect()
    con.execute("ATTACH ':memory:' AS pg")
    con.execute(f"CREATE SCHEMA pg.{SCHEMA}")
    yield con
    con.close()


def row(allele: str, *, model: str = "alphamissense", score: float | None = 0.5) -> ScoreRow:
    return ScoreRow(
        allele_id=allele,
        model=model,
        version="fixture-1",
        score=score,
        aux={"am_class": "likely_pathogenic"},
        digest="d" * 8,
        venue="laptop",
        licence="CC-BY-NC-SA-4.0",
    )


def stored(connection) -> list[tuple]:
    return connection.execute(
        f"SELECT allele_id, model, version, score, aux, run_id FROM pg.{SCHEMA}."
        f"{ALLELE_SCORES_TABLE} ORDER BY allele_id"
    ).fetchall()


class TestEnsureTable:
    def test_creates_the_pinned_columns(self, connection):
        cache.ensure_table(connection, SCHEMA)
        found = connection.execute(f"DESCRIBE pg.{SCHEMA}.{ALLELE_SCORES_TABLE}").fetchall()
        assert [row[0] for row in found] == [name for name, _ in ALLELE_SCORES_COLUMNS]
        assert [row[1] for row in found] == [sql_type for _, sql_type in ALLELE_SCORES_COLUMNS]

    def test_is_idempotent(self, connection):
        cache.ensure_table(connection, SCHEMA)
        cache.ensure_table(connection, SCHEMA)
        assert stored(connection) == []


class TestWrite:
    def test_inserts_every_new_row(self, connection):
        written = cache.write(connection, SCHEMA, [row("aa"), row("bb")], run_id="r1")
        assert (written.inserted, written.skipped, written.offered) == (2, 0, 2)
        assert [item[0] for item in stored(connection)] == ["aa", "bb"]

    def test_stamps_the_run_id_on_every_row(self, connection):
        cache.write(connection, SCHEMA, [row("aa")], run_id="r1")
        assert stored(connection)[0][5] == "r1"

    def test_a_repeat_is_a_no_op(self, connection):
        cache.write(connection, SCHEMA, [row("aa"), row("bb")], run_id="r1")
        again = cache.write(connection, SCHEMA, [row("aa"), row("bb")], run_id="r2")
        assert (again.inserted, again.skipped) == (0, 2)
        assert len(stored(connection)) == 2
        assert {item[5] for item in stored(connection)} == {"r1"}

    def test_a_new_version_is_a_new_row(self, connection):
        cache.write(connection, SCHEMA, [row("aa")], run_id="r1")
        newer = ScoreRow(allele_id="aa", model="alphamissense", version="fixture-2", score=0.9)
        written = cache.write(connection, SCHEMA, [newer], run_id="r2")
        assert written.inserted == 1
        assert len(stored(connection)) == 2

    def test_a_different_model_is_a_new_row(self, connection):
        cache.write(connection, SCHEMA, [row("aa")], run_id="r1")
        written = cache.write(connection, SCHEMA, [row("aa", model="esm1b")], run_id="r2")
        assert written.inserted == 1

    def test_duplicates_inside_one_batch_collapse(self, connection):
        written = cache.write(connection, SCHEMA, [row("aa"), row("aa")], run_id="r1")
        assert (written.inserted, written.skipped) == (1, 1)
        assert len(stored(connection)) == 1

    def test_batching_does_not_change_the_outcome(self, connection):
        rows = [row(f"a{index:03d}") for index in range(25)]
        written = cache.write(connection, SCHEMA, rows, run_id="r1", batch=4)
        assert written.inserted == 25
        assert cache.write(connection, SCHEMA, rows, run_id="r2", batch=4).skipped == 25

    def test_a_null_score_is_stored_as_null(self, connection):
        cache.write(connection, SCHEMA, [row("aa", score=None)], run_id="r1")
        assert stored(connection)[0][3] is None

    def test_aux_is_stored_as_json_text(self, connection):
        cache.write(connection, SCHEMA, [row("aa")], run_id="r1")
        assert stored(connection)[0][4] == '{"am_class": "likely_pathogenic"}'

    def test_an_empty_iterable_writes_nothing(self, connection):
        written = cache.write(connection, SCHEMA, [], run_id="r1")
        assert (written.inserted, written.skipped) == (0, 0)


class TestRead:
    def test_round_trips_a_row(self, connection):
        cache.write(connection, SCHEMA, [row("aa")], run_id="r1")
        (found,) = cache.read(connection, SCHEMA)
        assert found.allele_id == "aa"
        assert found.aux == {"am_class": "likely_pathogenic"}
        assert found.licence == "CC-BY-NC-SA-4.0"
        assert found.run_id == "r1"

    def test_filters_by_model(self, connection):
        cache.write(connection, SCHEMA, [row("aa"), row("bb", model="esm1b")], run_id="r1")
        found = cache.read(connection, SCHEMA, model="esm1b")
        assert [item.allele_id for item in found] == ["bb"]

    def test_filters_by_allele(self, connection):
        cache.write(connection, SCHEMA, [row("aa"), row("bb")], run_id="r1")
        found = cache.read(connection, SCHEMA, allele_ids=["bb"])
        assert [item.allele_id for item in found] == ["bb"]

    def test_chunks_a_long_allele_list(self, connection):
        rows = [row(f"a{index:03d}") for index in range(10)]
        cache.write(connection, SCHEMA, rows, run_id="r1")
        found = cache.read(
            connection, SCHEMA, allele_ids=[item.allele_id for item in rows], batch=3
        )
        assert len(found) == 10

    def test_an_empty_allele_list_finds_nothing(self, connection):
        cache.write(connection, SCHEMA, [row("aa")], run_id="r1")
        assert cache.read(connection, SCHEMA, allele_ids=[]) == []

    def test_an_unreadable_aux_is_reported_not_raised(self, connection):
        cache.ensure_table(connection, SCHEMA)
        connection.execute(
            f"INSERT INTO pg.{SCHEMA}.{ALLELE_SCORES_TABLE} VALUES "
            "('aa','m','v','','0.1','not json','laptop','','r1',now())"
        )
        (found,) = cache.read(connection, SCHEMA)
        assert found.aux == {"_unparsed": "not json"}


class TestRunId:
    def test_is_sortable_and_unique(self):
        first, second = cache.run_id(), cache.run_id()
        assert first[:4] == "20" + first[2:4]
        assert first != second
        assert "T" in first and first.split("-")[0].endswith("Z")


class TestLineage:
    def test_appends_one_edge_naming_the_model(self, connection):
        cache.write(connection, SCHEMA, [row("aa")], run_id="r1")
        cache.lineage_row(
            connection,
            SCHEMA,
            model="alphamissense",
            version="fixture-1",
            run_id="r1",
            rows=1,
            digest="d" * 8,
            source_ref="warehouse.it2_insilico_annotations.am_pathogenicity",
        )
        edges = connection.execute(
            f"SELECT target_table, target_rows, transform, tool, notes, source_ref "
            f"FROM pg.{SCHEMA}.data_lineage"
        ).fetchall()
        assert edges == [
            (
                ALLELE_SCORES_TABLE,
                1,
                "it4-score:alphamissense",
                "mva-zoo",
                "run_id=r1",
                "warehouse.it2_insilico_annotations.am_pathogenicity",
            )
        ]

    def test_two_runs_append_two_edges(self, connection):
        for run in ("r1", "r2"):
            cache.lineage_row(connection, SCHEMA, model="esm1b", version="v1", run_id=run, rows=3)
        count = connection.execute(f"SELECT count(*) FROM pg.{SCHEMA}.data_lineage").fetchone()[0]
        assert count == 2
