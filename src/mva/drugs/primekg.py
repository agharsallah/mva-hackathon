"""PrimeKG, read with DuckDB: the graph, the disease node, the phenotype and pathway checks.

*Plain words.* PrimeKG (Chandak 2023, PMID 36732524) ships as one edge table, ``kg.csv``
(converted once to ``kg.parquet`` by ``tools/fetch_primekg.py``). Each row is one directed
copy of an undirected edge: ``relation, x_index, x_type, x_name, x_id, x_source`` and the same
six for ``y``. ``x_index`` is PrimeKG's own node key; ``x_id`` is the upstream identifier.

**How a MONDO id becomes a node.** PrimeKG *groups* near-identical MONDO diseases into one
node (``x_source = 'MONDO_grouped'``) and joins the member numbers with ``_`` in ``x_id``,
without the ``MONDO:`` prefix or leading zeros — ``MONDO:0009759`` is the member ``9759`` of
one such node. :func:`disease_nodes` matches the card's number against every member, so a
grouped and an ungrouped disease resolve the same way, and returns every match (normally
one). The caller records which node, and which other members came with it.

Every function takes the parquet path and the values it needs; nothing names a gene, a
disease or a drug. Returns plain values; :mod:`mva.drugs.graph_walk` does the walking.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .graph_walk import DEFAULT_METAPATHS, Edge, Graph, Metapath, Node

__all__ = [
    "DEFAULT_PARQUET",
    "DiseaseNode",
    "PhenotypeCheck",
    "disease_genes",
    "disease_nodes",
    "load_graph",
    "mondo_number",
    "phenotype_check",
    "shared_pathways",
]

#: Where ``tools/fetch_primekg.py`` writes the converted graph (gitignored).
DEFAULT_PARQUET = Path("build/primekg/kg.parquet")

_COLUMNS = "relation, {s}_index, {s}_type, {s}_name, {s}_source, {s}_id"


def _connect(parquet: Path) -> Any:
    import duckdb

    con = duckdb.connect()
    con.execute(f"CREATE VIEW kg AS SELECT * FROM read_parquet('{parquet}')")
    return con


def mondo_number(curie: str) -> str:
    """``MONDO:0009759`` → ``9759``: PrimeKG's spelling of a MONDO member."""
    head, _, tail = curie.partition(":")
    digits = tail if head.upper() == "MONDO" else curie
    if not digits.isdigit():
        raise ValueError(f"not a MONDO CURIE: {curie!r}")
    return str(int(digits))


def _hpo_number(curie: str) -> str:
    head, _, tail = curie.partition(":")
    if head.upper() != "HP" or not tail.isdigit():
        raise ValueError(f"not an HPO CURIE: {curie!r}")
    return str(int(tail))


@dataclass(frozen=True)
class DiseaseNode:
    """One PrimeKG disease node a MONDO id resolved to, and the members grouped with it."""

    key: str
    name: str
    source: str
    members: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "primekg_index": self.key,
            "name": self.name,
            "source": self.source,
            "mondo_members": [f"MONDO:{int(m):07d}" for m in self.members],
        }


def disease_nodes(parquet: Path, mondo: str) -> list[DiseaseNode]:
    """Every disease node whose ``x_id`` member list contains the MONDO number."""
    number = mondo_number(mondo)
    rows = (
        _connect(parquet)
        .execute(
            "SELECT DISTINCT x_index, x_name, x_source, x_id FROM kg "
            "WHERE x_type = 'disease' AND list_contains(string_split(x_id, '_'), ?) "
            "ORDER BY x_index",
            [number],
        )
        .fetchall()
    )
    return [DiseaseNode(r[0], r[1], r[2], tuple(r[3].split("_"))) for r in rows]


def disease_genes(parquet: Path, keys: Iterable[str]) -> list[str]:
    """The gene symbols a disease node links to through ``disease_protein``, sorted."""
    wanted = sorted(set(keys))
    rows = (
        _connect(parquet)
        .execute(
            "SELECT DISTINCT y_name FROM kg WHERE relation = 'disease_protein' "
            "AND x_type = 'disease' AND list_contains(?, x_index) ORDER BY y_name",
            [wanted],
        )
        .fetchall()
    )
    return [r[0] for r in rows]


def load_graph(parquet: Path, metapaths: tuple[Metapath, ...] = DEFAULT_METAPATHS) -> Graph:
    """The subgraph over exactly the relations the metapaths walk.

    Degrees are therefore measured over those relations only: a gene's ``drug_drug`` or
    ``anatomy_protein_present`` edges never dilute a walk that cannot use them.
    """
    relations = sorted({rel for m in metapaths for rel, _ in m.hops})
    con = _connect(parquet)
    sql = (
        f"SELECT {_COLUMNS.format(s='x')}, y_index, y_type, y_name, y_source, y_id "
        "FROM kg WHERE list_contains(?, relation)"
    )
    nodes: dict[str, Node] = {}
    edges: list[Edge] = []
    for rel, xk, xt, xn, xs, xi, yk, yt, yn, ys, yi in con.execute(sql, [relations]).fetchall():
        nodes.setdefault(xk, Node(xk, xt, xn, xs, xi))
        nodes.setdefault(yk, Node(yk, yt, yn, ys, yi))
        edges.append(Edge(rel, xk, yk))
    return Graph.build(nodes.values(), edges)


@dataclass(frozen=True)
class PhenotypeCheck:
    """One clinical HPO term against the graph: is it a node, and is it on the disease?"""

    hpo: str
    node_name: str | None
    linked: bool

    def as_dict(self) -> dict[str, Any]:
        return {"hpo": self.hpo, "primekg_node": self.node_name, "linked_to_disease": self.linked}


def phenotype_check(
    parquet: Path, disease_keys: Iterable[str], hpo_terms: Iterable[str]
) -> list[PhenotypeCheck]:
    """For each HPO term: its PrimeKG phenotype node (if any) and a positive disease edge."""
    con = _connect(parquet)
    keys = sorted(set(disease_keys))
    out: list[PhenotypeCheck] = []
    for term in hpo_terms:
        number = _hpo_number(term)
        found = con.execute(
            "SELECT DISTINCT x_name FROM kg WHERE x_type = 'effect/phenotype' AND x_id = ?",
            [number],
        ).fetchone()
        linked = con.execute(
            "SELECT count(*) FROM kg WHERE relation = 'disease_phenotype_positive' "
            "AND x_type = 'effect/phenotype' AND x_id = ? AND list_contains(?, y_index)",
            [number, keys],
        ).fetchone()
        out.append(PhenotypeCheck(term, found[0] if found else None, bool(linked and linked[0])))
    return out


def shared_pathways(parquet: Path, gene_a: str, genes_b: Iterable[str]) -> list[tuple[str, str]]:
    """``(pathway, gene_b)`` pairs where ``gene_a`` and a ``genes_b`` member share a pathway."""
    rows = (
        _connect(parquet)
        .execute(
            "SELECT DISTINCT a.y_name, b.x_name FROM kg a JOIN kg b ON a.y_index = b.y_index "
            "WHERE a.relation = 'pathway_protein' AND b.relation = 'pathway_protein' "
            "AND a.x_type = 'gene/protein' AND b.x_type = 'gene/protein' "
            "AND a.x_name = ? AND list_contains(?, b.x_name) ORDER BY 1, 2",
            [gene_a, sorted(set(genes_b))],
        )
        .fetchall()
    )
    return [(r[0], r[1]) for r in rows]
