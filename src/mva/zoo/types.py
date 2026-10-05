"""The contracts every zoo module shares.

The zoo runs **frozen third-party models** as interchangeable lanes: nothing here is
trained. One record shape goes in, one score row comes out, and which model produced it
is a registry entry rather than a branch in the code.

Four shapes and one function:

* :class:`SequenceRecord` — the unit a model scores. One or more named chains plus free
  metadata, because what a lane needs varies: a protein language model reads a single
  chain, an interface predictor reads two, a structure predictor reads two and returns
  coordinates.
* :class:`ScoreRow` — one model's verdict on one record. ``score`` is the single summary
  number; anything vector-valued (per-residue probabilities, a contact map) goes in
  ``aux``.
* :class:`Coverage` — how much of a record set a model can score, by class.
* :class:`RemoteJob` — a tier-3 submission the workflow polls.
* :func:`item_id` — the stable content key.

The :class:`Adapter` protocol is what a model looks like to a caller: tier 1 and 2 score
locally, tier 3 submits a remote job and the caller collects it later.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypedDict

__all__ = [
    "Adapter",
    "Coverage",
    "RemoteJob",
    "ScoreRow",
    "SequenceRecord",
    "Tier",
    "item_id",
]

#: Inference tiers: 1 = precomputed table lookup, 2 = local CPU process, 3 = remote GPU.
Tier = Literal[1, 2, 3]


def item_id(*parts: str) -> str:
    """The stable key of one record: 16 hex chars of SHA-256 over ``parts`` joined by ``:``.

    Content-addressed on purpose. Two runs that build the same record from the same
    sequences agree on its id without coordinating, so a score cached by one run is a hit
    for the next, and a changed input is a different id rather than a silent overwrite.
    """
    text = ":".join(part.strip().upper() for part in parts)
    return hashlib.sha256(text.encode()).hexdigest()[:16]


class Chains(TypedDict, total=False):
    """The named chains of one record, as plain sequence strings.

    Named rather than positional because a lane asks for what it needs by name, and an
    interface model that silently swapped its two inputs would still run.
    """

    binder: str
    target: str


@dataclass(frozen=True)
class SequenceRecord:
    """One unit of work: named chains plus whatever a lane needs to know about them.

    ``meta`` is deliberately open. A record carries the identifiers, labels and grouping
    keys the surrounding analysis attached to it, and a lane reads only the keys it
    declares — so adding a field never breaks a lane that does not use it.
    """

    item_id: str
    chains: Chains = field(default_factory=Chains)
    meta: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def of(cls, chains: Chains, **meta: Any) -> SequenceRecord:
        """Build a record, deriving its id from the chain contents in a fixed order."""
        ordered = [f"{name}={chains[name]}" for name in sorted(chains)]  # type: ignore[literal-required]
        return cls(item_id=item_id(*ordered), chains=chains, meta=meta)


@dataclass(frozen=True)
class ScoreRow:
    """One model's score for one record.

    ``score`` is the model's primary number, oriented as the adapter defines it; ``aux``
    holds anything else it emitted — per-residue probability vectors, a contact map, a
    confidence. ``venue`` is where it ran (``laptop``, ``modal:<gpu>``); ``licence`` the
    model's terms; ``digest`` the weights or table digest the adapter read.

    ``digest`` is what makes a cached row trustworthy: a lane whose weights changed
    produces a different digest, so a stale score is visible rather than silently reused.
    """

    item_id: str
    model: str
    version: str
    score: float | None
    aux: dict[str, Any] = field(default_factory=dict)
    digest: str = ""
    venue: str = "laptop"
    licence: str = ""
    run_id: str = ""


@dataclass(frozen=True)
class Coverage:
    """How much of a record set one model can score, by class.

    A lane that scores 40% of the records is not a broken lane — it is a lane with a
    stated domain — so coverage is reported next to every result rather than hidden
    behind a filter.
    """

    model: str
    scored: int
    total: int
    by_class: dict[str, tuple[int, int]] = field(default_factory=dict)

    @property
    def fraction(self) -> float:
        return self.scored / self.total if self.total else 0.0


@dataclass(frozen=True)
class RemoteJob:
    """A tier-3 submission the caller polls: where it went and how to fetch the result."""

    model: str
    job_id: str
    venue: str
    submitted: int


class Adapter(Protocol):
    """What a model looks like to a caller.

    One module per model: a new lane is a new file plus a registry entry, never an edit to
    a shared one. ``catalogue_adjacent`` marks a model trained on the same public
    structures or complexes an evaluation is drawn from — such a lane is not excluded, but
    its agreement with the answer is reported separately, because it may be recall rather
    than prediction.
    """

    name: str
    version: str
    tier: Tier
    catalogue_adjacent: bool

    def coverage(self, records: Sequence[SequenceRecord]) -> Coverage: ...

    def score(self, records: Sequence[SequenceRecord]) -> Iterator[ScoreRow]:
        """Tier 1 and 2: score locally, yielding one row per record it can score."""
        ...

    def submit(self, records: Sequence[SequenceRecord]) -> RemoteJob:
        """Tier 3: send the chains and the ``item_id``, and nothing else."""
        ...
