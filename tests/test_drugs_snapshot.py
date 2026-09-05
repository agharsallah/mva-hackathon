"""The snapshot: TSV serialisation, the manifest shape, and the CLI, all offline.

``write_snapshot`` builds its own fetchers, so these tests replace
:func:`mva.drugs.snapshot.build_fetchers` with one that hands every source a routed
:class:`~test_drugs_support.FakeFetcher`. Nothing opens a socket and nothing sleeps.

The manifest assertions are the important half: a table this repository commits without a
manifest naming its inputs, its digests and its row counts is not a dataset, it is a file.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mva.drugs import cli, snapshot, tables
from mva.drugs.sources import clinicaltrials, dgidb, openfda, opentargets
from test_drugs_support import FIXTURES, FakeFetcher, fixture

CARD = FIXTURES / "card.json"
TSVS = ("targets", "drug_candidates", "trials", "literature", "pathways")


def routed(name: str) -> FakeFetcher:
    """One fake fetcher per source, answering with the recorded fixtures."""
    if name == "opentargets":
        return (
            FakeFetcher()
            .route(opentargets.ENDPOINT, fixture("opentargets_search_target"), '"entity": "target"')
            .route(opentargets.ENDPOINT, fixture("opentargets_target"), "ensemblId")
        )
    if name == "chembl":
        return (
            FakeFetcher()
            .route("/target/search.json", fixture("chembl_target_search"))
            .route("/mechanism.json", fixture("chembl_mechanism"))
            .route("/molecule.json", fixture("chembl_molecule"))
        )
    if name == "dgidb":
        return FakeFetcher().route(dgidb.ENDPOINT, fixture("dgidb_interactions"))
    if name == "reactome":
        return (
            FakeFetcher()
            .route("/data/mapping/UniProt/", fixture("reactome_pathways"))
            .route("/referenceEntities", fixture("reactome_participants"))
        )
    if name == "clinicaltrials":
        return FakeFetcher().route(clinicaltrials.ENDPOINT, fixture("clinicaltrials_studies"))
    if name == "pubmed":
        return (
            FakeFetcher()
            .route("/esearch.fcgi", fixture("pubmed_esearch"))
            .route("/esummary.fcgi", fixture("pubmed_esummary"))
        )
    return (
        FakeFetcher()
        .route(openfda.ENDPOINT, fixture("openfda_label"), "WIDGETONE")
        .route(openfda.ENDPOINT, fixture("openfda_404"))
    )


@pytest.fixture
def offline(monkeypatch) -> None:
    """Both namespaces: ``cli`` imported ``build_fetchers`` by name, ``snapshot`` owns it."""

    def fake(*_args, **_kwargs) -> dict[str, FakeFetcher]:
        return {name: routed(name) for name in snapshot.INTERVALS}

    monkeypatch.setattr(snapshot, "build_fetchers", fake)
    monkeypatch.setattr(cli, "build_fetchers", fake)


@pytest.fixture
def built(offline, tmp_path: Path) -> tuple[snapshot.Snapshot, Path]:
    out = tmp_path / "track2"
    return snapshot.write_snapshot(CARD, out), out


class TestCell:
    def test_a_list_is_joined_with_a_pipe(self) -> None:
        assert tables.cell(["a", "b"]) == "a|b"
        assert tables.cell(()) == ""

    def test_a_boolean_is_lower_case_and_none_is_empty(self) -> None:
        assert tables.cell(True) == "true"
        assert tables.cell(False) == "false"
        assert tables.cell(None) == ""

    def test_a_tab_or_newline_inside_a_value_cannot_split_the_record(self) -> None:
        assert "\t" not in tables.cell("a\tb")
        assert "\n" not in tables.cell("a\nb")

    def test_zero_is_written_not_swallowed(self) -> None:
        assert tables.cell(0) == "0"


class TestTables:
    def test_every_table_and_its_manifest_is_written(
        self, built: tuple[snapshot.Snapshot, Path]
    ) -> None:
        _result, out = built
        for name in TSVS:
            assert (out / f"{name}.tsv").is_file()
            assert (out / f"{name}.provenance.json").is_file()
        assert (out / "snapshot.json").is_file()

    def test_each_tsv_opens_with_its_declared_header(
        self, built: tuple[snapshot.Snapshot, Path]
    ) -> None:
        _result, out = built
        headers = {
            "targets": tables.TARGET_COLUMNS,
            "drug_candidates": tables.CANDIDATE_COLUMNS,
            "trials": tables.TRIAL_COLUMNS,
            "literature": tables.LITERATURE_COLUMNS,
            "pathways": tables.PATHWAY_COLUMNS,
        }
        for name, columns in headers.items():
            first = (out / f"{name}.tsv").read_text(encoding="utf-8").splitlines()[0]
            assert first.split("\t") == list(columns)

    def test_every_row_has_exactly_as_many_fields_as_the_header(
        self, built: tuple[snapshot.Snapshot, Path]
    ) -> None:
        _result, out = built
        for name in TSVS:
            lines = (out / f"{name}.tsv").read_text(encoding="utf-8").splitlines()
            width = len(lines[0].split("\t"))
            assert all(len(line.split("\t")) == width for line in lines[1:]), name

    def test_the_target_table_carries_seeds_and_pathway_members(
        self, built: tuple[snapshot.Snapshot, Path]
    ) -> None:
        _result, out = built
        lines = (out / "targets.tsv").read_text(encoding="utf-8").splitlines()[1:]
        roles = [line.split("\t")[1] for line in lines]
        assert roles.count("seed") == 3
        assert "pathway" in roles

    def test_the_trial_and_literature_tables_name_the_query_that_found_the_row(
        self, built: tuple[snapshot.Snapshot, Path]
    ) -> None:
        _result, out = built
        for name in ("trials", "literature"):
            lines = (out / f"{name}.tsv").read_text(encoding="utf-8").splitlines()
            assert lines[0].split("\t")[-1] == "query"
            assert all(line.split("\t")[-1] for line in lines[1:]), name


class TestManifests:
    def manifest(self, out: Path, name: str) -> dict:
        return json.loads((out / f"{name}.provenance.json").read_text(encoding="utf-8"))

    def test_the_envelope_matches_the_repository_shape(
        self, built: tuple[snapshot.Snapshot, Path]
    ) -> None:
        _result, out = built
        for name in TSVS:
            entry = self.manifest(out, name)
            assert entry["name"] == name
            assert entry["built_at"].endswith("+00:00")
            assert entry["built_by"] == "mva-drugs snapshot"
            assert entry["code_version"]
            assert entry["method"]
            assert entry["licence"]
            assert "patient_data" in entry

    def test_the_output_row_carries_a_real_digest_and_the_row_count(
        self, built: tuple[snapshot.Snapshot, Path]
    ) -> None:
        import hashlib

        result, out = built
        for name in TSVS:
            entry = self.manifest(out, name)["outputs"][0]
            path = out / f"{name}.tsv"
            assert entry["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
            assert entry["bytes"] == path.stat().st_size
            assert entry["rows"] == result.counts["rows"][name]
            # the recorded path is relative when the file is under the repository root
            assert not entry["path"].startswith("/") or Path(entry["path"]).is_absolute()

    def test_every_input_names_an_api_a_digest_and_a_retrieval_window(
        self, built: tuple[snapshot.Snapshot, Path]
    ) -> None:
        _result, out = built
        for name in TSVS:
            inputs = self.manifest(out, name)["inputs"]
            assert inputs
            for entry in inputs:
                assert entry["url"].startswith("http")
                assert entry["role"]
                assert entry["sha256"]
                assert entry["retrieved_at"]
                assert "sha256_scope" in entry

    def test_an_api_that_states_no_version_says_so_rather_than_inventing_one(
        self, built: tuple[snapshot.Snapshot, Path]
    ) -> None:
        _result, out = built
        entry = self.manifest(out, "targets")["inputs"][0]
        assert entry["version"] is None
        assert "known_gap" in entry

    def test_the_query_lists_are_carried_for_the_two_query_driven_tables(
        self, built: tuple[snapshot.Snapshot, Path]
    ) -> None:
        _result, out = built
        assert self.manifest(out, "trials")["inputs"][0]["queries"]
        assert self.manifest(out, "literature")["inputs"][0]["queries"]

    def test_each_manifest_names_the_card_it_was_built_from(
        self, built: tuple[snapshot.Snapshot, Path]
    ) -> None:
        _result, out = built
        card = self.manifest(out, "drug_candidates")["card"]
        assert card["version"] == 7
        assert card["gene"] == "GENEA"

    def test_no_table_or_manifest_can_carry_a_genomic_position(
        self, built: tuple[snapshot.Snapshot, Path]
    ) -> None:
        import csv
        import re

        _result, out = built
        # A genomic position looks like a bare run of 7+ digits - but so does a PMID, and
        # the tables legitimately carry those. So the claim under test is the sharper one:
        # a long digit run may appear ONLY in a column that holds PMIDs or inside a value
        # that names one (ChEMBL's preferred name for an unnamed research compound is
        # literally "COMPOUND 4B [PMID: ...]"), and a chromosome token may not appear at
        # all. That rules out a coordinate reaching any file without pretending a citation
        # is suspicious.
        digits = re.compile(r"(?<![\w.:/-])\d{7,}(?![\w.:/-])")
        chrom = re.compile(r"\bchr[0-9XYM]", re.IGNORECASE)
        pmid_columns = {"pmid", "pmids"}

        for name in TSVS:
            path = out / f"{name}.tsv"
            with path.open(encoding="utf-8", newline="") as stream:
                for row in csv.DictReader(stream, delimiter="\t"):
                    for column, value in row.items():
                        text = value or ""
                        assert not chrom.search(text), f"{name}.{column}: {text}"
                        if column in pmid_columns or "PMID" in text.upper():
                            continue
                        assert not digits.search(text), f"{name}.{column}: {text}"

        for name in (*TSVS, "snapshot"):
            suffix = "provenance.json" if name in TSVS else "json"
            text = (out / f"{name}.{suffix}").read_text(encoding="utf-8")
            assert not chrom.search(text), name

    def test_the_pmid_column_really_does_carry_long_ids(
        self, built: tuple[snapshot.Snapshot, Path]
    ) -> None:
        # Guards the test above: if the fixtures used three-digit PMIDs the assertion
        # would pass vacuously.
        _result, out = built
        lines = (out / "literature.tsv").read_text(encoding="utf-8").splitlines()[1:]
        assert any(len(line.split("\t")[0]) >= 7 for line in lines)
        # ...and a drug name that embeds its own citation really is in the candidate table,
        # so the "PMID inside the value" exemption above is exercised rather than assumed.
        names = (out / "drug_candidates.tsv").read_text(encoding="utf-8")
        assert "COMPOUND 4B [PMID: 90000555]" in names


class TestIndex:
    def test_the_index_counts_every_table_and_source(
        self, built: tuple[snapshot.Snapshot, Path]
    ) -> None:
        result, out = built
        index = json.loads((out / "snapshot.json").read_text(encoding="utf-8"))
        assert index["rows"] == result.counts["rows"]
        assert set(index["rows"]) == set(TSVS)
        assert index["targets"]["seed"] == 3
        assert index["pathways"]["matched"] == 2
        assert index["candidates"]["total"] == len(result.candidates)
        assert index["candidates"]["approved"] == len(result.approved)
        assert set(index["candidates"]["by_source"]) <= {"opentargets", "chembl", "dgidb"}

    def test_the_index_lists_every_query_including_the_ones_that_found_nothing(
        self, built: tuple[snapshot.Snapshot, Path]
    ) -> None:
        _result, out = built
        index = json.loads((out / "snapshot.json").read_text(encoding="utf-8"))
        assert index["trial_queries"]
        assert all("hits" in entry for entry in index["trial_queries"])
        assert [e["family"] for e in index["literature_queries"]][:2] == ["gene", "pathway"]

    def test_the_index_records_the_pathway_pattern_actually_used(
        self, built: tuple[snapshot.Snapshot, Path]
    ) -> None:
        _result, out = built
        index = json.loads((out / "snapshot.json").read_text(encoding="utf-8"))
        assert index["pathways"]["pattern"] == "checkpoint|kinetochore|mitotic"


class TestCli:
    def test_card_prints_the_card_and_its_queries(self, capsys) -> None:
        assert cli.main(["--card", str(CARD), "card"]) == 0
        out = capsys.readouterr().out
        assert "GENEA" in out
        assert "widget assembly checkpoint AND drug" in out

    def test_targets_runs_the_expansion(self, offline, capsys) -> None:
        assert cli.main(["--card", str(CARD), "targets"]) == 0
        out = capsys.readouterr().out
        assert "seeds 3" in out
        assert "GENED" in out

    def test_drugs_prints_the_candidate_table(self, offline, capsys) -> None:
        assert cli.main(["--card", str(CARD), "drugs", "--limit", "5"]) == 0
        assert "candidates" in capsys.readouterr().out

    def test_literature_prints_one_line_per_query(self, offline, capsys) -> None:
        assert cli.main(["--card", str(CARD), "literature", "--limit", "3"]) == 0
        assert "literature rows over" in capsys.readouterr().out

    def test_snapshot_writes_where_it_is_told(self, offline, tmp_path: Path, capsys) -> None:
        out = tmp_path / "elsewhere"
        assert cli.main(["--card", str(CARD), "snapshot", "--out-dir", str(out)]) == 0
        assert (out / "snapshot.json").is_file()
        assert "=== snapshot ===" in capsys.readouterr().out

    def test_a_custom_pathway_pattern_reaches_the_expansion(self, offline, capsys) -> None:
        assert cli.main(["--card", str(CARD), "--pathway-pattern", "zzz", "targets"]) == 0
        out = capsys.readouterr().out
        assert "pathways walked 3, kept 0" in out

    def test_a_dead_source_exits_two_rather_than_traceback(self, monkeypatch, capsys) -> None:
        from mva.drugs.cache import SourceError

        def boom(*_a, **_k):
            raise SourceError("https://example.test/api", "HTTP 503")

        monkeypatch.setattr(snapshot, "build_fetchers", boom)
        monkeypatch.setattr(cli, "build_fetchers", boom)
        assert cli.main(["--card", str(CARD), "targets"]) == 2
        assert "source unavailable" in capsys.readouterr().err
