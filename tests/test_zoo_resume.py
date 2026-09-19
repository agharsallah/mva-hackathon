"""The kill test for claim ``P4-5``: a DAG killed mid-fan-out resumes without recomputing.

The workflow runs in a **thread** with a cooperative kill hook injected through
:class:`~mva.zoo.workflow_types.Deps` — the third lane's ``score`` raises, exactly as a
``SIGKILL`` between two lanes would leave things, and nothing is monkey-patched. The deps
bundle counts its own calls, so "was this recomputed?" is a number rather than an impression.

Three things are asserted, and they are the claim:

1. **Nothing finished is recomputed.** Across the killed attempt *and* the restart, every
   finished stage's outside-world call happens exactly once, and each of the two lanes that
   finished before the kill is scored once, not twice. The lane the kill landed *inside* is
   asked again — its work never came back, so repeating it is the correct behaviour, and the
   test pins that boundary rather than papering over it.
2. **The result is the same.** The restarted run's ``merged.json``, per-model report JSON and
   merged report are identical to an uninterrupted run of the same config, once the
   generation timestamps are removed — they are the one thing that legitimately differs.
3. **One run, one manifest.** The run id is the config digest, so a resumed run overwrites
   its own manifest rather than filing a second one.

Plus the property that makes the resume trustworthy rather than merely fast: the checkpoints
are keyed by **content**, so a changed config, a changed record set or a changed model version
invalidates exactly the markers downstream of the change, and a truncated marker reads as
"not done" instead of taking the next run down.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import duckdb
import pytest

from mva.zoo import checkpoint, workflow
from mva.zoo.pairs import Pair
from mva.zoo.workflow_types import Config, Deps

CONFIG = "src/mva/zoo/zoo.example.toml"

#: Four lanes, scored in sorted order: alphamissense, esm1b, revel, spliceai. The kill lands
#: on the third, so two lanes are finished and two are not.
LANES = ("alphamissense", "esm1b", "revel", "spliceai")
KILL_AFTER = 2

RECORDS = [
    {"allele_id": "a1", "gene": "GA", "consequence": "missense_variant", "is_read_only": False},
    {"allele_id": "a2", "gene": "GA", "consequence": "missense_variant", "is_read_only": False},
    {"allele_id": "b1", "gene": "GB", "consequence": "stop_gained", "is_read_only": False},
    {"allele_id": "b2", "gene": "GB", "consequence": "missense_variant", "is_read_only": False},
]

PAIRS = [
    Pair("GA", "a1", "a2", "trans"),
    Pair("GB", "b1", "b2", "trans", is_confirmed=True),
]

SCORES = {
    "alphamissense": {"a1": 0.2, "a2": 0.3, "b1": 0.9, "b2": 0.8},
    "esm1b": {"a1": 0.1, "a2": 0.4, "b1": 0.95, "b2": 0.7},
    "revel": {"a1": 0.9, "a2": 0.9, "b1": 0.2, "b2": 0.2},
    "spliceai": {"a1": 0.5, "a2": 0.5},
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
    for model in LANES
}


class KilledError(RuntimeError):
    """What the injected hook raises in place of the signal a real kill would deliver."""


class Counting:
    """A deps bundle that counts every call it makes to the world outside the process."""

    def __init__(
        self,
        *,
        kill_after: int | None = None,
        versions: dict[str, str] | None = None,
        records: list[dict[str, Any]] | None = None,
    ):
        self.calls: dict[str, int] = {}
        self.kill_after = kill_after
        self.versions = versions or {}
        self.records = records if records is not None else [dict(r) for r in RECORDS]
        self.scored: list[str] = []
        self.returned: list[str] = []

    def _count(self, name: str) -> None:
        self.calls[name] = self.calls.get(name, 0) + 1

    def deps(self) -> Deps:
        return Deps(
            load_records=self._records,
            load_registry=self._registry,
            score=self._score,
            load_pairs=self._pairs,
            hpo_row=lambda _config, _gene: {"rank": 3, "genes_considered": 4812, "score": 0.87},
            fingerprint=self._fingerprint,
        )

    def _fingerprint(self, _config: Config, stage: str) -> str:
        """What the production bundle does: a cheap look at the source, without reading it.

        The record list stands in for the callset table's row count and the version map for
        the roster files' bytes.
        """
        if stage == "normalize":
            return checkpoint.digest_of(sorted(r["allele_id"] for r in self.records))
        if stage == "registry_check":
            return checkpoint.digest_of(self.versions)
        return ""

    def _records(self, _config: Config) -> list[Any]:
        self._count("load_records")
        return [dict(record) for record in self.records]

    def _registry(self, _config: Config) -> dict[str, dict[str, Any]]:
        self._count("load_registry")
        return {
            model: {**card, "version": self.versions.get(model, card["version"])}
            for model, card in CARDS.items()
        }

    def _score(self, _config: Config, model: str, _records: Any) -> dict[str, float]:
        self._count(f"score:{model}")
        self.scored.append(model)
        if self.kill_after is not None and len(self.scored) > self.kill_after:
            raise KilledError(f"killed while scoring {model}")
        self.returned.append(model)
        return dict(SCORES[model])

    def _pairs(self, _config: Config, _records: Any) -> list[Pair]:
        self._count("load_pairs")
        return list(PAIRS)


def connection() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("ATTACH ':memory:' AS pg")
    con.execute("CREATE SCHEMA pg.results")
    con.execute("CREATE SCHEMA pg.warehouse")
    return con


def paths_under(root: Path) -> dict[str, Path]:
    return {
        "out_dir": root / "build",
        "reports_dir": root / "reports",
        "docs_runs_dir": root / "runs",
        "merged_path": root / "report.md",
    }


def in_thread(**kwargs: Any) -> BaseException | None:
    """Run the workflow in a thread and hand back whatever killed it, or ``None``."""
    caught: list[BaseException] = []

    def target() -> None:
        try:
            workflow.run(CONFIG, **kwargs)
        except BaseException as error:
            caught.append(error)

    thread = threading.Thread(target=target, name="zoo-kill-test")
    thread.start()
    thread.join(timeout=60)
    assert not thread.is_alive(), "the workflow thread did not finish"
    return caught[0] if caught else None


# ── the kill and the restart ─────────────────────────────────────────────────────────────


@dataclass
class Resumed:
    """One killed attempt, its on-disk state at the moment of the kill, and the restart."""

    killed: Counting
    restart: Counting
    paths: dict[str, Path]
    markers_at_kill: list[str]
    lanes_at_kill: list[str]


@pytest.fixture
def resumed(tmp_path: Path) -> Resumed:
    """Kill a run inside ``fan_out`` after two lanes, then restart it with the same config."""
    paths = paths_under(tmp_path / "resumed")
    killed = Counting(kill_after=KILL_AFTER)
    error = in_thread(connection=connection(), deps=killed.deps(), **paths)
    assert isinstance(error, KilledError)
    directory = checkpoint.directory(Config.load(CONFIG, **paths))
    markers = sorted(p.stem for p in directory.glob("*.json"))
    lanes = sorted(p.stem for p in (directory / "fan_out").glob("*.json"))

    restart = Counting()
    assert in_thread(connection=connection(), deps=restart.deps(), **paths) is None
    return Resumed(killed, restart, paths, markers, lanes)


def test_the_kill_lands_inside_fan_out_with_two_lanes_finished(resumed: Resumed):
    assert resumed.killed.scored == [LANES[0], LANES[1], LANES[2]]  # the third raised
    assert resumed.lanes_at_kill == list(LANES[:2])
    # `fan_out` itself never finished, so it has no stage marker — only the two before it.
    assert resumed.markers_at_kill == ["normalize", "registry_check"]


def test_no_finished_stage_and_no_finished_lane_is_recomputed(resumed: Resumed):
    """The claim, as counters: one call each, across the killed attempt and the restart."""
    killed, restart = resumed.killed, resumed.restart
    total = {name: killed.calls.get(name, 0) + restart.calls.get(name, 0) for name in _names()}
    assert total["load_records"] == 1
    assert total["load_registry"] == 1
    assert total["load_pairs"] == 1
    # The two lanes that *finished* before the kill are asked once, across both attempts.
    for lane in LANES[:KILL_AFTER]:
        assert total[f"score:{lane}"] == 1, f"{lane} was scored twice"
    # The lane the kill landed inside never returned, so its work was lost and is redone —
    # attempted twice, completed once. That is the resolution the claim is about: finished
    # work is never repeated, unfinished work always is.
    assert total[f"score:{LANES[KILL_AFTER]}"] == 2
    assert killed.returned == list(LANES[:KILL_AFTER])
    assert restart.returned == list(LANES[KILL_AFTER:])
    # and the restart itself only did the work the kill left behind
    assert restart.calls == {f"score:{LANES[2]}": 1, f"score:{LANES[3]}": 1, "load_pairs": 1}


def _names() -> list[str]:
    return ["load_records", "load_registry", "load_pairs", *(f"score:{lane}" for lane in LANES)]


def test_the_resumed_outputs_match_an_uninterrupted_run(resumed: Resumed, tmp_path):
    paths = resumed.paths
    clean = paths_under(tmp_path / "clean")
    assert in_thread(connection=connection(), deps=Counting().deps(), **clean) is None

    assert _normalise(_artifacts(paths)) == _normalise(_artifacts(clean))


def test_exactly_one_manifest_exists_for_the_run(resumed: Resumed):
    paths = resumed.paths
    private = sorted((paths["out_dir"] / "runs").glob("*.json"))
    public = sorted(paths["docs_runs_dir"].glob("*.json"))
    assert len(private) == 1 and len(public) == 1
    assert private[0].stem == public[0].stem == Config.load(CONFIG, **paths).run_id


def _artifacts(paths: dict[str, Path]) -> dict[str, str]:
    """Every file the run is judged on, keyed by a path that does not include the tmp root."""
    found = {
        "report.md": paths["merged_path"].read_text(encoding="utf-8"),
        "merged.json": (paths["out_dir"] / "merged.json").read_text(encoding="utf-8"),
    }
    for report in sorted((paths["out_dir"] / "reports").glob("*.json")):
        found[f"reports/{report.name}"] = report.read_text(encoding="utf-8")
    for markdown in sorted(paths["reports_dir"].glob("*.md")):
        found[f"md/{markdown.name}"] = markdown.read_text(encoding="utf-8")
    return found


def _normalise(artifacts: dict[str, str]) -> dict[str, list[str]]:
    """Drop the generation instants — the one thing two runs may legitimately disagree on."""
    stamps = ("generated", "_at", "built_at", "ts")
    return {
        name: [line for line in text.splitlines() if not any(s in line for s in stamps)]
        for name, text in artifacts.items()
    }


# ── the checkpoints are keyed by content, not by name ────────────────────────────────────


def test_a_changed_source_invalidates_the_stage_that_reads_it_and_everything_after(tmp_path):
    """The stale-cache trap, closed: a re-built source is *seen*, not hidden by a marker.

    The bundle's ``fingerprint`` is the only thing that can notice — the stage's own read is
    the expensive work the resume exists to avoid. Here the record set shrinks, so
    ``normalize``'s fingerprint moves, the chain moves with it, and every lane is re-scored
    under a new key rather than restored against records that no longer exist.
    """
    paths = paths_under(tmp_path)
    assert in_thread(connection=connection(), deps=Counting().deps(), **paths) is None

    fewer = Counting(records=[dict(RECORDS[0]), dict(RECORDS[1])])
    assert in_thread(connection=connection(), deps=fewer.deps(), **paths) is None
    assert fewer.calls.get("load_records") == 1
    for lane in LANES:
        assert fewer.calls.get(f"score:{lane}") == 1


def test_a_source_the_bundle_cannot_fingerprint_is_restored_and_the_docs_say_so(tmp_path):
    """The limitation, pinned rather than left to be discovered.

    A bundle whose ``fingerprint`` returns ``""`` for a stage is saying "I cannot tell you
    whether my source moved". The resume then trusts the marker, so a changed source is
    *silently reused* until ``--force`` or ``--from``. That is the price of resuming a stage
    whose input cannot be hashed cheaply, and it is why :class:`Deps.warehouse` implements
    the hook for the two stages that read a table.
    """
    paths = paths_under(tmp_path)
    blind = Counting()
    assert (
        in_thread(
            connection=connection(),
            deps=replace(blind.deps(), fingerprint=lambda _config, _stage: ""),
            **paths,
        )
        is None
    )
    changed = Counting(records=[dict(RECORDS[0])])
    assert (
        in_thread(
            connection=connection(),
            deps=replace(changed.deps(), fingerprint=lambda _config, _stage: ""),
            **paths,
        )
        is None
    )
    assert changed.calls == {}  # every stage restored, the shrunken record set never read
    forced = Counting(records=[dict(RECORDS[0])])
    assert in_thread(connection=connection(), deps=forced.deps(), force=True, **paths) is None
    assert forced.calls.get("load_records") == 1


def test_a_changed_model_version_re_scores_only_that_lane(tmp_path):
    """Content, not name: the lane key is ``(chain, model, version)``, so a bump re-scores one.

    ``registry_check`` has to run for the bump to be visible at all — here through its
    fingerprint over the version map, which stands in for the roster files' bytes.
    """
    paths = paths_under(tmp_path)
    assert in_thread(connection=connection(), deps=Counting().deps(), **paths) is None

    bumped = Counting(versions={"esm1b": "test-2"})
    assert in_thread(connection=connection(), deps=bumped.deps(), **paths) is None
    assert bumped.calls.get("load_registry") == 1
    assert bumped.calls.get("score:esm1b") == 1
    for lane in ("alphamissense", "revel", "spliceai"):
        assert f"score:{lane}" not in bumped.calls


def test_a_truncated_marker_reads_as_not_done_rather_than_crashing(tmp_path):
    paths = paths_under(tmp_path)
    assert in_thread(connection=connection(), deps=Counting().deps(), **paths) is None
    directory = checkpoint.directory(Config.load(CONFIG, **paths))
    (directory / "normalize.json").write_text('{"stage": "normalize", "state', encoding="utf-8")

    again = Counting()
    assert in_thread(connection=connection(), deps=again.deps(), **paths) is None
    assert again.calls.get("load_records") == 1


def test_an_override_that_changes_the_case_is_not_the_same_run(tmp_path):
    """The seed is the *effective* config, not the TOML's bytes.

    ``config.digest`` — and with it the run id and the checkpoint folder — is the hash of the
    file alone, so ``--case-gene OTHER`` would otherwise land in the same folder and restore
    pairs flagged for a different gene. :func:`checkpoint.seed` folds the overrides in, so
    every stage re-runs instead.
    """
    paths = paths_under(tmp_path)
    assert in_thread(connection=connection(), deps=Counting().deps(), **paths) is None

    other = Counting()
    assert (
        in_thread(connection=connection(), deps=other.deps(), confirmed_gene="OTHER", **paths)
        is None
    )
    assert other.calls.get("load_records") == 1
    assert other.calls.get("load_pairs") == 1
    base, moved = Config.load(CONFIG, **paths), Config.load(CONFIG, confirmed_gene="OTHER", **paths)
    assert base.digest == moved.digest  # the file did not change …
    assert checkpoint.seed(base) != checkpoint.seed(moved)  # … but the case did


def test_force_clears_the_markers_it_is_pointed_at(tmp_path):
    paths = paths_under(tmp_path)
    assert in_thread(connection=connection(), deps=Counting().deps(), **paths) is None
    config = Config.load(CONFIG, **paths)
    removed = checkpoint.clear(config, from_stage="collect")
    assert removed == 5  # collect, rank_per_model, report_per_model, merge, render
    assert checkpoint.load(config, "normalize") is not None
    assert checkpoint.load(config, "collect") is None
    assert checkpoint.clear(config) == 3 + len(LANES)  # the three left, plus every lane file


def test_the_marker_file_is_json_a_human_can_read(tmp_path):
    paths = paths_under(tmp_path)
    assert in_thread(connection=connection(), deps=Counting().deps(), **paths) is None
    directory = checkpoint.directory(Config.load(CONFIG, **paths))
    payload = json.loads((directory / "fan_out.json").read_text(encoding="utf-8"))
    assert payload["stage"] == "fan_out"
    assert payload["finished_at"].startswith("20")
    assert sorted(payload["state"]["models"]) == list(LANES)
    assert payload["state"]["models"]["esm1b"]["version"] == "test-1"
