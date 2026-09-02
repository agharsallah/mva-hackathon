"""The whole research record in one object: steps, claims, evidence, spent probes.

The report needs all of it at once and each view needs a different slice, so it is read
once, here, and handed round. That is also what makes the report renderable from a JSON
export instead of a live database — :meth:`Record.from_register` rebuilds the same object
from what :mod:`mva.science.export` wrote, so a reviewer with a clone and no credentials
sees the same page the team sees.
"""

from dataclasses import dataclass, field

from . import steps
from .dossier import Dossier, tally
from .hypothesis import Status


@dataclass(frozen=True)
class SpentProbe:
    """One oracle submission, as the record cares about it.

    A thin view over ``warehouse.probe_ledger`` rather than a second copy of it: the
    ledger owns the truth, this carries only what the report draws.
    """

    probe_id: int
    probe_type: str
    submitted_by: str
    n_rows: int
    score: float | None
    response: str
    rationale: str
    hypothesis_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Record:
    """Everything the research report draws from."""

    dossiers: tuple[Dossier, ...] = ()
    probes: tuple[SpentProbe, ...] = ()
    budget_total: int = 0
    subject: str = "the warehouse"

    #: Cached grouping, filled on first access.
    _by_step: dict = field(default_factory=dict, compare=False, repr=False)

    def for_step(self, slug: str) -> list[Dossier]:
        """Every claim filed under one step, in id order."""
        if not self._by_step:
            for dossier in self.dossiers:
                self._by_step.setdefault(dossier.hypothesis.step, []).append(dossier)
        return self._by_step.get(slug, [])

    def tally_for(self, slug: str) -> dict[Status, int]:
        """The status breakdown for one step — the number on a step card."""
        return tally(self.for_step(slug))

    @property
    def steps(self) -> tuple[steps.Step, ...]:
        return steps.STEPS

    @property
    def is_empty(self) -> bool:
        """Whether anything has been recorded at all.

        A true statement the report must be able to make. An empty register renders as
        "nothing has been tested yet", never as a blank page that reads like a bug.
        """
        return not self.dossiers and not self.probes

    @property
    def budget_spent(self) -> int:
        return len(self.probes)

    @property
    def budget_left(self) -> int:
        return max(self.budget_total - self.budget_spent, 0)

    @property
    def open_claims(self) -> tuple[Dossier, ...]:
        """Claims still carrying an unanswered question."""
        return tuple(d for d in self.dossiers if not d.hypothesis.status.is_settled)

    @property
    def untested_claims(self) -> tuple[Dossier, ...]:
        """Claims with no evidence at all — the queue, in effect."""
        return tuple(d for d in self.dossiers if d.is_untested)

    @property
    def supported(self) -> tuple[Dossier, ...]:
        """Claims the evidence supports — the ones eligible to become submission rows."""
        return tuple(d for d in self.dossiers if d.hypothesis.status is Status.SUPPORTED)


def from_register(data: dict, subject: str = "the committed register") -> Record:
    """Rebuild the record from what :func:`mva.science.export.register` wrote.

    This is what lets a reviewer with a clone and no credentials render the same page the
    team sees. One thing does not survive the round trip: the export keeps only the latest
    revision of each claim, so :attr:`Dossier.history` comes back one entry long. The
    report shows current state, so nothing on the page depends on it — but a caller
    wanting the full trail has to read the warehouse.
    """
    from .dossier import Dossier
    from .evidence import Direction, Evidence, weigh
    from .hypothesis import Hypothesis, Status

    dossiers = []
    for entry in data.get("hypotheses", []):
        claim = Hypothesis(
            step=entry["step"],
            statement=entry["statement"],
            prediction=entry["prediction"],
            refuted_by=entry["refuted_by"],
            hypothesis_id=entry["id"],
            gene=entry.get("gene", "") or "",
            path=entry.get("path", "") or "",
            status=Status(entry["status"]),
            confidence=entry.get("confidence"),
        )
        rows = [
            Evidence(
                hypothesis_id=entry["id"],
                direction=Direction(row["direction"]),
                claim=row["claim"],
                source_ref=row["source_ref"],
                evidence_id=row["id"],
                kind=row["kind"],
                strength=row["strength"],
                lineage_ref=row.get("lineage_ref", "") or "",
            )
            for row in entry.get("evidence", [])
        ]
        dossiers.append(
            Dossier(
                hypothesis=claim,
                history=(claim,),
                evidence=tuple(rows),
                weighing=weigh(rows, entry["id"]),
            )
        )

    return Record(dossiers=tuple(dossiers), budget_total=_default_budget(), subject=subject)


def _default_budget() -> int:
    from ..warehouse.probes import BUDGET

    return BUDGET


def read(connection, schema: str, budget_total: int = 0, subject: str = "the warehouse") -> Record:
    """Read the whole record out of the warehouse in three queries."""
    from ..warehouse import probes as probe_module
    from .dossier import assemble_all

    dossiers = assemble_all(connection, schema)
    spent = tuple(
        SpentProbe(
            probe_id=int(row[0]),
            probe_type=row[3],
            submitted_by=row[4],
            n_rows=int(row[6] or 0),
            score=None if row[7] is None else float(row[7]),
            response=row[8] or "",
            rationale="",
            hypothesis_ids=_split_ids(row[10] if len(row) > 10 else ""),
        )
        for row in probe_module.listing(connection, schema)
    )
    return Record(
        dossiers=tuple(dossiers),
        probes=spent,
        budget_total=budget_total or probe_module.BUDGET,
        subject=subject,
    )


def _split_ids(value) -> tuple[str, ...]:
    """Parse the comma-separated hypothesis ids a probe was fired to test."""
    if not value:
        return ()
    return tuple(part.strip() for part in str(value).split(",") if part.strip())
