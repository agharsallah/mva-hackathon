"""Command line for the model zoo — ``mva-zoo``.

Six verbs, in the order a run uses them:

``records``
    build the normalised allele record set (step 1) and leave it in ``build/it4/``.
``models``
    print the registry's model cards — what each lane is, its version, tier and licence.
``coverage``
    how much of the record set one model can score, before spending anything on it.
``score``
    run one model over the record set and append its rows to the score cache, with a
    lineage edge. Re-running is a **no-op**: rows already cached are skipped.
``scores``
    every model's cached row for one allele — the "what does the zoo think of this one"
    view.
``run``
    the whole workflow from a config file (step 4), optionally resuming from one stage.

Everything here runs **in process**. There is no HTTP server in the MVP: the workflow calls
these same functions, and a result never needed a route. The read-only routes over the cache
are a later, optional addition.

Connection settings come from ``.env`` through :class:`~mva.warehouse.settings.Postgres`,
exactly as ``mva-warehouse`` reads them; ``--schema`` overrides the schema the cache and the
lineage edges live in.
"""

from __future__ import annotations

import argparse
import inspect
import json
import sys
from collections.abc import Iterator, Sequence
from dataclasses import asdict, is_dataclass, replace
from pathlib import Path
from typing import Any

from . import cache
from .adapters import DEFAULT_RECORDS, coverage_of, records_from_parquet
from .adapters import build as build_adapter
from .types import MODES, AlleleRecord, Coverage, ScoreRow

__all__ = ["main"]

DEFAULT_OUT = Path("build/it4")


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    parser = _parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 1
    try:
        return int(handler(args))
    except (RuntimeError, ValueError, FileNotFoundError, NotImplementedError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


# ── the parser ───────────────────────────────────────────────────────────────────────


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mva-zoo", description="Run the open-model zoo.")
    subparsers = parser.add_subparsers(dest="command")

    records = subparsers.add_parser("records", help="build the allele record set (step 1)")
    records.add_argument("--mask-catalogue", action="store_true", help="null the clin_sig field")
    records.add_argument("--limit", type=int, default=None, help="stop after N alleles (smoke run)")
    records.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    _schema_flags(records)
    records.set_defaults(handler=_do_records)

    models = subparsers.add_parser("models", help="print the registry's model cards")
    models.add_argument("--json", action="store_true", dest="as_json", help="machine-readable")
    models.set_defaults(handler=_do_models)

    coverage = subparsers.add_parser("coverage", help="what fraction of the records a model scores")
    coverage.add_argument("--model", required=True, help="the model card's key")
    coverage.add_argument("--records", type=Path, default=DEFAULT_RECORDS)
    coverage.add_argument("--limit", type=int, default=None)
    _schema_flags(coverage)
    coverage.set_defaults(handler=_do_coverage)

    score = subparsers.add_parser("score", help="score the record set with one model")
    score.add_argument("--model", required=True, help="the model card's key")
    score.add_argument("--mode", choices=list(MODES), default="catalogue-free")
    score.add_argument("--records", type=Path, default=DEFAULT_RECORDS)
    score.add_argument("--limit", type=int, default=None)
    score.add_argument("--dry-run", action="store_true", help="report coverage, write nothing")
    _schema_flags(score)
    score.set_defaults(handler=_do_score)

    scores = subparsers.add_parser("scores", help="every model's cached row for one allele")
    scores.add_argument("--allele-id", required=True, help="the coordinate-free allele key")
    _schema_flags(scores)
    scores.set_defaults(handler=_do_scores)

    run = subparsers.add_parser("run", help="run the whole workflow from a config file")
    run.add_argument("--config", type=Path, default=Path("zoo.toml"))
    run.add_argument("--from", dest="from_stage", default=None, help="resume from this stage")
    run.set_defaults(handler=_do_run)
    return parser


def _schema_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--schema", default=None, help="override the warehouse schema")
    parser.add_argument("--result-schema", default=None, help="override the result schema")


# ── shared plumbing ──────────────────────────────────────────────────────────────────


def _settings(args: argparse.Namespace) -> Any:
    """Resolve connection settings, letting flags override the environment and ``.env``."""
    from mva.warehouse.settings import Postgres

    settings = Postgres.from_env()
    overrides = {
        key: value for key in ("schema", "result_schema") if (value := getattr(args, key, None))
    }
    return replace(settings, **overrides) if overrides else settings


def _card(key: str) -> Any:
    """One model card from the registry, or a message naming the keys that do exist."""
    from . import registry

    cards = registry.load()
    if key not in cards:
        raise RuntimeError(f"no model {key!r} in the registry; known: {', '.join(sorted(cards))}")
    return cards[key]


def _records(args: argparse.Namespace, *, mode: str = "aware") -> list[AlleleRecord]:
    """Load the record set, masked if the run is catalogue-free."""
    rows = records_from_parquet(args.records, limit=args.limit)
    if not rows:
        raise RuntimeError(f"{args.records} holds no records")
    return [row.masked() for row in rows] if mode == "catalogue-free" else rows


def _print_coverage(coverage: Coverage) -> None:
    print(f"{coverage.model}: {coverage.scored:,}/{coverage.total:,} ({coverage.fraction:.1%})")
    for name, (hit, total) in coverage.by_consequence.items():
        share = hit / total if total else 0.0
        print(f"  {name:<32} {hit:>7,}/{total:>7,}  {share:6.1%}")


def _stamped(rows: Iterator[ScoreRow], *, mode: str) -> Iterator[ScoreRow]:
    """Record which mode produced each row, so the cache can be read back per mode."""
    for row in rows:
        yield replace(row, aux={**row.aux, "mode": mode})


def _describe(value: Any) -> str:
    if is_dataclass(value) and not isinstance(value, type):
        return ", ".join(f"{key}={item}" for key, item in asdict(value).items())
    return str(value)


# ── the verbs ────────────────────────────────────────────────────────────────────────


def _do_records(args: argparse.Namespace) -> int:
    """Delegate to step 1's builder and report what it produced."""
    from . import record

    summary = record.run(
        _settings(args),
        mask_catalogue=args.mask_catalogue,
        out_dir=args.out_dir,
        limit=args.limit,
    )
    print(_describe(summary))
    return 0


def _do_models(args: argparse.Namespace) -> int:
    """Print the registry, either as a table or as JSON for another tool to read."""
    from . import registry

    cards = registry.load()
    if args.as_json:
        print(json.dumps({key: _card_dict(card) for key, card in cards.items()}, indent=2))
        return 0
    rows = [
        (
            key,
            str(cards[key].tier),
            str(cards[key].adapter),
            str(cards[key].version),
            str(cards[key].licence)
            + (" (catalogue-adjacent)" if getattr(cards[key], "catalogue_adjacent", False) else ""),
        )
        for key in sorted(cards)
    ]
    header = ("key", "tier", "adapter", "version", "licence")
    widths = [max(len(header[index]), *(len(row[index]) for row in rows)) for index in range(4)]
    labels = [name.ljust(width) for name, width in zip(header[:4], widths, strict=True)]
    print("  ".join([*labels, header[4]]))
    for row in rows:
        cells = [row[index].ljust(widths[index]) for index in range(4)]
        print("  ".join([*cells, row[4]]))
    return 0


def _card_dict(card: Any) -> dict[str, Any]:
    if is_dataclass(card) and not isinstance(card, type):
        return asdict(card)
    return {key: value for key, value in vars(card).items() if not key.startswith("_")}


def _do_coverage(args: argparse.Namespace) -> int:
    """Build the lane and ask it how much of the record set it can answer for."""
    from mva.warehouse.postgres import attached

    card = _card(args.model)
    records = _records(args)
    with attached(_settings(args), read_only=True) as connection:
        adapter = build_adapter(card, connection=connection, records_parquet=Path(args.records))
        _print_coverage(coverage_of(adapter, records))
    return 0


def _do_score(args: argparse.Namespace) -> int:
    """Score the record set with one model and append the rows to the cache."""
    from mva.warehouse.postgres import attached

    settings = _settings(args)
    card = _card(args.model)
    records = _records(args, mode=args.mode)
    with attached(settings, read_only=args.dry_run) as connection:
        adapter = build_adapter(card, connection=connection, records_parquet=Path(args.records))
        coverage = coverage_of(adapter, records)
        _print_coverage(coverage)
        if args.dry_run:
            print("dry run: nothing written")
            return 0
        run_id = cache.run_id()
        written = cache.write(
            connection,
            settings.schema,
            _stamped(adapter.score(records), mode=args.mode),
            run_id=run_id,
        )
        cache.lineage_row(
            connection,
            settings.schema,
            model=card.key,
            version=str(card.version),
            run_id=run_id,
            rows=written.inserted,
            digest=str(getattr(adapter, "digest", "") or ""),
            source_ref=str(getattr(adapter, "source_ref", "") or card.source),
        )
    print(
        f"run {run_id}: inserted {written.inserted:,}, skipped {written.skipped:,} "
        f"(already cached) — mode {args.mode}"
    )
    return 0


def _do_scores(args: argparse.Namespace) -> int:
    """Every model's verdict on one allele, newest model first by name."""
    from mva.warehouse.postgres import attached

    settings = _settings(args)
    with attached(settings, read_only=True) as connection:
        rows = cache.read(connection, settings.schema, allele_ids=[args.allele_id])
    if not rows:
        print(f"no cached score for {args.allele_id}")
        return 0
    print(f"{'model':<20} {'version':<12} {'score':>10}  venue")
    for row in sorted(rows, key=lambda item: (item.model, item.version)):
        value = "null" if row.score is None else f"{row.score:.4f}"
        print(f"{row.model:<20} {row.version:<12} {value:>10}  {row.venue}")
    return 0


def _do_run(args: argparse.Namespace) -> int:
    """Hand the whole pipeline to the workflow module (step 4)."""
    from . import workflow

    kwargs: dict[str, Any] = {}
    if args.from_stage:
        accepted = _resume_parameter(workflow.run)
        if accepted is None:
            raise RuntimeError("this workflow build has no resume; drop --from and re-run")
        kwargs[accepted] = args.from_stage
    manifest = workflow.run(args.config, **kwargs)
    print(_describe(manifest))
    return 0


def _resume_parameter(function: Any) -> str | None:
    """Which keyword ``workflow.run`` spells its resume point with, if it has one."""
    names: Sequence[str] = tuple(inspect.signature(function).parameters)
    for candidate in ("from_stage", "start", "stage", "resume_from"):
        if candidate in names:
            return candidate
    return None
