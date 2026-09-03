"""Tests for the phenotype endpoints.

These routes read the committed reference tables rather than PostgreSQL, so the tests
point them at a temporary directory holding a handful of hand-written rows. No network, no
database, and no dependence on whether anyone has run the builder.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mva.viz import phenotype
from mva.viz.app import create_app

SCORES = (
    "term_set\tgenes_considered\tgene_symbol\tentrez_id\trank\tscore\tforward\treverse\t"
    "curated_terms\tbest_term\tbest_common_ancestor\tbest_ic\n"
    "proband-only\t5267\tBUB1B\t701\t6\t0.454802\t2.112318\t0.548150\t112\t"
    "HP:0002859\tHP:0002859\t5.524694\n"
    "proband-only\t5267\tNOBODY\t\t9\t0.100000\t0.100000\t0.100000\t3\t\t\t\n"
    "with-parental\t5267\tBUB1B\t701\t14\t0.360930\t1.848278\t0.548150\t112\t"
    "HP:0002859\tHP:0002859\t5.524694\n"
)

TERM_IC = (
    "hpo_id\tname\tdepth\tgene_count\tinformation_content\n"
    "HP:0002859\tRhabdomyosarcoma\t7\t21\t5.524694\n"
    "HP:0200067\tRecurrent spontaneous abortion\t4\t12\t6.081000\n"
)


@pytest.fixture
def tables(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "hpo_gene_scores.tsv").write_text(SCORES, encoding="utf-8")
    (tmp_path / "hpo_term_ic.tsv").write_text(TERM_IC, encoding="utf-8")
    monkeypatch.setattr(phenotype, "DEFAULT_ROOT", tmp_path)
    return tmp_path


@pytest.fixture
def client(tables: Path) -> TestClient:
    return TestClient(create_app())


def test_the_terms_endpoint_marks_which_term_is_the_parents(client: TestClient) -> None:
    """Seven features are the child's; one is the parents' history and must be visible."""
    data = client.get("/api/phenotype/terms").json()["data"]
    parental = [term for term in data["terms"] if not term["proband"]]
    assert [term["hpo_id"] for term in parental] == ["HP:0200067"]
    assert len(data["terms"]) == 8


def test_the_terms_endpoint_serves_both_readings(client: TestClient) -> None:
    sizes = {entry["name"]: entry["size"] for entry in data_sets(client)}
    assert sizes == {"with-parental": 8, "proband-only": 7}


def data_sets(client: TestClient) -> list[dict]:
    return client.get("/api/phenotype/terms").json()["data"]["sets"]


def test_absent_features_are_served_but_never_scored(client: TestClient) -> None:
    """HPO cannot say "asked and not present", so these are shown, not ranked."""
    absent = client.get("/api/phenotype/terms").json()["data"]["notably_absent"]
    assert {entry["hpo_id"] for entry in absent} == {"HP:0000252", "HP:0001249"}


def test_the_population_comes_from_the_table_not_from_the_highest_rank(
    client: TestClient,
) -> None:
    """Genes scoring zero are unwritten, so the row count understates what a rank beat."""
    data = client.get("/api/phenotype/genes").json()["data"]
    assert data["considered"] == 5267
    assert data["scored"] == 2


def test_panel_membership_is_marked_but_never_filtered_on(client: TestClient) -> None:
    """The flag exists so agreement is visible; the ranking never saw the panel."""
    rows = client.get("/api/phenotype/genes").json()["data"]["rows"]
    by_gene = {row["gene"]: row for row in rows}
    assert by_gene["BUB1B"]["in_panel"] is True
    assert by_gene["NOBODY"]["in_panel"] is False


def test_an_empty_best_match_comes_back_as_null_rather_than_zero(client: TestClient) -> None:
    rows = client.get("/api/phenotype/genes").json()["data"]["rows"]
    nobody = next(row for row in rows if row["gene"] == "NOBODY")
    assert nobody["best_term"] is None
    assert nobody["best_ic"] is None
    assert nobody["entrez_id"] is None


def test_the_limit_is_honoured(client: TestClient) -> None:
    assert len(client.get("/api/phenotype/genes?limit=1").json()["data"]["rows"]) == 1


def test_an_unknown_term_set_is_refused_and_names_the_real_ones(client: TestClient) -> None:
    response = client.get("/api/phenotype/genes?term_set=nonsense")
    assert response.status_code == 422
    assert "proband-only" in response.json()["detail"]


def test_one_gene_carries_both_term_sets_and_the_movement_between_them(
    client: TestClient,
) -> None:
    data = client.get("/api/phenotype/gene?symbol=bub1b").json()["data"]
    assert data["gene"] == "BUB1B"
    assert data["delta"] == {"with_parental": 14, "proband_only": 6, "moved": 8}


def test_an_uncurated_gene_says_so_rather_than_returning_an_empty_ranking(
    client: TestClient,
) -> None:
    """Missing curation is missing knowledge, and the message has to say that."""
    response = client.get("/api/phenotype/gene?symbol=CEP192")
    assert response.status_code == 404
    assert "absence of knowledge" in response.json()["detail"]


def test_the_delta_endpoint_reports_every_panel_gene_including_uncurated_ones(
    client: TestClient,
) -> None:
    data = client.get("/api/phenotype/delta").json()["data"]
    genes = {row["gene"]: row for row in data["rows"]}
    assert set(genes) == set(phenotype.PANEL)
    assert genes["BUB1B"]["moved"] == 8
    assert genes["CEP192"]["curated"] is False
    assert genes["CEP192"]["moved"] is None


def test_the_delta_endpoint_names_the_term_it_is_about(client: TestClient) -> None:
    data = client.get("/api/phenotype/delta").json()["data"]
    assert data["parental_term"] == "HP:0200067"
    assert data["parental_label"] == "Recurrent spontaneous abortion"


def test_a_missing_reference_table_names_the_command_that_writes_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A 503 that does not say how to fix it is a dead end for whoever hits it."""
    monkeypatch.setattr(phenotype, "DEFAULT_ROOT", tmp_path / "absent")
    response = TestClient(create_app(), raise_server_exceptions=False).get("/api/phenotype/genes")
    assert response.status_code == 503
    assert "build_phenotype_data.py" in response.json()["detail"]


def test_every_response_carries_the_standard_envelope(client: TestClient) -> None:
    body = client.get("/api/phenotype/genes").json()
    assert set(body) >= {"data", "cached_at", "source"}
    assert body["source"] == phenotype.SOURCE
