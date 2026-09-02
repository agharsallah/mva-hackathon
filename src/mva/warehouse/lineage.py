"""What each table was made from, and what each source object actually is.

The upload ledger in :mod:`mva.warehouse.source` answers "what did we put in the bucket,
and when". That is necessary but not sufficient. Two further questions get asked the moment
a result is disputed, and neither can be answered after the fact from memory:

* **What is this object?** A filename encodes lane, read number and flowcell, and those
  facts get re-parsed ad hoc in a dozen places unless they are extracted once. That is what
  :func:`enrich` does, in :mod:`mva.warehouse.lineage_naming` — it reads the delivery's
  naming convention into columns. :mod:`mva.warehouse.lineage_inventory` uses it to build
  the object inventory (:data:`~mva.warehouse.lineage_inventory.OBJECTS_TABLE`).
* **Where did this table come from?** Not "a VCF", but *which object, at which version,
  through which transformation, producing how many rows*. That is
  :data:`~mva.warehouse.lineage_edges.LINEAGE_TABLE`, an append-only edge list built in
  :mod:`mva.warehouse.lineage_edges`. A derived table with no lineage row is, by
  construction, a table nobody can vouch for.

Both tables are rebuilt or appended, never updated in place. Lineage that can be edited is
not evidence.

This module is the public entry point: it re-exports the naming, inventory and edge-list
pieces so every caller writes ``from .lineage import ...`` (or ``lineage.enrich(...)``)
without knowing they live in three files.
"""

from .lineage_edges import (
    LINEAGE_TABLE,
    RUN_REF,
    SUPERSEDES,
    backfill_derivations,
    derivation_edge,
    edges,
    ensure_lineage_table,
    record,
    repoint,
)
from .lineage_inventory import OBJECTS_TABLE, ensure_objects_table, replace_objects, survey
from .lineage_naming import Enriched, enrich

__all__ = [
    "LINEAGE_TABLE",
    "OBJECTS_TABLE",
    "RUN_REF",
    "SUPERSEDES",
    "Enriched",
    "backfill_derivations",
    "derivation_edge",
    "edges",
    "enrich",
    "ensure_tables",
    "record",
    "replace_objects",
    "repoint",
    "survey",
]


def ensure_tables(connection, schema: str) -> None:
    """Create the object inventory and the lineage edge list if absent."""
    ensure_objects_table(connection, schema)
    ensure_lineage_table(connection, schema)
