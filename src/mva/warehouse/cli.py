"""Command line for the warehouse.

Four verb families, each runnable and inspectable on its own.

The first is the **staging** step, which has no network at all.

``stage``
    Normalise a profile directory **and** the committed public reference tables
    (``ressources/reference/``) into typed Parquet under ``build/warehouse/``. This is
    what ``pg-ingest`` reads, so it is the first step of every load.

The second targets a **hosted PostgreSQL** — the one shared, concurrently-written store.
They read connection settings from ``.env`` and connect over the network, so they need
nothing installed on the server beyond the PostgreSQL already there.

``pg-check``
    Show the resolved settings and probe the server. Reads nothing, writes nothing.
``pg-ingest``
    Load the staged Parquet into the ingest schema.
``pg-derive``
    Run the analyses and write their outputs into the result schema.
``pg-list``
    List every table in both managed schemas with its row count.
``pg-query``
    Run one read-only SQL statement against the hosted database.

A third family covers the **callset** itself, and exists so that "we kept 100% of the
data" is a checked claim rather than an assumption. Run ``vcf-verify`` before any bulk
ingest.

``vcf-shape``
    Report what a VCF's header declares. Reads no records.
``vcf-verify``
    Rebuild every record through DuckDB and compare SHA-256 against the source file.
``vcf-stage``
    Write the lossless all-text raw layer to Parquet.

A fourth verb stands alone because it is the only one that reaches a **third party**.

``annotate-panel``
    Ask Ensembl VEP REST what every allele inside the candidate panel does, and land the
    answer in ``warehouse.panel_annotations``. ``--dry-run`` prints the batch plan without
    sending a request.

A fifth family targets the **object store** — the large immutable files kept on the
server, queried in place over HTTP range requests so nothing is downloaded whole and no
SSH session is needed.

``s3-check`` / ``s3-ls``
    Prove the store answers, and see what is in it.
``s3-put``
    Upload a Parquet.
``s3-query``
    Run SQL against a file that never leaves the server.
``s3-sort``
    Rewrite an object clustered by the columns you filter on, which is what makes
    range requests small.

A sixth family covers the two **ledgers** — append-only records of things that cannot be
reconstructed after the fact.

``lineage-repair`` / ``lineage-backfill`` / ``lineage-list``
    Which bytes produced which table. ``pg-derive`` records its own edges; these two
    repair edges written before the delivery reached the object store, and backfill runs
    that predate the automatic recording.
``probe-log`` / ``probe-list`` / ``probe-budget``
    Which of the team's oracle submissions has been spent, by whom, with what content and
    what reply.
"""

import argparse
import sys
from dataclasses import replace
from pathlib import Path

from . import cli_annotate, cli_it2, cli_ledger, cli_objects, cli_source, cli_vcf, reference
from . import postgres as pg
from .analysis import DERIVATIONS
from .catalog import discover
from .settings import Postgres, find_env
from .stage import stage as stage_profile

DEFAULT_PROFILE = Path("ressources/data-profile")
DEFAULT_REFERENCE = reference.DEFAULT_ROOT
DEFAULT_STAGE = Path("build/warehouse")


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    parser = _parser()
    args = parser.parse_args(argv)
    if not getattr(args, "handler", None):
        parser.print_help()
        return 1
    try:
        return args.handler(args)
    except RuntimeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def _do_stage(args) -> int:
    """Normalise the profile and reference directories into Parquet, and report."""
    datasets = discover(args.profile) + reference.datasets(args.reference)
    staged = stage_profile(args.profile, args.stagedir, datasets)
    print(
        f"staged {len(staged)} tables from {args.profile} and {args.reference} into {args.stagedir}"
    )
    width = max((len(s.table) for s in staged), default=0)
    for item in staged:
        size = item.parquet.stat().st_size
        print(
            f"  {item.table:<{width}}  {item.rows:>7,} rows  "
            f"{len(item.columns):>2} cols  {size:>8,} B"
        )
    total = sum(s.parquet.stat().st_size for s in staged)
    print(f"  {'total':<{width}}  {sum(s.rows for s in staged):>7,} rows{'':>10}{total:>10,} B")
    return 0


def _settings(args) -> Postgres:
    """Resolve connection settings, letting flags override the environment and .env."""
    settings = Postgres.from_env()
    overrides: dict[str, str] = {}
    for key in ("schema", "result_schema"):
        value = getattr(args, key, None)
        if value:
            overrides[key] = value
    return replace(settings, **overrides) if overrides else settings


def _do_pg_check(args) -> int:
    """Show where we would connect, then prove we can."""
    settings = _settings(args)
    env_path = find_env()
    print(f".env:     {env_path or 'not found — copy .env.example to .env'}")
    print(f"target:   {settings.describe()}")
    if settings.missing:
        print("\nmissing:  " + ", ".join(settings.missing))
        print("Fill these in .env, then run this again.")
        return 1
    info = pg.server_info(settings)
    print("\nconnected.")
    print(f"  server:  {info['version'].split(' on ')[0]}")
    print(f"  size:    {info['size']}")
    print(f"  schemas: {info['schemas']}")
    return 0


def _do_pg_ingest(args) -> int:
    """Load the staged Parquet into the hosted database."""
    settings = _settings(args)
    landed = pg.ingest(settings, args.stagedir, args.tables or None)
    print(
        f"ingested {len(landed)} tables into "
        f"{settings.host}/{settings.database}, schema {settings.schema}"
    )
    width = max((len(item.table) for item in landed), default=0)
    for item in landed:
        print(f"  {item.table:<{width}}  {item.rows:>7,} rows")
    edged = reference.record_lineage(settings, landed)
    if edged:
        print(f"\nlineage edges appended to {settings.schema}.data_lineage for " + ", ".join(edged))
    return 0


def _do_pg_derive(args) -> int:
    """Compute the analyses in DuckDB and write the results into Postgres."""
    settings = _settings(args)
    produced = pg.derive(settings, args.only or None)
    print(f"wrote {len(produced)} result tables into schema {settings.result_schema}")
    width = max((len(item.table) for item in produced), default=0)
    for item in produced:
        print(
            f"  {item.qualified:<{width + len(settings.result_schema) + 1}}  {item.rows:>5,} rows"
        )
    print(f"\nprovenance appended to {settings.result_schema}.derivation_runs")
    print(f"lineage edges appended to {settings.schema}.data_lineage")
    return 0


def _do_pg_load_it2(args) -> int:
    """Load iteration 2's step-1 target and decoy tables."""
    return cli_it2.load_it2_step1(args, _settings(args))


def _do_pg_load_it2_step2(args) -> int:
    """Load iteration 2's step-2 read-derived tables."""
    return cli_it2.load_it2_step2(args, _settings(args))


def _do_pg_load_it2_step3(args) -> int:
    """Load iteration 2's step-3 alignment-free genotype and copy-number tables."""
    return cli_it2.load_it2_step3(args, _settings(args))


def _do_pg_load_it2_step4(args) -> int:
    """Load iteration 2's step-4 likelihood-ratio ranking, P(trans) and null tables."""
    return cli_it2.load_it2_step4(args, _settings(args))


def _do_pg_load_it2_step5(args) -> int:
    """Load iteration 2's step-5 literature, anchor, protein and ranking tables."""
    return cli_it2.load_it2_step5(args, _settings(args))


def _do_pg_load_it2_step6(args) -> int:
    """Load iteration 2's step-6 fusion, leave-one-out and route-dependency tables."""
    return cli_it2.load_it2_step6(args, _settings(args))


def _do_pg_list(args) -> int:
    """List everything in both managed schemas."""
    settings = _settings(args)
    rows = pg.list_tables(settings)
    if not rows:
        print("no tables yet — run `pg-ingest` then `pg-derive`")
        return 0
    width = max(len(f"{schema}.{table}") for schema, table, _ in rows)
    for schema, table, count in rows:
        print(f"  {schema + '.' + table:<{width}}  {count:>9,} rows")
    return 0


def _do_pg_query(args) -> int:
    """Run one read-only statement against the hosted database."""
    print(pg.query(_settings(args), args.sql))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mva-warehouse",
        description="Stage a profile directory as Parquet, load it into hosted "
        "PostgreSQL, and manage the object store.",
    )
    subparsers = parser.add_subparsers()

    stage_parser = subparsers.add_parser(
        "stage", help="normalise a profile directory into typed Parquet"
    )
    stage_parser.add_argument(
        "--profile", type=Path, default=DEFAULT_PROFILE, help="directory of source tables to stage"
    )
    stage_parser.add_argument(
        "--reference",
        type=Path,
        default=DEFAULT_REFERENCE,
        help="directory of public reference tables to stage",
    )
    stage_parser.add_argument(
        "--stagedir", type=Path, default=DEFAULT_STAGE, help="where the staged Parquet lives"
    )
    stage_parser.set_defaults(handler=_do_stage)

    def add_pg(name: str, handler, help_text: str, *, staged: bool = False):
        sub = subparsers.add_parser(name, help=help_text)
        if staged:
            sub.add_argument(
                "--stagedir",
                type=Path,
                default=DEFAULT_STAGE,
                help="where the staged Parquet lives",
            )
        sub.add_argument("--schema", help="override PGSCHEMA (ingested source tables)")
        sub.add_argument(
            "--result-schema",
            dest="result_schema",
            help="override PGRESULTSCHEMA (derived outputs)",
        )
        sub.set_defaults(handler=handler)
        return sub

    add_pg("pg-check", _do_pg_check, "show the resolved settings and probe the server")
    ingest = add_pg(
        "pg-ingest", _do_pg_ingest, "load the staged Parquet into the hosted database", staged=True
    )
    ingest.add_argument(
        "--tables", nargs="*", help="only these tables (default: everything staged)"
    )
    derive = add_pg(
        "pg-derive", _do_pg_derive, "run the analyses and write results into the result schema"
    )
    derive.add_argument(
        "--only",
        nargs="*",
        choices=[item.name for item in DERIVATIONS],
        help="only these derivations (default: all)",
    )
    load_it2 = add_pg(
        "pg-load-it2",
        _do_pg_load_it2,
        "load iteration 2's step-1 target and decoy tables from a build directory",
    )
    load_it2.add_argument(
        "--out",
        type=Path,
        default=Path("build/it2/step-1"),
        help="the directory tools/build_it2_targets.py wrote",
    )

    load_step2 = add_pg(
        "pg-load-it2-step2",
        _do_pg_load_it2_step2,
        "load iteration 2's step-2 read-derived tables from a build directory",
    )
    load_step2.add_argument(
        "--out",
        type=Path,
        default=Path("build/it2/step-2"),
        help="the directory tools/export_it2_step2_tables.py wrote its tables under",
    )

    load_step3 = add_pg(
        "pg-load-it2-step3",
        _do_pg_load_it2_step3,
        "load iteration 2's step-3 k-mer genotype and copy-number tables",
    )
    load_step3.add_argument(
        "--out",
        type=Path,
        default=Path("build/it2/step-3"),
        help="the directory tools/export_it2_step3_tables.py wrote its tables under",
    )

    load_step4 = add_pg(
        "pg-load-it2-step4",
        _do_pg_load_it2_step4,
        "load iteration 2's step-4 likelihood-ratio ranking, P(trans) and null tables",
    )
    load_step4.add_argument(
        "--out",
        type=Path,
        default=Path("build/it2/step-4"),
        help="the directory tools/rank_it2_pairs.py wrote its tables under",
    )

    load_step5 = add_pg(
        "pg-load-it2-step5",
        _do_pg_load_it2_step5,
        "load iteration 2's step-5 literature, anchor, protein and ranking tables",
    )
    load_step5.add_argument(
        "--out",
        type=Path,
        default=Path("build/it2/step-5"),
        help="the directory the step-5 tools wrote their tables under",
    )

    load_step6 = add_pg(
        "pg-load-it2-step6",
        _do_pg_load_it2_step6,
        "load iteration 2's step-6 fusion, leave-one-out and route-dependency tables",
    )
    load_step6.add_argument(
        "--out",
        type=Path,
        default=Path("build/it2/step-6"),
        help="the directory tools/fuse_it2_routes.py wrote its tables under",
    )

    add_pg("pg-list", _do_pg_list, "list every table in both managed schemas")
    pgquery = add_pg(
        "pg-query", _do_pg_query, "run one read-only SQL statement against the hosted database"
    )
    pgquery.add_argument("sql", help="the statement to run")

    cli_vcf.register(subparsers)
    cli_annotate.register(subparsers)
    cli_objects.register(subparsers)
    cli_source.register(subparsers)
    cli_ledger.register(subparsers)

    return parser
