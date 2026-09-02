"""One observation bearing on one claim, and the arithmetic that turns a pile into a number.

An evidence row is not a conclusion. It is a single observation, tagged with which way it
cuts, how hard, and — this is the load-bearing field — **where it came from**. A row with
no ``source_ref`` is rejected, because an unsourced claim is the exact failure this
register exists to prevent: a number in a report that nobody can trace back to a run.

``source_ref`` names the receipt: a methodology entry (``methodology/003``), a warehouse
table (``results.panel_gene_counts``), a publication (``PMID:12345678``), a database record
(``ClinVar:VCV000012345``), or an oracle reply (``probe:4``). ``lineage_ref`` is the
optional stronger form — a row in ``warehouse.data_lineage`` — which ties the observation
to the exact bytes it was computed from.

**On the weighing.** :func:`weigh` accumulates evidence in log-odds and reports the
arithmetic term by term. It is a transparent heuristic for ordering and triage, *not* a
calibrated posterior: the strengths are human judgments, and evidence rows drawn from the
same underlying data are not independent the way the sum pretends. It exists so that a
suggested confidence can be argued with, and it never writes anything — committing a
confidence takes a human, a ``--commit`` and a stated reason.
"""

import math
from dataclasses import dataclass
from enum import Enum

from ..render.theme import BAD, GOOD, MUTED, Hue

#: Append-only record of observations.
EVIDENCE_TABLE = "evidence"

#: Where an observation came from. Not enforced by the schema — a mislabelled kind should
#: still be recorded rather than rejected, the same call :mod:`mva.warehouse.probes` makes.
KINDS = ("measurement", "annotation", "literature", "oracle", "absence")

#: How far one unit of strength moves the log-odds. At 2.0 a single decisive observation
#: (strength 1.0) takes an even prior to roughly 0.88, and two take it to 0.98 — strong,
#: but never certain, which is the right shape for a heuristic.
WEIGHT = 2.0

#: Where the accumulation starts when nothing is known. Deliberately even: the register
#: should not smuggle in a prior nobody stated.
PRIOR = 0.5


class Direction(Enum):
    """Which way an observation cuts."""

    SUPPORTS = "supports"
    REFUTES = "refutes"
    NEUTRAL = "neutral"

    @property
    def sign(self) -> int:
        """The multiplier this direction contributes to the log-odds sum."""
        return {Direction.SUPPORTS: 1, Direction.REFUTES: -1, Direction.NEUTRAL: 0}[self]

    @property
    def hue(self) -> Hue:
        """The colour this direction is drawn in, from the one palette."""
        return {Direction.SUPPORTS: GOOD, Direction.REFUTES: BAD, Direction.NEUTRAL: MUTED}[self]


@dataclass(frozen=True)
class Evidence:
    """One observation, exactly as it will be stored."""

    hypothesis_id: str
    direction: Direction
    claim: str
    source_ref: str
    evidence_id: int = 0
    kind: str = "measurement"
    strength: float = 0.5
    lineage_ref: str = ""
    author: str = ""

    def __post_init__(self) -> None:
        if not self.claim.strip():
            raise ValueError("claim is required: say what was observed, in one sentence")
        if not self.source_ref.strip():
            raise ValueError(
                "source_ref is required: an observation with no receipt cannot be "
                "checked, and an unverifiable observation is not evidence"
            )
        if not 0.0 <= self.strength <= 1.0:
            raise ValueError(f"strength must be in [0, 1], got {self.strength}")

    @property
    def contribution(self) -> float:
        """How far this row moves the log-odds. Zero for neutral, by construction."""
        return self.direction.sign * self.strength * WEIGHT


@dataclass(frozen=True)
class Weighing:
    """A suggested confidence, and every term that produced it."""

    hypothesis_id: str
    prior: float
    terms: tuple[tuple[str, float], ...]
    confidence: float
    supports: int
    refutes: int
    neutral: int

    @property
    def is_decided(self) -> bool:
        """Whether the evidence points anywhere at all."""
        return bool(self.supports or self.refutes)

    def arithmetic(self) -> list[str]:
        """The sum, line by line, for a human to disagree with."""
        lines = [f"prior {self.prior:.2f}  (log-odds {_logit(self.prior):+.3f})"]
        running = _logit(self.prior)
        for label, term in self.terms:
            running += term
            lines.append(f"  {term:+.3f}  {label}   -> {_sigmoid(running):.3f}")
        lines.append(
            f"suggested confidence {self.confidence:.2f} "
            f"({self.supports} supporting, {self.refutes} refuting, "
            f"{self.neutral} neutral)"
        )
        return lines


def _logit(probability: float) -> float:
    bounded = min(max(probability, 1e-6), 1 - 1e-6)
    return math.log(bounded / (1 - bounded))


def _sigmoid(log_odds: float) -> float:
    return 1.0 / (1.0 + math.exp(-log_odds))


def weigh(rows: list[Evidence], hypothesis_id: str = "", prior: float = PRIOR) -> Weighing:
    """Accumulate evidence into a suggested confidence, keeping every term visible.

    Writes nothing. The caller decides whether the number is worth committing, and the
    register only accepts it alongside a stated reason.
    """
    log_odds = _logit(prior)
    terms: list[tuple[str, float]] = []
    tally = dict.fromkeys(Direction, 0)

    for row in rows:
        tally[row.direction] += 1
        term = row.contribution
        log_odds += term
        terms.append((f"{row.direction.value} {row.strength:.2f} — {row.claim}", term))

    return Weighing(
        hypothesis_id=hypothesis_id or (rows[0].hypothesis_id if rows else ""),
        prior=prior,
        terms=tuple(terms),
        confidence=_sigmoid(log_odds),
        supports=tally[Direction.SUPPORTS],
        refutes=tally[Direction.REFUTES],
        neutral=tally[Direction.NEUTRAL],
    )


def ensure_table(connection, schema: str) -> None:
    """Create the ledger if absent. Idempotent, like every other ``ensure_*`` here."""
    from ..warehouse.postgres import ALIAS, safe_identifier

    safe = safe_identifier(schema)
    connection.execute(f"""
        CREATE TABLE IF NOT EXISTS {ALIAS}.{safe}.{EVIDENCE_TABLE} (
            evidence_id   BIGINT,
            recorded_at   TIMESTAMP,
            hypothesis_id VARCHAR,
            kind          VARCHAR,
            direction     VARCHAR,
            strength      DOUBLE,
            claim         VARCHAR,
            source_ref    VARCHAR,
            lineage_ref   VARCHAR,
            author        VARCHAR
        )""")


def _qualified(schema: str) -> str:
    from ..warehouse.postgres import ALIAS, safe_identifier

    return f"{ALIAS}.{safe_identifier(schema)}.{EVIDENCE_TABLE}"


def record(connection, schema: str, evidence: Evidence) -> int:
    """Append one observation and return the id it was given.

    ``max + 1`` rather than a sequence, for the reason spelled out in
    :mod:`mva.warehouse.probes`: the DDL subset shared by DuckDB and PostgreSQL over the
    attachment has none, and two people recording in the same instant is not a risk this
    ledger runs.
    """
    qualified = _qualified(schema)
    next_id = (
        connection.execute(f"SELECT coalesce(max(evidence_id), 0) + 1 FROM {qualified}").fetchone()
        or [1]
    )[0]
    connection.execute(
        f"INSERT INTO {qualified} VALUES (?, now(), ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            next_id,
            evidence.hypothesis_id,
            evidence.kind,
            evidence.direction.value,
            evidence.strength,
            evidence.claim,
            evidence.source_ref,
            evidence.lineage_ref,
            evidence.author,
        ],
    )
    return int(next_id)


_COLUMNS = (
    "evidence_id",
    "hypothesis_id",
    "kind",
    "direction",
    "strength",
    "claim",
    "source_ref",
    "lineage_ref",
    "author",
)

_SELECT = f"SELECT {', '.join(_COLUMNS)} FROM {{table}}"


def _hydrate(row: tuple) -> Evidence:
    fields = dict(zip(_COLUMNS, row, strict=True))
    fields["direction"] = Direction(fields["direction"])
    fields["strength"] = float(fields["strength"])
    fields["evidence_id"] = int(fields["evidence_id"])
    fields["lineage_ref"] = fields["lineage_ref"] or ""
    fields["author"] = fields["author"] or ""
    return Evidence(**fields)


def listing(connection, schema: str, hypothesis_id: str | None = None) -> list[Evidence]:
    """Every observation, oldest first, optionally narrowed to one claim."""
    sql = _SELECT.format(table=_qualified(schema))
    params: list = []
    if hypothesis_id is not None:
        sql += " WHERE hypothesis_id = ?"
        params = [hypothesis_id]
    sql += " ORDER BY evidence_id"
    return [_hydrate(row) for row in connection.execute(sql, params).fetchall()]


def by_hypothesis(rows: list[Evidence]) -> dict[str, list[Evidence]]:
    """Group a listing by claim, preserving order within each group."""
    grouped: dict[str, list[Evidence]] = {}
    for row in rows:
        grouped.setdefault(row.hypothesis_id, []).append(row)
    return grouped


#: Headers matching :func:`listing`, so the CLI does not restate them.
LISTING_COLUMNS = ("id", "hypothesis", "kind", "direction", "strength", "claim", "source")


def as_row(evidence: Evidence, width: int = 50) -> tuple:
    """One ledger row, with the claim trimmed to a terminal-previewable width."""
    claim = evidence.claim
    if len(claim) > width:
        claim = claim[: width - 1] + "…"
    return (
        evidence.evidence_id,
        evidence.hypothesis_id,
        evidence.kind,
        evidence.direction.value,
        f"{evidence.strength:.2f}",
        claim,
        evidence.source_ref,
    )
