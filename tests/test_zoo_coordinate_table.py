"""The coordinate-keyed lane, and the tabix subset that feeds it.

Two halves, one story:

* :mod:`mva.zoo.tabix_subset` decides *which* rows of a 37 GB remote table this case needs
  and range-reads them. Nothing here touches the network: the planning half runs on the
  fixture record set, and the fan-out half is driven by a fake ``tabix`` written into
  ``tmp_path``, so the wiring (argv, shards, concatenation, Parquet) is tested for real
  while the bytes are invented.
* :mod:`mva.zoo.adapters.coordinate_table` joins the resulting table. The load-bearing
  assertion is that the id it computes **in SQL** over the published table's coordinates
  equals :func:`mva.zoo.types.allele_id` computed in Python over the record's — a silent
  disagreement there is a lane with 0 % coverage and no error at all.

Everything runs against ``fixtures/it4/`` — 200 synthetic records on a fake chromosome,
invented genes, invented scores. No patient data, no network.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb
import pytest

from mva.zoo import adapters, tabix_subset
from mva.zoo.adapters import coordinate_table
from mva.zoo.types import AlleleRecord, allele_id

FIXTURES = Path("fixtures/it4")
RECORDS_TSV = FIXTURES / "records.tsv"


@dataclass
class Card:
    """The slice of a registry model card this lane reads."""

    key: str = "gpnmsa"
    version: str = "fixture-1"
    adapter: str = "coordinate_table"
    tier: int = 1
    source: str = "table"
    licence: str = "MIT"
    catalogue_adjacent: bool = False
    enabled: bool = True
    name: str = ""
    params: dict[str, Any] = field(default_factory=dict)


@pytest.fixture
def records_parquet(tmp_path: Path) -> Path:
    """The fixture records as the Parquet step 1 writes, coordinate columns and all."""
    target = tmp_path / "records.parquet"
    con = duckdb.connect()
    con.execute(
        "CREATE OR REPLACE TEMP TABLE raw AS SELECT * FROM read_csv(?, delim='\t', header=true)",
        [str(RECORDS_TSV)],
    )
    con.execute("COPY (SELECT * FROM raw) TO ? (FORMAT parquet)", [str(target)])
    con.close()
    return target


@pytest.fixture
def records(records_parquet: Path) -> list[AlleleRecord]:
    return adapters.records_from_parquet(records_parquet)


def coordinates(records_parquet: Path) -> list[tuple[str, int, str, str]]:
    con = duckdb.connect()
    rows = con.execute(
        "SELECT chrom, pos, ref, alt FROM read_parquet(?) ORDER BY pos", [str(records_parquet)]
    ).fetchall()
    con.close()
    return [(str(r[0]), int(r[1]), str(r[2]), str(r[3])) for r in rows]


@pytest.fixture
def score_table(tmp_path: Path, records_parquet: Path) -> Path:
    """A published-looking SNV table: every other fixture SNV, scored, sign as published.

    The numbers are negative like GPN-MSA's, so the lane's ``score_sign = -1`` has
    something real to flip.
    """
    target = tmp_path / "gpnmsa.parquet"
    rows = [row for row in coordinates(records_parquet) if len(row[2]) == 1 == len(row[3])][::2]
    con = duckdb.connect()
    con.execute(
        "CREATE TEMP TABLE t (chrom VARCHAR, pos BIGINT, ref VARCHAR, alt VARCHAR, score DOUBLE)"
    )
    con.executemany(
        "INSERT INTO t VALUES (?, ?, ?, ?, ?)",
        [[c, p, r, a, -1.0 - index / 100] for index, (c, p, r, a) in enumerate(rows)],
    )
    con.execute("COPY (SELECT * FROM t) TO ? (FORMAT parquet)", [str(target)])
    con.close()
    return target


# ── planning the subset ───────────────────────────────────────────────────────────────


class TestRegionPlanning:
    def test_only_snv_positions_are_asked_for(self, records_parquet: Path) -> None:
        wanted = tabix_subset.snv_positions(records_parquet)
        every = coordinates(records_parquet)
        snvs = {(c, p) for c, p, r, a in every if len(r) == 1 and len(a) == 1}
        assert set(wanted) == snvs
        assert len(wanted) < len(every) or all(len(r) == 1 == len(a) for _, _, r, a in every)

    def test_contig_loses_its_chr_prefix(self, tmp_path: Path) -> None:
        source = tmp_path / "r.parquet"
        con = duckdb.connect()
        con.execute(
            "COPY (SELECT 'chr7' AS chrom, 12 AS pos, 'A' AS ref, 'T' AS alt) "
            "TO ? (FORMAT parquet)",
            [str(source)],
        )
        assert tabix_subset.snv_positions(source) == [("7", 12)]

    def test_neighbours_inside_the_gap_become_one_region(self) -> None:
        regions = tabix_subset.merge_positions([("1", 10), ("1", 20), ("1", 5000)], merge_gap=100)
        assert regions == [tabix_subset.Region("1", 10, 20), tabix_subset.Region("1", 5000, 5000)]

    def test_a_contig_boundary_always_breaks_a_region(self) -> None:
        regions = tabix_subset.merge_positions([("1", 10), ("2", 11)], merge_gap=1_000_000)
        assert [region.contig for region in regions] == ["1", "2"]

    def test_merging_never_loses_a_position(self, records_parquet: Path) -> None:
        wanted = tabix_subset.snv_positions(records_parquet)
        regions = tabix_subset.merge_positions(wanted, merge_gap=500)
        covered = {(r.contig, p) for r in regions for p in range(r.start, r.end + 1)}
        assert set(wanted) <= covered

    def test_bed_is_zero_based_half_open(self) -> None:
        assert tabix_subset.Region("1", 10, 12).bed_line() == "1\t9\t12\n"
        assert tabix_subset.Region("1", 10, 12).span == 3

    def test_write_bed_writes_one_line_per_region(self, tmp_path: Path) -> None:
        regions = [tabix_subset.Region("1", 1, 2), tabix_subset.Region("2", 5, 5)]
        written = tabix_subset.write_bed(regions, tmp_path / "deep" / "r.bed")
        assert written == 2
        assert (tmp_path / "deep" / "r.bed").read_text().splitlines() == ["1\t0\t2", "2\t4\t5"]

    def test_shards_are_contiguous_and_cover_everything(self) -> None:
        regions = [tabix_subset.Region("1", i, i) for i in range(1, 11)]
        blocks = tabix_subset.shard(regions, 3)
        assert [len(block) for block in blocks] == [4, 4, 2]
        assert [r for block in blocks for r in block] == regions

    def test_more_workers_than_regions_is_not_an_error(self) -> None:
        assert tabix_subset.shard([tabix_subset.Region("1", 1, 1)], 8) == [
            [tabix_subset.Region("1", 1, 1)]
        ]

    def test_a_missing_record_set_says_which_command_makes_it(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="mva-zoo records"):
            tabix_subset.snv_positions(tmp_path / "nope.parquet")


class TestTabixCommand:
    def test_the_index_is_pinned_with_the_htslib_idx_syntax(self, tmp_path: Path) -> None:
        argv = tabix_subset.tabix_command("https://x/s.bgz", tmp_path / "s.tbi", tmp_path / "r.bed")
        assert argv[0] == "tabix"
        assert argv[1:3] == ["-R", str(tmp_path / "r.bed")]
        assert argv[3] == f"https://x/s.bgz##idx##{tmp_path / 's.tbi'}"

    def test_a_missing_tabix_is_named_not_guessed(self, tmp_path: Path) -> None:
        with pytest.raises(tabix_subset.TabixMissingError, match="not on the PATH"):
            tabix_subset.subset("https://x/s.bgz", tmp_path / "r.parquet", tmp_path, tabix="nope")


class TestSubsetFanOut:
    """The whole fan-out, with a fake ``tabix`` that reads the BED and invents scores."""

    @pytest.fixture
    def fake_tabix(self, tmp_path: Path) -> str:
        script = tmp_path / "faketabix"
        script.write_text(
            "#!/bin/sh\n"
            "while read -r contig start end; do\n"
            "  pos=$((start + 1))\n"
            '  while [ "$pos" -le "$end" ]; do\n'
            '    printf "%s\\t%s\\tA\\tT\\t-1.25\\n" "$contig" "$pos"\n'
            "    pos=$((pos + 1))\n"
            "  done\n"
            'done < "$2"\n'
        )
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        os.environ["PATH"] = f"{tmp_path}{os.pathsep}{os.environ['PATH']}"
        return "faketabix"

    def test_it_writes_one_parquet_covering_every_wanted_position(
        self, tmp_path: Path, records_parquet: Path, fake_tabix: str, monkeypatch: Any
    ) -> None:
        monkeypatch.setattr(tabix_subset, "resolve_url", lambda url: url + "?signed")
        monkeypatch.setattr(tabix_subset, "upstream_head", lambda url: (37_274_961_495, "etag-1"))
        monkeypatch.setattr(tabix_subset, "download", lambda url, dest: _stub(dest))
        result = tabix_subset.subset(
            "https://example/scores.tsv.bgz",
            records_parquet,
            tmp_path / "lane",
            jobs=3,
            merge_gap=100,
            tabix=fake_tabix,
            progress=lambda *a: None,
        )
        assert result.failures == []
        assert result.shards == 3
        assert result.upstream_bytes == 37_274_961_495
        assert result.upstream_etag == "etag-1"
        assert result.rows == result.span
        assert result.parquet_rows == result.rows
        assert result.parquet_path == tmp_path / "lane.parquet"
        assert len(result.subset_sha256) == 64

    def test_the_provenance_dict_carries_no_coordinate(
        self, tmp_path: Path, records_parquet: Path, fake_tabix: str, monkeypatch: Any
    ) -> None:
        monkeypatch.setattr(tabix_subset, "resolve_url", lambda url: "https://cdn.example/blob")
        monkeypatch.setattr(tabix_subset, "upstream_head", lambda url: (10, ""))
        monkeypatch.setattr(tabix_subset, "download", lambda url, dest: _stub(dest))
        result = tabix_subset.subset(
            "https://example/scores.tsv.bgz",
            records_parquet,
            tmp_path / "lane",
            jobs=1,
            merge_gap=100,
            tabix=fake_tabix,
            progress=lambda *a: None,
        )
        payload = result.as_dict()
        assert payload["resolved_host"] == "cdn.example"
        assert "pos" not in payload and "regions" in payload
        assert payload["subset_rows"] == result.rows

    def test_a_worker_that_fails_is_reported_not_swallowed(
        self, tmp_path: Path, records_parquet: Path, monkeypatch: Any
    ) -> None:
        script = tmp_path / "brokentabix"
        script.write_text("#!/bin/sh\necho 'index not found' >&2\nexit 3\n")
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        os.environ["PATH"] = f"{tmp_path}{os.pathsep}{os.environ['PATH']}"
        monkeypatch.setattr(tabix_subset, "resolve_url", lambda url: url)
        monkeypatch.setattr(tabix_subset, "upstream_head", lambda url: (None, ""))
        monkeypatch.setattr(tabix_subset, "download", lambda url, dest: _stub(dest))
        result = tabix_subset.subset(
            "https://example/scores.tsv.bgz",
            records_parquet,
            tmp_path / "lane",
            jobs=2,
            tabix="brokentabix",
            progress=lambda *a: None,
        )
        assert len(result.failures) == 2
        assert "exit 3" in result.failures[0]
        assert result.rows == 0


def _stub(dest: Path) -> str:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"not a real index")
    return tabix_subset.digest(dest)


class TestToParquet:
    def test_a_headerless_tsv_gains_the_lane_s_column_names(self, tmp_path: Path) -> None:
        tsv = tmp_path / "s.tsv"
        tsv.write_text("1\t100\tA\tT\t-1.60\n1\t100\tA\tC\t-1.47\n")
        rows = tabix_subset.to_parquet(tsv, tmp_path / "s.parquet")
        assert rows == 2
        con = duckdb.connect()
        got = con.execute(
            "SELECT chrom, pos, ref, alt, score FROM read_parquet(?) ORDER BY alt",
            [str(tmp_path / "s.parquet")],
        ).fetchall()
        assert got == [("1", 100, "A", "C", -1.47), ("1", 100, "A", "T", -1.6)]


# ── the lane ──────────────────────────────────────────────────────────────────────────


class TestCoordinateTableAdapter:
    def test_it_scores_exactly_the_alleles_the_table_holds(
        self, score_table: Path, records: list[AlleleRecord]
    ) -> None:
        lane = coordinate_table.CoordinateTableAdapter(
            name="gpnmsa", version="v1", parquet=score_table, score_sign=-1
        )
        scored = list(lane.score(records))
        con = duckdb.connect()
        expected = con.execute(
            "SELECT count(*) FROM read_parquet(?)", [str(score_table)]
        ).fetchone()
        assert expected is not None
        assert len(scored) == expected[0]

    def test_the_id_it_computes_in_sql_matches_the_python_one(
        self, score_table: Path, records_parquet: Path, records: list[AlleleRecord]
    ) -> None:
        lane = coordinate_table.CoordinateTableAdapter(
            name="gpnmsa", version="v1", parquet=score_table
        )
        scored = {row.allele_id for row in lane.score(records)}
        con = duckdb.connect()
        table = con.execute(
            "SELECT chrom, pos, ref, alt FROM read_parquet(?)", [str(score_table)]
        ).fetchall()
        assert scored == {allele_id(str(c), int(p), str(r), str(a)) for c, p, r, a in table}

    def test_a_published_negative_score_is_flipped_to_the_zoo_s_direction(
        self, score_table: Path, records: list[AlleleRecord]
    ) -> None:
        lane = coordinate_table.CoordinateTableAdapter(
            name="gpnmsa", version="v1", parquet=score_table, score_sign=-1
        )
        assert all(row.score is not None and row.score > 0 for row in lane.score(records))

    def test_without_the_flip_the_sign_is_the_publisher_s(
        self, score_table: Path, records: list[AlleleRecord]
    ) -> None:
        lane = coordinate_table.CoordinateTableAdapter(
            name="gpnmsa", version="v1", parquet=score_table, score_sign=1
        )
        assert all(row.score is not None and row.score < 0 for row in lane.score(records))

    def test_coverage_counts_per_consequence_class(
        self, score_table: Path, records: list[AlleleRecord]
    ) -> None:
        lane = coordinate_table.CoordinateTableAdapter(
            name="gpnmsa", version="v1", parquet=score_table
        )
        cover = lane.coverage(records)
        assert cover.total == len(records)
        assert 0 < cover.scored < cover.total
        assert sum(total for _, total in cover.by_consequence.values()) == len(records)

    def test_every_row_carries_its_provenance(
        self, score_table: Path, records: list[AlleleRecord]
    ) -> None:
        lane = coordinate_table.CoordinateTableAdapter(
            name="gpnmsa", version="v1", parquet=score_table, licence="MIT"
        )
        row = next(iter(lane.score(records)))
        assert row.model == "gpnmsa" and row.version == "v1"
        assert row.licence == "MIT" and row.venue == "laptop"
        assert len(row.digest) == 64

    def test_an_aux_column_travels_with_its_own_row(
        self, tmp_path: Path, records_parquet: Path, records: list[AlleleRecord]
    ) -> None:
        target = tmp_path / "aux.parquet"
        first = coordinates(records_parquet)[0]
        con = duckdb.connect()
        con.execute(
            "CREATE TEMP TABLE t (chrom VARCHAR, pos BIGINT, ref VARCHAR, alt VARCHAR, "
            "score DOUBLE, label VARCHAR)"
        )
        con.execute("INSERT INTO t VALUES (?, ?, ?, ?, -2.0, 'conserved')", list(first))
        con.execute("COPY (SELECT * FROM t) TO ? (FORMAT parquet)", [str(target)])
        lane = coordinate_table.CoordinateTableAdapter(
            name="gpnmsa", version="v1", parquet=target, aux=("label",), score_sign=-1
        )
        rows = list(lane.score(records))
        assert [row.aux for row in rows] == [{"label": "conserved"}]
        assert rows[0].score == 2.0

    def test_a_missing_table_names_the_fetch_command(
        self, tmp_path: Path, records: list[AlleleRecord]
    ) -> None:
        lane = coordinate_table.CoordinateTableAdapter(
            name="gpnmsa", version="v1", parquet=tmp_path / "absent.parquet"
        )
        with pytest.raises(FileNotFoundError, match="--subset-from"):
            list(lane.score(records))

    def test_four_coordinate_columns_or_an_error(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="exactly chrom, pos, ref and alt"):
            coordinate_table.CoordinateTableAdapter(
                name="x",
                version="v",
                parquet=tmp_path / "t.parquet",
                columns=("chrom", "pos", "ref"),  # type: ignore[arg-type]
            )

    def test_it_is_a_lookup_lane_so_submit_refuses(
        self, score_table: Path, records: list[AlleleRecord]
    ) -> None:
        lane = coordinate_table.CoordinateTableAdapter(
            name="gpnmsa", version="v1", parquet=score_table
        )
        with pytest.raises(NotImplementedError, match="tier-1 lookup"):
            lane.submit(records)


class TestBuildFromCard:
    def test_the_factory_reaches_this_lane_by_name(self, score_table: Path) -> None:
        card = Card(params={"parquet": str(score_table), "score_sign": -1})
        lane = adapters.build(card)
        assert isinstance(lane, coordinate_table.CoordinateTableAdapter)
        assert lane.score_sign == -1

    def test_the_default_table_path_is_the_fetch_target(self) -> None:
        lane = coordinate_table.build(Card())
        assert isinstance(lane, coordinate_table.CoordinateTableAdapter)
        assert lane.parquet == coordinate_table.TABLES / "gpnmsa.parquet"

    def test_the_card_may_rename_the_coordinate_columns(self, score_table: Path) -> None:
        card = Card(params={"parquet": str(score_table), "columns": ["chrom", "pos", "ref", "alt"]})
        lane = coordinate_table.build(card)
        assert isinstance(lane, coordinate_table.CoordinateTableAdapter)
        assert lane.columns == ("chrom", "pos", "ref", "alt")

    def test_the_records_parquet_is_accepted_and_unused(
        self, score_table: Path, records_parquet: Path, records: list[AlleleRecord]
    ) -> None:
        lane = coordinate_table.build(
            Card(params={"parquet": str(score_table)}), records_parquet=Path("/nowhere.parquet")
        )
        assert list(lane.score(records))


class TestRegistryKnowsTheLane:
    def test_the_roster_may_pair_a_table_source_with_this_adapter(self) -> None:
        from mva.zoo import registry

        assert "coordinate_table" in registry.ADAPTER_FOR_SOURCE["table"]
        assert registry.ADAPTER_PARAMS["coordinate_table"] == ("key", "url")


class TestResume:
    """A multi-hour fan-out must not start from zero; the first real run proved it."""

    @pytest.fixture
    def fake_tabix(self, tmp_path: Path) -> str:
        script = tmp_path / "faketabix2"
        script.write_text(
            "#!/bin/sh\n"
            "while read -r contig start end; do\n"
            "  pos=$((start + 1))\n"
            '  while [ "$pos" -le "$end" ]; do\n'
            '    printf "%s\\t%s\\tA\\tT\\t-1.25\\n" "$contig" "$pos"\n'
            "    pos=$((pos + 1))\n"
            "  done\n"
            'done < "$2"\n'
        )
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        os.environ["PATH"] = f"{tmp_path}{os.pathsep}{os.environ['PATH']}"
        return "faketabix2"

    def _patch(self, monkeypatch: Any) -> None:
        monkeypatch.setattr(tabix_subset, "resolve_url", lambda url: url)
        monkeypatch.setattr(tabix_subset, "upstream_head", lambda url: (10, "e"))
        monkeypatch.setattr(tabix_subset, "download", lambda url, dest: _stub(dest))

    def test_a_second_run_asks_for_nothing_and_keeps_every_row(
        self, tmp_path: Path, records_parquet: Path, fake_tabix: str, monkeypatch: Any
    ) -> None:
        self._patch(monkeypatch)
        first = tabix_subset.subset(
            "https://example/s.tsv.bgz",
            records_parquet,
            tmp_path / "lane",
            jobs=2,
            merge_gap=100,
            tabix=fake_tabix,
            progress=lambda *a: None,
        )
        second = tabix_subset.subset(
            "https://example/s.tsv.bgz",
            records_parquet,
            tmp_path / "lane",
            jobs=2,
            merge_gap=100,
            tabix=fake_tabix,
            progress=lambda *a: None,
        )
        assert second.regions == 0
        assert second.rows == first.rows
        assert second.parquet_rows == first.parquet_rows

    def test_the_previous_run_s_output_is_kept_as_a_part(
        self, tmp_path: Path, records_parquet: Path, fake_tabix: str, monkeypatch: Any
    ) -> None:
        self._patch(monkeypatch)
        for _ in range(2):
            tabix_subset.subset(
                "https://example/s.tsv.bgz",
                records_parquet,
                tmp_path / "lane",
                jobs=2,
                merge_gap=100,
                tabix=fake_tabix,
                progress=lambda *a: None,
            )
        assert sorted(p.name for p in (tmp_path / "lane").glob("scores.part-*.tsv")) == [
            "scores.part-000.tsv",
            "scores.part-001.tsv",
        ]

    def test_the_workers_are_given_the_unresolved_url(
        self, tmp_path: Path, records_parquet: Path, fake_tabix: str, monkeypatch: Any
    ) -> None:
        seen: list[list[str]] = []
        self._patch(monkeypatch)
        monkeypatch.setattr(tabix_subset, "resolve_url", lambda url: "https://signed.example/x")
        real = tabix_subset.tabix_command
        monkeypatch.setattr(
            tabix_subset,
            "tabix_command",
            lambda url, index, bed, **kw: (seen.append([url]), real(url, index, bed, **kw))[1],
        )
        tabix_subset.subset(
            "https://example/s.tsv.bgz",
            records_parquet,
            tmp_path / "lane",
            jobs=1,
            merge_gap=100,
            tabix=fake_tabix,
            progress=lambda *a: None,
        )
        assert seen and all(url == ["https://example/s.tsv.bgz"] for url in seen)
