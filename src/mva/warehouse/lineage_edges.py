"""Where did this table come from: the append-only "what produced what" edge list.

Not "a VCF", but *which object, at which version, through which transformation, producing
how many rows*. :data:`LINEAGE_TABLE` is an edge list, appended to, never updated — a
correction is a newer row naming what it supersedes (:data:`SUPERSEDES`), because lineage
that can be edited is not evidence. This module writes edges (:func:`record`,
:func:`derivation_edge`), reads them back (:func:`edges`), and repairs or backfills the
ones automation did not produce yet (:func:`repoint`, :func:`backfill_derivations`), using
the verified inventory in :mod:`mva.warehouse.lineage_inventory` as the source of truth.
"""

from .lineage_inventory import OBJECTS_TABLE

#: Append-only record of which inputs produced which table.
LINEAGE_TABLE = "data_lineage"

#: Prefix written into ``notes`` when an edge replaces an earlier one for the same target.
#: The table is append-only, so a correction is a *newer row*, not an edit; this marker is
#: how a reader knows the older row was not simply a second, equally valid input.
SUPERSEDES = "supersedes the edge produced at "

#: Prefix tying a derivation edge back to its row in ``results.derivation_runs``.
RUN_REF = "derivation_runs.run_at="


def ensure_lineage_table(connection, schema: str) -> None:
    """Create the lineage edge list if absent."""
    from .postgres import ALIAS, safe_identifier

    safe = safe_identifier(schema)
    connection.execute(f"""
        CREATE TABLE IF NOT EXISTS {ALIAS}.{safe}.{LINEAGE_TABLE} (
            produced_at    TIMESTAMP,
            target_schema  VARCHAR,
            target_table   VARCHAR,
            target_rows    BIGINT,
            source_kind    VARCHAR,
            source_ref     VARCHAR,
            source_version VARCHAR,
            source_sha256  VARCHAR,
            transform      VARCHAR,
            tool           VARCHAR,
            notes          VARCHAR
        )""")


def record(
    connection,
    schema: str,
    *,
    target_schema: str,
    target_table: str,
    target_rows: int,
    source_kind: str,
    source_ref: str,
    source_version: str = "",
    source_sha256: str = "",
    transform: str = "",
    tool: str = "mva-warehouse",
    notes: str = "",
) -> None:
    """Append one lineage edge: this table came from that input, this way."""
    from .postgres import ALIAS, safe_identifier

    safe = safe_identifier(schema)
    connection.execute(
        f"INSERT INTO {ALIAS}.{safe}.{LINEAGE_TABLE} VALUES (now(), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            target_schema,
            target_table,
            target_rows,
            source_kind,
            source_ref,
            source_version,
            source_sha256,
            transform,
            tool,
            notes,
        ],
    )


def edges(connection, schema: str) -> list[tuple]:
    """Every lineage edge, newest first, with the marker column a reader needs.

    ``is_current`` is computed rather than stored: the latest edge for a target is the one
    that describes it now, and the older rows stay as the audit trail of how the claim
    changed. Storing a flag would mean updating a table whose whole value is that it is
    never updated.
    """
    from .postgres import ALIAS, safe_identifier

    safe = safe_identifier(schema)
    return connection.execute(f"""
        SELECT produced_at, target_schema, target_table, target_rows, source_kind,
               source_ref, source_version, source_sha256, tool, notes,
               produced_at = max(produced_at) OVER (
                   PARTITION BY target_schema, target_table) AS is_current
        FROM {ALIAS}.{safe}.{LINEAGE_TABLE}
        ORDER BY target_schema, target_table, produced_at DESC""").fetchall()


def _fetch(connection, schema: str, sql: str, params: list | None = None) -> list[tuple]:
    from .postgres import ALIAS, safe_identifier

    return connection.execute(
        sql.format(t=f"{ALIAS}.{safe_identifier(schema)}"), params or []
    ).fetchall()


def repoint(connection, schema: str, bucket: str) -> list[dict]:
    """Append a superseding edge for every input recorded as a local path.

    An edge written before the bytes reached the object store names a file on somebody's
    laptop — unreachable, unversioned, unhashed. The verified truth is in
    :data:`~mva.warehouse.lineage_inventory.OBJECTS_TABLE`, so the fix is to look the
    object up **by file name** and append an edge naming ``s3://bucket/key`` plus the hash
    and version the inventory verified.

    Case-agnostic on purpose: it repairs whatever local-path edges exist, matching on the
    name, rather than knowing anything about this delivery's callset.
    """
    stale = _fetch(
        connection,
        schema,
        """
        SELECT produced_at, target_schema, target_table, target_rows, source_ref,
               transform, tool, notes
        FROM {t}."""
        + LINEAGE_TABLE
        + """
        WHERE source_ref NOT LIKE 's3://%'""",
    )
    done = {
        (row[0], row[1])
        for row in _fetch(
            connection,
            schema,
            """
        SELECT target_schema, target_table FROM {t}."""
            + LINEAGE_TABLE
            + """
        WHERE source_ref LIKE 's3://%'""",
        )
    }
    objects = {
        row[0]: row
        for row in _fetch(
            connection,
            schema,
            """
        SELECT file_name, object_key, sha256, version_id, hash_verified
        FROM {t}."""
            + OBJECTS_TABLE,
        )
    }

    appended: list[dict] = []
    for produced_at, tschema, table, rows, ref, transform, tool, notes in stale:
        if (tschema, table) in done:
            continue
        found = objects.get(ref.split("/")[-1])
        if not found:
            continue
        _, key, sha, version, verified = found
        note = (
            f"{SUPERSEDES}{produced_at:%Y-%m-%d %H:%M:%S}; the same bytes, now named "
            f"by their object-store location, publisher-verified hash and version. "
            f"hash_verified={bool(verified)}. {notes}"
        ).strip()
        record(
            connection,
            schema,
            target_schema=tschema,
            target_table=table,
            target_rows=rows,
            source_kind="object",
            source_ref=f"s3://{bucket}/{key}",
            source_version=version or "",
            source_sha256=sha or "",
            transform=transform,
            tool=tool,
            notes=note,
        )
        appended.append(
            {
                "target": f"{tschema}.{table}",
                "was": ref,
                "now": f"s3://{bucket}/{key}",
                "sha256": sha,
                "version_id": version,
            }
        )
    return appended


def derivation_edge(
    connection, schema: str, *, result_schema: str, derivation, target_rows: int, run_ref: str
) -> None:
    """Append the edge for one derivation: which ingest tables produced which result.

    The inputs are read off the derivation's declared ``depends_on`` rather than parsed out
    of its SQL, so the edge and the statement cannot drift apart — a test already asserts
    every declared dependency is actually selected from.
    """
    sources = ", ".join(f"{schema}.{table}" for table in derivation.depends_on)
    record(
        connection,
        schema,
        target_schema=result_schema,
        target_table=derivation.name,
        target_rows=target_rows,
        source_kind="table",
        source_ref=sources,
        transform=f"SQL derivation {derivation.name}: {derivation.question}",
        tool="mva-warehouse pg-derive",
        notes=f"{RUN_REF}{run_ref}",
    )


def backfill_derivations(connection, schema: str, result_schema: str) -> list[dict]:
    """Give every logged derivation run an edge, skipping runs that already have one.

    ``pg-derive`` records its own edge from now on. This exists for the runs that happened
    before it did — and, being idempotent, is safe to re-run afterwards.
    """
    from .analysis import DERIVATIONS, PROVENANCE_TABLE

    runs = _fetch(
        connection,
        result_schema,
        """
        SELECT derivation, max(run_at), max_by(n_rows, run_at)
        FROM {t}."""
        + PROVENANCE_TABLE
        + " GROUP BY derivation",
    )
    have = {
        (row[0], row[1])
        for row in _fetch(
            connection,
            schema,
            """
        SELECT target_table, notes FROM {t}."""
            + LINEAGE_TABLE
            + """
        WHERE source_kind = 'table'""",
        )
    }
    known = {item.name: item for item in DERIVATIONS}

    appended: list[dict] = []
    for name, run_at, rows in runs:
        derivation = known.get(name)
        run_ref = f"{run_at:%Y-%m-%d %H:%M:%S.%f}"
        if derivation is None or (name, f"{RUN_REF}{run_ref}") in have:
            continue
        derivation_edge(
            connection,
            schema,
            result_schema=result_schema,
            derivation=derivation,
            target_rows=rows,
            run_ref=run_ref,
        )
        appended.append(
            {
                "target": f"{result_schema}.{name}",
                "rows": rows,
                "sources": ", ".join(derivation.depends_on),
                "run": run_ref,
            }
        )
    return appended
