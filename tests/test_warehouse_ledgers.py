"""Tests for the two append-only ledgers: lineage edges and the oracle probe ledger.

No test here contacts a database. Both modules talk to PostgreSQL only through a DuckDB
connection object, so a fake that records the SQL it was handed and replays canned result
sets exercises every decision worth testing — which rows get repaired, which get skipped
as already done, what lands in ``notes``, and that nothing is ever UPDATEd or DELETEd.

That last one is the point of the ledgers, so it is asserted directly.
"""

from datetime import datetime

import pytest

from mva.warehouse import lineage, probes
from mva.warehouse.analysis import DERIVATIONS


class FakeConnection:
    """Records every statement; answers SELECTs from a queue of canned result sets."""

    def __init__(self, answers: list[list[tuple]] | None = None):
        self.statements: list[tuple[str, list]] = []
        self.answers = list(answers or [])
        self._last: list[tuple] = []

    def execute(self, sql: str, params: list | None = None):
        text = " ".join(sql.split())
        self.statements.append((text, list(params or [])))
        # Only a SELECT consumes a canned answer, so a test's answer queue lines up with
        # the reads it cares about and does not have to count CREATE/INSERT statements.
        self._last = (self.answers.pop(0)
                      if self.answers and text.upper().startswith("SELECT") else [])
        return self

    def fetchall(self) -> list[tuple]:
        return self._last

    def fetchone(self):
        return self._last[0] if self._last else None

    @property
    def sql_text(self) -> str:
        return "\n".join(sql for sql, _ in self.statements)

    def inserts(self) -> list[list]:
        return [params for sql, params in self.statements
                if sql.upper().startswith("INSERT")]


def test_ledgers_never_update_or_delete():
    """The whole claim of an append-only ledger, asserted rather than trusted."""
    connection = FakeConnection([
        [("/home/x/f.vcf.gz",)],  # placeholder, real shapes come from the tests below
    ])
    lineage.ensure_tables(connection, "warehouse")
    probes.ensure_table(connection, "warehouse")
    text = connection.sql_text.upper()
    assert "UPDATE " not in text and "DELETE " not in text and "DROP " not in text


STALE_EDGE = (datetime(2026, 8, 29, 16, 37, 29), "warehouse", "variants_raw", 5012204,
              "/home/abdu/ubuntu/data/WGS_EX2312012_HGWCNDSX7.vcf.gz",
              "read_csv all_varchar", "mva-warehouse", "columns: line_no + chrom")

OBJECT_ROW = ("WGS_EX2312012_HGWCNDSX7.vcf.gz", "source/WGS_EX2312012_HGWCNDSX7.vcf.gz",
              "bec64c68", "3a79ea8b", True)


class TestRepoint:
    def test_appends_an_s3_edge_carrying_hash_and_version(self):
        connection = FakeConnection([[STALE_EDGE], [], [OBJECT_ROW]])
        appended = lineage.repoint(connection, "warehouse", "mva")
        assert len(appended) == 1
        assert appended[0]["now"] == "s3://mva/source/WGS_EX2312012_HGWCNDSX7.vcf.gz"
        params = connection.inserts()[0]
        assert "s3://mva/source/WGS_EX2312012_HGWCNDSX7.vcf.gz" in params
        assert "bec64c68" in params and "3a79ea8b" in params
        assert params[3] == "object"

    def test_notes_name_the_row_being_superseded(self):
        connection = FakeConnection([[STALE_EDGE], [], [OBJECT_ROW]])
        lineage.repoint(connection, "warehouse", "mva")
        notes = connection.inserts()[0][-1]
        assert lineage.SUPERSEDES in notes and "2026-08-29 16:37:29" in notes

    def test_is_idempotent_once_the_target_has_an_object_edge(self):
        connection = FakeConnection(
            [[STALE_EDGE], [("warehouse", "variants_raw")], [OBJECT_ROW]])
        assert lineage.repoint(connection, "warehouse", "mva") == []
        assert connection.inserts() == []

    def test_leaves_an_edge_whose_file_is_not_in_the_inventory_alone(self):
        connection = FakeConnection([[STALE_EDGE], [], []])
        assert lineage.repoint(connection, "warehouse", "mva") == []

    def test_matches_by_file_name_not_by_a_hardcoded_delivery(self):
        other = (datetime(2026, 1, 1), "warehouse", "reads_raw", 10, "/tmp/other.fastq.gz",
                 "t", "mva-warehouse", "")
        connection = FakeConnection(
            [[other], [], [("other.fastq.gz", "source/other.fastq.gz", "aa", "bb", True)]])
        appended = lineage.repoint(connection, "warehouse", "mva")
        assert appended[0]["now"] == "s3://mva/source/other.fastq.gz"


RUNS = [(item.name, datetime(2026, 8, 29, 12, 49, 49, 377449), 8) for item in DERIVATIONS]


class TestBackfillDerivations:
    def test_appends_one_edge_per_logged_run(self):
        connection = FakeConnection([RUNS, []])
        appended = lineage.backfill_derivations(connection, "warehouse", "results")
        assert len(appended) == len(DERIVATIONS)
        assert len(connection.inserts()) == len(DERIVATIONS)

    def test_edge_names_the_declared_input_tables_qualified(self):
        connection = FakeConnection([RUNS, []])
        lineage.backfill_derivations(connection, "warehouse", "results")
        first = connection.inserts()[0]
        assert first[0] == "results" and first[1] == DERIVATIONS[0].name
        assert first[4] == ", ".join(
            f"warehouse.{table}" for table in DERIVATIONS[0].depends_on)
        assert first[3] == "table"

    def test_edge_carries_the_run_reference(self):
        connection = FakeConnection([RUNS, []])
        lineage.backfill_derivations(connection, "warehouse", "results")
        assert connection.inserts()[0][-1] == (
            lineage.RUN_REF + "2026-08-29 12:49:49.377449")

    def test_skips_runs_that_already_have_an_edge(self):
        have = [(name, lineage.RUN_REF + "2026-08-29 12:49:49.377449")
                for name, _, _ in RUNS]
        connection = FakeConnection([RUNS, have])
        assert lineage.backfill_derivations(connection, "warehouse", "results") == []

    def test_ignores_a_run_of_a_derivation_that_no_longer_exists(self):
        connection = FakeConnection([[("retired", datetime(2026, 1, 1), 3)], []])
        assert lineage.backfill_derivations(connection, "warehouse", "results") == []


class TestBudget:
    def test_remaining_counts_down_from_eighteen(self):
        assert probes.Budget(spent=0).remaining == probes.BUDGET == 18
        assert probes.Budget(spent=4).remaining == 14

    def test_never_goes_negative(self):
        assert probes.Budget(spent=25).remaining == 0

    def test_renders_both_halves(self):
        assert str(probes.Budget(spent=3)) == "3/18 spent, 15 remaining"

    def test_reads_a_count_off_the_connection(self):
        connection = FakeConnection([[(2,)]])
        assert probes.budget(connection, "warehouse").remaining == 16

    def test_can_be_scoped_to_one_track(self):
        connection = FakeConnection([[(1,)]])
        probes.budget(connection, "warehouse", track="2")
        assert connection.statements[-1][1] == ["2"]


class TestProbeLog:
    def test_appends_with_the_next_id(self):
        connection = FakeConnection([[(7,)]])
        assert probes.log(connection, "warehouse", probes.Probe(submitted_by="a")) == 7
        assert connection.inserts()[0][0] == 7

    def test_stores_every_field_it_was_given(self):
        connection = FakeConnection([[(1,)]])
        probe = probes.Probe(track="1", probe_type="S", submitted_by="abdu",
                             submission_ref="build/probe_s1.csv", payload="a,b\n1,2",
                             n_rows=10, response="rank_points=50", score=50.0,
                             rationale="singles scan")
        probes.log(connection, "warehouse", probe)
        params = connection.inserts()[0]
        for value in ("S", "abdu", "build/probe_s1.csv", "a,b\n1,2", "rank_points=50"):
            assert value in params
        assert 50.0 in params and 10 in params

    def test_creation_is_idempotent(self):
        connection = FakeConnection()
        probes.ensure_table(connection, "warehouse")
        assert "CREATE TABLE IF NOT EXISTS" in connection.sql_text

    def test_table_lives_in_the_ingest_schema_it_is_given(self):
        connection = FakeConnection()
        probes.ensure_table(connection, "warehouse")
        assert "pg.warehouse.probe_ledger" in connection.sql_text

    @pytest.mark.parametrize("schema", ["drop table x", "a-b", ""])
    def test_rejects_an_unsafe_schema_name(self, schema):
        from mva.warehouse.postgres import InvalidIdentifier
        with pytest.raises(InvalidIdentifier):
            probes.ensure_table(FakeConnection(), schema)


class TestListing:
    def test_columns_match_the_select(self):
        connection = FakeConnection([[]])
        probes.listing(connection, "warehouse")
        selected = connection.statements[0][0]
        assert selected.count(",") + 1 >= len(probes.LISTING_COLUMNS)
        assert "ORDER BY probe_id" in selected

    def test_limit_is_an_integer_not_interpolated_text(self):
        connection = FakeConnection([[]])
        probes.listing(connection, "warehouse", limit=5)
        assert connection.statements[0][0].endswith("LIMIT 5")


class TestEdges:
    def test_marks_the_newest_edge_per_target_as_current(self):
        connection = FakeConnection([[]])
        lineage.edges(connection, "warehouse")
        sql = connection.statements[0][0]
        assert "PARTITION BY target_schema, target_table" in sql
        assert "is_current" in sql


class TestLedgerCli:
    """The CLI handlers, with the database connection replaced by the fake.

    Worth testing separately: ``probe-log`` is the one verb that turns command-line flags
    into a stored row, and a flag wired to the wrong column would be discovered only when
    an irreplaceable submission had already been mis-recorded.
    """

    @staticmethod
    def _patch(monkeypatch, connection):
        import contextlib

        from mva.warehouse import cli_ledger

        @contextlib.contextmanager
        def fake_attached(settings, read_only=False):
            yield connection

        monkeypatch.setattr(cli_ledger, "attached", fake_attached)
        monkeypatch.setattr(cli_ledger, "_settings",
                            lambda: __import__("mva.warehouse.settings", fromlist=["x"])
                            .Postgres(schema="warehouse", result_schema="results"))
        return cli_ledger

    def test_probe_log_counts_rows_from_the_submission_csv(self, monkeypatch, tmp_path):
        connection = FakeConnection([[(1,)], [(1,)]])
        cli = self._patch(monkeypatch, connection)
        csv = tmp_path / "probe.csv"
        csv.write_text("proband_id,chrom_1\nPROBAND01,chr1\nPROBAND01,chr2\n")
        args = _Args(track="1", type="S", by="abdu", ref=None, payload=None,
                     payload_file=csv, rows=None, response="rank_points=50",
                     score=50.0, rationale="singles scan")
        assert cli.do_probe_log(args) == 0
        params = connection.inserts()[0]
        assert params[6] == 2                      # n_rows, counted from the CSV
        assert params[4] == str(csv)               # submission_ref defaults to the file
        assert "PROBAND01,chr1" in params[5]       # payload is the file's content

    def test_probe_list_prints_the_budget(self, monkeypatch, capsys):
        connection = FakeConnection([[], [(3,)]])
        cli = self._patch(monkeypatch, connection)
        cli.do_probe_list(_Args(limit=None))
        assert "3/18 spent, 15 remaining" in capsys.readouterr().out

    def test_lineage_repair_reports_when_there_is_nothing_to_do(self, monkeypatch, capsys):
        connection = FakeConnection([[], [], []])
        cli = self._patch(monkeypatch, connection)
        monkeypatch.setattr(cli, "object_store", lambda: _Args(bucket="mva"))
        assert cli.do_lineage_repair(_Args(bucket=None)) == 0
        assert "nothing to repair" in capsys.readouterr().out


class _Args:
    """A stand-in for the argparse namespace, holding exactly the attributes given."""

    def __init__(self, **fields):
        self.__dict__.update(fields)
