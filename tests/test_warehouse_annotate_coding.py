"""The genome-wide annotator: checkpointing, resumption, and the panel-shaped landing.

No network and no Postgres. The database is an in-memory DuckDB attached as ``pg`` (the
same alias the real path uses), handed to the module by monkeypatching ``attached``; the
annotator is a fake that records what it was asked.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import duckdb
import pytest

from mva.pipeline.variant import Variant
from mva.pipeline.vep_response import VepRecord
from mva.warehouse import annotate_coding
from mva.warehouse.annotate_coding import CODING_TABLE, Checkpoint
from mva.warehouse.settings import Postgres

SETTINGS = Postgres(
    host="h",
    port="5432",
    database="d",
    user="u",
    password="p",
    schema="warehouse",
    result_schema="results",
)

ALLELES = [
    ("15", 100, "C", "T"),
    ("15", 400, "G", "A"),
    ("2", 500, "TA", "T"),
]


def record_for(variant: Variant, **fields) -> VepRecord:
    return VepRecord(variant=variant, **fields)


class FakeAnnotator:
    """Answers every allele with a missense call and remembers each batch it saw."""

    def __init__(self) -> None:
        self.batches: list[list[Variant]] = []
        self.requests = 0
        self.closed = False

    def version(self) -> dict[str, str]:
        return {"release": "116", "assembly": "GRCh38"}

    def annotate_many(self, variants):
        self.batches.append(list(variants))
        self.requests += 1
        return [
            record_for(
                v,
                gene="G",
                consequence="missense_variant",
                impact="MODERATE",
                gnomad_af=1e-5,
                clin_sig=("pathogenic",),
            )
            for v in variants
        ]

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def warehouse(monkeypatch) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("ATTACH ':memory:' AS pg")
    con.execute("CREATE SCHEMA pg.warehouse; CREATE SCHEMA pg.results")
    con.execute(
        "CREATE TABLE pg.results.coding_alleles (gene VARCHAR, chrom VARCHAR, pos BIGINT,"
        " ref VARCHAR, alt VARCHAR)"
    )
    con.executemany(
        "INSERT INTO pg.results.coding_alleles VALUES (?,?,?,?,?)",
        [("G", *a) for a in ALLELES] + [("G2", *ALLELES[0])],  # a duplicate across genes
    )

    @contextmanager
    def fake_attached(settings, read_only: bool = False):
        yield con

    monkeypatch.setattr(annotate_coding, "attached", fake_attached)
    return con


class TestCheckpoint:
    def test_round_trips_a_record_including_the_tuple_field(self, tmp_path: Path):
        store = Checkpoint(tmp_path / "cp")
        variant = Variant("chr15", 100, "C", "T")
        store.append(
            0, [record_for(variant, gene="BUB1B", clin_sig=("pathogenic", "likely_pathogenic"))]
        )
        loaded = store.load()
        assert loaded[variant].gene == "BUB1B"
        assert loaded[variant].clin_sig == ("pathogenic", "likely_pathogenic")
        assert loaded[variant].gnomad_af is None

    def test_next_index_continues_after_the_last_batch(self, tmp_path: Path):
        store = Checkpoint(tmp_path / "cp")
        assert store.next_index() == 0
        store.append(0, [])
        store.append(1, [])
        assert store.next_index() == 2

    def test_missing_directory_is_an_empty_checkpoint(self, tmp_path: Path):
        assert Checkpoint(tmp_path / "nope").load() == {}


class TestRun:
    def test_alleles_are_distinct_sorted_and_chr_prefixed(self, warehouse):
        found = annotate_coding.alleles(warehouse, "results")
        assert found == sorted(found)
        assert len(found) == 3
        assert all(v.chrom.startswith("chr") for v in found)

    def test_lands_a_panel_shaped_table_and_a_lineage_edge(self, warehouse, tmp_path: Path):
        fake = FakeAnnotator()
        result = annotate_coding.run(
            SETTINGS, batch_size=2, checkpoint=tmp_path / "cp", annotator=fake
        )
        assert result["rows"] == 3
        assert result["asked"] == 3
        assert [len(b) for b in fake.batches] == [2, 1]
        assert fake.closed is False  # injected annotators are the caller's to close
        columns = [
            r[0] for r in warehouse.execute(f"DESCRIBE pg.warehouse.{CODING_TABLE}").fetchall()
        ]
        assert columns == [
            "chrom",
            "pos",
            "ref",
            "alt",
            "rsid",
            "gene",
            "consequence",
            "impact",
            "gnomad_af",
            "gnomad_af_grpmax",
            "clin_sig",
            "annotated_at",
            "source",
        ]
        chroms = warehouse.execute(
            f"SELECT DISTINCT chrom FROM pg.warehouse.{CODING_TABLE} ORDER BY 1"
        ).fetchall()
        assert chroms == [("15",), ("2",)]  # written bare, the way variants_raw spells them
        edge = warehouse.execute(
            "SELECT target_table, source_kind, tool FROM pg.warehouse.data_lineage"
        ).fetchall()
        assert edge == [(CODING_TABLE, "api", "mva-warehouse annotate-coding")]

    def test_a_second_run_resumes_from_the_checkpoint(self, warehouse, tmp_path: Path):
        first = FakeAnnotator()
        annotate_coding.run(SETTINGS, batch_size=2, checkpoint=tmp_path / "cp", annotator=first)
        second = FakeAnnotator()
        result = annotate_coding.run(
            SETTINGS, batch_size=2, checkpoint=tmp_path / "cp", annotator=second
        )
        assert second.batches == []
        assert result["asked"] == 0
        assert result["rows"] == 3

    def test_concurrent_workers_checkpoint_every_batch_once(self, warehouse, tmp_path: Path):
        fake = FakeAnnotator()
        result = annotate_coding.run(
            SETTINGS, batch_size=1, checkpoint=tmp_path / "cp", annotator=fake, workers=3
        )
        assert result["rows"] == 3
        assert sorted(p.name for p in (tmp_path / "cp").glob("*.jsonl")) == [
            "batch-00000.jsonl",
            "batch-00001.jsonl",
            "batch-00002.jsonl",
        ]
        assert len(Checkpoint(tmp_path / "cp").load()) == 3

    def test_plan_counts_without_asking(self, warehouse, tmp_path: Path):
        store = Checkpoint(tmp_path / "cp")
        store.append(0, [record_for(Variant("chr15", 100, "C", "T"))])
        found = annotate_coding.plan(SETTINGS, 200, tmp_path / "cp")
        assert found == {"alleles": 3, "checkpointed": 1, "todo": 2, "batches": 1, "batch_size": 2}
