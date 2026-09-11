"""The research register as JSON: the hypotheses, the evidence, and the empty case.

Two endpoints, and one design problem the rest of the API does not have: **the tables may
not exist yet.** ``warehouse.hypotheses`` and ``warehouse.evidence`` are created on first
write by ``mva-science``, exactly like every other ledger in this repository. Today no
hypothesis has been proposed, so nothing has written them, so they are absent from the
database — and an absent register is the honest state of a project that has not made a
claim yet, not a fault to paper over.

So both endpoints answer with an object rather than a bare list::

    {"table_exists": false, "rows": []}  # the register has never been written
    {"table_exists": true, "rows": [...]}  # it exists; it may still be empty

The browser needs the distinction: *"no hypothesis has been recorded"* and *"the register
does not exist yet"* are different sentences, and the page says which one is true. The
envelope is unchanged — this object is the ``data`` field, the same way
``/api/callset/tstv`` puts an object there.

**This surface is read-only, and creating the table here would be a lie.** ``ensure_table``
in :mod:`mva.science.hypothesis` is deliberately *not* called: a GET that materialises a
table would turn "nobody has made a claim" into "the register exists and is empty", which
is a different fact. Only the ``mva-science`` verbs write.

**Why this module imports from** :mod:`mva.science`. It imports the two table *names* and
nothing else — the same import :mod:`mva.viz.catalog_semantics` already makes, for the same
reason: a renamed table must be one edit, and a viz module that hard-codes ``"hypotheses"``
would silently serve nothing the day it is renamed. No science *behaviour* is imported; the
rows are read by SQL here, like every other viz query.

**Positions.** Statements and claims never carry a genomic position — ``mva-science check``
refuses one on the way in. This layer serves the text verbatim and adds no coordinate.
"""

from fastapi import APIRouter

from ..science.evidence import EVIDENCE_TABLE
from ..science.hypothesis import HYPOTHESIS_TABLE
from ..warehouse.postgres import ALIAS, attached, safe_identifier
from ..warehouse.settings import Postgres
from .queries.access import rows
from .response import Envelope, live

#: Columns of ``warehouse.hypotheses``, in the DDL's order
#: (:func:`mva.science.hypothesis.ensure_table`). Named rather than ``SELECT *`` so a
#: column added upstream cannot silently change the shape the browser is typed against.
HYPOTHESIS_COLUMNS = (
    "hypothesis_id",
    "revision",
    "recorded_at",
    "step",
    "statement",
    "prediction",
    "refuted_by",
    "path",
    "gene",
    "status",
    "confidence",
    "reasoning",
    "author",
    # Which iteration's step map this claim's ``step`` slug belongs to. Slugs restart at
    # ``step-1`` each iteration, so a row without it cannot be resolved to a goal.
    "iteration",
)

#: Columns of ``warehouse.evidence`` (:func:`mva.science.evidence.ensure_table`).
EVIDENCE_COLUMNS = (
    "evidence_id",
    "recorded_at",
    "hypothesis_id",
    "kind",
    "direction",
    "strength",
    "claim",
    "source_ref",
    "lineage_ref",
    "author",
)

#: Every revision, oldest first per claim. The client picks the latest; the history is the
#: point of an append-only register, so the API never throws the earlier revisions away.
HYPOTHESIS_ORDER = "ORDER BY hypothesis_id, revision"

#: Insertion order. ``evidence_id`` is ``max + 1``, so it is also chronological.
EVIDENCE_ORDER = "ORDER BY evidence_id"

HYPOTHESES_SOURCE = f"pg.warehouse.{HYPOTHESIS_TABLE}"
EVIDENCE_SOURCE = f"pg.warehouse.{EVIDENCE_TABLE}"

#: Does one table exist in one schema? ``information_schema`` is metadata, so this costs a
#: round trip and no scan, and it runs on the connection the read is about to use.
EXISTS_SQL = (
    f"SELECT table_name FROM {ALIAS}.information_schema.tables "
    f"WHERE table_schema = ? AND table_name = ?"
)


def register(settings: Postgres, table: str, columns: tuple[str, ...], order: str) -> dict:
    """Read one register table, or report that it has never been written.

    One attach for both statements: the existence check and the read share a connection,
    so the missing-table answer costs the same round trip the present-table answer does.
    """
    schema = safe_identifier(settings.schema)
    name = safe_identifier(table)
    with attached(settings, read_only=True) as connection:
        if not rows(connection, EXISTS_SQL, [settings.schema, table]):
            return {"table_exists": False, "rows": []}
        selected = ", ".join(safe_identifier(column) for column in columns)
        return {
            "table_exists": True,
            "rows": rows(connection, f"SELECT {selected} FROM {ALIAS}.{schema}.{name} {order}"),
        }


def hypotheses(settings: Postgres) -> dict:
    """Every revision of every registered claim, oldest first."""
    return register(settings, HYPOTHESIS_TABLE, HYPOTHESIS_COLUMNS, HYPOTHESIS_ORDER)


def evidence(settings: Postgres) -> dict:
    """Every recorded observation, in the order it was recorded."""
    return register(settings, EVIDENCE_TABLE, EVIDENCE_COLUMNS, EVIDENCE_ORDER)


def add_routes(api: APIRouter, settings: Postgres) -> None:
    """Register the two science routes on the warehouse router.

    Kept here rather than in :mod:`mva.viz.routes_warehouse`'s ``TABLES`` map because both
    routes carry a contract subtlety — the ``table_exists`` flag — that belongs in the
    generated ``/docs`` next to the endpoint, and the map has nowhere to put a docstring.
    """

    @api.get(
        "/science/hypotheses",
        response_model=Envelope,
        tags=["science"],
        summary=f"read {HYPOTHESES_SOURCE}",
    )
    def science_hypotheses() -> dict:
        """Every revision of every registered claim.

        ``data`` is ``{table_exists, rows}``, not a bare list. The register is created on
        first write by ``mva-science hypothesis-add``, so before the first claim the table
        is **absent** and ``table_exists`` is ``false`` — distinct from an existing table
        with no rows. This endpoint never creates it.

        Rows are **every revision**, oldest first: the register is append-only, so a
        changed belief is a new ``revision`` of the same ``hypothesis_id`` rather than an
        edit. The current belief is the highest revision per id; the earlier ones are the
        record of it moving. ``confidence``, ``reasoning``, ``gene`` and ``path`` are
        **null** until a verdict is committed.
        """
        return live(hypotheses(settings), HYPOTHESES_SOURCE)

    @api.get(
        "/science/evidence",
        response_model=Envelope,
        tags=["science"],
        summary=f"read {EVIDENCE_SOURCE}",
    )
    def science_evidence() -> dict:
        """Every recorded observation, bound to the claim it moves and to its source.

        ``data`` is ``{table_exists, rows}`` with the same missing-table grace as
        ``/api/science/hypotheses``. ``direction`` is ``supports``, ``refutes`` or
        ``neutral``; ``strength`` is a human judgement in ``0..1``; ``source_ref`` is the
        methodology entry, table, PMID, ClinVar id or probe reply the observation came
        from, and is never null — the constructor refuses an unsourced row. ``lineage_ref``
        **is** null wherever the observation is not tied to one derivation.
        """
        return live(evidence(settings), EVIDENCE_SOURCE)
