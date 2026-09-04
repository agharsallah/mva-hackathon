"""The probe ledger: who spent which oracle submission, on what, and what came back.

The Track 1 scorer is an oracle — every submission returns `rank_points`, `f_max`,
`full_match_rank` and friends — and the team gets exactly **6 per
registered member** (one member is registered, so six in total). That makes a submission a
*consumable resource*, and a consumable resource tracked in chat messages is a resource
that gets double-spent.

This module is the ledger for it: one append-only row per submission, carrying the payload
that was uploaded, the reply that came back, and who spent it.

**Schema placement.** It lives in the ingest schema (``warehouse``) rather than the result
schema, because it is hand-written operational state — like the upload ledger and the
lineage edge list beside it — not something ``pg-derive`` computes and rebuilds; the result
schema is reserved for tables that are a pure function of their inputs, and this one is a
record of irreversible actions taken in the outside world.
"""

import os
from dataclasses import dataclass

#: Append-only record of oracle submissions spent.
PROBE_TABLE = "probe_ledger"

#: Track 1 oracle submissions granted per registered team member.
PER_MEMBER = 6


def _registered_members() -> int:
    """How many team members are registered, from ``MVA_TEAM_MEMBERS`` (default one).

    The budget is a property of the team roster, not of the code, so it is configuration
    rather than a constant. A roster of fewer than one member cannot exist, and silently
    treating it as one would hide a misconfigured environment, so it raises instead.
    """
    raw = os.environ.get("MVA_TEAM_MEMBERS", "1")
    members = int(raw)
    if members < 1:
        raise ValueError(f"MVA_TEAM_MEMBERS must be at least 1, got {members!r}")
    return members


#: Total Track 1 oracle submissions available to the team: 6 per registered member.
#: See ``ideation/hackathon-intel.md`` §9 for how they are meant to be spent.
BUDGET = PER_MEMBER * _registered_members()

#: Probe kinds from the oracle protocol, plus the catch-all. Not enforced by the schema —
#: a mislabelled probe should still be recorded rather than rejected.
PROBE_TYPES = ("S", "P", "F", "final", "other")


@dataclass(frozen=True)
class Probe:
    """One spent submission, exactly as it will be stored."""

    track: str = "1"
    probe_type: str = "other"
    submitted_by: str = ""
    submission_ref: str = ""
    payload: str = ""
    n_rows: int = 0
    response: str = ""
    score: float | None = None
    rationale: str = ""
    #: Comma-separated ids of the hypotheses this submission was fired to test. A probe
    #: exists to move a belief, so the reply is only decodable against the claims it was
    #: aimed at. Empty is allowed and means "not tied to the register" — the ledger records
    #: what happened, and refusing an untagged probe would lose the record of a real spend.
    hypothesis_ids: str = ""


@dataclass(frozen=True)
class Budget:
    """How much of the oracle allowance is gone."""

    spent: int
    total: int = BUDGET

    @property
    def remaining(self) -> int:
        return max(self.total - self.spent, 0)

    def __str__(self) -> str:
        return f"{self.spent}/{self.total} spent, {self.remaining} remaining"


def ensure_table(connection, schema: str) -> None:
    """Create the ledger if absent. Idempotent, like every other ``ensure_*`` here."""
    from .postgres import ALIAS, safe_identifier

    connection.execute(f"""
        CREATE TABLE IF NOT EXISTS {ALIAS}.{safe_identifier(schema)}.{PROBE_TABLE} (
            probe_id       BIGINT,
            logged_at      TIMESTAMP,
            track          VARCHAR,
            probe_type     VARCHAR,
            submitted_by   VARCHAR,
            submission_ref VARCHAR,
            payload        VARCHAR,
            n_rows         INTEGER,
            response       VARCHAR,
            score          DOUBLE,
            rationale      VARCHAR,
            hypothesis_ids VARCHAR
        )""")


def _qualified(schema: str) -> str:
    from .postgres import ALIAS, safe_identifier

    return f"{ALIAS}.{safe_identifier(schema)}.{PROBE_TABLE}"


def budget(connection, schema: str, track: str | None = None) -> Budget:
    """How many submissions are gone — the "how many of the budget are left" query, as one call."""
    sql = f"SELECT count(*) FROM {_qualified(schema)}"
    params: list = []
    if track:
        sql += " WHERE track = ?"
        params = [track]
    return Budget(spent=connection.execute(sql, params).fetchone()[0])


def log(connection, schema: str, probe: Probe) -> int:
    """Append one probe and return the id it was given.

    The id is ``max + 1`` computed here rather than a sequence, because the table is
    created through DuckDB's PostgreSQL attachment, which speaks a common subset of DDL.
    Two people logging at the same instant would collide; the ledger records events that
    are minutes apart at best, so that is a cost worth not paying a sequence for.
    """
    qualified = _qualified(schema)
    next_id = (
        connection.execute(f"SELECT coalesce(max(probe_id), 0) + 1 FROM {qualified}").fetchone()
        or [1]
    )[0]
    connection.execute(
        f"INSERT INTO {qualified} VALUES (?, now(), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            next_id,
            probe.track,
            probe.probe_type,
            probe.submitted_by,
            probe.submission_ref,
            probe.payload,
            probe.n_rows,
            probe.response,
            probe.score,
            probe.rationale,
            probe.hypothesis_ids,
        ],
    )
    return int(next_id)


def listing(connection, schema: str, limit: int = 0) -> list[tuple]:
    """Every probe, oldest first, with the payload trimmed to a previewable width.

    The full payload stays in the table; showing 60 characters of a ten-row CSV in a
    terminal listing is enough to recognise which probe a row is.
    """
    sql = (
        f"SELECT probe_id, logged_at, track, probe_type, submitted_by, "
        f"submission_ref, n_rows, score, "
        f"left(coalesce(response, ''), 60) AS response, "
        f"left(coalesce(payload, ''), 60) AS payload_head, "
        f"coalesce(hypothesis_ids, '') AS hypothesis_ids "
        f"FROM {_qualified(schema)} ORDER BY probe_id"
    )
    if limit:
        sql += f" LIMIT {int(limit)}"
    return connection.execute(sql).fetchall()


#: Column headers matching :func:`listing`, so the CLI does not restate them.
LISTING_COLUMNS = (
    "probe_id",
    "logged_at",
    "track",
    "type",
    "submitted_by",
    "submission_ref",
    "n_rows",
    "score",
    "response",
    "payload_head",
    "hypotheses",
)
