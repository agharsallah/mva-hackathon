"""The generator table contract: one ranked drug list and one universe per generator.

*Plain words.* A **generator** is an independent source that *proposes* drugs (a graph walk, a
mouse-model literature table, a cell-line screen, a signature-reversal search). Each writes
the same three files, so the convergence test (:mod:`mva.drugs.convergence`) can join any of
them without knowing where they came from:

* ``<id>.tsv`` - the list: one row per proposed drug, columns :data:`GENERATOR_COLUMNS`;
* ``<id>.universe.tsv`` - every drug the generator *could* have proposed (``drug``,
  ``approved``); the permutation null draws from it;
* ``<id>.provenance.json`` - how the list was made.

The join key is ``drug``, which must already be :func:`mva.drugs.names.base_name` of the
source's own spelling. The reader re-folds it anyway, so a hand-edited table cannot break the
join silently. Generator ids and directories are parameters everywhere: nothing here knows
about any particular case.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .names import base_name

__all__ = [
    "DIRECTION_HINTS",
    "GENERATOR_COLUMNS",
    "UNIVERSE_COLUMNS",
    "GeneratorList",
    "GeneratorRow",
    "read_generator",
    "read_universe",
    "write_generator",
]

GENERATOR_COLUMNS = (
    "generator",
    "rank",
    "drug",
    "drug_label",
    "approved",
    "approval_evidence",
    "score",
    "score_name",
    "direction_hint",
    "evidence",
    "source_ids",
)

UNIVERSE_COLUMNS = ("drug", "approved")

#: The direction words the table contract allows (step-10 README, "The table contract").
DIRECTION_HINTS = frozenset({"D2", "D3", "D4", "D5", "none"})


@dataclass(frozen=True)
class GeneratorRow:
    """One proposed drug, in the contract's columns."""

    generator: str
    rank: int
    drug: str
    drug_label: str
    approved: bool
    approval_evidence: str
    score: str
    score_name: str
    direction_hint: str
    evidence: str
    source_ids: str = ""

    def as_row(self) -> dict[str, str]:
        return {
            "generator": self.generator,
            "rank": str(self.rank),
            "drug": self.drug,
            "drug_label": self.drug_label,
            "approved": "true" if self.approved else "false",
            "approval_evidence": self.approval_evidence,
            "score": self.score,
            "score_name": self.score_name,
            "direction_hint": self.direction_hint,
            "evidence": self.evidence,
            "source_ids": self.source_ids,
        }


@dataclass(frozen=True)
class GeneratorList:
    """A generator's approved list and its approved universe, keyed on the join key.

    ``rows`` keeps every row read (approved or not); :attr:`drugs` is the approved set the
    convergence count uses; :attr:`universe` is the approved universe the null draws from.
    ``outside_universe`` names listed drugs the universe file omitted - they are added to
    the universe (a list is always a subset of what it was drawn from) and reported.
    """

    generator: str
    rows: tuple[GeneratorRow, ...]
    universe: frozenset[str]
    outside_universe: tuple[str, ...] = field(default=())

    @property
    def drugs(self) -> frozenset[str]:
        return frozenset(r.drug for r in self.rows if r.approved)

    def best(self) -> dict[str, GeneratorRow]:
        """The best-ranked approved row per drug (a drug may appear twice, e.g. two salts)."""
        out: dict[str, GeneratorRow] = {}
        for row in sorted(self.rows, key=lambda r: r.rank):
            if row.approved and row.drug not in out:
                out[row.drug] = row
        return out


def _flag(value: str) -> bool:
    return value.strip().lower() in {"true", "yes", "1"}


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def read_universe(path: Path) -> frozenset[str]:
    """The approved drugs of a universe file, as join keys."""
    return frozenset(base_name(u["drug"]) for u in _read_tsv(path) if _flag(u["approved"]))


def read_generator(directory: Path, generator: str) -> GeneratorList:
    """Read ``<directory>/<generator>.tsv`` and its universe into a :class:`GeneratorList`."""
    raw = _read_tsv(directory / f"{generator}.tsv")
    missing = [c for c in GENERATOR_COLUMNS if raw and c not in raw[0]]
    if missing:
        raise ValueError(f"{generator}.tsv lacks contract columns {missing}")
    rows = tuple(
        GeneratorRow(
            generator=r["generator"] or generator,
            rank=int(float(r["rank"])),
            drug=base_name(r["drug"]),
            drug_label=r["drug_label"],
            approved=_flag(r["approved"]),
            approval_evidence=r["approval_evidence"],
            score=r["score"],
            score_name=r["score_name"],
            direction_hint=r["direction_hint"] or "none",
            evidence=r["evidence"],
            source_ids=r.get("source_ids", "") or "",
        )
        for r in raw
    )
    universe = read_universe(directory / f"{generator}.universe.tsv")
    listed = {r.drug for r in rows if r.approved}
    outside = tuple(sorted(listed - universe))
    return GeneratorList(generator, rows, frozenset(universe | listed), outside)


def write_generator(
    directory: Path,
    generator: str,
    rows: Sequence[GeneratorRow],
    universe: Mapping[str, bool] | Iterable[str],
) -> tuple[Path, Path]:
    """Write the list and the universe; a bare iterable universe means every drug approved."""
    directory.mkdir(parents=True, exist_ok=True)
    listing = directory / f"{generator}.tsv"
    with listing.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=GENERATOR_COLUMNS, delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(r.as_row() for r in rows)
    flags = dict(universe) if isinstance(universe, Mapping) else dict.fromkeys(universe, True)
    universe_path = directory / f"{generator}.universe.tsv"
    with universe_path.open("w", encoding="utf-8", newline="") as handle:
        plain = csv.writer(handle, delimiter="\t", lineterminator="\n")
        plain.writerow(UNIVERSE_COLUMNS)
        for drug in sorted(flags):
            plain.writerow([drug, "true" if flags[drug] else "false"])
    return listing, universe_path
