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
    if args.dry_run:
        return _narrate_dry_run(json_dir, args.only or [], settings, citable_rows, build_prompt)
    result = narrate_module.run_narrate(
        json_dir=json_dir,
        reports_dir=case.reports_dir,
        settings=settings,
        models=args.only or (),
        run_id=case.run_id,
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
            run_id=case.run_id,
            table=table,
            source_ref=f"{case.schema}.{case.table('model_reports')}",
            lineage_schema=case.warehouse_schema,
        )
    print(f"stored {written} rows in {case.schema}.{table}")
