"""Where a narrative is kept: ``<schema>.<prefix>_narratives``, append-only.

Split out of :mod:`mva.zoo.narrate` so that module stays about *writing* section 6 and this
one about *recording* it. The split is also what lets the writing half be imported — by a
test, by the API, by a second case — without a database driver anywhere in sight.

One row per (model, run, mode). A second mode's narrative is a new row beside the first, not
an update: that is what makes two modes comparable months later, and what lets the
hand-written version be measured by the same checker as the generated one.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

__all__ = [
    "LINEAGE_SCHEMA",
    "NARRATIVES_COLUMNS",
    "NARRATIVES_TABLE",
    "write_narratives",
]


#: ``<schema>.<prefix>_narratives`` — one row per (model, run, mode). Append-only: a second
#: mode's narrative is a new row beside the first, never an update, which is what makes the
#: two modes comparable after the fact. The name below is the *default* prefix; a run passes
#: its own through :meth:`mva.zoo.workflow_types.Config.table`.
NARRATIVES_TABLE = "it4_narratives"
NARRATIVES_COLUMNS: tuple[tuple[str, str], ...] = (
    ("model", "VARCHAR"),
    ("run_id", "VARCHAR"),
    ("mode", "VARCHAR"),
    ("llm_model_id", "VARCHAR"),
    ("prompt", "VARCHAR"),
    ("reply", "VARCHAR"),
    ("words", "INTEGER"),
    ("cited_sentences", "INTEGER"),
    ("uncited_sentences", "INTEGER"),
    ("created_at", "TIMESTAMP"),
)

#: Where the append-only lineage edge lands — the shared schema, not the result schema. The
#: same two-argument split :func:`mva.zoo.report.write_reports` explains.
LINEAGE_SCHEMA = "warehouse"


def write_narratives(
    connection: Any,
    schema: str,
    narratives: Sequence[Any],
    *,
    run_id: str = "",
    table: str = NARRATIVES_TABLE,
    source_ref: str = "results.it4_model_reports",
    lineage_schema: str = LINEAGE_SCHEMA,
) -> int:
    """Append this run's narratives and record one lineage edge. Returns the rows written.

    ``connection`` is a DuckDB connection with the warehouse attached (the argument, never a
    module-level handle — the same injection every writer in this package takes).
    ``narratives`` are :class:`mva.zoo.narrate.Narrative` objects, typed structurally rather
    than imported: this module must not import the module that imports it.
    """
    from ..warehouse.lineage import ensure_tables, record
    from ..warehouse.postgres import ALIAS, safe_identifier

    safe, safe_table = safe_identifier(schema), safe_identifier(table)
    columns = ", ".join(f"{name} {sql}" for name, sql in NARRATIVES_COLUMNS)
    connection.execute(f"CREATE TABLE IF NOT EXISTS {ALIAS}.{safe}.{safe_table} ({columns})")
    placeholders = ", ".join("?" for _ in NARRATIVES_COLUMNS)
    now = datetime.now(UTC)
    modes: list[str] = []
    for item in narratives:
        connection.execute(
            f"INSERT INTO {ALIAS}.{safe}.{safe_table} VALUES ({placeholders})",
            [
                item.model,
                item.run_id or run_id,
                item.mode,
                item.llm_model_id,
                item.prompt,
                item.reply,
                item.words,
                item.cited_sentences,
                item.uncited_sentences,
                now,
            ],
        )
        if item.mode not in modes:
            modes.append(item.mode)
    ensure_tables(connection, lineage_schema)
    record(
        connection,
        lineage_schema,
        target_schema=schema,
        target_table=table,
        target_rows=len(narratives),
        source_kind="table",
        source_ref=source_ref,
        source_version=run_id,
        transform=(
            "mva.zoo.narrate.narrate_report (sections 2-5 rows -> LLM interpretation, "
            "checked by mva.zoo.narrate_check)"
        ),
        tool="mva-zoo narrate",
        notes=f"{len(narratives)} narratives, modes: {', '.join(modes) or 'none'}",
    )
    return len(narratives)
