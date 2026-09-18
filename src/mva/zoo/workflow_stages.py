"""The eight stages themselves — one function each, every one idempotent.

Each stage takes ``(config, state, deps, connection)`` and returns a :class:`StageResult`. A
stage reads what earlier stages put in :class:`RunState`, writes its own table and lineage row
when a connection was given, and hands back one sentence for the checkpoint line the runner
prints. Re-running a stage with the same config writes nothing twice: the warehouse writers
are skipped when this ``run_id`` already wrote that table.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from . import merge as merge_module
from . import rank as rank_module
from . import report as report_module
from .report_sections import hpo_sentence
from .workflow_types import Config, Deps, RunState, StageResult

__all__ = ["STAGE_FUNCTIONS"]


# ---------------------------------------------------------------------------------------
# The stages
# ---------------------------------------------------------------------------------------


def normalize(config: Config, state: RunState, deps: Deps, connection: Any) -> StageResult:
    """Load the allele records every lane reads (step 1's output)."""
    state.records = deps.load_records(config)
    return StageResult("normalize", 0.0, len(state.records), f"{len(state.records)} records")


def registry_check(config: Config, state: RunState, deps: Deps, connection: Any) -> StageResult:
    """Keep the configured lanes that the registry knows and marks enabled."""
    cards = deps.load_registry(config)
    wanted = config.models or tuple(sorted(cards))
    missing = [m for m in wanted if m not in cards]
    state.cards = {m: cards[m] for m in wanted if m in cards and cards[m].get("enabled", True)}
    note = f"{len(state.cards)} lanes" + (f"; missing from registry: {missing}" if missing else "")
    return StageResult("registry_check", 0.0, len(state.cards), note)


def fan_out(config: Config, state: RunState, deps: Deps, connection: Any) -> StageResult:
    """Score every lane. Scores land in the cache; this stage only asks for them."""
    total = 0
    for model in sorted(state.cards):
        scores = deps.score(config, model, state.records)
        state.scores[model] = dict(scores)
        state.venues[model] = deps.venue(model)
        total += len(scores)
    return StageResult("fan_out", 0.0, total, f"{total} scores over {len(state.cards)} lanes")


def collect(config: Config, state: RunState, deps: Deps, connection: Any) -> StageResult:
    """Coverage per lane, by consequence class — the number section 2 of every report prints."""
    for model, scores in state.scores.items():
        state.coverage[model] = _coverage(model, state.records, scores)
    return StageResult("collect", 0.0, len(state.coverage), f"{len(state.coverage)} coverages")


def rank_per_model(config: Config, state: RunState, deps: Deps, connection: Any) -> StageResult:
    """Rank the callset's biallelic pairs once per lane and write ``it4_model_ranks``."""
    state.pairs = list(deps.load_pairs(config, state.records))
    state.ranks = rank_module.rank_per_model(state.pairs, state.scores)
    rows = 0
    if connection is not None and not _already_written(
        connection, config.schema, rank_module.MODEL_RANKS_TABLE, config.run_id
    ):
        rows = rank_module.write_ranks(connection, config.schema, state.ranks, run_id=config.run_id)
    return StageResult("rank_per_model", 0.0, rows, f"{len(state.pairs)} pairs, {rows} rows")


def report_per_model(config: Config, state: RunState, deps: Deps, connection: Any) -> StageResult:
    """Build and render one seven-section report per lane."""
    state.reports = []
    for model in sorted(state.ranks):
        card = state.cards.get(model, {"key": model})
        gene = _confirmed_gene(state.pairs)
        sentence = hpo_sentence(deps.hpo_row(config, gene), gene=gene, model=model)
        state.reports.append(
            report_module.model_report_json(
                card,
                state.coverage.get(model, {"scored": 0, "total": len(state.records)}),
                state.scores.get(model, {}),
                state.ranks[model],
                sentence,
                report_module.Runtime(venue=state.venues.get(model, "laptop")),
                run_id=config.run_id,
                mode=config.mode,
                llm_mode=config.llm_mode,
            )
        )
    report_module.write_markdown(state.reports, config.reports_dir)
    _dump_report_json(config, state)
    if connection is not None and not _already_written(
        connection, config.schema, report_module.MODEL_REPORTS_TABLE, config.run_id
    ):
        report_module.write_reports(connection, config.schema, state.reports, run_id=config.run_id)
    return StageResult("report_per_model", 0.0, len(state.reports), f"{len(state.reports)} reports")


def _dump_report_json(config: Config, state: RunState) -> None:
    """The same JSON the warehouse row holds, on disk, so the figure script needs no database."""
    directory = config.out_dir / "reports"
    directory.mkdir(parents=True, exist_ok=True)
    for payload in state.reports:
        path = directory / f"{payload.get('model', 'model')}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def merge(config: Config, state: RunState, deps: Deps, connection: Any) -> StageResult:
    """The deterministic layer: agreement matrix, RRF both ways, disagreement table."""
    state.merged = merge_module.merged_report(
        state.ranks,
        state.cards,
        state.scores,
        run_id=config.run_id,
        method=config.method,
        rrf_k=config.rrf_k,
        sources=[
            f"{config.schema}.{rank_module.MODEL_RANKS_TABLE}",
            "warehouse.allele_scores",
            f"{config.schema}.coding_alleles",
        ],
    )
    path = config.out_dir / "merged.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state.merged, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    free = state.merged["consensus"]["catalogue_free"]["rank"]
    return StageResult("merge", 0.0, len(state.merged.get("lanes", [])), f"RRF rank (free): {free}")


def render(config: Config, state: RunState, deps: Deps, connection: Any) -> StageResult:
    """Write ``docs/iteration4/report.md`` with the hand-written narrative slot marked."""
    narrative = _existing_narrative(config.merged_path)
    text = merge_module.render_merged(state.merged, narrative)
    config.merged_path.parent.mkdir(parents=True, exist_ok=True)
    config.merged_path.write_text(text, encoding="utf-8")
    return StageResult("render", 0.0, 1, str(config.merged_path))


STAGE_FUNCTIONS: dict[str, Callable[[Config, RunState, Deps, Any], StageResult]] = {
    "normalize": normalize,
    "registry_check": registry_check,
    "fan_out": fan_out,
    "collect": collect,
    "rank_per_model": rank_per_model,
    "report_per_model": report_per_model,
    "merge": merge,
    "render": render,
}


def _coverage(model: str, records: Sequence[Any], scores: Mapping[str, float]) -> dict[str, Any]:
    """Scored-vs-total per consequence class, from what actually came back."""
    by: dict[str, list[int]] = {}
    scored = 0
    for item in records:
        key = str(_field(item, "allele_id") or "")
        consequence = str(_field(item, "consequence") or "unknown")
        bucket = by.setdefault(consequence, [0, 0])
        bucket[1] += 1
        if key in scores:
            bucket[0] += 1
            scored += 1
    return {
        "model": model,
        "scored": scored,
        "total": len(records),
        "by_consequence": {name: (hit, total) for name, (hit, total) in by.items()},
    }


def _field(record: Any, name: str) -> Any:
    if isinstance(record, Mapping):
        return record.get(name)
    return getattr(record, name, None)


def _confirmed_gene(pairs: Sequence[rank_module.Pair]) -> str:
    return next((p.gene for p in pairs if p.is_confirmed), rank_module.CONFIRMED_GENE)


def _already_written(connection: Any, schema: str, table: str, run_id: str) -> bool:
    """True when this run already wrote that table — what makes a stage safe to re-run."""
    from ..warehouse.postgres import ALIAS, safe_identifier

    safe = safe_identifier(schema)
    try:
        found = connection.execute(
            f"SELECT count(*) FROM {ALIAS}.{safe}.{table} WHERE run_id = ?",
            [run_id],
        ).fetchone()
    except Exception:
        return False
    return bool(found and found[0])


def _existing_narrative(path: Path) -> str:
    """Keep a narrative a human already wrote under the marker; never overwrite prose."""
    if not path.is_file():
        return ""
    marker = "<!-- narrative: hand-written"
    text = path.read_text(encoding="utf-8")
    if marker not in text:
        return ""
    tail = text.split(marker, 1)[1].split("-->", 1)[-1]
    return tail.split("\n## ", 1)[0].strip()
