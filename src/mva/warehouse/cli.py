"""Command line for the warehouse.

Seven verbs, arranged so each one can be run and inspected on its own before the next is
attempted. The happy path is ``preflight`` → ``ship``; the five verbs in between exist so
that when something goes wrong you are debugging one step, not a pipeline.

``preflight``
    Ask the remote box what it has. Read-only, uploads nothing, changes nothing.
``stage``
    Normalise a profile directory into typed Parquet locally. No network at all.
``local``
    Build the DuckDB file on this machine from the staged Parquet — the rehearsal, so the
    schema is known good before a byte is shipped.
``provision``
    Install the pinned DuckDB binary on the remote box. Idempotent.
``push``
    ``rsync`` the staged Parquet up.
``load``
    Rebuild every remote table from the Parquet that was pushed.
``ship``
    ``stage`` + ``provision`` + ``push`` + ``load`` in order.
``query``
    Run one read-only SQL statement against the remote warehouse.

A second family of verbs targets a **hosted PostgreSQL** instead of a file on a box, for
the shared, concurrently-written case the file design cannot serve. They read connection
settings from ``.env`` and connect over the network, so they need nothing installed on the
server beyond the PostgreSQL already there.

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

A fourth family targets the **object store** — the large immutable files kept on the
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

``--dry-run`` is accepted by every verb that touches the network and prints the exact
commands instead of running them.
"""

import argparse
import os
import sys
from dataclasses import replace
from pathlib import Path

from . import cli_objects
from . import cli_vcf
from . import postgres as pg
from .analysis import DERIVATIONS
from .catalog import discover
from .remote import (Remote, load_command, load_sql, preflight_script, provision_script,
                     query_command, run)
from .settings import Postgres, find_env
from .stage import stage as stage_profile

#: Read when ``--host`` is not given, so day-to-day use is a bare verb.
HOST_ENV = "MVA_WAREHOUSE_HOST"

DEFAULT_PROFILE = Path("ressources/data-profile")
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


def _remote(args) -> Remote:
    """Build the remote description, failing loudly when no host is known."""
    host = args.host or os.environ.get(HOST_ENV)
    if not host:
        raise RuntimeError(
            f"no remote host: pass --host user@box or set {HOST_ENV}")
    return Remote(host=host, root=args.root, database=args.database)


def _do_stage(args) -> int:
    """Normalise the profile directory into Parquet and report what was written."""
    datasets = discover(args.profile)
    staged = stage_profile(args.profile, args.stagedir, datasets)
    print(f"staged {len(staged)} tables from {args.profile} into {args.stagedir}")
    width = max((len(s.table) for s in staged), default=0)
    for item in staged:
        size = item.parquet.stat().st_size
        print(f"  {item.table:<{width}}  {item.rows:>7,} rows  "
              f"{len(item.columns):>2} cols  {size:>8,} B")
    total = sum(s.parquet.stat().st_size for s in staged)
    print(f"  {'total':<{width}}  {sum(s.rows for s in staged):>7,} rows"
          f"{'':>10}{total:>10,} B")
    return 0


def _do_local(args) -> int:
    """Build a DuckDB file on this machine from the staged Parquet."""
    import duckdb

    tables = _staged_tables(args.stagedir)
    if not tables:
        raise RuntimeError(f"no Parquet in {args.stagedir}; run `stage` first")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(args.output)) as connection:
        for table in tables:
            connection.execute(
                f"CREATE OR REPLACE TABLE {table} AS "
                f"SELECT * FROM read_parquet('{args.stagedir / (table + '.parquet')}')")
        rows = connection.execute(
            "SELECT table_name, estimated_size FROM duckdb_tables() ORDER BY table_name"
        ).fetchall()
    print(f"built {args.output} with {len(rows)} tables")
    for name, size in rows:
        print(f"  {name:<28} {size:>9,} rows")
    return 0


def _do_preflight(args) -> int:
    """Report what the remote box has, without changing it."""
    remote = _remote(args)
    print(f"preflight against {remote.host}")
    return run(remote.ssh_command(preflight_script(remote)), args.dry_run)


def _do_provision(args) -> int:
    """Install the pinned DuckDB binary on the remote box."""
    remote = _remote(args)
    print(f"provisioning duckdb on {remote.host}")
    return run(remote.ssh_command(provision_script(remote)), args.dry_run)


def _do_push(args) -> int:
    """Mirror the staged Parquet onto the remote box."""
    remote = _remote(args)
    if not args.dry_run and not args.stagedir.is_dir():
        raise RuntimeError(f"nothing staged at {args.stagedir}; run `stage` first")
    print(f"pushing {args.stagedir} to {remote.host}:{remote.parquet_dir}")
    run(remote.ssh_command(f"mkdir -p {remote.parquet_dir}"), args.dry_run)
    return run(remote.rsync_command(args.stagedir), args.dry_run)


def _do_load(args) -> int:
    """Rebuild every remote table from the Parquet already pushed."""
    remote = _remote(args)
    tables = _staged_tables(args.stagedir)
    if not tables:
        raise RuntimeError(f"no Parquet in {args.stagedir}; run `stage` first")
    print(f"loading {len(tables)} tables into {remote.host}:{remote.database_path}")
    return run(load_command(remote, load_sql(tables, remote)), args.dry_run)


def _do_ship(args) -> int:
    """Stage, provision, push and load, stopping at the first failure."""
    for step in (_do_stage, _do_provision, _do_push, _do_load):
        code = step(args)
        if code != 0:
            return code
    remote = _remote(args)
    print(f"\ndone. query it with:\n"
          f"  mva-warehouse query --host {remote.host} "
          f"'SELECT * FROM warehouse_catalog'")
    return 0


def _do_query(args) -> int:
    """Run one read-only statement against the remote warehouse."""
    remote = _remote(args)
    return run(query_command(remote, args.sql), args.dry_run)


def _settings(args) -> Postgres:
    """Resolve connection settings, letting flags override the environment and .env."""
    settings = Postgres.from_env()
    overrides = {key: getattr(args, key, None)
                 for key in ("schema", "result_schema") if getattr(args, key, None)}
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
    print(f"\nconnected.")
    print(f"  server:  {info['version'].split(' on ')[0]}")
    print(f"  size:    {info['size']}")
    print(f"  schemas: {info['schemas']}")
    return 0


def _do_pg_ingest(args) -> int:
    """Load the staged Parquet into the hosted database."""
    settings = _settings(args)
    landed = pg.ingest(settings, args.stagedir, args.tables or None)
    print(f"ingested {len(landed)} tables into "
          f"{settings.host}/{settings.database}, schema {settings.schema}")
    width = max((len(item.table) for item in landed), default=0)
    for item in landed:
        print(f"  {item.table:<{width}}  {item.rows:>7,} rows")
    return 0


def _do_pg_derive(args) -> int:
    """Compute the analyses in DuckDB and write the results into Postgres."""
    settings = _settings(args)
    produced = pg.derive(settings, args.only or None)
    print(f"wrote {len(produced)} result tables into schema {settings.result_schema}")
    width = max((len(item.table) for item in produced), default=0)
    for item in produced:
        print(f"  {item.qualified:<{width + len(settings.result_schema) + 1}}"
              f"  {item.rows:>5,} rows")
    print("\nprovenance appended to "
          f"{settings.result_schema}.derivation_runs")
    return 0


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


def _staged_tables(stagedir: Path) -> list[str]:
    """Table names implied by the Parquet files currently in the staging directory."""
    if not stagedir.is_dir():
        return []
    return sorted(path.stem for path in stagedir.glob("*.parquet"))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mva-warehouse",
        description="Stage a profile directory as Parquet and load it into DuckDB "
                    "on a remote box reached over SSH.",
    )
    subparsers = parser.add_subparsers()

    def add(name: str, handler, help_text: str, *, remote: bool = True,
            staged: bool = True, profile: bool = False):
        sub = subparsers.add_parser(name, help=help_text)
        if profile:
            sub.add_argument("--profile", type=Path, default=DEFAULT_PROFILE,
                             help="directory of source tables to stage")
        if staged:
            sub.add_argument("--stagedir", type=Path, default=DEFAULT_STAGE,
                             help="where the staged Parquet lives")
        if remote:
            sub.add_argument("--host", help=f"ssh target; defaults to ${HOST_ENV}")
            sub.add_argument("--root", default="~/warehouse",
                             help="remote directory holding the Parquet and the database")
            sub.add_argument("--database", default="profile.duckdb",
                             help="remote database filename")
            sub.add_argument("-n", "--dry-run", action="store_true",
                             help="print the commands instead of running them")
        sub.set_defaults(handler=handler)
        return sub

    add("preflight", _do_preflight, "report what the remote box has, changing nothing",
        staged=False)
    add("stage", _do_stage, "normalise a profile directory into typed Parquet",
        remote=False, profile=True)
    local = add("local", _do_local, "build the DuckDB file on this machine", remote=False)
    local.add_argument("-o", "--output", type=Path,
                       default=DEFAULT_STAGE / "profile.duckdb",
                       help="where to write the local database")
    add("provision", _do_provision, "install the pinned duckdb binary on the remote box",
        staged=False)
    add("push", _do_push, "rsync the staged Parquet to the remote box")
    add("load", _do_load, "rebuild the remote tables from the pushed Parquet")
    add("ship", _do_ship, "stage, provision, push and load in one go", profile=True)
    query = add("query", _do_query, "run one read-only SQL statement remotely", staged=False)
    query.add_argument("sql", help="the statement to run")

    def add_pg(name: str, handler, help_text: str, *, staged: bool = False):
        sub = subparsers.add_parser(name, help=help_text)
        if staged:
            sub.add_argument("--stagedir", type=Path, default=DEFAULT_STAGE,
                             help="where the staged Parquet lives")
        sub.add_argument("--schema", help="override PGSCHEMA (ingested source tables)")
        sub.add_argument("--result-schema", dest="result_schema",
                         help="override PGRESULTSCHEMA (derived outputs)")
        sub.set_defaults(handler=handler)
        return sub

    add_pg("pg-check", _do_pg_check, "show the resolved settings and probe the server")
    ingest = add_pg("pg-ingest", _do_pg_ingest,
                    "load the staged Parquet into the hosted database", staged=True)
    ingest.add_argument("--tables", nargs="*",
                        help="only these tables (default: everything staged)")
    derive = add_pg("pg-derive", _do_pg_derive,
                    "run the analyses and write results into the result schema")
    derive.add_argument("--only", nargs="*",
                        choices=[item.name for item in DERIVATIONS],
                        help="only these derivations (default: all)")
    add_pg("pg-list", _do_pg_list, "list every table in both managed schemas")
    pgquery = add_pg("pg-query", _do_pg_query,
                     "run one read-only SQL statement against the hosted database")
    pgquery.add_argument("sql", help="the statement to run")

    cli_vcf.register(subparsers)
    cli_objects.register(subparsers)

    return parser
