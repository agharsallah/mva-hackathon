"""The one shape a derivation has, and the placeholder that points it at a schema.

Split out of :mod:`mva.warehouse.analysis` so that a second registry module
(:mod:`mva.warehouse.analysis_reference`) can declare derivations without importing the
module that collects them — which would be a cycle. Nothing here knows what any
particular analysis does; it is the type plus one string substitution.
"""

from dataclasses import dataclass

#: Placeholder replaced with the fully-qualified ingest schema before execution.
SOURCE = "{src}"


@dataclass(frozen=True)
class Derivation:
    """One analysis: a name, what it answers, and the SELECT that answers it."""

    name: str
    question: str
    sql: str
    depends_on: tuple[str, ...] = ()


def resolve(sql: str, source_schema: str) -> str:
    """Point a derivation's SQL at a concrete schema."""
    return sql.replace(SOURCE, source_schema)
