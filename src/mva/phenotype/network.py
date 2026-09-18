"""Network proximity for the genes the symptom ranker cannot score at all.

The human-only ranker of entry 067 scores a gene only if somebody has curated a phenotype
for it. Full hiPHIVE never leaves a gene unscored: a random walk over the protein
interaction network gives an uncurated gene a proximity score to the genes that *are*
curated (Smedley 2015, p. 2007-2008). The 741 MB hiPHIVE matrix was declined as too large
for this machine, so this module does the small version of the same idea: ask STRING for
the interaction partners of the top-scoring genes, and score an uncurated gene by how
strongly it connects to them.

**Deliberately kept out of** :mod:`mva.phenotype.prioritise`. That module is the
human-only ranker and its output is a phenotype claim; this one mixes in a second,
weaker kind of evidence. Keeping them apart is what lets the report say which tier a gene
came from and what that tier is worth.

The network is a **third tier**, never a promotion into the scored ranking: a gene here
has no phenotype evidence, only a neighbour that has some.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

#: STRING's REST base. Versioned in the URL by STRING itself; the release actually reached
#: is recorded by the caller in its methodology entry, never assumed from this constant.
STRING_BASE_URL = "https://string-db.org/api"

#: NCBI taxon id for human.
HUMAN = 9606

#: STRING's combined score runs 0-1000. Its own "high confidence" cut is 700, which is the
#: one used here so the tier is built from edges STRING itself would defend.
HIGH_CONFIDENCE = 700


@dataclass(frozen=True)
class Edge:
    """One interaction, as STRING reports it."""

    source: str
    target: str
    #: STRING's combined score, 0-1000.
    score: int


@dataclass(frozen=True)
class Neighbour:
    """One uncurated gene, and how strongly it sits beside the scored ones."""

    symbol: str
    #: Sum of the edge scores to seed genes, scaled to 0-1 by the best possible tie to a
    #: single seed. A sum, not a maximum: a gene wired to three seeds is closer to the
    #: phenotype's neighbourhood than one wired to a single seed just as strongly.
    proximity: float
    partners: tuple[str, ...]

    @property
    def degree(self) -> int:
        return len(self.partners)


def neighbours(
    edges: Iterable[Edge],
    seeds: Sequence[str],
    *,
    exclude: Iterable[str] = (),
    minimum_score: int = HIGH_CONFIDENCE,
) -> tuple[Neighbour, ...]:
    """Score every non-seed gene by its high-confidence ties to ``seeds``.

    ``exclude`` is every gene that already has a phenotype score: this tier exists for the
    genes the ranker could not place, and a curated gene appearing here would be a second,
    weaker score for a gene that already has a better one.
    """
    seed_set = {s.upper() for s in seeds}
    skip = seed_set | {s.upper() for s in exclude}
    totals: dict[str, list[Edge]] = {}
    for edge in edges:
        if edge.score < minimum_score:
            continue
        for gene, partner in ((edge.source, edge.target), (edge.target, edge.source)):
            if partner.upper() in seed_set and gene.upper() not in skip:
                totals.setdefault(gene, []).append(edge)
    scale = float(len(seed_set) * 1000) or 1.0
    scored = [
        Neighbour(
            symbol=gene,
            proximity=sum(e.score for e in found) / scale,
            partners=tuple(sorted({(e.target if e.source == gene else e.source) for e in found})),
        )
        for gene, found in totals.items()
    ]
    scored.sort(key=lambda n: (-n.proximity, n.symbol))
    return tuple(scored)


def parse_string_network(payload: Iterable[Mapping[str, object]]) -> tuple[Edge, ...]:
    """Read STRING's ``network`` JSON rows into edges.

    STRING answers with ``preferredName_A``/``preferredName_B`` and a ``score`` in 0-1.
    Rescaled to STRING's own 0-1000 integer here, so :data:`HIGH_CONFIDENCE` means the
    same number a STRING user would type into the web interface.
    """
    edges: list[Edge] = []
    for row in payload:
        source = str(row.get("preferredName_A", "") or "")
        target = str(row.get("preferredName_B", "") or "")
        if not source or not target or source == target:
            continue
        raw = row.get("score", 0) or 0
        if not isinstance(raw, (int, float, str)):
            continue
        try:
            score = float(raw)
        except (TypeError, ValueError):
            continue
        edges.append(Edge(source=source, target=target, score=round(score * 1000)))
    return tuple(edges)


def network_url(seeds: Sequence[str], *, base: str = STRING_BASE_URL, species: int = HUMAN) -> str:
    """The sub-network **among** the seeds — edges where both ends are already seeds.

    Useful for drawing the seed set, and useless for finding new genes: by construction it
    returns no gene that was not asked for. Step 1's network tier called this endpoint and
    produced zero rows for exactly that reason. Use :func:`partners_url` to reach outward.
    """
    identifiers = "%0d".join(seeds)
    return f"{base}/json/network?identifiers={identifiers}&species={species}"


def partners_url(
    seeds: Sequence[str],
    *,
    base: str = STRING_BASE_URL,
    species: int = HUMAN,
    limit: int = 0,
    required_score: int = HIGH_CONFIDENCE,
) -> str:
    """The seeds' interaction **partners** — the edges that leave the seed set.

    This is the request a proximity tier actually needs: it returns genes that were not
    asked about, which is the only way an uncurated gene can enter. ``limit`` caps partners
    per seed (0 = STRING's own default), and ``required_score`` is applied server-side as
    well as in :func:`neighbours`, so a large seed set does not download edges it will drop.
    """
    identifiers = "%0d".join(seeds)
    query = f"identifiers={identifiers}&species={species}&required_score={required_score}"
    if limit:
        query += f"&limit={limit}"
    return f"{base}/json/interaction_partners?{query}"
