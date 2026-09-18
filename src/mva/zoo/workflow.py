"""The zoo's DAG: eight stages, one command, one manifest.

A *DAG* here is nothing exotic — it is eight ordinary functions run in order, each one
idempotent (running it twice changes nothing the first run did not already do) and each one
printing a checkpoint line::

    normalize → registry_check → fan_out → collect → rank_per_model
              → report_per_model → merge → render

Two design rules make it testable and reusable:

* **Dependencies are injected, never imported at the top.** The stages talk to a
  :class:`~mva.zoo.workflow_types.Deps` bundle of callables. In production that bundle reaches
  ``mva.zoo.record``, ``registry``, ``adapters`` and ``cache``; in a test it reads
  ``fixtures/it4/``. Nothing is monkey-patched, so a test failure is a real failure.
* **Every stage writes its table, its lineage row and a checkpoint line.** A stage that
  produced no lineage row produced a table nobody can vouch for.

``run()`` returns a :class:`~mva.zoo.workflow_types.Manifest`: run id, config digest, model
versions, venues, wall-clock per stage and dollars. That object is the measured answer to the
methods form's "how long did it take and what did it cost", and it is written twice — with the
local file paths under ``build/it4/runs/``, and coordinate-free under ``docs/iteration4/runs/``.

The stages live in :mod:`mva.zoo.workflow_stages`; the shapes in
:mod:`mva.zoo.workflow_types`.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .workflow_types import STAGES, Config, Deps, Manifest, RunState, StageResult

__all__ = ["STAGES", "Config", "Deps", "Manifest", "RunState", "StageResult", "run"]


def run(
    config_path: str | Path,
    *,
    from_stage: str | None = None,
    connection: Any = None,
    deps: Deps | None = None,
    **overrides: Any,
) -> Manifest:
    """Run the DAG and return its manifest.

    Three ways to call it, and the default is deliberately the real one:

    * nothing injected → open the warehouse from the environment and run against it;
    * ``connection=`` a DuckDB connection with Postgres attached → run against that;
    * ``deps=`` a :class:`Deps` bundle → run against whatever it reads (a test's fakes, or
      ``Deps.fixtures()`` for the synthetic set). With ``deps`` and no ``connection``, no
      warehouse table and no lineage row is written and the manifest says so.

    ``from_stage`` skips the stages before it that only re-read what the cache already holds
    (resume proper, with a kill test, is plan §5 step 4's opt-A substep and is **not** claimed
    here).
    """
    if deps is None and connection is None:
        from ..warehouse.postgres import attached
        from ..warehouse.settings import Postgres

        with attached(Postgres.from_env()) as opened:
            return run(config_path, from_stage=from_stage, connection=opened, **overrides)
    return _run(config_path, from_stage=from_stage, connection=connection, deps=deps, **overrides)


def _run(
    config_path: str | Path,
    *,
    from_stage: str | None = None,
    connection: Any = None,
    deps: Deps | None = None,
    **overrides: Any,
) -> Manifest:
    """The runner itself, once the connection and the dependency bundle are settled."""
    from .workflow_stages import STAGE_FUNCTIONS

    config = Config.load(config_path, **overrides)
    bundle = deps or Deps.warehouse(connection)
    if from_stage is not None and from_stage not in STAGES:
        raise ValueError(f"unknown stage {from_stage!r}; expected one of {', '.join(STAGES)}")
    start_index = STAGES.index(from_stage) if from_stage else 0

    state = RunState()
    started = datetime.now(UTC)
    results: list[StageResult] = []
    config.out_dir.mkdir(parents=True, exist_ok=True)
    for index, stage in enumerate(STAGES):
        skip = index < start_index and stage in ("fan_out", "report_per_model")
        began = time.perf_counter()
        if skip:
            result = StageResult(stage, 0.0, 0, "skipped (--from)", skipped=True)
        else:
            result = STAGE_FUNCTIONS[stage](config, state, bundle, connection)
        result = StageResult(
            result.stage,
            round(time.perf_counter() - began, 4),
            result.rows,
            result.note,
            result.skipped,
        )
        results.append(result)
        print(f"[{config.run_id}] {stage:<18} {result.seconds:>8.3f}s  {result.note}")

    manifest = Manifest(
        run_id=config.run_id,
        config_path=str(config.path),
        config_digest=config.digest,
        mode=config.mode,
        method=config.method,
        models={m: str(card.get("version", "")) for m, card in sorted(state.cards.items())},
        venues=dict(sorted(state.venues.items())),
        stages=[vars(r) for r in results],
        dollars=0.0,
        started_at=started.isoformat(timespec="seconds"),
        finished_at=datetime.now(UTC).isoformat(timespec="seconds"),
        outputs=[
            str(config.out_dir / "merged.json"),
            str(config.merged_path),
            *(f"{config.reports_dir}/{r['model']}.md" for r in state.reports),
        ],
    )
    _write_manifest(config, manifest)
    return manifest


def _write_manifest(config: Config, manifest: Manifest) -> None:
    """The private copy under ``build/`` and the coordinate-free copy under ``docs/``."""
    private = config.out_dir / "runs"
    private.mkdir(parents=True, exist_ok=True)
    (private / f"{manifest.run_id}.json").write_text(
        json.dumps(manifest.to_json(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    public = config.docs_runs_dir
    public.mkdir(parents=True, exist_ok=True)
    (public / f"{manifest.run_id}.json").write_text(
        json.dumps(manifest.public(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    readme = public / "README.md"
    if not readme.is_file():
        readme.write_text(_RUNS_README, encoding="utf-8")


_RUNS_README = """# Iteration 4 — run manifests

**Standing:** written by `mva.zoo.workflow` on every `mva-zoo run`; re-verify by re-running.

One JSON per run: run id, config digest, model versions, venues, wall-clock per stage, and
dollars. These are the coordinate-free copies — the private copies, with the `build/` output
paths, stay under `build/it4/runs/`. The run id is derived from the config digest, so the same
configuration re-run is the same run id, not a new one.

Read with [`../plan.md`](../plan.md) §5 step 4 (the DAG) and the step-4 methodology entry that
files the run.
"""
