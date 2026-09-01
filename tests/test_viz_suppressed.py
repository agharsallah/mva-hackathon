"""The suppressed-calls endpoint: two grains in one payload, and what it refuses to guess.

Mocked below the database exactly as ``test_viz_api.py`` mocks it: ``queries.fetch`` is
replaced, so a failure here means the route, the envelope or the gene validation is wrong,
never that PostgreSQL was unreachable.

Positions in this file are three-digit counters. They are not coordinates.
"""

import pytest
from fastapi.testclient import TestClient

from mva.viz import queries
from mva.viz.app import create_app
from mva.viz.cache import Cache

#: One row per (gene, FILTER value), PASS included — what `panel_filter_census` holds.
#: CEP57 is the case that matters twice: a real panel gene with nothing suppressed.
CENSUS = [
    {"gene": "BUB1B", "chrom": "15", "filter": "PASS", "is_pass": True, "n": 76,
     "n_gene_all": 80, "pct_of_gene": 95.0},
    {"gene": "BUB1B", "chrom": "15", "filter": "MQ40", "is_pass": False, "n": 3,
     "n_gene_all": 80, "pct_of_gene": 3.75},
    {"gene": "BUB1B", "chrom": "15", "filter": "LowQual;QD2", "is_pass": False, "n": 1,
     "n_gene_all": 80, "pct_of_gene": 1.25},
    {"gene": "CEP57", "chrom": "11", "filter": "PASS", "is_pass": True, "n": 13,
     "n_gene_all": 13, "pct_of_gene": 100.0},
    {"gene": "TRIP13", "chrom": "5", "filter": "PASS", "is_pass": True, "n": 6,
     "n_gene_all": 12, "pct_of_gene": 50.0},
    {"gene": "TRIP13", "chrom": "5", "filter": "MQ40", "is_pass": False, "n": 5,
     "n_gene_all": 12, "pct_of_gene": 41.67},
    {"gene": "TRIP13", "chrom": "5", "filter": "QD2", "is_pass": False, "n": 1,
     "n_gene_all": 12, "pct_of_gene": 8.33},
]


def record(gene: str, pos: int, filter_value: str, *, annotated: bool = True) -> dict:
    return {"gene": gene, "chrom": "5", "pos": pos, "ref": "A", "alt": "G",
            "qual": 62.8, "filter": filter_value, "gt": "0/1", "dp": 24, "gq": 91,
            "ad_ref": 18, "ad_alt": 6, "vaf": 0.25, "is_het": True,
            "annotated_alt": "G" if annotated else None,
            "rsid": None,
            "consequence": "missense_variant" if annotated else None,
            "impact": "MODERATE" if annotated else None,
            "gnomad_af": 0.0001 if annotated else None,
            "gnomad_af_grpmax": 0.0002 if annotated else None,
            "clin_sig": None, "annotated": annotated}


RECORDS = {
    "TRIP13": [record("TRIP13", 300, "MQ40"),
               record("TRIP13", 320, "QD2", annotated=False)],
    "BUB1B": [record("BUB1B", 500, "LowQual;QD2")],
    "CEP57": [],
}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    def fetch(settings, sql, params=None):
        if "panel_filter_census" in sql:
            return [dict(row) for row in CENSUS]
        if "panel_suppressed" in sql:
            gene = (params or [None])[0]
            if gene is None:
                return [dict(r) for rows in RECORDS.values() for r in rows]
            return [dict(r) for r in RECORDS.get(gene, [])]
        raise AssertionError(f"unexpected SQL: {sql}")

    monkeypatch.setattr(queries, "fetch", fetch)
    with TestClient(create_app(settings=None, cache=Cache(tmp_path),
                               origins=["http://localhost:5173"])) as running:
        yield running


class TestEnvelope:
    def test_it_answers_in_the_standard_envelope(self, client):
        body = client.get("/api/panel/suppressed").json()
        assert set(body) == {"data", "cached_at", "source"}
        assert body["cached_at"] is None, "20 rows off derived tables — cheap enough live"

    def test_the_source_names_both_tables_behind_the_payload(self, client):
        body = client.get("/api/panel/suppressed").json()
        assert body["source"] == ("pg.results.panel_filter_census + "
                                  "pg.results.panel_suppressed")

    def test_the_payload_carries_the_census_and_the_records(self, client):
        data = client.get("/api/panel/suppressed").json()["data"]
        assert set(data) == {"gene", "census", "records"}


class TestCensus:
    def test_the_census_is_the_whole_panel_even_when_one_gene_is_asked_for(self, client):
        """The chart compares genes, so narrowing the census would empty the comparison."""
        data = client.get("/api/panel/suppressed?gene=TRIP13").json()["data"]
        assert {row["gene"] for row in data["census"]} == {"BUB1B", "CEP57", "TRIP13"}

    def test_pass_travels_with_the_suppression_reasons(self, client):
        census = client.get("/api/panel/suppressed").json()["data"]["census"]
        trip13 = [r for r in census if r["gene"] == "TRIP13"]
        assert [r["filter"] for r in trip13] == ["PASS", "MQ40", "QD2"]
        assert sum(r["n"] for r in trip13) == trip13[0]["n_gene_all"]

    def test_a_semicolon_joined_reason_reaches_the_client_verbatim(self, client):
        census = client.get("/api/panel/suppressed").json()["data"]["census"]
        assert "LowQual;QD2" in {r["filter"] for r in census}


class TestRecords:
    def test_omitting_the_gene_returns_every_suppressed_record_in_the_panel(self, client):
        data = client.get("/api/panel/suppressed").json()["data"]
        assert data["gene"] is None
        assert len(data["records"]) == 3

    def test_naming_a_gene_narrows_the_records_and_echoes_the_gene(self, client):
        data = client.get("/api/panel/suppressed?gene=TRIP13").json()["data"]
        assert data["gene"] == "TRIP13"
        assert {r["gene"] for r in data["records"]} == {"TRIP13"}

    def test_the_genotype_evidence_reaches_the_client(self, client):
        """The point of the table is that a reader can judge the suppression, so the
        depths behind the call travel with it, not just the verdict."""
        first = client.get("/api/panel/suppressed?gene=TRIP13").json()["data"]["records"][0]
        assert (first["gt"], first["dp"], first["ad_alt"]) == ("0/1", 24, 6)
        assert first["is_het"] is True and first["qual"] == 62.8

    def test_an_unannotated_record_is_served_as_null_not_dropped(self, client):
        records = client.get("/api/panel/suppressed?gene=TRIP13").json()["data"]["records"]
        unannotated = next(r for r in records if not r["annotated"])
        assert unannotated["consequence"] is None and unannotated["gnomad_af"] is None


class TestGeneValidation:
    def test_a_panel_gene_with_nothing_suppressed_is_an_empty_list_not_a_404(self, client):
        """Nothing suppressed is the good outcome and must not look like a typo."""
        response = client.get("/api/panel/suppressed?gene=CEP57")
        assert response.status_code == 200
        assert response.json()["data"]["records"] == []

    def test_a_gene_the_panel_does_not_know_is_a_404(self, client):
        response = client.get("/api/panel/suppressed?gene=ZZZ")
        assert response.status_code == 404
        assert "ZZZ" in response.json()["detail"]

    def test_the_gene_is_optional_unlike_the_locus_route(self, client):
        assert client.get("/api/panel/suppressed").status_code == 200
