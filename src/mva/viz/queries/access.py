"""Running one statement and handing back JSON-safe rows.

The plumbing every query module in this package sits on: attach, execute, convert. It
knows nothing about the schema — which is why it is the one module here with no SQL of
its own.
"""

from datetime import date, datetime
from decimal import Decimal

from ...warehouse.postgres import attached
from ...warehouse.settings import Postgres

#: Canonical contigs are the ones whose name is at most two characters — 1..22, X, Y, M.
#: The same predicate is used by every derivation, so the API and the tables agree.
CANONICAL = "length(chrom) <= 2"


def jsonable(value):
    """One value in a shape ``json.dumps`` accepts."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", "replace")
    return value


def rows(connection, sql: str, params: list | None = None) -> list[dict]:
    """Run one statement on an open connection and return JSON-safe dicts."""
    cursor = connection.execute(sql, params or [])
    columns = [description[0] for description in cursor.description or ()]
    return [
        {column: jsonable(value) for column, value in zip(columns, row, strict=True)}
        for row in cursor.fetchall()
    ]


def fetch(settings: Postgres, sql: str, params: list | None = None) -> list[dict]:
    """Attach, run one read-only statement, detach."""
    with attached(settings, read_only=True) as connection:
        return rows(connection, sql, params)


def table(settings: Postgres, schema: str, name: str, order: str = "") -> list[dict]:
    """A whole (small) table, optionally ordered."""
    from ...warehouse.postgres import safe_identifier

    qualified = f"pg.{safe_identifier(schema)}.{safe_identifier(name)}"
    return fetch(settings, f"SELECT * FROM {qualified} {order}")
