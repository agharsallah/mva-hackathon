"""The mechanism card: the Track 1 → Track 2 hand-off, parsed.

A card is one JSON file (``ressources/track2/mechanism.json`` for this case) naming the
gene, the protein, the disease, the affected pathway and a list of **repurposing
directions** — each a hypothesis about how to compensate for the broken mechanism, with a
list of seed gene symbols to look for drugs against.

Nothing in this package hard-codes any of those values. Everything downstream reads them
off the card, so pointing the CLI at a different card runs the same pipeline on a
different case. That is the whole point of the indirection.

The card is coordinate-free by construction — it names a gene and a consequence class,
never a genomic position — and this module never adds one.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = ["DEFAULT_CARD", "Direction", "MechanismCard", "load"]

#: Where the card lives for this case. A caller may point anywhere else.
DEFAULT_CARD = Path("ressources/track2/mechanism.json")

#: A parenthetical aside, and everything after it, in a free-text field. ``tumour_context``
#: is written as ``"rhabdomyosarcoma (HP:0002859), a reported MVA1 malignancy (PMID:…)"``;
#: the searchable term is what stands before the first bracket or comma.
_ASIDE = re.compile(r"[(,].*$", re.DOTALL)

#: A trailing gloss on a pathway name: ``"spindle assembly checkpoint (SAC) - mitotic …"``
#: searches far better as its head phrase than as the whole sentence.
_GLOSS = re.compile(r"\s+[-–—]\s+.*$", re.DOTALL)


@dataclass(frozen=True)
class Direction:
    """One repurposing hypothesis: a name, why it is worth trying, and where to look."""

    id: str
    name: str
    rationale: str
    seed_targets: tuple[str, ...]

    @property
    def query_phrase(self) -> str:
        """The name as a literature query: slash-separated alternatives, OR'd.

        ``"SAC reinforcement / chromosomal-instability reduction"`` becomes
        ``"(SAC reinforcement OR chromosomal-instability reduction)"``. Segments are left
        unquoted so PubMed applies its own term translation to each; a single-segment name
        comes back wrapped in brackets and otherwise unchanged.
        """
        parts = [part.strip() for part in self.name.split("/") if part.strip()]
        return "(" + " OR ".join(parts) + ")" if parts else ""


@dataclass(frozen=True)
class MechanismCard:
    """One parsed card. Every accessor is derived; the raw payload is kept for provenance."""

    path: Path
    raw: dict[str, Any]

    # ── identity ────────────────────────────────────────────────────────────────────

    @property
    def version(self) -> int:
        return int(self.raw.get("version", 0))

    @property
    def gene_symbol(self) -> str:
        return str(self._gene.get("symbol", ""))

    @property
    def uniprot(self) -> str | None:
        value = self._gene.get("uniprot")
        return str(value) if value else None

    @property
    def ensembl_gene_id(self) -> str | None:
        value = self._gene.get("ensembl_gene_id")
        return str(value) if value else None

    @property
    def protein(self) -> str:
        return str(self._gene.get("protein", ""))

    # ── the case ────────────────────────────────────────────────────────────────────

    @property
    def disease_name(self) -> str:
        return str(self._case.get("disease", ""))

    @property
    def disease_query(self) -> str:
        """The disease as a search string: the name with any parenthetical gloss dropped."""
        return _ASIDE.sub("", self.disease_name).strip()

    @property
    def tumour_context(self) -> str | None:
        """The presenting malignancy as one searchable term, or ``None`` when absent."""
        value = self._case.get("tumour_context")
        if not value:
            return None
        term = _ASIDE.sub("", str(value)).strip()
        return term or None

    @property
    def pathway(self) -> str:
        """The affected pathway, trimmed to its head phrase for use as a query term."""
        raw = str(self.raw.get("mechanism", {}).get("pathway", ""))
        return _ASIDE.sub("", _GLOSS.sub("", raw)).strip()

    @property
    def mechanism_class(self) -> str:
        return str(self.raw.get("mechanism", {}).get("class", ""))

    @property
    def literature_pmids(self) -> tuple[str, ...]:
        """The PMIDs the card already cites, in card order."""
        entries = self.raw.get("mechanism", {}).get("literature", [])
        return tuple(str(e["pmid"]) for e in entries if isinstance(e, dict) and e.get("pmid"))

    # ── the directions ──────────────────────────────────────────────────────────────

    @property
    def directions(self) -> tuple[Direction, ...]:
        out: list[Direction] = []
        for entry in self.raw.get("repurposing_directions", []):
            if not isinstance(entry, dict):
                continue
            out.append(
                Direction(
                    id=str(entry.get("id", "")),
                    name=str(entry.get("name", "")),
                    rationale=str(entry.get("rationale", "")),
                    seed_targets=tuple(str(s) for s in entry.get("seed_targets", []) if s),
                )
            )
        return tuple(out)

    @property
    def seed_targets(self) -> tuple[str, ...]:
        """The union of every direction's seed targets: first-seen order, deduped.

        Order is the card's, not alphabetical, so a re-run asks the APIs in the same
        sequence and the cache keys line up run to run.
        """
        seen: dict[str, None] = {}
        for direction in self.directions:
            for symbol in direction.seed_targets:
                seen.setdefault(symbol, None)
        return tuple(seen)

    def directions_for(self, symbol: str) -> tuple[str, ...]:
        """Which direction ids listed ``symbol`` as a seed."""
        return tuple(d.id for d in self.directions if symbol in d.seed_targets)

    # ── internals ───────────────────────────────────────────────────────────────────

    @property
    def _gene(self) -> dict[str, Any]:
        value = self.raw.get("gene", {})
        return value if isinstance(value, dict) else {}

    @property
    def _case(self) -> dict[str, Any]:
        value = self.raw.get("case", {})
        return value if isinstance(value, dict) else {}


def load(path: Path | str = DEFAULT_CARD) -> MechanismCard:
    """Read and parse one card. A missing or malformed file raises, never guesses."""
    where = Path(path)
    payload = json.loads(where.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"{where}: a mechanism card must be a JSON object")
    return MechanismCard(path=where, raw=payload)
