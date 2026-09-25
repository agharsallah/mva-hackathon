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
    """Score every lane. Scores land in the cache; this stage only asks for them.

    Resumable **per lane**, not only as a whole: each lane writes its own checkpoint marker
    the moment it comes back, keyed by ``(chain digest, model, version)``. A run killed after
    the second of four lanes restarts with two lanes to score, and a lane whose declared
    version changed is re-scored even though its name is unchanged
    (:mod:`mva.zoo.checkpoint`).
    """
    from . import checkpoint

    # A lane's key is what *that lane* consumed — the case, the record set, and its own
    # (model, version). Deliberately not the stage's chain digest: that carries every card in
    # the roster, so adding a fifth lane would re-score the four that did not change.
    base = checkpoint.digest_of(
        checkpoint.seed(config), [_field(record, "allele_id") for record in state.records]
    )
    total = restored = 0
    for model in sorted(state.cards):
        version = str(state.cards[model].get("version", ""))
        key = checkpoint.digest_of(base, model, version)
        marker = None if state.force else checkpoint.load_model(config, model, key)
        if marker is None:
            scores = dict(deps.score(config, model, state.records))
            venue = deps.venue(model)
            checkpoint.save_model(
                config, model, version=version, venue=venue, inputs_digest=key, scores=scores
            )
        else:
            scores, venue = marker.scores, marker.venue
            restored += 1
        state.scores[model] = scores
        state.venues[model] = venue
        total += len(scores)
    note = f"{total} scores over {len(state.cards)} lanes"
    if restored:
        note += f" ({restored} restored from checkpoints)"
    return StageResult("fan_out", 0.0, total, note)


def collect(config: Config, state: RunState, deps: Deps, connection: Any) -> StageResult:
    """Coverage per lane, by consequence class — the number section 2 of every report prints."""
    for model, scores in state.scores.items():
        state.coverage[model] = _coverage(model, state.records, scores)
    return StageResult("collect", 0.0, len(state.coverage), f"{len(state.coverage)} coverages")


def rank_per_model(config: Config, state: RunState, deps: Deps, connection: Any) -> StageResult:
    """Rank the callset's biallelic pairs once per lane and write ``<prefix>_model_ranks``."""
    built: Any = deps.load_pairs(config, state.records)
    # Either shape is accepted: a PairBuild (the real one, which also carries the skipped
    # genes) or a bare list of pairs (a fixture or a test double).
    state.pairs = list(getattr(built, "pairs", built))
    state.pair_build = _pair_build(built)
    state.ranks = rank_module.rank_per_model(state.pairs, state.scores)
    rows = 0
    if connection is not None and not _already_written(
        connection, config.schema, rank_module.MODEL_RANKS_TABLE, config.run_id
    ):
        rows = rank_module.write_ranks(
            connection,
            config.schema,
            state.ranks,
            run_id=config.run_id,
            lineage_schema=config.warehouse_schema,
        )
    skipped = state.pair_build.get("skipped_genes", [])
    note = f"{len(state.pairs)} pairs, {rows} rows"
    if skipped:
        note += f", {len(skipped)} genes skipped as too dense to pair"
    return StageResult("rank_per_model", 0.0, rows, note)


def _pair_build(built: Any) -> dict[str, Any]:
    """The bookkeeping beside the pairs, as JSON — ``{}`` when the source gave bare pairs.

    A gene with more heterozygous calls than :data:`mva.zoo.pairs.MAX_CALLS_PER_GENE` is
    skipped rather than paired (the pair count grows as n²), and the run has to say which:
    "of N pairs" means the pairs outside those genes, and a reader who is not told cannot know
    that. It was computed and dropped until the API needed it.
    """
    if not hasattr(built, "pairs"):
        return {}
    from .pairs import MAX_CALLS_PER_GENE

    return {
        "genes": int(getattr(built, "genes", 0)),
        "het_calls": int(getattr(built, "het_calls", 0)),
        "skipped_genes": sorted(getattr(built, "skipped_genes", ())),
        # The reader needs to tell "nothing was skipped" from "nobody wrote it down". A run
        # whose pair source returned bare pairs has no entry at all; one that returned a
        # PairBuild says so here, empty list or not — the same two fields `/api/zoo/ranks`
        # serves (`src/mva/viz/api_zoo_ranks.py`).
        "skipped_genes_recorded": True,
        "max_calls_per_gene": MAX_CALLS_PER_GENE,
        "confirmed_note": str(getattr(built, "confirmed_note", "")),
    }


def report_per_model(config: Config, state: RunState, deps: Deps, connection: Any) -> StageResult:
    """Build and render one seven-section report per lane."""
    state.reports = []
    reports_table = config.table("model_reports")
    for model in sorted(state.ranks):
        card = state.cards.get(model, {"key": model})
        gene = _confirmed_gene(state.pairs, config)
        sentence = hpo_sentence(
            deps.hpo_row(config, gene),
            gene=gene or "(none declared)",
            model=model,
            term_set=config.phenotype_term_set,
        )
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
                reports_table=reports_table,
                case=config.case_json(),
            )
        )
    report_module.write_markdown(state.reports, config.reports_dir)
    _dump_report_json(config, state)
    if connection is not None and not _already_written(
        connection, config.schema, reports_table, config.run_id
    ):
        report_module.write_reports(
            connection,
            config.schema,
            state.reports,
            run_id=config.run_id,
            lineage_schema=config.warehouse_schema,
            table=reports_table,
        )
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
    """Write the case's merged report (``[paths] merged_report``), every narrative kept.

    Section 5 holds **more than one** version once an LLM has synthesised one beside the
    hand-written paragraph, and a re-render that restored only the hand-written one deleted the
    synthesised one — a $0.116 model call thrown away by an idempotent stage. So the stage reads
    *every* version back out of the rendered file
    (:func:`mva.zoo.merge_render.existing_narratives`, which rebuilds each block from its own
    marker) and hands the whole list back to the renderer. Same rule, same reason, as
    ``report.write_markdown`` for section 6. Every hand-written ``## `` section outside §1–§6
    (a headline, a Track 2 chapter) is read back too
    (:func:`mva.zoo.merge_render.hand_written_sections`) and kept verbatim.
    """
    # The renderer, not `merge.render_merged`: that forwarder takes one narrative and is
    # another group's file. Calling the module that owns the template is the smaller change.
    from .merge_render import existing_narratives, hand_written_sections, render_merged

    kept = existing_narratives(config.merged_path)
    text = render_merged(
        state.merged,
        kept[0]["text"] if kept else "",
        narratives=kept,
        hand_written=hand_written_sections(config.merged_path),
    )
    config.merged_path.parent.mkdir(parents=True, exist_ok=True)
    config.merged_path.write_text(text, encoding="utf-8")
    state.method = _realised_method(config.method, kept)
    note = str(config.merged_path)
    if state.method != config.method:
        note += f"; method realised as {state.method!r} (configured {config.method!r})"
    return StageResult("render", 0.0, 1, note)


def _realised_method(configured: str, narratives: Sequence[Mapping[str, Any]]) -> str:
    """What the merge method **was**, not what was asked for — the manifest records this.

    ``fusion+synthesis`` means "a model synthesised section 5". The synthesis is produced by
    ``mva-zoo narrate --merged``, deliberately not by this stage: a billable, non-deterministic
    call inside a resumable stage would run on the first pass and be restored on every later
    one, so the same config would not give the same page. The stage therefore reports what the
    rendered page actually carries — a page with a synthesised version is
    ``fusion+synthesis`` whatever the config says, and a config that asks for one without a
    synthesis on the page is ``fusion``, plus a note saying which command is owed.
    """
    synthesised = any(str(block.get("llm_mode") or "none") != "none" for block in narratives)
    if synthesised:
        return "fusion+synthesis"
    return "fusion" if configured == "fusion+synthesis" else configured


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


def _confirmed_gene(pairs: Sequence[rank_module.Pair], config: Config) -> str:
    """The gene a flagged pair carries, else whatever the case config declared (maybe none)."""
    return next((p.gene for p in pairs if p.is_confirmed), config.confirmed_gene)


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
