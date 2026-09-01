"""The three endpoints that finally serve tables the warehouse already held.

``results.sequencing_yield``, ``warehouse.vcf_fields`` and ``results.stats_af`` each
existed with nothing reading them. These tests pin what the routes now promise.

Mocked below the API exactly as `test_viz_api.py` is: `queries.fetch` is replaced, so a
failure here means the routing, the envelope or the SQL's shape is wrong — never that the
database was unreachable. No positions appear in this file; none of the three tables has
one.
"""

import pytest
from fastapi.testclient import TestClient

from mva.viz import queries
from mva.viz.app import create_app
from mva.viz.cache import Cache
from mva.viz.routes_warehouse import TABLES

#: Rows as the live endpoints actually answered them, matched on a SQL fragment.
ANSWERS = {
    "sequencing_yield": [
        {"lane": "L001", "est_reads": 276180373.0, "est_gbases": 41.15,
         "gigabytes": 21.5, "n_files": 2},
        {"lane": "L002", "est_reads": 272700071.0, "est_gbases": 40.63,
         "gigabytes": 21.29, "n_files": 2},
    ],
    "vcf_fields": [
        {"kind": "FILTER", "id": "PASS", "description": "All filters passed"},
        {"kind": "INFO", "id": "DB", "description": "dbSNP membership"},
        {"kind": "FORMAT", "id": "GT", "description": "Genotype"},
    ],
    "stats_af": [
        {"af_bin": 0.0, "zygosity": "heterozygous", "n_snps": 2536505,
         "n_ts": 1665690, "n_tv": 870815, "n_indels": 644292, "n_alleles": 3180797,
         "ts_tv": 1.913, "pct_of_alleles": 62.63},
        {"af_bin": 0.99, "zygosity": "homozygous alternate", "n_snps": 1552121,
         "n_ts": 1032666, "n_tv": 519455, "n_indels": 346146, "n_alleles": 1898267,
         "ts_tv": 1.988, "pct_of_alleles": 37.37},
    ],
}

#: route → the table string its envelope must name.
ROUTES = {
    "/api/reads/yield": "pg.results.sequencing_yield",
    "/api/callset/fields": "pg.warehouse.vcf_fields",
    "/api/callset/zygosity-split": "pg.results.stats_af",
}


@pytest.fixture()
def seen():
    return {}


@pytest.fixture()
def client(tmp_path, monkeypatch, seen):
    def fetch(settings, sql, params=None):
        for fragment, answer in ANSWERS.items():
            if fragment in sql:
                seen[fragment] = sql
                return [dict(row) for row in answer]
        raise AssertionError(f"unexpected SQL: {sql}")

    monkeypatch.setattr(queries, "fetch", fetch)
    with TestClient(create_app(settings=None, cache=Cache(tmp_path),
                               origins=["http://localhost:5173"])) as running:
        yield running


def body(response) -> dict:
    assert response.status_code == 200, response.text
    payload = response.json()
    assert set(payload) == {"data", "cached_at", "source"}
    return payload


# ── the contract ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("path,source", sorted(ROUTES.items()))
def test_each_route_answers_in_the_envelope_and_names_its_table(client, path, source):
    payload = body(client.get(path))
    assert payload["source"] == source
    assert payload["cached_at"] is None, "all three are cheap reads; none is cached"
    assert isinstance(payload["data"], list) and payload["data"]


def test_the_routes_are_registered_as_plain_table_reads(client):
    """Data, not code: each of the three is one line in the TABLES map."""
    for path, source in ROUTES.items():
        assert TABLES[path.removeprefix("/api")][1] == source


# ── the yield table ──────────────────────────────────────────────────────────────────

def test_yield_is_ordered_by_lane_and_carries_the_estimate_columns(client):
    rows = body(client.get("/api/reads/yield"))["data"]
    assert [row["lane"] for row in rows] == ["L001", "L002"]
    assert set(rows[0]) == {"lane", "est_reads", "est_gbases", "gigabytes", "n_files"}


def test_yield_lanes_are_the_file_names_spelling_not_an_integer(client):
    """`ReadRunRow.lane` is `1`; this one is `L001`. The exhibit joins across that."""
    for row in body(client.get("/api/reads/yield"))["data"]:
        assert isinstance(row["lane"], str) and row["lane"].startswith("L")


# ── the header fields ────────────────────────────────────────────────────────────────

def test_fields_are_grouped_filter_then_info_then_format(client, seen):
    """The order is the endpoint's job, so the table renders grouped without sorting."""
    client.get("/api/callset/fields")
    sql = seen["vcf_fields"]
    assert sql.index("'FILTER' THEN 0") < sql.index("'INFO' THEN 1")
    assert "ORDER BY CASE kind" in sql


def test_fields_serves_the_three_header_namespaces_and_nothing_else(client):
    rows = body(client.get("/api/callset/fields"))["data"]
    assert {row["kind"] for row in rows} <= {"FILTER", "INFO", "FORMAT"}
    assert all(row["description"] for row in rows), "a field with no description is a bug"


# ── the zygosity split ───────────────────────────────────────────────────────────────

def test_the_split_carries_the_reading_beside_the_raw_bin(client):
    """`af_bin` alone invites the population-frequency misreading; `zygosity` is the fix."""
    rows = body(client.get("/api/callset/zygosity-split"))["data"]
    assert [row["zygosity"] for row in rows] == ["heterozygous", "homozygous alternate"]
    assert [row["af_bin"] for row in rows] == [0.0, 0.99]


def test_the_split_is_ordered_by_bin_so_het_comes_first(client, seen):
    client.get("/api/callset/zygosity-split")
    assert "ORDER BY af_bin" in seen["stats_af"]


def test_the_shares_of_the_two_bins_sum_to_a_hundred(client):
    rows = body(client.get("/api/callset/zygosity-split"))["data"]
    assert round(sum(row["pct_of_alleles"] for row in rows), 2) == 100.00
