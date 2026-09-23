"""A deterministic walk over a knowledge graph: disease → gene → (pathway | gene) → drug.

*Plain words.* A **knowledge graph** is a table of typed edges between typed nodes — think
of a property graph in a graph database, where ``disease —disease_protein— gene`` and
``drug —drug_protein— gene`` are two edge labels. This module asks one question of it:
*starting from the disease, which drugs can be reached in a few hops, and by how many
distinct routes?*

A **metapath** (a path template: the sequence of edge and node types a route must follow)
fixes the hop shape. Three are walked by default:

| name | route |
|---|---|
| ``direct`` | disease → gene → drug (a drug targets the disease gene itself) |
| ``ppi`` | disease → gene → gene → drug (through one protein–protein interaction) |
| ``pathway`` | disease → gene → pathway → gene → drug (through a shared pathway) |

**Score** = the sum over a drug's paths of ∏ ``degree(v) ** -damping`` for every node *v*
strictly between the disease and the drug. This is **degree-weighted path count** (DWPC,
Himmelstein 2015): a route through a hub protein that touches 2,000 neighbours counts for
less than one through a specific partner, so a drug is not ranked high merely because it
sits next to a hub. ``damping = 1`` is plain inverse degree.

Deterministic by construction: neighbours are visited in sorted order, ties in score break
on the drug name, and no randomness is used anywhere. Every path is kept, so every score
can be printed as the sum it is.

Pure: no I/O. :mod:`mva.drugs.primekg` builds the :class:`Graph` from PrimeKG.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

__all__ = [
    "DEFAULT_METAPATHS",
    "Edge",
    "Graph",
    "Metapath",
    "Node",
    "Path",
    "Ranked",
    "WalkResult",
    "overlap",
    "walk",
]


@dataclass(frozen=True)
class Node:
    """One graph node. ``key`` is the graph's own id; ``source_id`` is the upstream one."""

    key: str
    type: str
    name: str
    source: str = ""
    source_id: str = ""


@dataclass(frozen=True)
class Edge:
    """One undirected typed edge between two node keys."""

    relation: str
    a: str
    b: str


@dataclass(frozen=True)
class Metapath:
    """A named hop template: ``hops[i] = (relation, node type reached)``."""

    name: str
    hops: tuple[tuple[str, str], ...]


DEFAULT_METAPATHS: tuple[Metapath, ...] = (
    Metapath("direct", (("disease_protein", "gene/protein"), ("drug_protein", "drug"))),
    Metapath(
        "ppi",
        (
            ("disease_protein", "gene/protein"),
            ("protein_protein", "gene/protein"),
            ("drug_protein", "drug"),
        ),
    ),
    Metapath(
        "pathway",
        (
            ("disease_protein", "gene/protein"),
            ("pathway_protein", "pathway"),
            ("pathway_protein", "gene/protein"),
            ("drug_protein", "drug"),
        ),
    ),
)


@dataclass
class Graph:
    """An undirected multi-relation graph held as ``node → relation → neighbours``."""

    nodes: dict[str, Node] = field(default_factory=dict)
    adjacency: dict[str, dict[str, set[str]]] = field(default_factory=dict)

    @classmethod
    def build(cls, nodes: Iterable[Node], edges: Iterable[Edge]) -> Graph:
        graph = cls()
        for node in nodes:
            graph.nodes[node.key] = node
        for edge in edges:
            if edge.a == edge.b:
                continue
            graph.adjacency.setdefault(edge.a, {}).setdefault(edge.relation, set()).add(edge.b)
            graph.adjacency.setdefault(edge.b, {}).setdefault(edge.relation, set()).add(edge.a)
        return graph

    def neighbours(self, key: str, relation: str, node_type: str) -> list[str]:
        """Neighbours over one relation, of one type, in sorted order (determinism)."""
        found = self.adjacency.get(key, {}).get(relation, set())
        return sorted(k for k in found if self.nodes[k].type == node_type)

    def degree(self, key: str) -> int:
        """Distinct neighbours over every relation the graph was built with."""
        seen: set[str] = set()
        for group in self.adjacency.get(key, {}).values():
            seen |= group
        return len(seen)


@dataclass(frozen=True)
class Path:
    """One route from a source disease to a drug, with its weight."""

    metapath: str
    keys: tuple[str, ...]
    weight: float

    @property
    def drug(self) -> str:
        return self.keys[-1]

    def render(self, graph: Graph) -> str:
        """``MVA1 → BUB1B → Mitotic Spindle Checkpoint → CDC20 → Drug (w=…)``."""
        names = " → ".join(graph.nodes[k].name for k in self.keys)
        return f"[{self.metapath}] {names}  (w={self.weight:.3g})"


@dataclass(frozen=True)
class Ranked:
    """One drug's row: its score, its path counts per metapath, the genes it is reached by."""

    drug: Node
    score: float
    paths: int
    by_metapath: dict[str, int]
    targets: tuple[str, ...]
    best: Path


@dataclass
class WalkResult:
    """Every path the walk found, and the drugs ranked by score."""

    graph: Graph
    sources: tuple[str, ...]
    damping: float
    metapaths: tuple[Metapath, ...]
    paths: list[Path]

    def paths_for(self, drug_key: str) -> list[Path]:
        """Every path ending at one drug, heaviest first, then by the path's names."""
        mine = [p for p in self.paths if p.drug == drug_key]
        return sorted(mine, key=lambda p: (-p.weight, self._names(p)))

    def ranking(self) -> list[Ranked]:
        """Drugs by descending score; ties break on drug name, then key."""
        grouped: dict[str, list[Path]] = defaultdict(list)
        for path in self.paths:
            grouped[path.drug].append(path)
        rows: list[Ranked] = []
        for key, paths in grouped.items():
            counts = {m.name: 0 for m in self.metapaths}
            for path in paths:
                counts[path.metapath] += 1
            best = min(paths, key=lambda p: (-p.weight, self._names(p)))
            targets = sorted({self.graph.nodes[p.keys[-2]].name for p in paths})
            rows.append(
                Ranked(
                    drug=self.graph.nodes[key],
                    score=sum(p.weight for p in paths),
                    paths=len(paths),
                    by_metapath=counts,
                    targets=tuple(targets),
                    best=best,
                )
            )
        return sorted(rows, key=lambda r: (-r.score, r.drug.name, r.drug.key))

    def _names(self, path: Path) -> tuple[str, ...]:
        return tuple(self.graph.nodes[k].name for k in path.keys)


def _extend(
    graph: Graph, prefix: tuple[str, ...], hops: tuple[tuple[str, str], ...]
) -> Iterator[tuple[str, ...]]:
    if not hops:
        yield prefix
        return
    relation, node_type = hops[0]
    for nxt in graph.neighbours(prefix[-1], relation, node_type):
        if nxt in prefix:  # simple paths only: no node visited twice
            continue
        yield from _extend(graph, (*prefix, nxt), hops[1:])


def walk(
    graph: Graph,
    sources: Iterable[str],
    *,
    metapaths: tuple[Metapath, ...] = DEFAULT_METAPATHS,
    damping: float = 1.0,
) -> WalkResult:
    """Enumerate every simple path along each metapath from each source node."""
    starts = tuple(sorted(set(sources)))
    missing = [s for s in starts if s not in graph.nodes]
    if missing:
        raise KeyError(f"source node(s) not in the graph: {missing}")
    found: list[Path] = []
    for source in starts:
        for metapath in metapaths:
            for keys in _extend(graph, (source,), metapath.hops):
                weight = 1.0
                for inner in keys[1:-1]:
                    weight *= graph.degree(inner) ** -damping
                found.append(Path(metapath.name, keys, weight))
    return WalkResult(graph, starts, damping, metapaths, found)


def overlap(a: Iterable[str], b: Iterable[str]) -> list[str]:
    """The names two top-k lists share, sorted. The caller normalises names first."""
    return sorted(set(a) & set(b))
