"""The ``mva-zoo narrate`` verb: section 6 written by an LLM, then checked.

Its own module because :mod:`mva.zoo.cli` is at the project's 400-line cap and because the
verb is optional: a build that never calls an LLM imports none of the machinery behind it.
The parser is registered by :func:`add_narrate_parser`, which :mod:`mva.zoo.cli` calls with
its own subparsers — one line there, everything else here.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

__all__ = ["add_narrate_parser"]


def add_narrate_parser(subparsers: Any, *, default_config: Path) -> None:
    """Register ``mva-zoo narrate`` on an existing subparser set."""
    parser = subparsers.add_parser(
        "narrate", help="write section 6 of each report with an LLM and check its citations"
    )
    parser.add_argument("--config", type=Path, default=default_config)
    parser.add_argument("--mode", default=None, help="override [llm] mode for this call")
    parser.add_argument("--llm-model", default=None, help="override [llm] model for this call")
    parser.add_argument(
        "--model",
        action="append",
        default=None,
        dest="only",
        help="only this lane (repeatable); the default is every report on disk",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the rows and the prompt for each lane; call nothing, write nothing",
    )
    parser.add_argument(
        "--no-store",
        action="store_true",
        help="do not append rows to <schema>.<prefix>_narratives",
    )
    parser.add_argument(
        "--merged",
        action="store_true",
        help="synthesise the merged report's narrative instead (step 6, fusion+synthesis)",
    )
    parser.set_defaults(handler=do_narrate)


def do_narrate(args: argparse.Namespace) -> int:
    """Section 6 of every report, written by the configured LLM and checked row by row.

    The case config supplies the paths, the table prefix and the schemas; ``[llm]`` supplies
    the mode, the model, the temperature and the word budget. ``--dry-run`` prints exactly
    what would be sent and calls nothing, which is the cheapest way to review a prompt.
    """
    from . import narrate as narrate_module
    from .cli import _case
    from .narrate_modes import LlmSettings
    from .narrate_rows import build_prompt, citable_rows

    case = _case(args)
    if case is None:
        raise RuntimeError("narrate needs --config <case.toml>")
    settings = LlmSettings.load(args.config)
    if args.mode:
        settings = replace(settings, mode=args.mode)
    if args.llm_model:
        settings = replace(settings, model=args.llm_model)
    json_dir = case.out_dir / "reports"
    if args.merged:
        return _narrate_merged(args, case, settings, json_dir)
    if args.dry_run:
        return _narrate_dry_run(json_dir, args.only or [], settings, citable_rows, build_prompt)
    result = narrate_module.run_narrate(
        json_dir=json_dir,
        reports_dir=case.reports_dir,
        settings=settings,
        models=args.only or (),
        # Not `case.run_id`: a narrative's run id is **the run of the report it explains**,
        # so `<prefix>_narratives.run_id` joins `<prefix>_model_reports.run_id`. The narrate
        # call's own config digest is a different run (editing `[llm]` changes it) and would
        # break that join. It is recorded on the lineage edge instead.
        case=case.case_json(),
        reports_table=f"{case.schema}.{case.table('model_reports')}",
    )
    for item in result.narratives:
        print(json.dumps(item.summary(), sort_keys=True))
    if result.narratives and not args.no_store:
        _store_narratives(args, case, result.narratives)
    print(f"{len(result.narratives)} narratives, {len(result.paths)} files rewritten")
    return 0


def _narrate_dry_run(
    json_dir: Path,
    only: Sequence[str],
    settings: Any,
    citable_rows: Any,
    build_prompt: Any,
) -> int:
    """Print the rows and the prompt for each lane. No process is spawned, no file written."""
    wanted = set(only)
    for path in sorted(json_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        key = str(payload.get("model") or path.stem)
        if wanted and key not in wanted:
            continue
        rows = citable_rows(payload)
        print(f"--- {key}: {len(rows)} citable rows, mode {settings.mode!r} ---")
        print(build_prompt(rows, max_words=settings.max_words))
    return 0


def _store_narratives(args: argparse.Namespace, case: Any, narratives: Sequence[Any]) -> None:
    """Append the narratives to this case's table, with one lineage edge."""
    from mva.warehouse.postgres import attached

    from . import narrate as narrate_module
    from .cli import _settings

    settings = _settings(args)
    table = case.table("narratives")
    with attached(settings, read_only=False) as connection:
        written = narrate_module.write_narratives(
            connection,
            case.schema,
            list(narratives),
            run_id=case.run_id,  # the lineage edge's source_version: this narrate call
            table=table,
            source_ref=f"{case.schema}.{case.table('model_reports')}",
            lineage_schema=case.warehouse_schema,
        )
    print(f"stored {written} rows in {case.schema}.{table}")


def _narrate_merged(args: argparse.Namespace, case: Any, settings: Any, json_dir: Path) -> int:
    """Step 6's ``fusion+synthesis``: one synthesised narrative for the merged report.

    Reads the merged JSON the run left in the case's output directory, plus each lane's own
    section 6 so the synthesis can build on the lanes rather than re-read their numbers. The
    hand-written narrative already in ``report.md`` is kept under the synthesised one, badge
    and all — the same rule section 6 of every per-model report follows.
    """
    from . import narrate as narrate_module
    from .merge_render import existing_narratives, hand_written_sections, render_merged
    from .narrate_rows import build_merge_prompt, merged_rows

    merged_path = case.out_dir / "merged.json"
    if not merged_path.is_file():
        raise RuntimeError(f"{merged_path} is missing; run the merge stage first")
    merged = json.loads(merged_path.read_text(encoding="utf-8"))
    readings = _lane_readings(json_dir)
    if args.dry_run:
        rows = merged_rows(merged, readings)
        print(f"--- merged: {len(rows)} citable rows, mode {settings.mode!r} ---")
        print(build_merge_prompt(rows, max_words=settings.max_words))
        return 0
    item = narrate_module.narrate_merged(merged, readings, settings=settings)
    mode = item.mode if item is not None else ""
    versions = [narrate_module.interpretation_block(item, "narrative")] if item is not None else []
    # Every version already on the page is kept under the new one, minus an earlier run of
    # the same mode — the rule section 6 of each lane's report follows.
    versions += [
        block for block in existing_narratives(case.merged_path) if block.get("llm_mode") != mode
    ]
    if not versions:
        raise RuntimeError("nothing to write: mode is 'none' and report.md holds no narrative")
    case.merged_path.parent.mkdir(parents=True, exist_ok=True)
    case.merged_path.write_text(
        render_merged(
            merged,
            versions[0]["text"],
            narratives=versions,
            hand_written=hand_written_sections(case.merged_path),
        ),
        encoding="utf-8",
    )
    if item is not None:
        print(json.dumps(item.summary(), sort_keys=True))
        if not args.no_store:
            _store_narratives(args, case, [item])
    print(f"{len(versions)} narrative version(s) -> {case.merged_path}")
    return 0


def _lane_readings(json_dir: Path) -> dict[str, str]:
    """Each lane's own section 6, keyed by lane — the ``interp.<model>`` rows of the prompt."""
    out: dict[str, str] = {}
    for path in sorted(json_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        block = payload.get("sections", {}).get("interpretation") or {}
        text = str(block.get("text") or "")
        if text:
            out[str(payload.get("model") or path.stem)] = text
    return out
