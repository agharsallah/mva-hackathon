"""The DAG end to end on fixtures: eight stages, one manifest, one merged page.

Nothing is monkey-patched. The fake registry and the fake scorer are passed in as a
:class:`mva.zoo.workflow_types.Deps` bundle, which is the whole point of injecting them: the
production path and the test path run the same stage code.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import duckdb
import pytest

from mva.zoo import rank, report, workflow
from mva.zoo.pairs import Pair
from mva.zoo.workflow_types import Config, Deps

CONFIG = "src/mva/zoo/zoo.example.toml"

RECORDS = [
    {"allele_id": "a1", "gene": "GA", "consequence": "missense_variant", "is_read_only": False},
    {"allele_id": "a2", "gene": "GA", "consequence": "missense_variant", "is_read_only": False},
    {"allele_id": "b1", "gene": "GB", "consequence": "stop_gained", "is_read_only": False},
    {"allele_id": "b2", "gene": "GB", "consequence": "missense_variant", "is_read_only": False},
    {"allele_id": "r1", "gene": "GC", "consequence": "missense_variant", "is_read_only": True},
]

PAIRS = [
    Pair("GA", "a1", "a2", "trans"),
    Pair("GB", "b1", "b2", "trans", is_confirmed=True),
]

LANE_SCORES = {
    "alphamissense": {"a1": 0.2, "a2": 0.3, "b1": 0.9, "b2": 0.8, "r1": 0.4},
    "esm1b": {"a1": 0.1, "a2": 0.4, "b1": 0.95, "b2": 0.7},
    "spliceai": {"a1": 0.5, "a2": 0.5},  # this lane has no opinion on the confirmed pair
    "revel": {"a1": 0.9, "a2": 0.9, "b1": 0.2, "b2": 0.2},  # the catalogue-adjacent lane
}

CARDS = {
    model: {
        "key": model,
        "name": model,
        "version": "test-1",
        "tier": 1,
        "enabled": True,
        "catalogue_adjacent": model == "revel",
        "licence": "test",
    }
    for model in LANE_SCORES
}


def fake_deps() -> Deps:
    return Deps(
        load_records=lambda _config: list(RECORDS),
        load_registry=lambda _config: {k: dict(v) for k, v in CARDS.items()},
        score=lambda _config, model, _records: dict(LANE_SCORES.get(model, {})),
        load_pairs=lambda _config, _records: list(PAIRS),
        hpo_row=lambda _config, _gene: {"rank": 3, "genes_considered": 4812, "score": 0.87},
    )


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


@pytest.fixture
def paths(tmp_path: Path) -> dict:
    return {
        "out_dir": tmp_path / "build",
        "reports_dir": tmp_path / "reports",
        "docs_runs_dir": tmp_path / "runs",
        "merged_path": tmp_path / "report.md",
    }


# ── the config ───────────────────────────────────────────────────────────────────────────


def test_the_example_config_parses_into_the_mvp_shape():
    config = Config.load(CONFIG)
    assert config.mode == "catalogue-free"
    assert config.method == "fusion"
    assert config.rrf_k == 60
    assert config.llm_mode == "none"
    assert config.out_dir == Path("build/it4")
    assert "alphamissense" in config.models


def test_the_run_id_is_the_config_digest_so_a_re_run_is_the_same_run():
    assert Config.load(CONFIG).run_id == Config.load(CONFIG).run_id
    assert Config.load(CONFIG).run_id.startswith("it4-")


def test_an_unknown_stage_name_is_refused_by_name(paths):
    with pytest.raises(ValueError, match="unknown stage"):
        workflow.run(CONFIG, from_stage="not-a-stage", deps=fake_deps(), **paths)


# ── the chain ────────────────────────────────────────────────────────────────────────────


def test_the_whole_chain_runs_and_returns_a_manifest(connection, paths, capsys):
    manifest = workflow.run(CONFIG, connection=connection, deps=fake_deps(), **paths)
    assert [stage["stage"] for stage in manifest.stages] == list(workflow.STAGES)
    assert manifest.models == dict.fromkeys(CARDS, "test-1")
    assert manifest.dollars == 0.0
    assert manifest.config_digest
    printed = capsys.readouterr().out
    for stage in workflow.STAGES:
        assert stage in printed  # every stage prints its checkpoint line


def test_the_manifest_is_written_twice_and_the_public_copy_drops_build_paths(connection, paths):
    manifest = workflow.run(CONFIG, connection=connection, deps=fake_deps(), **paths)
    private = paths["out_dir"] / "runs" / f"{manifest.run_id}.json"
    public = paths["docs_runs_dir"] / f"{manifest.run_id}.json"
    assert private.is_file() and public.is_file()
    assert any(
        p.startswith("build") or "build" in p for p in json.loads(private.read_text())["outputs"]
    )
    assert not [p for p in json.loads(public.read_text())["outputs"] if p.startswith("build/")]
    readme = (paths["docs_runs_dir"] / "README.md").read_text()
    assert "**Standing:**" in readme


def test_the_skipped_genes_reach_the_manifest_when_the_pair_source_counted_them(connection, paths):
    """A gene too dense to pair is a caveat on every "of N pairs" the run prints.

    `PairBuild` counted them from the first run and the number was dropped on the floor, so
    `/api/zoo/ranks` had to serve `skipped_genes: []` with `skipped_genes_recorded: false`
    beside it. The manifest now carries both, and the cap that caused them.
    """
    from mva.zoo.pairs import MAX_CALLS_PER_GENE, PairBuild

    build = PairBuild(
        pairs=list(PAIRS),
        confirmed_note="GB has one pair; flagged confirmed",
        genes=3,
        het_calls=7,
        skipped_genes=("MUC16", "AHNAK2"),
    )
    deps = replace(fake_deps(), load_pairs=lambda _config, _records: build)
    manifest = workflow.run(CONFIG, connection=connection, deps=deps, **paths)

    assert manifest.pairs["skipped_genes"] == ["AHNAK2", "MUC16"]  # sorted, not insertion order
    assert manifest.pairs["skipped_genes_recorded"] is True
    assert manifest.pairs["max_calls_per_gene"] == MAX_CALLS_PER_GENE
    assert manifest.pairs["genes"] == 3 and manifest.pairs["het_calls"] == 7
    assert "flagged confirmed" in manifest.pairs["confirmed_note"]
    # and it survives both copies of the manifest, not just the object
    public = json.loads((paths["docs_runs_dir"] / f"{manifest.run_id}.json").read_text())
    assert public["pairs"]["skipped_genes"] == ["AHNAK2", "MUC16"]


def test_a_pair_source_that_only_returns_pairs_records_nothing_rather_than_empty(connection, paths):
    """Absent measurement, never a claim that nothing was skipped."""
    manifest = workflow.run(CONFIG, connection=connection, deps=fake_deps(), **paths)
    assert manifest.pairs == {}
    assert (
        "skipped_genes"
        not in json.loads((paths["docs_runs_dir"] / f"{manifest.run_id}.json").read_text())["pairs"]
    )


def test_the_fixture_run_records_no_pair_build_because_a_fixture_counts_nothing(paths):
    """A pairs TSV is not a callset: it cannot say how many genes or het calls it came from.

    So the fixture bundle returns bare pairs and the manifest carries no `pairs` block at all,
    rather than a block of zeros that would read as a measurement.
    """
    manifest = workflow.run(CONFIG, deps=Deps.fixtures("fixtures/it4"), **paths)
    assert manifest.pairs == {}
    assert (
        json.loads((paths["docs_runs_dir"] / f"{manifest.run_id}.json").read_text())["pairs"] == {}
    )


def test_the_merged_page_is_written_with_the_narrative_slot(connection, paths):
    workflow.run(CONFIG, connection=connection, deps=fake_deps(), **paths)
    text = paths["merged_path"].read_text(encoding="utf-8")
    assert "<!-- narrative: hand-written" in text
    assert "## 3. Consensus — reciprocal rank fusion" in text
    assert "`alphamissense`" in text


def test_one_report_per_lane_is_rendered(connection, paths):
    workflow.run(CONFIG, connection=connection, deps=fake_deps(), **paths)
    written = sorted(p.name for p in paths["reports_dir"].iterdir())
    assert written == ["alphamissense.md", "esm1b.md", "revel.md", "spliceai.md"]
    assert "## 6. Interpretation" in (paths["reports_dir"] / "esm1b.md").read_text()


def test_the_lane_that_could_not_score_the_pair_says_it_has_no_opinion(connection, paths):
    workflow.run(CONFIG, connection=connection, deps=fake_deps(), **paths)
    text = (paths["reports_dir"] / "spliceai.md").read_text(encoding="utf-8")
    assert "no opinion" in text


def test_the_consensus_is_reported_with_and_without_the_adjacent_lane(connection, paths):
    workflow.run(CONFIG, connection=connection, deps=fake_deps(), **paths)
    merged = json.loads((paths["out_dir"] / "merged.json").read_text(encoding="utf-8"))
    free = merged["consensus"]["catalogue_free"]
    aware = merged["consensus"]["all_lanes"]
    assert free["excluded_lanes"] == ["revel"]
    assert aware["excluded_lanes"] == []
    assert free["lanes"] == ["alphamissense", "esm1b", "spliceai"]
    assert free["rank"] == 2 and aware["rank"] == 2
    assert free["k"] == 60


def test_a_thin_lane_hands_its_one_ranked_pair_a_full_top_rank_vote(connection, paths):
    """A real property of RRF on partial lists, worth seeing rather than discovering later.

    ``spliceai`` can score only GA, so GA is rank 1 *in that lane* and collects 1/(60+1) —
    the same contribution a lane that ranked every pair would give its winner. Two lanes put
    the confirmed GB first (2/61 = 0.03279) and GA second (2/62), but GA's extra 1/61 from
    the thin lane (total 0.04865) takes it past GB. Fusing lists of different lengths is not
    neutral, and the merged report therefore prints ``n_ranked`` per lane beside every rank.
    """
    workflow.run(CONFIG, connection=connection, deps=fake_deps(), **paths)
    merged = json.loads((paths["out_dir"] / "merged.json").read_text(encoding="utf-8"))
    by_model = {lane["model"]: lane for lane in merged["lanes"]}
    assert by_model["spliceai"]["n_ranked"] == 1
    assert by_model["spliceai"]["unscored_pairs"] == 1
    assert by_model["spliceai"]["confirmed"]["rank"] is None
    assert merged["consensus"]["catalogue_free"]["fused_score"] == pytest.approx(2 / 61)


# ── idempotence ──────────────────────────────────────────────────────────────────────────


def test_running_twice_writes_the_warehouse_rows_once(connection, paths):
    workflow.run(CONFIG, connection=connection, deps=fake_deps(), **paths)
    first = _counts(connection)
    workflow.run(CONFIG, connection=connection, deps=fake_deps(), **paths)
    assert _counts(connection) == first


def test_running_twice_produces_the_same_markdown(connection, paths):
    workflow.run(CONFIG, connection=connection, deps=fake_deps(), **paths)
    once = paths["merged_path"].read_text(encoding="utf-8")
    workflow.run(CONFIG, connection=connection, deps=fake_deps(), **paths)
    twice = paths["merged_path"].read_text(encoding="utf-8")
    assert _without_timestamps(once) == _without_timestamps(twice)


def test_a_hand_written_narrative_survives_a_re_render(connection, paths):
    workflow.run(CONFIG, connection=connection, deps=fake_deps(), **paths)
    text = paths["merged_path"].read_text(encoding="utf-8")
    edited = text.replace(
        "_(narrative not yet written)_", "Three lanes agree; the adjacent one does not."
    )
    paths["merged_path"].write_text(edited, encoding="utf-8")
    # `force=True` so `render` really runs again: a restored render leaves the file alone and
    # would pass this test without exercising the narrative-preserving code at all.
    workflow.run(CONFIG, force=True, connection=connection, deps=fake_deps(), **paths)
    assert "Three lanes agree" in paths["merged_path"].read_text(encoding="utf-8")


def test_a_run_without_a_connection_writes_files_but_no_table(paths):
    manifest = workflow.run(CONFIG, deps=fake_deps(), **paths)
    assert paths["merged_path"].is_file()
    assert manifest.run_id


def test_from_stage_re_runs_that_stage_on_and_restores_everything_before_it(connection, paths):
    """``--from collect`` means "collect onwards is stale", not "skip the expensive ones".

    The pre-checkpoint build read it the other way round: it skipped `fan_out` and
    `report_per_model` whatever came before them, so `--from collect` could produce a run with
    no scores at all. With markers on disk the earlier stages are *restored* — same data, no
    deps call — and every stage from `collect` on is recomputed.
    """
    workflow.run(CONFIG, connection=connection, deps=fake_deps(), **paths)
    manifest = workflow.run(
        CONFIG, from_stage="collect", connection=connection, deps=fake_deps(), **paths
    )
    skipped = [s["stage"] for s in manifest.stages if s["skipped"]]
    assert skipped == ["normalize", "registry_check", "fan_out"]


def test_a_plain_re_run_restores_every_stage_from_its_checkpoint(connection, paths):
    workflow.run(CONFIG, connection=connection, deps=fake_deps(), **paths)
    manifest = workflow.run(CONFIG, connection=connection, deps=fake_deps(), **paths)
    assert [s["stage"] for s in manifest.stages if s["skipped"]] == list(workflow.STAGES)


def test_force_drops_the_checkpoints_and_recomputes_everything(connection, paths):
    workflow.run(CONFIG, connection=connection, deps=fake_deps(), **paths)
    manifest = workflow.run(CONFIG, force=True, connection=connection, deps=fake_deps(), **paths)
    assert [s["stage"] for s in manifest.stages if s["skipped"]] == []


def _counts(connection) -> tuple[int, int, int]:
    return (
        connection.execute(f"SELECT count(*) FROM pg.results.{rank.MODEL_RANKS_TABLE}").fetchone()[
            0
        ],
        connection.execute(
            f"SELECT count(*) FROM pg.results.{report.MODEL_REPORTS_TABLE}"
        ).fetchone()[0],
        connection.execute("SELECT count(*) FROM pg.results.data_lineage").fetchone()[0],
    )


def _without_timestamps(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if "generated" not in line)


# ── the fixture bundle the figure script and the smoke run use ───────────────────────────


def test_the_fixture_deps_read_the_committed_fixtures(paths):
    manifest = workflow.run(CONFIG, deps=Deps.fixtures("fixtures/it4"), **paths)
    assert set(manifest.models) == {"alphamissense", "esm1b", "revel", "spliceai"}
    merged = json.loads((paths["out_dir"] / "merged.json").read_text(encoding="utf-8"))
    assert len(merged["lanes"]) == 4
    assert merged["agreement"]["models"] == ["alphamissense", "esm1b", "revel", "spliceai"]


def test_the_report_quotes_the_phenotype_ranking_when_the_warehouse_has_one(tmp_path):
    """Section 5 is the clinical half of the evidence and must not silently read empty.

    The first real run printed "produced no `BUB1B` row" for a gene the phenotype table
    ranks #14 of 5,267, because `Deps.warehouse` never supplied an `hpo_row` reader at all
    (entry 128). This pins the sentence against a stand-in row.
    """
    from mva.zoo.report_stats import hpo_sentence

    row = {"gene_symbol": "GENEA", "rank": 14, "score": 0.3609, "genes_considered": 5267}
    sentence = hpo_sentence(row, gene="GENEA", model="fake", term_set="with-parental")
    assert "#14 of 5267" in sentence
    assert "0.3609" in sentence
    assert "never sees the phenotype" in sentence
    assert "produced no" not in hpo_sentence(row, gene="GENEA", model="fake")
