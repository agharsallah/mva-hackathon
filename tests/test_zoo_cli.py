"""``mva-zoo``: every verb reaches a handler, and the ones with no external dependency run.

The three modules other wave-1 agents own — ``registry``, ``record``, ``workflow`` — are
stood in for by fakes injected into ``sys.modules``, so this file tests the CLI's own
behaviour rather than theirs. The warehouse is an in-memory DuckDB with the server's alias
attached, the same stand-in the cache tests use.

Every value is invented; the score table is ``fixtures/it4/scores/esm1b.tsv``. Nothing here
reads patient data or makes a network call.
"""

from __future__ import annotations

import contextlib
import json
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb
import pytest

from mva.zoo import cache, cli
from mva.zoo.types import ALLELE_SCORES_TABLE

FIXTURES = Path("fixtures/it4")
SCHEMA = "warehouse"


@dataclass
class Card:
    key: str
    version: str = "fixture-1"
    adapter: str = "duckdb_lookup"
    tier: int = 1
    source: str = "table"
    licence: str = "MIT"
    catalogue_adjacent: bool = False
    enabled: bool = True
    name: str = "ESM1b (fixture)"
    params: dict[str, Any] = field(default_factory=dict)


def fake_module(name: str, **members: Any) -> types.ModuleType:
    module = types.ModuleType(name)
    for key, value in members.items():
        setattr(module, key, value)
    return module


@pytest.fixture
def install(monkeypatch: pytest.MonkeyPatch):
    """Put a fake ``mva.zoo.<name>`` in place of a module wave 1 has not landed yet."""
    import mva.zoo

    def put(name: str, **members: Any) -> types.ModuleType:
        module = fake_module(f"mva.zoo.{name}", **members)
        monkeypatch.setitem(sys.modules, f"mva.zoo.{name}", module)
        monkeypatch.setattr(mva.zoo, name, module, raising=False)
        return module

    return put


@pytest.fixture
def parquet(tmp_path: Path) -> dict[str, Path]:
    """The fixture record set and one fixture score table, both as Parquet."""
    con = duckdb.connect()
    paths = {}
    for name, source in (
        ("records", FIXTURES / "records.tsv"),
        ("esm1b", FIXTURES / "scores/esm1b.tsv"),
    ):
        target = tmp_path / f"{name}.parquet"
        con.execute(
            "CREATE OR REPLACE TEMP TABLE raw AS "
            "SELECT * FROM read_csv(?, delim='\t', header=true)",
            [str(source)],
        )
        con.execute("COPY (SELECT * FROM raw) TO ? (FORMAT parquet)", [str(target)])
        paths[name] = target
    con.close()
    return paths


@pytest.fixture
def warehouse(monkeypatch: pytest.MonkeyPatch):
    """An in-memory stand-in for the hosted warehouse, wired into ``attached``."""
    con = duckdb.connect()
    con.execute("ATTACH ':memory:' AS pg")
    con.execute(f"CREATE SCHEMA pg.{SCHEMA}")

    @contextlib.contextmanager
    def attached(settings, read_only: bool = False):
        yield con

    from mva.warehouse import postgres

    monkeypatch.setattr(postgres, "attached", attached)
    yield con
    con.close()


@pytest.fixture
def registry(install, parquet):
    card = Card(key="esm1b", params={"parquet": str(parquet["esm1b"])})
    return install("registry", load=lambda: {"esm1b": card})


def score_argv(parquet: dict[str, Path], *extra: str) -> list[str]:
    return ["score", "--model", "esm1b", "--records", str(parquet["records"]), *extra]


class TestParser:
    def test_every_verb_has_a_handler(self):
        parser = cli._parser()
        (verbs,) = [action for action in parser._actions if getattr(action, "choices", None)]
        assert set(verbs.choices) == {"records", "models", "coverage", "score", "scores", "run"}
        for name, subparser in verbs.choices.items():
            assert callable(subparser.get_default("handler")), name

    def test_no_verb_prints_help_and_fails(self, capsys):
        assert cli.main([]) == 1
        assert "mva-zoo" in capsys.readouterr().out

    def test_score_defaults_to_catalogue_free(self):
        args = cli._parser().parse_args(["score", "--model", "x"])
        assert args.mode == "catalogue-free"
        assert args.records == cli.DEFAULT_RECORDS
        assert args.dry_run is False

    def test_score_rejects_an_unknown_mode(self):
        with pytest.raises(SystemExit):
            cli._parser().parse_args(["score", "--model", "x", "--mode", "omniscient"])

    def test_records_flags(self):
        args = cli._parser().parse_args(["records", "--mask-catalogue", "--limit", "10"])
        assert args.mask_catalogue is True
        assert args.limit == 10

    def test_run_takes_a_config_and_a_resume_point(self):
        args = cli._parser().parse_args(["run", "--config", "zoo.toml", "--from", "collect"])
        assert args.config == Path("zoo.toml")
        assert args.from_stage == "collect"

    def test_scores_needs_an_allele(self):
        with pytest.raises(SystemExit):
            cli._parser().parse_args(["scores"])


class TestModels:
    def test_prints_one_line_per_card(self, install, capsys):
        install("registry", load=lambda: {"esm1b": Card(key="esm1b")})
        assert cli.main(["models"]) == 0
        out = capsys.readouterr().out
        assert "esm1b" in out and "duckdb_lookup" in out and "MIT" in out

    def test_flags_a_catalogue_adjacent_lane(self, install, capsys):
        install("registry", load=lambda: {"revel": Card(key="revel", catalogue_adjacent=True)})
        cli.main(["models"])
        assert "catalogue-adjacent" in capsys.readouterr().out

    def test_json_is_machine_readable(self, install, capsys):
        install("registry", load=lambda: {"esm1b": Card(key="esm1b")})
        assert cli.main(["models", "--json"]) == 0
        parsed = json.loads(capsys.readouterr().out)
        assert parsed["esm1b"]["tier"] == 1


class TestRecords:
    def test_passes_the_flags_through_to_step_one(self, install, capsys):
        seen: dict[str, Any] = {}

        def run(settings, *, mask_catalogue, out_dir, limit=None):
            seen.update(mask_catalogue=mask_catalogue, out_dir=out_dir, limit=limit)
            return "built 200 records"

        install("record", run=run)
        assert cli.main(["records", "--mask-catalogue", "--limit", "5"]) == 0
        assert seen == {"mask_catalogue": True, "out_dir": cli.DEFAULT_OUT, "limit": 5}
        assert "built 200 records" in capsys.readouterr().out


class TestCoverage:
    def test_reports_the_fraction_and_the_classes(self, registry, warehouse, parquet, capsys):
        assert cli.main(["coverage", "--model", "esm1b", "--records", str(parquet["records"])]) == 0
        out = capsys.readouterr().out
        assert "esm1b: 50/200" in out
        assert "missense_variant" in out

    def test_an_unknown_model_lists_the_known_ones(self, registry, warehouse, parquet, capsys):
        assert cli.main(["coverage", "--model", "evo2", "--records", str(parquet["records"])]) == 1
        assert "known: esm1b" in capsys.readouterr().err


class TestScore:
    def cached(self, warehouse) -> list[tuple]:
        return warehouse.execute(
            f"SELECT allele_id, model, score, aux, run_id FROM pg.{SCHEMA}.{ALLELE_SCORES_TABLE}"
        ).fetchall()

    def test_writes_one_row_per_scored_allele(self, registry, warehouse, parquet, capsys):
        assert cli.main(score_argv(parquet)) == 0
        assert len(self.cached(warehouse)) == 50
        assert "inserted 50" in capsys.readouterr().out

    def test_stamps_the_mode_into_the_row(self, registry, warehouse, parquet):
        cli.main(score_argv(parquet, "--mode", "aware"))
        assert json.loads(self.cached(warehouse)[0][3])["mode"] == "aware"

    def test_a_second_run_inserts_nothing(self, registry, warehouse, parquet, capsys):
        cli.main(score_argv(parquet))
        capsys.readouterr()
        assert cli.main(score_argv(parquet)) == 0
        assert "inserted 0, skipped 50" in capsys.readouterr().out
        assert len(self.cached(warehouse)) == 50

    def test_writes_one_lineage_edge_per_run(self, registry, warehouse, parquet):
        cli.main(score_argv(parquet))
        edges = warehouse.execute(
            f"SELECT transform, tool, target_rows FROM pg.{SCHEMA}.data_lineage"
        ).fetchall()
        assert edges == [("it4-score:esm1b", "mva-zoo", 50)]

    def test_dry_run_writes_nothing(self, registry, warehouse, parquet, capsys):
        assert cli.main(score_argv(parquet, "--dry-run")) == 0
        out = capsys.readouterr().out
        assert "dry run: nothing written" in out
        cache.ensure_table(warehouse, SCHEMA)
        assert self.cached(warehouse) == []

    def test_limit_shrinks_the_record_set(self, registry, warehouse, parquet, capsys):
        assert cli.main(score_argv(parquet, "--limit", "20")) == 0
        assert "/20 " in capsys.readouterr().out

    def test_an_empty_record_set_is_an_error_not_a_crash(
        self, registry, warehouse, parquet, tmp_path, capsys
    ):
        empty = tmp_path / "empty.parquet"
        con = duckdb.connect()
        con.execute(
            "CREATE TEMP TABLE none AS SELECT * FROM read_parquet(?) WHERE false",
            [str(parquet["records"])],
        )
        con.execute("COPY none TO ? (FORMAT parquet)", [str(empty)])
        con.close()
        assert cli.main(["score", "--model", "esm1b", "--records", str(empty)]) == 1
        assert "holds no records" in capsys.readouterr().err


class TestScores:
    def test_prints_every_model_row_for_one_allele(self, warehouse, capsys):
        from mva.zoo.types import ScoreRow

        rows = [
            ScoreRow(allele_id="aa", model="esm1b", version="v1", score=0.4),
            ScoreRow(allele_id="aa", model="alphamissense", version="v1", score=0.9),
            ScoreRow(allele_id="bb", model="esm1b", version="v1", score=0.1),
        ]
        cache.write(warehouse, SCHEMA, rows, run_id="r1")
        assert cli.main(["scores", "--allele-id", "aa"]) == 0
        out = capsys.readouterr().out
        assert "alphamissense" in out and "0.9000" in out and "bb" not in out

    def test_an_unscored_allele_says_so(self, warehouse, capsys):
        assert cli.main(["scores", "--allele-id", "zz"]) == 0
        assert "no cached score" in capsys.readouterr().out


class TestRun:
    def test_delegates_to_the_workflow(self, install, capsys):
        install("workflow", run=lambda config: f"manifest for {config}")
        assert cli.main(["run", "--config", "zoo.toml"]) == 0
        assert "manifest for zoo.toml" in capsys.readouterr().out

    def test_passes_the_resume_point_when_the_workflow_accepts_one(self, install, capsys):
        install("workflow", run=lambda config, from_stage=None: f"from {from_stage}")
        assert cli.main(["run", "--from", "collect"]) == 0
        assert "from collect" in capsys.readouterr().out

    def test_says_so_when_the_workflow_cannot_resume(self, install, capsys):
        install("workflow", run=lambda config: "manifest")
        assert cli.main(["run", "--from", "collect"]) == 1
        assert "no resume" in capsys.readouterr().err


class TestResumeParameter:
    @pytest.mark.parametrize("name", ["from_stage", "start", "stage", "resume_from"])
    def test_finds_the_keyword_whatever_it_is_called(self, name):
        namespace: dict[str, Any] = {}
        exec(f"def run(config, {name}=None): pass", namespace)
        assert cli._resume_parameter(namespace["run"]) == name

    def test_returns_none_when_there_is_no_resume(self):
        assert cli._resume_parameter(lambda config: None) is None
