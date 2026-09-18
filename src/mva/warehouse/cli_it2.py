"""The ``pg-load-it2-*`` verbs: one loader per iteration-2 step.

Split out of :mod:`mva.warehouse.cli` because they are all the same shape — read a build
directory, land its TSVs, append a lineage row per table — and there is one per step, so the
set grows with the research rather than with the platform. Keeping them here leaves the CLI
module about the platform's own verbs.

Each verb refuses to pretend: a build directory with no tables is an error naming the tool
that writes them, never an empty load.
"""

from __future__ import annotations

from . import postgres as pg
from .settings import Postgres

__all__ = [
    "load_it2_step1",
    "load_it2_step2",
    "load_it2_step3",
    "load_it2_step4",
]


def load_it2_step1(args, settings: Postgres) -> int:
    """Load iteration 2's step-1 target and decoy tables from a build directory."""
    from . import it2_tables

    with pg.attached(settings) as connection:
        loaded = it2_tables.load(
            connection,
            schema=settings.schema,
            result_schema=settings.result_schema,
            out_dir=args.out,
        )
    for item in loaded:
        print(f"  {settings.result_schema}.{item.table:<12} {item.rows:>5,} rows  <- {item.source}")
    print(f"\nlineage edges appended to {settings.schema}.data_lineage")
    return 0


def load_it2_step4(args, settings: Postgres) -> int:
    """Load iteration 2's step-4 likelihood-ratio ranking, P(trans) and null tables."""
    from . import it2_step4_tables

    with pg.attached(settings) as connection:
        loaded = it2_step4_tables.load(
            connection,
            schema=settings.schema,
            result_schema=settings.result_schema,
            out_dir=args.out,
        )
    if not loaded:
        print(f"nothing to load: no TSVs under {args.out}/tables")
        print("run `uv run python tools/rank_it2_pairs.py` first")
        return 1
    for item in loaded:
        print(f"  {settings.result_schema}.{item.table:<14} {item.rows:>7,} rows  <- {item.source}")
    print(f"\nlineage edges appended to {settings.schema}.data_lineage")
    return 0


def load_it2_step3(args, settings: Postgres) -> int:
    """Load iteration 2's step-3 alignment-free genotype and copy-number tables."""
    from . import it2_step3_tables

    with pg.attached(settings) as connection:
        loaded = it2_step3_tables.load(
            connection,
            schema=settings.schema,
            result_schema=settings.result_schema,
            out_dir=args.out,
        )
    if not loaded:
        print(f"nothing to load: no TSVs under {args.out}/tables")
        print("run `uv run python tools/export_it2_step3_tables.py` first")
        return 1
    for item in loaded:
        print(f"  {settings.result_schema}.{item.table:<22} {item.rows:>9,} rows  <- {item.source}")
    print(f"\nlineage edges appended to {settings.schema}.data_lineage")
    return 0


def load_it2_step2(args, settings: Postgres) -> int:
    """Load iteration 2's step-2 read-derived tables from a build directory."""
    from . import it2_step2_tables

    with pg.attached(settings) as connection:
        loaded = it2_step2_tables.load(
            connection,
            schema=settings.schema,
            result_schema=settings.result_schema,
            out_dir=args.out,
        )
    if not loaded:
        print(f"nothing to load: no TSVs under {args.out}/tables")
        print("run `uv run python tools/export_it2_step2_tables.py` first")
        return 1
    for item in loaded:
        print(f"  {settings.result_schema}.{item.table:<20} {item.rows:>9,} rows  <- {item.source}")
    print(f"\nlineage edges appended to {settings.schema}.data_lineage")
    return 0
