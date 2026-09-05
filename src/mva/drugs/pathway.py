"""Seed targets → the full target set, by walking the affected protein's pathways.

The card names a few dozen **seed** genes per direction: the ones a human already thought
of. That list is where the bias lives. The pathway walk is the correction — it asks
Reactome which curated pathways contain the affected protein, keeps the ones whose name
matches the mechanism, and adds *every* protein in them as a ``pathway`` target.

The rule, stated once so it can be criticised:

    Take the card's UniProt accession. Ask Reactome for the lower-level pathways
    containing it. Keep a pathway whose ``displayName`` matches :data:`PATHWAY_PATTERN`.
    Every human gene product participating in a kept pathway becomes a target with role
    ``pathway``.

:data:`PATHWAY_PATTERN` is the only case-shaped thing here and it is a *parameter*, not a
constant embedded in the logic: :func:`expand` takes ``pattern``. The default reads the
mechanism words that describe this class of disease (checkpoint, kinetochore, mitotic);
another card passes its own. A seed target keeps role ``seed`` even when a pathway also
contains it, because a seed carries a direction id and a pathway member does not.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from .mechanism import MechanismCard
from .sources import reactome

__all__ = ["PATHWAY_PATTERN", "PathwayRow", "TargetRow", "expand", "rule_text"]

#: The default pathway-name filter. Case-insensitive, matched against ``displayName``.
PATHWAY_PATTERN = re.compile(r"checkpoint|kinetochore|mitotic", re.IGNORECASE)


@dataclass(frozen=True)
class TargetRow:
    """One gene to look for drugs against, and why it is in the set."""

    symbol: str
    role: str
    direction_ids: tuple[str, ...] = ()
    pathways: tuple[str, ...] = ()
    uniprot: str | None = None


@dataclass(frozen=True)
class PathwayRow:
    """One Reactome pathway the walk considered, kept or not, and how big it was."""

    st_id: str
    display_name: str
    matched: bool
    n_participants: int = 0


@dataclass
class Expansion:
    """What :func:`expand` produced: the target set, and the pathways it walked."""

    targets: list[TargetRow] = field(default_factory=list)
    pathways: list[PathwayRow] = field(default_factory=list)

    @property
    def seeds(self) -> list[TargetRow]:
        return [t for t in self.targets if t.role == "seed"]

    @property
    def members(self) -> list[TargetRow]:
        return [t for t in self.targets if t.role == "pathway"]


def rule_text(pattern: re.Pattern[str]) -> str:
    """The expansion rule as one sentence, for the provenance manifest."""
    return (
        "Seed targets are the union of the card's per-direction seed_targets, in card "
        "order. Pathway targets are every human ReferenceGeneProduct participating in a "
        "Reactome pathway that (a) contains the card's UniProt accession, per "
        "/data/mapping/UniProt/{acc}/pathways?species=9606, and (b) whose displayName "
        f"matches /{pattern.pattern}/i. A gene that is already a seed keeps role 'seed'. "
        "The pattern is a parameter of the expansion, not a constant: a different "
        "mechanism card passes its own."
    )


def expand(
    card: MechanismCard,
    fetcher: object,
    *,
    pattern: re.Pattern[str] = PATHWAY_PATTERN,
    progress: Callable[[str], None] | None = None,
) -> Expansion:
    """Build the target set for one card. ``fetcher`` is a :class:`~mva.drugs.cache.Fetcher`.

    Seeds come first, in card order, then pathway members in the order Reactome returned
    them. That ordering is stable across runs, so a diff between two snapshots is a real
    change and not a re-shuffle.
    """
    say = progress or (lambda _line: None)
    result = Expansion()
    seen: dict[str, None] = {}

    for symbol in card.seed_targets:
        seen.setdefault(symbol, None)
        is_card_gene = symbol == card.gene_symbol
        result.targets.append(
            TargetRow(
                symbol=symbol,
                role="seed",
                direction_ids=card.directions_for(symbol),
                uniprot=card.uniprot if is_card_gene else None,
            )
        )
    say(f"seeds {len(result.targets)}")

    if not card.uniprot:
        say("card names no UniProt accession - no pathway expansion")
        return result

    found = reactome.pathways_for_uniprot(fetcher, card.uniprot)  # type: ignore[arg-type]
    say(f"reactome pathways containing {card.uniprot}: {len(found)}")

    members: dict[str, list[str]] = {}
    for entry in found:
        matched = bool(pattern.search(entry["displayName"]))
        if not matched:
            result.pathways.append(PathwayRow(entry["stId"], entry["displayName"], False))
            continue
        symbols = reactome.participants(fetcher, entry["stId"])  # type: ignore[arg-type]
        result.pathways.append(PathwayRow(entry["stId"], entry["displayName"], True, len(symbols)))
        for symbol in symbols:
            members.setdefault(symbol, []).append(entry["stId"])

    for symbol, pathways in members.items():
        if symbol in seen:
            continue
        seen[symbol] = None
        result.targets.append(TargetRow(symbol=symbol, role="pathway", pathways=tuple(pathways)))

    kept = sum(1 for p in result.pathways if p.matched)
    say(f"kept {kept}/{len(result.pathways)} pathways, {len(result.members)} new targets")
    return result
