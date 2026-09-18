"""Every result-schema table that arrives by a loader rather than by SQL.

A derivation may read a table only if something produces it. Two things do: another
derivation, declared earlier in :data:`mva.warehouse.analysis.DERIVATIONS`, or one of the
``pg-load-*`` verbs, which land rows a non-SQL pipeline computed. This module is the single
list of the second kind, so the check that nothing reads an unproduced table has one place
to look instead of a hand-kept copy in each test that wants it.
"""

from __future__ import annotations

from . import it2_step2_tables, it2_step3_tables, it2_step4_tables, it2_tables

__all__ = ["LOADED_TABLES"]

#: Result-schema tables written by a loader, not by a derivation.
LOADED_TABLES: frozenset[str] = frozenset(
    set(it2_step2_tables.SCHEMAS)
    | set(it2_step3_tables.SCHEMAS)
    | set(it2_step4_tables.SCHEMAS)
    | {it2_tables.TARGETS_TABLE, it2_tables.DECOYS_TABLE}
)
