"""The step-7 graph walk on a tiny synthetic graph: paths, weights, ranking, approval, PrimeKG.

Every gene, drug and disease name here is invented; the graph has eight nodes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mva.drugs import graph_walk, primekg, walk_table
from mva.drugs.graph_walk import Edge, Graph, Node

pytest.importorskip("duckdb")


def _graph() -> Graph:
    nodes = [
        Node("d", "disease", "Disease X"),
        Node("g1", "gene/protein", "GENEA"),
        Node("g2", "gene/protein", "GENEB"),
        Node("g3", "gene/protein", "GENEC"),
        Node("p", "pathway", "Pathway P"),
        Node("r1", "drug", "Alphamab", source_id="DB0001"),
        Node("r2", "drug", "Betanib Hydrochloride", source_id="DB0002"),
        Node("r3", "drug", "Gammastat", source_id="DB0003"),
    ]
    edges = [
        Edge("disease_protein", "d", "g1"),
        Edge("drug_protein", "r1", "g1"),  # direct
        Edge("protein_protein", "g1", "g2"),
        Edge("drug_protein", "r2", "g2"),  # via ppi
        Edge("pathway_protein", "p", "g1"),
        Edge("pathway_protein", "p", "g3"),
        Edge("drug_protein", "r2", "g3"),  # via pathway
        Edge("drug_protein", "r3", "g3"),
    ]
    return Graph.build(nodes, edges)


def test_walk_enumerates_each_metapath_and_weights_by_inverse_degree() -> None:
    result = graph_walk.walk(_graph(), ["d"])
    shapes = sorted((p.metapath, p.keys) for p in result.paths)
    assert shapes == [
        ("direct", ("d", "g1", "r1")),
        ("pathway", ("d", "g1", "p", "g3", "r2")),
        ("pathway", ("d", "g1", "p", "g3", "r3")),
        ("ppi", ("d", "g1", "g2", "r2")),
    ]
    # g1 touches d, r1, g2, p -> degree 4; g2 degree 2; p degree 2; g3 degree 3.
    ppi = next(p for p in result.paths if p.metapath == "ppi")
    assert ppi.weight == pytest.approx(1 / 4 * 1 / 2)
    via_pathway = next(p for p in result.paths if p.keys[-1] == "r3")
    assert via_pathway.weight == pytest.approx(1 / 4 * 1 / 2 * 1 / 3)


def test_ranking_sums_paths_and_breaks_ties_on_name() -> None:
    ranking = graph_walk.walk(_graph(), ["d"]).ranking()
    assert [r.drug.name for r in ranking] == ["Alphamab", "Betanib Hydrochloride", "Gammastat"]
    betanib = ranking[1]
    assert betanib.paths == 2
    assert betanib.by_metapath == {"direct": 0, "ppi": 1, "pathway": 1}
    assert betanib.score == pytest.approx(1 / 8 + 1 / 24)
    assert betanib.targets == ("GENEB", "GENEC")
    # Same graph, same answer: the walk is deterministic.
    again = graph_walk.walk(_graph(), ["d"]).ranking()
    assert [(r.drug.key, r.score) for r in again] == [(r.drug.key, r.score) for r in ranking]


def test_damping_zero_is_a_plain_path_count() -> None:
    ranking = graph_walk.walk(_graph(), ["d"], damping=0.0).ranking()
    assert {r.drug.name: r.score for r in ranking}["Betanib Hydrochloride"] == 2.0


def test_unknown_source_is_refused() -> None:
    with pytest.raises(KeyError):
        graph_walk.walk(_graph(), ["nope"])


def test_keep_approved_stops_at_keep_and_folds_salts() -> None:
    ranking = graph_walk.walk(_graph(), ["d"]).ranking()
    asked: list[str] = []

    def label(name: str) -> dict[str, object]:
        asked.append(name)
        return {"has_label": name != "ALPHAMAB", "generic_name": name}

    kept, checked = walk_table.keep_approved(ranking, label, keep=1)
    assert [k.row.drug.name for k in kept] == ["Betanib Hydrochloride"]
    assert (checked, kept[0].rank_all) == (2, 2)
    assert asked == ["ALPHAMAB", "BETANIB"]


def test_rows_flag_candidates_and_standard_of_care() -> None:
    result = graph_walk.walk(_graph(), ["d"])
    kept, _ = walk_table.keep_approved(
        result.ranking(), lambda n: {"has_label": True, "generic_name": n}, keep=3
    )
    rows = walk_table.rows(result, kept, candidates={"BETANIB"}, standard_of_care=["gammastat"])
    flags = {r["drug_name"]: (r["in_drug_candidates"], r["standard_of_care"]) for r in rows}
    assert flags["Betanib Hydrochloride"] == ("true", "false")
    assert flags["Gammastat"] == ("false", "true")
    assert rows[1]["via_disease_genes"] == "GENEA:2"
    paths = walk_table.path_rows(result, kept, top=3)
    assert sum(1 for p in paths if p["drug_name"] == "Betanib Hydrochloride") == 2


def _write_kg(tmp_path: Path) -> Path:
    import duckdb

    disease = ("d1", "disease", "Disease X", "MONDO_grouped", "13582_9759")
    gene_a = ("g1", "gene/protein", "GENEA", "NCBI", "1")
    gene_z = ("g2", "gene/protein", "GENEZ", "NCBI", "2")
    stature = ("h1", "effect/phenotype", "Short stature", "HPO", "4322")
    rows = [
        ("disease_protein", *disease, *gene_a),
        ("disease_phenotype_positive", *stature, *disease),
        ("pathway_protein", *gene_a, "p1", "pathway", "Pathway P", "REACTOME", "R-1"),
        ("pathway_protein", *gene_z, "p2", "pathway", "Pathway Q", "REACTOME", "R-2"),
    ]
    path = tmp_path / "kg.parquet"
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE kg (relation VARCHAR, x_index VARCHAR, x_type VARCHAR, x_name VARCHAR, "
        "x_source VARCHAR, x_id VARCHAR, y_index VARCHAR, y_type VARCHAR, y_name VARCHAR, "
        "y_source VARCHAR, y_id VARCHAR)"
    )
    con.executemany("INSERT INTO kg VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    con.execute(f"COPY kg TO '{path}' (FORMAT parquet)")
    return path


def test_primekg_resolves_a_grouped_mondo_member_and_checks_phenotypes(tmp_path: Path) -> None:
    kg = _write_kg(tmp_path)
    nodes = primekg.disease_nodes(kg, "MONDO:0009759")
    assert [n.key for n in nodes] == ["d1"]
    assert nodes[0].as_dict()["mondo_members"] == ["MONDO:0013582", "MONDO:0009759"]
    assert primekg.disease_nodes(kg, "MONDO:0000975") == []  # a prefix is not a member
    assert primekg.disease_genes(kg, ["d1"]) == ["GENEA"]
    checks = primekg.phenotype_check(kg, ["d1"], ["HP:0004322", "HP:0002859"])
    assert [(c.node_name, c.linked) for c in checks] == [("Short stature", True), (None, False)]
    assert primekg.shared_pathways(kg, "GENEA", ["GENEZ"]) == []


def test_mondo_number_rejects_other_curies() -> None:
    assert primekg.mondo_number("MONDO:0009759") == "9759"
    with pytest.raises(ValueError):
        primekg.mondo_number("HP:0009759")
