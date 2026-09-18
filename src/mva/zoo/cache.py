"""The score cache — ``warehouse.allele_scores``, append-only, a no-op on a repeat.

What this is, in software terms: a **feature store** (a table of pre-computed inputs that
several downstream jobs read instead of recomputing). One row = one model's verdict on one
allele. The **cache key** (the columns that decide whether a row already exists) is
``(model, version, allele_id)``; writing the same key twice inserts nothing, so re-running
``mva-zoo score`` after a crash costs only the models that had not finished — a **no-op
re-run**.

Three properties are load-bearing:

* **Append-only.** Nothing is ever updated or deleted. A corrected score is a *new version*
  of the model, never an edit, because a cache you can edit is not evidence.
* **The skip is a SQL anti-join, not a Python loop.** The incoming batch lands in a local
  temporary table and only the rows with no match in the target are inserted, so the cost
  is one round trip per batch rather than one per row.
* **Every write leaves a lineage edge.** :func:`lineage_row` appends one
  ``warehouse.data_lineage`` row per ``(model, version, run_id)`` — which table was written,
  from which source, by which transform.

Every function takes a ``connection`` (a DuckDB connection with PostgreSQL attached as
``pg``) rather than opening one, so tests can hand in an in-memory database and exercise the
real SQL.
"""

from __future__ import annotations

import json
import secrets
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .types import ALLELE_SCORES_COLUMNS, ALLELE_SCORES_TABLE, ScoreRow

__all__ = [
    "BATCH",
    "KEY_COLUMNS",
    "Written",
    "ensure_table",
    "lineage_row",
    "read",
    "run_id",
    "write",
]

#: The cache key: a row whose three key columns already exist is skipped, never rewritten.
KEY_COLUMNS: tuple[str, ...] = ("model", "version", "allele_id")

#: Rows per round trip. Large enough that ~40k alleles is a handful of statements, small
#: enough that one batch's temporary table stays in memory.
BATCH = 5_000

#: Name of the local staging table the anti-join reads. Temporary, so it never touches the
#: server and two runs in one process cannot collide with each other's leftovers.
_STAGING = "zoo_incoming"


@dataclass(frozen=True)
class Written:
    """The outcome of one :func:`write`: rows added, rows already present."""

    inserted: int
    skipped: int

    @property
    def offered(self) -> int:
        return self.inserted + self.skipped


def run_id() -> str:
    """A fresh run identifier: a UTC timestamp plus four random hex characters.

    Sortable by construction (the timestamp leads) and collision-free in practice (the
    suffix), so two runs started in the same second are still distinguishable.
    """
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{secrets.token_hex(2)}"


def _qualified(schema: str, table: str) -> str:
    from mva.warehouse.postgres import ALIAS, safe_identifier

    return f"{ALIAS}.{safe_identifier(schema)}.{safe_identifier(table)}"


def ensure_table(connection: Any, schema: str) -> None:
    """Create ``<schema>.allele_scores`` if it is not there, from the pinned column list.

    The DDL is generated from :data:`~mva.zoo.types.ALLELE_SCORES_COLUMNS` rather than
    written out here, so the table and the dataclass cannot drift apart.
    """
    columns = ", ".join(f"{name} {sql_type}" for name, sql_type in ALLELE_SCORES_COLUMNS)
    connection.execute(
        f"CREATE TABLE IF NOT EXISTS {_qualified(schema, ALLELE_SCORES_TABLE)} ({columns})"
    )


def write(
    connection: Any,
    schema: str,
    rows: Iterable[ScoreRow],
    *,
    run_id: str,
    batch: int = BATCH,
) -> Written:
    """Append every row whose ``(model, version, allele_id)`` is not cached yet.

    ``run_id`` is stamped onto every row as it lands, so the adapter that produced the rows
    does not need to know which run it belongs to. Duplicates *inside* one batch are
    collapsed before the insert (first one wins), which is what makes the function safe to
    hand a generator that yields the same allele twice.

    Returns the count inserted and the count skipped — the second number is the evidence
    that a re-run did nothing.
    """
    ensure_table(connection, schema)
    target = _qualified(schema, ALLELE_SCORES_TABLE)
    names = [name for name, _ in ALLELE_SCORES_COLUMNS]
    key_match = " AND ".join(f"t.{column} = s.{column}" for column in KEY_COLUMNS)
    key_list = ", ".join(KEY_COLUMNS)
    inserted = total = 0

    for chunk in _chunks(rows, max(1, batch)):
        total += len(chunk)
        _stage(connection, chunk, run_id=run_id)
        before = _count(connection, target)
        connection.execute(
            f"INSERT INTO {target} ({', '.join(names)}) "
            f"SELECT {', '.join(names)} FROM {_STAGING} s "
            f"WHERE NOT EXISTS (SELECT 1 FROM {target} t WHERE {key_match}) "
            f"QUALIFY row_number() OVER (PARTITION BY {key_list}) = 1"
        )
        inserted += _count(connection, target) - before
    connection.execute(f"DROP TABLE IF EXISTS {_STAGING}")
    return Written(inserted=inserted, skipped=total - inserted)


def _count(connection: Any, target: str) -> int:
    return int(connection.execute(f"SELECT count(*) FROM {target}").fetchone()[0])


def _chunks(rows: Iterable[ScoreRow], size: int) -> Iterable[list[ScoreRow]]:
    """Group an iterator of rows into lists of at most ``size``, lazily."""
    batch: list[ScoreRow] = []
    for row in rows:
        batch.append(row)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def _stage(connection: Any, chunk: Sequence[ScoreRow], *, run_id: str) -> None:
    """Materialise one batch as a local temporary table the anti-join can read."""
    columns = ", ".join(f"{name} {sql_type}" for name, sql_type in ALLELE_SCORES_COLUMNS)
    placeholders = ", ".join("?" for _ in ALLELE_SCORES_COLUMNS)
    connection.execute(f"CREATE OR REPLACE TEMP TABLE {_STAGING} ({columns})")
    stamp = datetime.now(UTC).replace(tzinfo=None)
    connection.executemany(
        f"INSERT INTO {_STAGING} VALUES ({placeholders})",
        [_values(row, run_id=run_id, stamp=stamp) for row in chunk],
    )


def _values(row: ScoreRow, *, run_id: str, stamp: datetime) -> list[Any]:
    return [
        row.allele_id,
        row.model,
        row.version,
        row.digest,
        row.score,
        json.dumps(row.aux, sort_keys=True, default=str),
        row.venue,
        row.licence,
        run_id,
        stamp,
    ]


def read(
    connection: Any,
    schema: str,
    *,
    model: str | None = None,
    allele_ids: Sequence[str] | None = None,
    batch: int = BATCH,
) -> list[ScoreRow]:
    """Read cached rows back, optionally narrowed to one model and/or a set of alleles.

    ``allele_ids`` is chunked the same way a write is, so asking for 40k alleles is a few
    statements rather than one SQL string megabytes long.
    """
    ensure_table(connection, schema)
    target = _qualified(schema, ALLELE_SCORES_TABLE)
    select = (
        "SELECT allele_id, model, version, score, aux, digest, venue, licence, run_id "
        f"FROM {target}"
    )
    if allele_ids is None:
        where = " WHERE model = ?" if model else ""
        params: list[Any] = [model] if model else []
        return _rows(connection.execute(select + where, params).fetchall())

    found: list[ScoreRow] = []
    for chunk in _id_chunks(list(allele_ids), max(1, batch)):
        marks = ", ".join("?" for _ in chunk)
        where = f" WHERE allele_id IN ({marks})" + (" AND model = ?" if model else "")
        args: list[Any] = [*chunk, model] if model else list(chunk)
        found.extend(_rows(connection.execute(select + where, args).fetchall()))
    return found


def _id_chunks(ids: list[str], size: int) -> Iterable[list[str]]:
    for start in range(0, len(ids), size):
        yield ids[start : start + size]


def _rows(raw: Sequence[Sequence[Any]]) -> list[ScoreRow]:
    return [
        ScoreRow(
            allele_id=str(row[0]),
            model=str(row[1]),
            version=str(row[2]),
            score=None if row[3] is None else float(row[3]),
            aux=_aux(row[4]),
            digest=str(row[5] or ""),
            venue=str(row[6] or ""),
            licence=str(row[7] or ""),
            run_id=str(row[8] or ""),
        )
        for row in raw
    ]


def _aux(value: Any) -> dict[str, Any]:
    """Parse the ``aux`` column, which is JSON text. An unreadable value is not fatal."""
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {"_unparsed": str(value)}
    return parsed if isinstance(parsed, dict) else {"value": parsed}


def lineage_row(
    connection: Any,
    schema: str,
    *,
    model: str,
    version: str,
    run_id: str,
    rows: int,
    digest: str = "",
    source_ref: str = "",
) -> None:
    """Append the ``data_lineage`` edge for one scoring run.

    The transform reads ``it4-score:<model>``, so a reader scanning the edge list sees at a
    glance which lane produced which rows, and ``notes`` carries the run id that ties the
    edge back to the cache rows it describes.
    """
    from mva.warehouse import lineage

    lineage.ensure_tables(connection, schema)
    lineage.record(
        connection,
        schema,
        target_schema=schema,
        target_table=ALLELE_SCORES_TABLE,
        target_rows=rows,
        source_kind="model",
        source_ref=source_ref or model,
        source_version=version,
        source_sha256=digest,
        transform=f"it4-score:{model}",
        tool="mva-zoo",
        notes=f"run_id={run_id}",
    )
