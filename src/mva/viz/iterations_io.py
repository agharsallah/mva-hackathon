"""Two facts a catalogue needs beyond the entries: which tables exist, which files are tracked.

Split from :mod:`mva.viz.iterations` so :mod:`mva.viz.submissions` can read them too
without importing the overview route that itself imports the submissions payload.
Both degrade instead of failing: a checkout with no database knows no tables, a checkout
with no git falls back to "``build/`` is not committed".
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..warehouse.postgres import ALIAS
from ..warehouse.settings import Postgres
from .queries import access

#: Schemas whose tables a catalogue may name.
CATALOGUED_SCHEMAS = ("results", "track2", "warehouse")

#: The data roots whose tracked files matter to a catalogue.
DATA_ROOTS = ("ressources", "data")

TABLES_SQL = (
    f"SELECT table_schema, table_name FROM {ALIAS}.information_schema.tables "
    f"WHERE table_schema IN ({', '.join('?' for _ in CATALOGUED_SCHEMAS)})"
)


def known_tables(settings: Postgres) -> set[str]:
    """Every ``schema.table`` the database holds, or an empty set when it cannot be read.

    Broad ``except`` for the reason :func:`mva.viz.submissions_lineage.read_ledger` gives:
    an unreachable warehouse surfaces as unrelated exception classes, and the contract is
    the same for all of them — the catalogue still renders, it knows fewer tables.
    """
    try:
        found = access.fetch(settings, TABLES_SQL, list(CATALOGUED_SCHEMAS))
    except Exception:
        return set()
    return {f"{row['table_schema']}.{row['table_name']}" for row in found}


def tracked_files(root: Path) -> set[str] | None:
    """``git ls-files`` under the data roots; ``None`` where git is not available."""
    try:
        done = subprocess.run(
            ["git", "ls-files", *DATA_ROOTS],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
            cwd=root,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return set(done.stdout.splitlines()) if done.returncode == 0 else None
