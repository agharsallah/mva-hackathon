"""Step 1's output half: the table, the parquet, the manifest, the lineage edge, the counts.

Split from ``test_zoo_record.py`` so neither file outgrows the 600-line test limit, and
because the two halves test different things: that file pins what is *read* out of the
warehouse, this one pins what is *written* back and what the run says about itself. The
miniature warehouse and the fake annotator are imported rather than rebuilt — one fixture,
one meaning.
"""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from pathlib import Path

import pytest

from mva.warehouse.settings import Postgres
from mva.zoo import record as rec
from mva.zoo.types import RECORD_COLUMNS, RECORDS_TABLE, AlleleRecord
from test_zoo_record import SCHEMAS, FakeVep, fixture_rows, make_warehouse

SETTINGS = Postgres(schema="warehouse", result_schema="results")


@pytest.fixture
def warehouse():
    """The same miniature warehouse the read half uses — one fixture, one meaning."""
    connection = make_warehouse(fixture_rows())
    yield connection
    connection.close()


@contextmanager
def _attached(_settings, read_only: bool = False):
    """Stand in for :func:`mva.warehouse.postgres.attached`: hand back the test database."""
    yield CONNECTION[0]


#: Set by the two ``TestRun`` cases before they monkeypatch ``attached``.
CONNECTION: list = [None]


class TestWrite:
    def _written(self, connection, tmp_path, records, coordinates, **kwargs):
        return rec.write(
            connection,
            "results",
            "warehouse",
            records,
            coordinates,
            out_dir=tmp_path,
            run_id="test-run",
            inputs={"results.coding_alleles": 3},
            parameters={"mask_catalogue": False},
            source="ensembl-vep-rest release=116 assembly=GRCh38",
            **kwargs,
        )

    def test_the_table_holds_the_pinned_columns_and_no_coordinate(self, warehouse, tmp_path):
        built = rec.read_alleles(warehouse, SCHEMAS)

        written = self._written(warehouse, tmp_path, built.records, built.coordinates)

        columns = warehouse.execute(f"SELECT * FROM pg.results.{RECORDS_TABLE} LIMIT 0").description
        assert [name for name, *_ in columns] == [name for name, _kind in RECORD_COLUMNS]
        assert written.rows == len(built.records)
        count = warehouse.execute(f"SELECT count(*) FROM pg.results.{RECORDS_TABLE}").fetchone()
        assert count is not None and count[0] == len(built.records)

    def test_a_second_run_replaces_rather_than_doubles(self, warehouse, tmp_path):
        built = rec.read_alleles(warehouse, SCHEMAS)

        self._written(warehouse, tmp_path, built.records, built.coordinates)
        self._written(warehouse, tmp_path, built.records, built.coordinates)

        count = warehouse.execute(f"SELECT count(*) FROM pg.results.{RECORDS_TABLE}").fetchone()
        assert count is not None and count[0] == len(built.records)

    def test_the_parquet_carries_the_coordinate_the_table_may_not(self, warehouse, tmp_path):
        built = rec.read_alleles(warehouse, SCHEMAS)

        written = self._written(warehouse, tmp_path, built.records, built.coordinates)

        parquet = str(written.parquet).replace("'", "''")
        columns = warehouse.execute(f"SELECT * FROM '{parquet}' LIMIT 0").description
        assert {"chrom", "pos", "ref", "alt"} <= {name for name, *_ in columns}
        rows = warehouse.execute(f"SELECT count(*) FROM '{parquet}'").fetchone()
        assert rows is not None and rows[0] == len(built.records)

    def test_the_digest_is_the_parquet_on_disk(self, warehouse, tmp_path):
        built = rec.read_alleles(warehouse, SCHEMAS, limit=10)

        written = self._written(warehouse, tmp_path, built.records, built.coordinates)

        assert written.sha256 == hashlib.sha256(written.parquet.read_bytes()).hexdigest()

    def test_the_manifest_names_inputs_parameters_counts_and_the_digest(self, warehouse, tmp_path):
        built = rec.read_alleles(warehouse, SCHEMAS)

        written = self._written(warehouse, tmp_path, built.records, built.coordinates)

        payload = json.loads(written.provenance.read_text())
        assert payload["sha256"] == written.sha256
        assert payload["run_id"] == "test-run"
        assert payload["transform"] == rec.TRANSFORM
        assert payload["inputs"] == {"results.coding_alleles": 3}
        assert payload["parameters"] == {"mask_catalogue": False}
        assert payload["rows"]["total"] == len(built.records)
        assert payload["rows"]["read_only"] == 5
        assert payload["annotation_source"].startswith("ensembl-vep-rest")
        assert "chrom" in payload["columns"]

    def test_one_lineage_edge_names_the_transform(self, warehouse, tmp_path):
        built = rec.read_alleles(warehouse, SCHEMAS, limit=5)

        written = self._written(warehouse, tmp_path, built.records, built.coordinates)

        edge = warehouse.execute(
            "SELECT target_schema, target_table, target_rows, transform, tool, source_sha256 "
            "FROM pg.warehouse.data_lineage"
        ).fetchall()
        assert len(edge) == 1
        schema, table, count, transform, tool, digest = edge[0]
        assert (schema, table, count) == ("results", RECORDS_TABLE, 5)
        assert transform.startswith(rec.TRANSFORM)
        assert tool == rec.TOOL
        assert digest == written.sha256

    def test_the_parquet_column_list_covers_every_record_field(self):
        names = {name for name, _kind in rec.PARQUET_COLUMNS}

        assert set(AlleleRecord("x").__dict__) <= names
        assert {"chrom", "pos", "ref", "alt", "built_at", "source", "run_id"} <= names
        assert "uniprot" in names


class TestRun:
    def test_the_summary_counts_what_the_pass_produced(self, warehouse, tmp_path, monkeypatch):
        CONNECTION[0] = warehouse
        monkeypatch.setattr(rec, "attached", _attached)
        settings = SETTINGS

        summary = rec.run(
            settings, mask_catalogue=False, out_dir=tmp_path, annotator=FakeVep(skip=10)
        )

        assert summary.total == summary.coding + summary.read_only
        assert summary.read_only == 5
        assert summary.with_hgvs_c > 0
        assert 0.0 < summary.p4_1a_fraction < 1.0
        assert summary.sha256 and Path(summary.parquet).exists()
        assert Path(summary.provenance).exists()
        assert sum(summary.by_consequence.values()) == summary.total
        assert summary.source.startswith("ensembl-vep-rest")
        assert summary.masked is False

    def test_mask_catalogue_is_recorded_in_the_summary_and_the_table(
        self, warehouse, tmp_path, monkeypatch
    ):
        CONNECTION[0] = warehouse
        monkeypatch.setattr(rec, "attached", _attached)
        settings = SETTINGS

        summary = rec.run(
            settings, mask_catalogue=True, out_dir=tmp_path, annotator=FakeVep(), limit=40
        )

        assert summary.masked is True
        assert summary.total == 40
        found = warehouse.execute(
            f"SELECT count(*) FROM pg.results.{RECORDS_TABLE} WHERE clin_sig IS NOT NULL"
        ).fetchone()
        assert found is not None and found[0] == 0

    def test_p4_1a_is_computed_not_judged(self):
        """The threshold lives in the plan and the methodology entry, never in the code."""
        records = [
            AlleleRecord("a", hgvs_c="c.1A>G"),
            AlleleRecord("b", hgvs_p="p.Ala1Gly"),
            AlleleRecord("c"),
            AlleleRecord("d", is_read_only=True),
        ]

        summary = rec.summarise(records)

        assert (summary.coding, summary.read_only) == (3, 1)
        assert summary.p4_1a_fraction == pytest.approx(2 / 3)
