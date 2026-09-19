"""The three tier-1 lanes, and the key they all agree on.

Everything here runs against ``fixtures/it4/`` — 200 synthetic allele records on a fake
chromosome, invented genes ``GENEA``–``GENEJ``, invented scores. No patient data is read
and no network call is made: the VEP lane is driven by a fake asker that returns canned
JSON.

The load-bearing assertion is :class:`TestAlleleIdSql`: the id computed in SQL must equal
:func:`mva.zoo.types.allele_id` for every row. A silent disagreement there would show up
much later as a lane with 0 % coverage and no error at all.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb
import pytest

from mva.zoo import adapters
from mva.zoo.adapters import duckdb_lookup, vep_rest
from mva.zoo.types import AlleleRecord, allele_id

FIXTURES = Path("fixtures/it4")
RECORDS_TSV = FIXTURES / "records.tsv"
SCHEMA = "warehouse"
ANNOTATIONS = "it2_insilico_annotations"


@dataclass
class Card:
    """The slice of a registry model card an adapter reads."""

    key: str
    version: str = "fixture-1"
    adapter: str = "duckdb_lookup"
    tier: int = 1
    source: str = "table"
    licence: str = "MIT"
    catalogue_adjacent: bool = False
    enabled: bool = True
    name: str = ""
    params: dict[str, Any] = field(default_factory=dict)


def read_tsv(connection: Any, path: Path) -> None:
    connection.execute(
        "CREATE OR REPLACE TEMP TABLE raw AS SELECT * FROM read_csv(?, delim='\t', header=true)",
        [str(path)],
    )


@pytest.fixture
def records_parquet(tmp_path: Path) -> Path:
    """The fixture records as the Parquet step 1 writes, coordinate columns and all."""
    target = tmp_path / "records.parquet"
    con = duckdb.connect()
    read_tsv(con, RECORDS_TSV)
    con.execute("COPY (SELECT * FROM raw) TO ? (FORMAT parquet)", [str(target)])
    con.close()
    return target


@pytest.fixture
def records(records_parquet: Path) -> list[AlleleRecord]:
    return adapters.records_from_parquet(records_parquet)


@pytest.fixture
def warehouse(tmp_path: Path):
    """An in-memory stand-in for the hosted warehouse, holding an annotations table.

    The score column is invented: every third record gets a number, the rest stay NULL, so
    the lane's coverage is a fact of the fixture rather than of the real table.
    """
    con = duckdb.connect()
    con.execute("ATTACH ':memory:' AS pg")
    con.execute(f"CREATE SCHEMA pg.{SCHEMA}")
    read_tsv(con, RECORDS_TSV)
    con.execute(f"""
        CREATE TABLE pg.{SCHEMA}.{ANNOTATIONS} AS
        SELECT chrom, pos, ref, alt, gene, consequence,
               CASE WHEN row_number() OVER (ORDER BY allele_id) % 3 = 0
                    THEN round(0.5 + 0.004 * (row_number() OVER (ORDER BY allele_id)), 4)
                    END AS am_pathogenicity,
               CASE WHEN row_number() OVER (ORDER BY allele_id) % 3 = 0
                    THEN 'likely_pathogenic' END AS am_class
        FROM raw
    """)
    yield con
    con.close()


class TestAlleleIdSql:
    def test_agrees_with_the_python_key_on_every_fixture_row(self, warehouse):
        rows = warehouse.execute(
            f"SELECT {adapters.allele_id_sql()}, chrom, pos, ref, alt "
            f"FROM pg.{SCHEMA}.{ANNOTATIONS}"
        ).fetchall()
        assert rows
        for computed, chrom, pos, ref, alt in rows:
            assert computed == allele_id(str(chrom), pos, ref, alt)

    @pytest.mark.parametrize("chrom", ["1", "chr1", "CHR1", "X", "chrX"])
    def test_agrees_on_both_contig_spellings(self, chrom):
        con = duckdb.connect()
        (computed,) = con.execute(
            f"SELECT {adapters.allele_id_sql()} FROM "
            "(SELECT ? AS chrom, ? AS pos, ? AS ref, ? AS alt)",
            [chrom, 700, "a", "g"],
        ).fetchone()
        con.close()
        assert computed == allele_id(chrom, 700, "a", "g")


class TestRecordsFromParquet:
    def test_loads_every_row_without_a_coordinate(self, records_parquet):
        found = adapters.records_from_parquet(records_parquet)
        assert len(found) == 200
        assert all(isinstance(item, AlleleRecord) for item in found)
        assert not any(hasattr(item, "pos") for item in found)

    def test_limit_stops_early(self, records_parquet):
        assert len(adapters.records_from_parquet(records_parquet, limit=7)) == 7

    def test_selects_by_allele_id(self, records_parquet, records):
        wanted = [records[3].allele_id, records[9].allele_id]
        found = adapters.records_from_parquet(records_parquet, allele_ids=wanted)
        assert sorted(item.allele_id for item in found) == sorted(wanted)

    def test_a_missing_file_says_what_to_run(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="mva-zoo records"):
            adapters.records_from_parquet(tmp_path / "absent.parquet")

    def test_masking_nulls_the_catalogue_field(self, records):
        with_class = [item for item in records if item.clin_sig]
        assert with_class
        assert all(item.masked().clin_sig is None for item in with_class)


class TestCoverageFromIds:
    def test_counts_overall_and_per_consequence(self, records):
        scored = {item.allele_id for item in records if item.consequence == "missense_variant"}
        coverage = adapters.coverage_from_ids("m", records, scored)
        assert coverage.scored == len(scored)
        assert coverage.total == len(records)
        assert coverage.by_consequence["missense_variant"][0] == len(scored)
        assert sum(total for _, total in coverage.by_consequence.values()) == len(records)

    def test_an_empty_record_set_is_zero_not_a_crash(self):
        coverage = adapters.coverage_from_ids("m", [], set())
        assert coverage.fraction == 0.0


class TestFactory:
    def test_dispatches_on_the_card(self, records_parquet):
        card = Card(key="esm1b", adapter="duckdb_lookup", params={"parquet": "nowhere.parquet"})
        built = adapters.build(card, records_parquet=records_parquet)
        assert isinstance(built, duckdb_lookup.DuckdbLookupAdapter)

    def test_accepts_the_dotted_module_path(self, records_parquet):
        card = Card(
            key="esm1b",
            adapter="mva.zoo.adapters.duckdb_lookup",
            params={"parquet": "nowhere.parquet"},
        )
        assert isinstance(
            adapters.build(card, records_parquet=records_parquet),
            duckdb_lookup.DuckdbLookupAdapter,
        )

    def test_an_unknown_lane_lists_the_known_ones(self):
        with pytest.raises(adapters.UnknownAdapterError, match="warehouse_column"):
            adapters.build(Card(key="x", adapter="telepathy"))

    def test_every_registered_module_supplies_a_build(self):
        import importlib

        for path in adapters.ADAPTER_MODULES.values():
            assert callable(importlib.import_module(path).build)


class TestWarehouseColumn:
    def card(self, **params: Any) -> Card:
        base = {"table": ANNOTATIONS, "column": "am_pathogenicity", "aux": ["am_class"]}
        return Card(
            key="alphamissense",
            adapter="warehouse_column",
            licence="CC-BY-NC-SA-4.0",
            params={**base, **params},
        )

    def build(self, warehouse, **params: Any):
        return adapters.build(self.card(**params), connection=warehouse)

    def test_coverage_counts_only_non_null_scores(self, warehouse, records):
        coverage = self.build(warehouse).coverage(records)
        expected = warehouse.execute(
            f"SELECT count(*) FROM pg.{SCHEMA}.{ANNOTATIONS} WHERE am_pathogenicity IS NOT NULL"
        ).fetchone()[0]
        assert coverage.scored == expected
        assert coverage.total == len(records)
        assert 0.0 < coverage.fraction < 1.0

    def test_scores_carry_the_aux_column_and_the_licence(self, warehouse, records):
        rows = list(self.build(warehouse).score(records))
        assert rows
        assert all(row.model == "alphamissense" for row in rows)
        assert all(row.aux["am_class"] == "likely_pathogenic" for row in rows)
        assert all(row.licence == "CC-BY-NC-SA-4.0" for row in rows)
        assert all(row.venue == "laptop" for row in rows)

    def test_a_row_is_yielded_only_for_the_alleles_asked_about(self, warehouse, records):
        asked = records[:10]
        rows = list(self.build(warehouse).score(asked))
        assert {row.allele_id for row in rows} <= {item.allele_id for item in asked}

    def test_never_emits_a_coordinate(self, warehouse, records):
        rows = list(self.build(warehouse).score(records))
        text = json.dumps([{"id": row.allele_id, "aux": row.aux} for row in rows])
        assert "chrom" not in text and "pos" not in text

    def test_the_lane_is_not_catalogue_adjacent(self, warehouse):
        assert self.build(warehouse).catalogue_adjacent is False
        assert self.build(warehouse).tier == 1

    def test_max_collapses_several_rows_for_one_allele(self, warehouse, records):
        target = records[2]
        warehouse.execute(
            f"INSERT INTO pg.{SCHEMA}.{ANNOTATIONS} "
            f"SELECT chrom, pos, ref, alt, gene, consequence, 0.99, 'pathogenic' "
            f"FROM pg.{SCHEMA}.{ANNOTATIONS} WHERE {adapters.allele_id_sql()} = ?",
            [target.allele_id],
        )
        warehouse.execute(
            f"INSERT INTO pg.{SCHEMA}.{ANNOTATIONS} "
            "VALUES (?, ?, ?, ?, 'GENEA', 'missense', 0.01, 'benign')",
            _coordinate(warehouse, target.allele_id),
        )
        rows = {
            row.allele_id: row
            for row in self.build(warehouse, score_transform="max").score([target])
        }
        assert rows[target.allele_id].score == pytest.approx(0.99)
        assert rows[target.allele_id].aux["am_class"] == "pathogenic"

    def test_an_unknown_transform_is_refused(self, warehouse):
        with pytest.raises(ValueError, match="score_transform"):
            self.build(warehouse, score_transform="median")

    def test_without_a_connection_the_lane_says_so(self):
        with pytest.raises(ValueError, match="connection"):
            adapters.build(self.card())

    def test_submit_is_not_a_tier_one_verb(self, warehouse, records):
        with pytest.raises(NotImplementedError, match="tier-1"):
            self.build(warehouse).submit(records)

    def test_score_sign_flips_a_column_that_points_the_other_way(self, warehouse, records):
        plain = {row.allele_id: row.score for row in self.build(warehouse).score(records)}
        flipped = {
            row.allele_id: row.score for row in self.build(warehouse, score_sign=-1).score(records)
        }
        assert flipped
        assert all(flipped[key] == pytest.approx(-value) for key, value in plain.items())

    def test_source_ref_names_the_column(self, warehouse):
        assert self.build(warehouse).source_ref == f"{SCHEMA}.{ANNOTATIONS}.am_pathogenicity"


def _coordinate(connection: Any, allele: str) -> list[Any]:
    return list(
        connection.execute(
            f"SELECT chrom, pos, ref, alt FROM pg.{SCHEMA}.{ANNOTATIONS} "
            f"WHERE {adapters.allele_id_sql()} = ? LIMIT 1",
            [allele],
        ).fetchone()
    )


@pytest.fixture
def esm1b_parquet(tmp_path: Path) -> Path:
    target = tmp_path / "esm1b.parquet"
    con = duckdb.connect()
    read_tsv(con, FIXTURES / "scores" / "esm1b.tsv")
    con.execute("COPY (SELECT * FROM raw) TO ? (FORMAT parquet)", [str(target)])
    con.close()
    return target


@pytest.fixture
def protein_parquet(tmp_path: Path, records: list[AlleleRecord]) -> Path:
    """A second table keyed on ``(gene, hgvs_p)`` — the other join shape a lane meets."""
    target = tmp_path / "protein.parquet"
    rows = [item for item in records if item.hgvs_p][:20]
    con = duckdb.connect()
    con.execute("CREATE TABLE t (gene VARCHAR, hgvs_p VARCHAR, llr DOUBLE, note VARCHAR)")
    con.executemany(
        "INSERT INTO t VALUES (?, ?, ?, ?)",
        [[item.gene, item.hgvs_p, 0.1 * index, f"n{index}"] for index, item in enumerate(rows)],
    )
    con.execute("COPY t TO ? (FORMAT parquet)", [str(target)])
    con.close()
    return target


class TestDuckdbLookup:
    def build(self, parquet: Path, **params: Any):
        card = Card(
            key="esm1b",
            adapter="duckdb_lookup",
            params={"parquet": str(parquet), "score_column": "score", **params},
        )
        return adapters.build(card)

    def test_joins_on_the_allele_id(self, esm1b_parquet, records):
        adapter = self.build(esm1b_parquet)
        rows = list(adapter.score(records))
        assert len(rows) == 50
        assert all(row.model == "esm1b" for row in rows)
        assert adapter.coverage(records).scored == 50

    def test_coverage_is_reported_per_consequence(self, esm1b_parquet, records):
        coverage = self.build(esm1b_parquet).coverage(records)
        assert coverage.total == len(records)
        assert sum(hit for hit, _ in coverage.by_consequence.values()) == coverage.scored

    def test_joins_on_a_two_field_key(self, protein_parquet, records):
        adapter = self.build(
            protein_parquet, key=["gene", "hgvs_p"], score_column="llr", aux=["note"]
        )
        rows = list(adapter.score(records))
        assert len(rows) >= 20
        assert all(row.aux["note"].startswith("n") for row in rows)

    def test_score_sign_flips_a_log_likelihood_ratio(self, esm1b_parquet, records):
        plain = {row.allele_id: row.score for row in self.build(esm1b_parquet).score(records)}
        flipped = {
            row.allele_id: row.score
            for row in self.build(esm1b_parquet, score_sign=-1).score(records)
        }
        assert len(flipped) == len(plain) == 50
        assert all(flipped[key] == pytest.approx(-value) for key, value in plain.items())

    def test_the_card_falls_back_to_the_converted_table_path(self):
        card = Card(key="esm1b", adapter="duckdb_lookup", params={"key": ["allele_id"]})
        built = adapters.build(card)
        assert built.parquet == duckdb_lookup.TABLES / "esm1b.parquet"

    def test_the_digest_is_the_file_hash(self, esm1b_parquet):
        import hashlib

        expected = hashlib.sha256(esm1b_parquet.read_bytes()).hexdigest()
        assert self.build(esm1b_parquet).table_digest() == expected

    def test_a_key_the_record_has_no_field_for_is_refused(self, esm1b_parquet):
        with pytest.raises(ValueError, match="key"):
            self.build(esm1b_parquet, key=["nonsense"])

    def test_a_missing_table_names_the_fetch_script(self, tmp_path, records):
        adapter = self.build(tmp_path / "absent.parquet")
        with pytest.raises(FileNotFoundError, match="fetch script"):
            list(adapter.score(records))

    def test_scoring_twice_reuses_the_cached_lookup(self, esm1b_parquet, records):
        adapter = self.build(esm1b_parquet)
        first = list(adapter.score(records))
        esm1b_parquet.unlink()
        assert [row.allele_id for row in adapter.score(records)] == [row.allele_id for row in first]

    def test_submit_is_not_a_tier_one_verb(self, esm1b_parquet, records):
        with pytest.raises(NotImplementedError):
            self.build(esm1b_parquet).submit(records)


class FakeAsker:
    """Stands in for Ensembl: canned JSON, and a count of how often it was asked."""

    def __init__(self, values: dict[str, float]):
        self.values = values
        self.calls = 0

    def raw_many(self, variants):
        from mva.pipeline.vep_response import query_line

        self.calls += 1
        replies = {}
        for variant in variants:
            key = query_line(variant)
            score = self.values.get(f"{variant.ref}{variant.alt}")
            replies[key] = {
                "input": key,
                "transcript_consequences": [
                    {"revel": score} if score is not None else {"gene_symbol": "GENEA"}
                ],
            }
        return replies


class TestVepRest:
    def adapter(self, records_parquet: Path, tmp_path: Path, asker: Any):
        card = Card(
            key="revel",
            adapter="vep_rest",
            source="vep-rest",
            catalogue_adjacent=True,
            params={"plugin": "REVEL", "field": "revel"},
        )
        built = adapters.build(card, records_parquet=records_parquet)
        built.asker = asker
        vep_rest.CHECKPOINT_ROOT = tmp_path
        return built

    def test_is_flagged_catalogue_adjacent(self, records_parquet, tmp_path):
        built = self.adapter(records_parquet, tmp_path, FakeAsker({}))
        assert built.catalogue_adjacent is True
        assert built.venue == "vep-rest"
        assert built.source_ref == "ensembl-vep-rest:REVEL"

    def test_scores_the_alleles_the_server_answered_for(self, records_parquet, tmp_path, records):
        asker = FakeAsker({"CG": 0.71})
        built = self.adapter(records_parquet, tmp_path, asker)
        rows = list(built.score(records[:20]))
        assert rows
        assert all(row.score == pytest.approx(0.71) for row in rows)
        assert all(row.aux == {"plugin": "REVEL", "field": "revel"} for row in rows)

    def test_the_checkpoint_holds_ids_and_numbers_only(self, records_parquet, tmp_path, records):
        built = self.adapter(records_parquet, tmp_path, FakeAsker({"CG": 0.71}))
        list(built.score(records[:20]))
        lines = (tmp_path / "vep-revel" / "answers.jsonl").read_text().splitlines()
        assert len(lines) == 20
        assert set(json.loads(lines[0])) == {"allele_id", "score"}

    def test_a_resumed_run_asks_nothing(self, records_parquet, tmp_path, records):
        asker = FakeAsker({"CG": 0.71})
        first = self.adapter(records_parquet, tmp_path, asker)
        list(first.score(records[:20]))
        second = self.adapter(records_parquet, tmp_path, asker)
        rows = list(second.score(records[:20]))
        assert asker.calls == 1
        assert len(rows) == len(list(first.score(records[:20])))

    def test_coverage_is_the_alleles_it_can_ask_about(self, records_parquet, tmp_path, records):
        built = self.adapter(records_parquet, tmp_path, FakeAsker({}))
        assert built.coverage(records).scored == len(records)

    def test_a_missing_record_set_says_it_needs_coordinates(self, tmp_path, records):
        built = self.adapter(tmp_path / "absent.parquet", tmp_path, FakeAsker({}))
        with pytest.raises(FileNotFoundError, match="coordinates"):
            list(built.score(records))

    def test_submit_is_not_how_this_lane_answers(self, records_parquet, tmp_path, records):
        with pytest.raises(NotImplementedError, match="synchronously"):
            self.adapter(records_parquet, tmp_path, FakeAsker({})).submit(records)


class TestPickField:
    def test_takes_the_largest_value_across_transcripts(self):
        reply = {"transcript_consequences": [{"revel": 0.2}, {"revel": 0.8}, {}]}
        assert vep_rest._pick(reply, "revel") == pytest.approx(0.8)

    def test_reads_a_list_valued_field(self):
        assert vep_rest._pick({"revel": ["0.3", "0.9"]}, "revel") == pytest.approx(0.9)

    def test_an_absent_field_is_none(self):
        assert vep_rest._pick({"transcript_consequences": [{}]}, "revel") is None

    def test_an_empty_reply_is_none(self):
        assert vep_rest._pick(None, "revel") is None

    def test_a_non_numeric_value_is_none(self):
        assert vep_rest._pick({"revel": "high"}, "revel") is None


class TestPluginAsker:
    def test_adds_the_plugin_to_the_request_body(self, monkeypatch):
        sent: list[dict[str, Any]] = []

        def fake_request(self, method, path, json=None):
            sent.append(json or {})
            return [{"input": "1 1 . A G . . .", "revel": 0.4}]

        from mva.pipeline import annotate_vep

        monkeypatch.setattr(annotate_vep.VepRestAnnotator, "_request", fake_request)
        asker = vep_rest.PluginAsker("REVEL")
        from mva.pipeline.variant import Variant

        replies = asker.raw_many([Variant("chr1", 1, "A", "G")])
        assert sent[0]["REVEL"] == 1
        # Only the plugin and the variants: the annotation pass's QUERY_PARAMS would add
        # two more plugin lookups and two frequency joins per allele, which read-timed out
        # on the real endpoint at a 200-allele batch (entry 119).
        assert set(sent[0]) == {"variants", "REVEL"}
        assert replies["1 1 . A G . . ."]["revel"] == 0.4
        asker.close()
