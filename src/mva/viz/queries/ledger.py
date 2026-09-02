"""The append-only ledgers: lineage, derivations, sources, probes.

Provenance rather than measurement — what ran, from which input, and how much of the
oracle budget is left. Small tables, read whole.
"""

from ...warehouse.settings import Postgres
from . import access


def lineage(settings: Postgres) -> list[dict]:
    return access.fetch(
        settings,
        """
        SELECT produced_at, target_schema, target_table, target_rows, source_kind,
               source_ref, source_version, source_sha256, transform, tool, notes
        FROM pg.warehouse.data_lineage ORDER BY produced_at DESC
    """,
    )


def derivations(settings: Postgres) -> list[dict]:
    return access.fetch(
        settings,
        "SELECT run_at, derivation, question, n_rows "
        "FROM pg.results.derivation_runs ORDER BY run_at DESC",
    )


def sources(settings: Postgres) -> list[dict]:
    return access.fetch(
        settings,
        """
        SELECT file_name, kind, role, size_bytes, hash_verified, sha256_source,
               version_id, lane, read_num
        FROM pg.warehouse.source_objects ORDER BY file_name
    """,
    )


def probe_ledger(settings: Postgres) -> list[dict]:
    return access.fetch(
        settings,
        """
        SELECT probe_id, logged_at, track, probe_type, payload, n_rows, response,
               score, rationale
        FROM pg.warehouse.probe_ledger ORDER BY probe_id
    """,
    )
