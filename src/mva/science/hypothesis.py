"""A falsifiable claim, and every revision of what we believed about it.

The table is **append-only revisions**, not a mutable row per hypothesis. Believing
something less strongly than you did last week is a fact about the investigation, and
overwriting a confidence destroys the only record that the belief ever moved. A verdict is
therefore a new revision, never an ``UPDATE``.

Two rules are enforced in code rather than asked for in a template, because a template is
advice and a constructor is a gate:

* **No hypothesis without a refutation condition.** ``refuted_by`` must say what
  observation would kill the claim. A claim nothing could refute is not a hypothesis, and
  writing that sentence down *before* the run is what stops the result from being
  reinterpreted afterwards to fit.
* **No hypothesis outside a research step.** Every claim names the step whose goal it
  serves, so the report can group by question rather than by chronology.

Schema placement follows :mod:`mva.warehouse.probes`: this lives in the ingest schema
(``warehouse``) because it is hand-written state recording judgments made in the outside
world, not something ``pg-derive`` recomputes from inputs.
"""

from dataclasses import dataclass, replace
from enum import Enum

from ..render.theme import BAD, DECISION, GOOD, MACHINE, MUTED, Hue
from . import steps

#: Append-only record of hypothesis revisions.
HYPOTHESIS_TABLE = "hypotheses"

#: How an id is spelled. Zero-padded so lexical order is numeric order, which lets the
#: next-id query be a plain ``max`` the way :mod:`mva.warehouse.probes` does it.
ID_FORMAT = "H{:03d}"


class Status(Enum):
    """Where a claim stands. The palette is the repository's, not a second scale."""

    PROPOSED = "proposed"
    TESTING = "testing"
    SUPPORTED = "supported"
    REFUTED = "refuted"
    SUPERSEDED = "superseded"

    @property
    def hue(self) -> Hue:
        """The colour this status is drawn in, from the one palette in the repository."""
        return {
            Status.PROPOSED: MACHINE,
            Status.TESTING: DECISION,
            Status.SUPPORTED: GOOD,
            Status.REFUTED: BAD,
            Status.SUPERSEDED: MUTED,
        }[self]

    @property
    def is_settled(self) -> bool:
        """Whether the claim still has an open question attached to it."""
        return self in (Status.SUPPORTED, Status.REFUTED, Status.SUPERSEDED)


@dataclass(frozen=True)
class Hypothesis:
    """One revision of one claim, exactly as it will be stored."""

    step: str
    statement: str
    prediction: str
    refuted_by: str
    hypothesis_id: str = ""
    revision: int = 1
    path: str = ""
    gene: str = ""
    status: Status = Status.PROPOSED
    confidence: float | None = None
    reasoning: str = ""
    author: str = ""
    #: The submission iteration whose step map this claim's ``step`` slug belongs to.
    #: Slugs restart at ``step-1`` each iteration, so without this an iteration-1 claim
    #: would render an iteration-2 goal. Empty means the current iteration; a row written
    #: before the column existed is hydrated as iteration 1, the only iteration that had
    #: filed claims then.
    iteration: str = ""
    #: When the warehouse recorded this revision (``now()`` at insert time). Read-only:
    #: never set by a caller filing a claim, only hydrated back from a row. Exists so a
    #: re-export of unchanged data can stamp itself with *this*, not with the moment the
    #: export happened to run — see :mod:`mva.science.export`.
    recorded_at: str = ""

    def __post_init__(self) -> None:
        for field_name in ("statement", "prediction", "refuted_by"):
            if not str(getattr(self, field_name)).strip():
                raise ValueError(
                    f"{field_name} is required: a claim with no {field_name} cannot be "
                    "tested, and an untestable claim does not belong in the record"
                )
        step = self.step_record
        if not step.takes_hypotheses:
            raise ValueError(
                f"{step.slug} is a {step.kind} step: it records decisions, not claims "
                f"about the patient. File this under one of "
                f"{', '.join(s.slug for s in steps.research_steps())}"
            )
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0, 1], got {self.confidence}")
        if self.revision < 1:
            raise ValueError(f"revision starts at 1, got {self.revision}")

    @property
    def filed_under(self) -> str:
        """The iteration this claim belongs to; unset means the one being worked now."""
        return self.iteration or steps.ITERATION

    @property
    def step_record(self) -> steps.Step:
        """The step this claim serves, read from *its own* iteration's map."""
        return steps.by_slug(self.step, iteration=self.filed_under)

    @property
    def goal(self) -> str:
        """The research goal this claim serves."""
        return self.step_record.goal

    def __str__(self) -> str:
        confidence = "—" if self.confidence is None else f"{self.confidence:.2f}"
        return (
            f"{self.hypothesis_id}r{self.revision} [{self.status.value}] "
            f"{confidence} — {self.statement}"
        )


def ensure_table(connection, schema: str) -> None:
    """Create the register if absent. Idempotent, like every other ``ensure_*`` here."""
    from ..warehouse.postgres import ALIAS, safe_identifier

    safe = safe_identifier(schema)
    connection.execute(f"""
        CREATE TABLE IF NOT EXISTS {ALIAS}.{safe}.{HYPOTHESIS_TABLE} (
            hypothesis_id VARCHAR,
            revision      INTEGER,
            recorded_at   TIMESTAMP,
            step          VARCHAR,
            statement     VARCHAR,
            prediction    VARCHAR,
            refuted_by    VARCHAR,
            path          VARCHAR,
            gene          VARCHAR,
            status        VARCHAR,
            confidence    DOUBLE,
            reasoning     VARCHAR,
            author        VARCHAR,
            iteration     VARCHAR
        )""")
    # The column above was added after the first claims were filed, so a table created
    # before that needs it too; those rows read back empty, which
    # :attr:`Hypothesis.filed_under` reads as iteration 1.
    connection.execute(
        f"ALTER TABLE {ALIAS}.{safe}.{HYPOTHESIS_TABLE} ADD COLUMN IF NOT EXISTS iteration VARCHAR"
    )


def _qualified(schema: str) -> str:
    from ..warehouse.postgres import ALIAS, safe_identifier

    return f"{ALIAS}.{safe_identifier(schema)}.{HYPOTHESIS_TABLE}"


def _insert(connection, schema: str, hypothesis: Hypothesis) -> Hypothesis:
    """Append one revision. Column order matches the DDL, which is load-bearing."""
    connection.execute(
        f"INSERT INTO {_qualified(schema)} VALUES (?, ?, now(), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            hypothesis.hypothesis_id,
            hypothesis.revision,
            hypothesis.step,
            hypothesis.statement,
            hypothesis.prediction,
            hypothesis.refuted_by,
            hypothesis.path,
            hypothesis.gene,
            hypothesis.status.value,
            hypothesis.confidence,
            hypothesis.reasoning,
            hypothesis.author,
            hypothesis.filed_under,
        ],
    )
    return hypothesis


def next_id(connection, schema: str) -> str:
    """The id the next hypothesis will get.

    ``max`` over a zero-padded text column, for the reason given in
    :mod:`mva.warehouse.probes`: the table is created through DuckDB's PostgreSQL
    attachment, which has no sequences in the DDL subset both sides speak.
    """
    highest = connection.execute(
        f"SELECT coalesce(max(hypothesis_id), '') FROM {_qualified(schema)}"
    ).fetchone()
    current = (highest or [""])[0] or ""
    return ID_FORMAT.format(int(current[1:]) + 1 if current else 1)


def propose(connection, schema: str, hypothesis: Hypothesis) -> Hypothesis:
    """Record a new claim at revision 1, allocating its id."""
    stamped = replace(hypothesis, hypothesis_id=next_id(connection, schema), revision=1)
    return _insert(connection, schema, stamped)


def revise(
    connection,
    schema: str,
    hypothesis_id: str,
    *,
    status: Status,
    confidence: float | None = None,
    reasoning: str = "",
    author: str = "",
) -> Hypothesis:
    """Append a new revision carrying a changed status or confidence.

    The unchanged fields are copied from the latest revision rather than re-typed, so a
    verdict cannot silently reword the statement it is a verdict on.
    """
    if not reasoning.strip():
        raise ValueError(
            "reasoning is required: a confidence with no stated basis is a number "
            "nobody can check, which is exactly what this register exists to prevent"
        )
    current = latest(connection, schema, hypothesis_id)
    revised = replace(
        current,
        revision=current.revision + 1,
        status=status,
        confidence=current.confidence if confidence is None else confidence,
        reasoning=reasoning,
        author=author or current.author,
    )
    return _insert(connection, schema, revised)


#: Column order of the SELECT in :func:`_select`, so a row can be rebuilt into an object.
_COLUMNS = (
    "hypothesis_id",
    "revision",
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
    "iteration",
    "recorded_at",
)

_SELECT = f"SELECT {', '.join(_COLUMNS)} FROM {{table}}"


def _hydrate(row: tuple) -> Hypothesis:
    """Rebuild a :class:`Hypothesis` from a row in :data:`_COLUMNS` order.

    A row may end before ``_COLUMNS`` does: ``iteration`` and ``recorded_at`` were both
    added after this table existed, so a row written earlier (a fixture, an archived
    export) simply stops short of them. The missing trailing fields take the same default
    an ``ALTER TABLE`` backfill would have given them.
    """
    if len(row) > len(_COLUMNS):
        raise ValueError(f"row has {len(row)} columns, _COLUMNS only names {len(_COLUMNS)}")
    fields = dict(zip(_COLUMNS, row, strict=False))
    fields["status"] = Status(fields["status"])
    fields["confidence"] = None if fields["confidence"] is None else float(fields["confidence"])
    fields["recorded_at"] = "" if fields.get("recorded_at") is None else str(fields["recorded_at"])
    fields["revision"] = int(fields["revision"])
    # A row from before the column existed belongs to iteration 1 — made explicit here so
    # nothing downstream re-reads it as the current iteration.
    fields["iteration"] = fields.get("iteration") or steps.FIRST_ITERATION
    return Hypothesis(**fields)


def latest(connection, schema: str, hypothesis_id: str) -> Hypothesis:
    """The most recent revision of one claim."""
    sql = (
        _SELECT.format(table=_qualified(schema))
        + " WHERE hypothesis_id = ? ORDER BY revision DESC LIMIT 1"
    )
    row = connection.execute(sql, [hypothesis_id]).fetchone()
    if not row:
        raise KeyError(f"no hypothesis {hypothesis_id!r} in {schema}")
    return _hydrate(row)


def board(connection, schema: str, step: str | None = None) -> list[Hypothesis]:
    """The current state of every claim: one latest revision each, oldest id first.

    Written as a self-join on the maximum revision rather than a window function, because
    the query runs through DuckDB's PostgreSQL attachment and the simpler form is the one
    both planners agree on.
    """
    table = _qualified(schema)
    sql = (
        f"{_SELECT.format(table=table)} h WHERE h.revision = ("
        f"SELECT max(revision) FROM {table} m "
        f"WHERE m.hypothesis_id = h.hypothesis_id)"
    )
    params: list = []
    if step is not None:
        sql += " AND h.step = ?"
        params = [step]
    sql += " ORDER BY h.hypothesis_id"
    return [_hydrate(row) for row in connection.execute(sql, params).fetchall()]


def all_revisions(connection, schema: str, step: str | None = None) -> list[Hypothesis]:
    """Every revision of every claim, ordered by id then revision.

    One query for the whole register. The report and the export both need all of it, and a
    per-hypothesis round trip over an attached database is a cost that only becomes
    visible once the register is large.
    """
    sql = _SELECT.format(table=_qualified(schema))
    params: list = []
    if step is not None:
        sql += " WHERE step = ?"
        params = [step]
    sql += " ORDER BY hypothesis_id, revision"
    return [_hydrate(row) for row in connection.execute(sql, params).fetchall()]


def history(connection, schema: str, hypothesis_id: str) -> list[Hypothesis]:
    """Every revision of one claim, oldest first — how the belief actually moved."""
    sql = _SELECT.format(table=_qualified(schema)) + " WHERE hypothesis_id = ? ORDER BY revision"
    return [_hydrate(row) for row in connection.execute(sql, [hypothesis_id]).fetchall()]


#: Headers matching :func:`board`, so the CLI does not restate them.
BOARD_COLUMNS = ("id", "rev", "step", "status", "confidence", "gene", "statement")


def as_row(hypothesis: Hypothesis, width: int = 60) -> tuple:
    """One board row, with the statement trimmed to a terminal-previewable width."""
    statement = hypothesis.statement
    if len(statement) > width:
        statement = statement[: width - 1] + "…"
    return (
        hypothesis.hypothesis_id,
        hypothesis.revision,
        hypothesis.step,
        hypothesis.status.value,
        "—" if hypothesis.confidence is None else f"{hypothesis.confidence:.2f}",
        hypothesis.gene or "—",
        statement,
    )
