"""Ingest staged Parquet into a hosted PostgreSQL, using DuckDB as the engine.

The division of labour is the one measured in ``methodology/009``: PostgreSQL holds what
*changes* and what several people read at once; Parquet holds the big immutable tables;
DuckDB is the engine that reads both and writes results back. Nothing here loads a Postgres
driver — DuckDB's ``postgres`` extension does the talking, which means one engine, one SQL
dialect, and no second connection library to keep in step.

Everything runs from the client. DuckDB attaches to the server over the network, so an
ingest needs credentials in ``.env`` and nothing installed on the box beyond the PostgreSQL
that is already there.

Table names are validated rather than escaped. They come from filenames on disk, so they
are attacker-influenced in principle; :func:`safe_identifier` rejects anything that is not
already a plain identifier instead of trying to quote its way out of trouble.
"""

import re
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path

from .settings import Postgres

#: A SQL identifier we are willing to interpolate: letters, digits, underscore, no leading
#: digit. Staging already produces names of this shape, so a violation means something
#: unexpected reached us and should stop the run.
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

#: Alias the remote database is attached under inside DuckDB.
ALIAS = "pg"


class InvalidIdentifierError(ValueError):
    """Raised when a table or schema name is not a plain SQL identifier."""


def safe_identifier(name: str) -> str:
    """Return ``name`` if it is a plain SQL identifier, else raise.

    Rejecting is deliberate. These names are derived from filenames, and a name needing
    quotes to be safe is a name that should never have reached the database.
    """
    if not IDENTIFIER.match(name or ""):
        raise InvalidIdentifierError(f"not a usable SQL identifier: {name!r}")
    return name


@dataclass(frozen=True)
class Ingested:
    """One table after it landed in Postgres."""

    table: str
    rows: int
    schema: str

    @property
    def qualified(self) -> str:
        return f"{self.schema}.{self.table}"


@contextmanager
def attached(settings: Postgres, read_only: bool = False):
    """Yield a DuckDB connection with the hosted Postgres attached as :data:`ALIAS`.

    The connection itself is in-memory: DuckDB is acting purely as an engine here, so there
    is no local database file to lock, and therefore none of the single-writer problem that
    makes a shared ``.duckdb`` file unworkable in the first place.
    """
    import duckdb

    if settings.missing:
        raise RuntimeError(
            "missing settings: "
            + ", ".join(settings.missing)
            + " — add them to .env (see .env.example)"
        )

    connection = duckdb.connect()
    try:
        connection.execute("INSTALL postgres; LOAD postgres;")
        suffix = ", READ_ONLY" if read_only else ""
        connection.execute(f"ATTACH '{settings.dsn()}' AS {ALIAS} (TYPE postgres{suffix})")
        yield connection
    finally:
        connection.close()


def server_info(settings: Postgres) -> dict[str, str]:
    """Connect and report what the server is. Used by ``pg-check`` as a live probe."""
    with attached(settings, read_only=True) as connection:
        version = connection.execute(
            f"SELECT version FROM postgres_query('{ALIAS}', 'SELECT version() AS version')"
        ).fetchone()
        size = connection.execute(
            f"SELECT s FROM postgres_query('{ALIAS}', "
            f"'SELECT pg_size_pretty(pg_database_size(current_database())) AS s')"
        ).fetchone()
        schemas = connection.execute(
            f"SELECT nspname FROM postgres_query('{ALIAS}', "
            f"'SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE ''pg_%'' "
            f"AND nspname <> ''information_schema'' ORDER BY nspname')"
        ).fetchall()
    return {
        "version": (version or ["unknown"])[0],
        "size": (size or ["unknown"])[0],
        "schemas": ", ".join(row[0] for row in schemas) or "(none)",
    }


def ensure_schemas(connection, settings: Postgres) -> None:
    """Create the ingest and result schemas if the server does not already have them."""
    for schema in (settings.schema, settings.result_schema):
        connection.execute(f"CREATE SCHEMA IF NOT EXISTS {ALIAS}.{safe_identifier(schema)}")


def ingest(settings: Postgres, stagedir: Path, tables: list[str] | None = None) -> list[Ingested]:
    """Load every staged Parquet file into the ingest schema, replacing what is there.

    ``CREATE OR REPLACE`` keeps the ingest schema a pure function of the Parquet beside it,
    exactly as the file-based warehouse is. Results live in a *separate* schema precisely so
    that this wholesale replacement never destroys a derived table.
    """
    paths = sorted(stagedir.glob("*.parquet"))
    if tables is not None:
        wanted = set(tables)
        paths = [path for path in paths if path.stem in wanted]
    if not paths:
        raise RuntimeError(f"no Parquet in {stagedir}; run `mva-warehouse stage` first")

    landed: list[Ingested] = []
    with attached(settings) as connection:
        ensure_schemas(connection, settings)
        schema = safe_identifier(settings.schema)
        for path in paths:
            table = safe_identifier(path.stem)
            connection.execute(
                f"CREATE OR REPLACE TABLE {ALIAS}.{schema}.{table} AS "
                f"SELECT * FROM read_parquet(?)",
                [str(path)],
            )
            count = connection.execute(f"SELECT count(*) FROM {ALIAS}.{schema}.{table}").fetchone()[
                0
            ]
            landed.append(Ingested(table, count, schema))
    return landed


def list_tables(settings: Postgres) -> list[tuple[str, str, int]]:
    """Every table in both managed schemas, as ``(schema, table, rows)``."""
    with attached(settings, read_only=True) as connection:
        rows = []
        for schema in (settings.schema, settings.result_schema):
            safe = safe_identifier(schema)
            names = connection.execute(
                f"SELECT table_name FROM {ALIAS}.information_schema.tables "
                f"WHERE table_schema = ? ORDER BY table_name",
                [safe],
            ).fetchall()
            for (name,) in names:
                count = connection.execute(
                    f"SELECT count(*) FROM {ALIAS}.{safe}.{safe_identifier(name)}"
                ).fetchone()[0]
                rows.append((safe, name, count))
    return rows


@dataclass(frozen=True)
class Result:
    """A materialised query result.

    Materialised on purpose. DuckDB's ``sql()`` hands back a *lazy* relation that is only
    evaluated when consumed, so returning one from inside the ``attached`` block yields an
    object whose connection is already closed by the time anything reads it. Fetching here
    makes the result independent of the connection that produced it.
    """

    columns: tuple[str, ...]
    rows: list[tuple]

    def __str__(self) -> str:
        return render_table(self.columns, self.rows)


def render_table(columns: tuple[str, ...], rows: list[tuple]) -> str:
    """Render rows as a bordered table, in DuckDB's own box style."""
    if not columns:
        return "(no columns)"
    cells = [[("NULL" if value is None else str(value)) for value in row] for row in rows]
    widths = [
        max(len(str(columns[i])), *(len(row[i]) for row in cells))
        if cells
        else len(str(columns[i]))
        for i in range(len(columns))
    ]

    def line(left: str, mid: str, right: str) -> str:
        return left + mid.join("─" * (w + 2) for w in widths) + right

    def fmt(values) -> str:
        paired = zip(values, widths, strict=True)
        return "│ " + " │ ".join(str(value).ljust(width) for value, width in paired) + " │"

    out = [line("┌", "┬", "┐"), fmt(columns), line("├", "┼", "┤")]
    out += [fmt(row) for row in cells]
    out.append(line("└", "┴", "┘"))
    out.append(f"({len(rows)} row{'s' if len(rows) != 1 else ''})")
    return "\n".join(out)


def query(settings: Postgres, sql: str) -> Result:
    """Run one read-only statement with the hosted database attached."""
    with attached(settings, read_only=True) as connection:
        relation = connection.sql(sql)
        if relation is None:
            return Result((), [])
        return Result(tuple(relation.columns), relation.fetchall())


def derive(settings: Postgres, names: list[str] | None = None) -> list[Ingested]:
    """Run the derivations and write each result into the result schema.

    DuckDB does the computation — joins, windows, aggregates — reading the ingested tables
    over the attached connection; only the finished table is written back. Each run also
    stamps :data:`~mva.warehouse.analysis.PROVENANCE_TABLE` so a result sitting in the
    database can be traced to when it was produced and by which statement.
    """
    from datetime import datetime

    from . import lineage
    from .analysis import DERIVATIONS, PROVENANCE_TABLE, by_name, resolve

    chosen = [by_name(name) for name in names] if names else list(DERIVATIONS)
    produced: list[Ingested] = []
    # One timestamp for the whole run, so the provenance stamp and the lineage edge that
    # references it name the *same* instant. Per-statement ``now()`` would not.
    run_at = datetime.now(UTC).replace(tzinfo=None)

    with attached(settings) as connection:
        ensure_schemas(connection, settings)
        lineage.ensure_tables(connection, settings.schema)
        source = f"{ALIAS}.{safe_identifier(settings.schema)}"
        target = safe_identifier(settings.result_schema)
        stamps: list[tuple[str, str, int]] = []

        for derivation in chosen:
            table = safe_identifier(derivation.name)
            body = resolve(derivation.sql, source, f"{ALIAS}.{target}").strip()
            connection.execute(f"CREATE OR REPLACE TABLE {ALIAS}.{target}.{table} AS {body}")
            count = connection.execute(f"SELECT count(*) FROM {ALIAS}.{target}.{table}").fetchone()[
                0
            ]
            produced.append(Ingested(table, count, target))
            stamps.append((derivation.name, derivation.question, count))
            # Recorded here rather than by a separate verb: a result whose lineage is a
            # second command someone has to remember is a result that will lack lineage.
            lineage.derivation_edge(
                connection,
                settings.schema,
                result_schema=target,
                derivation=derivation,
                target_rows=count,
                run_ref=f"{run_at:%Y-%m-%d %H:%M:%S.%f}",
            )

        _stamp_provenance(connection, target, stamps, PROVENANCE_TABLE, run_at)
    return produced


def _stamp_provenance(
    connection, schema: str, stamps: list[tuple[str, str, int]], table: str, run_at
) -> None:
    """Record what was derived, when, and how many rows it produced.

    Appended rather than replaced: the point is the history. Someone asking "which run
    produced this table?" needs the previous answers to still be there.
    """
    qualified = f"{ALIAS}.{schema}.{safe_identifier(table)}"
    connection.execute(
        f"CREATE TABLE IF NOT EXISTS {qualified} ("
        "  run_at TIMESTAMP, derivation VARCHAR, question VARCHAR, n_rows BIGINT)"
    )
    for name, question, count in stamps:
        connection.execute(
            f"INSERT INTO {qualified} VALUES (?, ?, ?, ?)", [run_at, name, question, count]
        )
