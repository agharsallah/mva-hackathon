"""What every ``mva-science`` verb needs: the connection, and where the report goes.

Separate from the verbs so that the handler modules do not import each other, and so a
test replaces one thing — ``context.attached`` or ``context.settings`` — rather than one
per module.
"""

from ...warehouse.postgres import attached, render_table
from ...warehouse.settings import Postgres

__all__ = ["DEFAULT_REPORT", "attached", "render_table", "settings"]

#: Where ``report`` writes when no path is given.
DEFAULT_REPORT = "figures/science-report.html"


def settings() -> Postgres:
    """Resolved connection settings. Replaced wholesale in tests."""
    return Postgres.from_env()
