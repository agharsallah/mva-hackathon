"""Tests for the hosted-PostgreSQL path: settings, identifier safety, and derivations.

No test here contacts a database. The parts that need a live server are exercised by
running the CLI against a throwaway instance (recorded in ``methodology/010``); what is
unit-tested is everything that can be got wrong *before* a connection is opened — a
credential leaking into a log, an identifier reaching SQL unvalidated, a derivation
referring to a table that ingest does not produce.
"""

from pathlib import Path

import pytest

from mva.warehouse import reference
from mva.warehouse.analysis import DERIVATIONS, SOURCE, by_name, resolve
from mva.warehouse.annotate import ANNOTATIONS_TABLE
from mva.warehouse.catalog import NOTES, OVERRIDES, table_name
from mva.warehouse.cli_vcf import RAW_TABLE
from mva.warehouse.stage import SCALARS_TABLE
from mva.warehouse.postgres import (InvalidIdentifier, Result, render_table,
                                    safe_identifier)
from mva.warehouse.settings import (ENV_FILE_OVERRIDE, Postgres, find_env,
                                    parse_env)


class TestParseEnv:
    def test_reads_plain_pairs(self):
        assert parse_env("PGHOST=box\nPGPORT=5432\n") == {"PGHOST": "box", "PGPORT": "5432"}

    def test_skips_comments_and_blanks(self):
        assert parse_env("# a comment\n\nPGHOST=box\n") == {"PGHOST": "box"}

    def test_tolerates_export_prefix(self):
        assert parse_env("export PGHOST=box\n") == {"PGHOST": "box"}

    def test_strips_one_matching_quote_pair(self):
        assert parse_env("A='x y'\nB=\"z\"\nC='mixed\"\n") == {
            "A": "x y", "B": "z", "C": "'mixed\""}

    def test_keeps_special_characters_in_a_password(self):
        assert parse_env("PGPASSWORD=p@ss=w/rd+1\n")["PGPASSWORD"] == "p@ss=w/rd+1"

    def test_ignores_a_line_without_an_equals(self):
        assert parse_env("garbage\nPGHOST=box\n") == {"PGHOST": "box"}


class TestSettings:
    """These are the tests that exercise env-file discovery itself.

    ``conftest.hermetic_settings`` pins the env file away for the whole suite; discovery
    cannot be tested with discovery disabled, so each test here lifts the pin and then
    supplies its own file under ``tmp_path``.
    """

    @pytest.fixture(autouse=True)
    def discoverable(self, monkeypatch):
        monkeypatch.delenv(ENV_FILE_OVERRIDE, raising=False)

    def test_real_environment_beats_the_file(self, tmp_path: Path, monkeypatch):
        (tmp_path / ".env").write_text("PGHOST=from-file\nPGPASSWORD=x\n")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("PGHOST", "from-environment")
        assert Postgres.from_env().host == "from-environment"

    def test_the_override_pins_one_file(self, tmp_path: Path, monkeypatch):
        pinned = tmp_path / "pinned.env"
        pinned.write_text("PGHOST=pinned\n")
        (tmp_path / ".env").write_text("PGHOST=discovered\n")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv(ENV_FILE_OVERRIDE, str(pinned))
        assert find_env() == pinned

    def test_an_empty_override_means_no_file(self, tmp_path: Path, monkeypatch):
        (tmp_path / ".env").write_text("PGHOST=discovered\n")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv(ENV_FILE_OVERRIDE, "")
        assert find_env() is None

    def test_a_pinned_file_that_is_missing_raises(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv(ENV_FILE_OVERRIDE, str(tmp_path / "absent.env"))
        with pytest.raises(FileNotFoundError):
            find_env()

    def test_env_is_found_from_a_subdirectory(self, tmp_path: Path, monkeypatch):
        (tmp_path / ".env").write_text("PGHOST=box\n")
        nested = tmp_path / "a" / "b"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)
        assert find_env() == tmp_path / ".env"

    def test_missing_lists_what_is_absent(self):
        assert "PGPASSWORD" in Postgres(password="").missing

    def test_missing_is_empty_when_complete(self):
        assert Postgres(host="h", database="d", user="u", password="p").missing == []

    def test_describe_never_reveals_the_password(self):
        described = Postgres(password="hunter2").describe()
        assert "hunter2" not in described and "password: set" in described

    def test_repr_never_reveals_the_password(self):
        assert "hunter2" not in repr(Postgres(password="hunter2"))

    def test_dsn_does_carry_the_password(self):
        assert "password=hunter2" in Postgres(password="hunter2").dsn()


class TestSafeIdentifier:
    @pytest.mark.parametrize("name", ["variants", "panel_gene_density", "_x", "t9"])
    def test_accepts_plain_identifiers(self, name):
        assert safe_identifier(name) == name

    @pytest.mark.parametrize("name", [
        "drop table x", 'x"; DROP TABLE y; --', "9lives", "", "a-b", "sch.table", None])
    def test_rejects_anything_needing_quotes(self, name):
        with pytest.raises(InvalidIdentifier):
            safe_identifier(name)

    def test_every_staged_table_name_is_accepted(self):
        for source in list(OVERRIDES) + [f"{name}.tsv" for name in NOTES]:
            candidate = OVERRIDES[source].table if source in OVERRIDES else table_name(source)
            assert safe_identifier(candidate) == candidate


class TestDerivations:
    def test_names_are_unique(self):
        names = [item.name for item in DERIVATIONS]
        assert len(names) == len(set(names))

    def test_names_are_safe_as_table_names(self):
        for item in DERIVATIONS:
            assert safe_identifier(item.name) == item.name

    def test_every_derivation_reads_the_source_schema(self):
        for item in DERIVATIONS:
            assert SOURCE in item.sql, f"{item.name} never references the ingest schema"

    def test_declared_dependencies_are_actually_referenced(self):
        for item in DERIVATIONS:
            for table in item.depends_on:
                assert f"{SOURCE}.{table}" in item.sql, \
                    f"{item.name} declares {table} but does not select from it"

    def test_dependencies_are_tables_that_staging_produces(self):
        # Four producers land tables in the ingest schema: `stage` + `pg-ingest` for the
        # profile-derived tables the catalogue describes and for the committed public
        # reference tables, `vcf-stage` + `vcf-ingest` for the callset's raw layer, and
        # `annotate-panel` for the VEP answers. A derivation may read any of them.
        produced = ({dataset.table for dataset in OVERRIDES.values()} | set(NOTES)
                    | {dataset.table for dataset in reference.datasets()}
                    | {RAW_TABLE, ANNOTATIONS_TABLE, SCALARS_TABLE})
        for item in DERIVATIONS:
            for table in item.depends_on:
                assert table in produced, f"{item.name} depends on unproduced {table}"

    def test_resolve_replaces_every_placeholder(self):
        for item in DERIVATIONS:
            assert SOURCE not in resolve(item.sql, "pg.warehouse")

    def test_by_name_error_lists_the_alternatives(self):
        with pytest.raises(KeyError, match="panel_gene_density"):
            by_name("nope")


class TestRenderTable:
    def test_renders_headers_and_rows(self):
        out = render_table(("gene", "n"), [("BUB1B", 80)])
        assert "gene" in out and "BUB1B" in out and "(1 row)" in out

    def test_nulls_are_shown_not_blank(self):
        assert "NULL" in render_table(("a",), [(None,)])

    def test_empty_result_still_renders_the_header(self):
        out = render_table(("a", "b"), [])
        assert "a" in out and "(0 rows)" in out

    def test_result_str_delegates_to_the_renderer(self):
        assert "BUB1B" in str(Result(("gene",), [("BUB1B",)]))
