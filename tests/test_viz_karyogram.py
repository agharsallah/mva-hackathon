"""`GET /api/genome/baf-bins`: the routing, the envelope, the contig spellings.

Mocked below the API in the style of `tests/test_viz_api.py`: `queries.fetch` is replaced,
so a failure here means the route, the parameter or the SQL the query builds is wrong —
never that the database was unreachable.

The rows below are fabricated shapes, not measurements.
"""

import pytest
from fastapi.testclient import TestClient

from mva.viz import queries
from mva.viz.app import create_app
from mva.viz.cache import Cache

#: One balanced bin and one deliberately shifted thin bin, so both branches are exercised.
BAF_ROWS = [
    {
        "chrom": "7",
        "mb": 12,
        "n_het": 1840,
        "mean_vaf": 0.4971,
        "median_vaf": 0.5,
        "sd_vaf": 0.0919,
        "vaf_deviation": -0.0029,
        "pct_in_0_40_0_60": 77.3,
        "mean_dp": 42.4,
        "low_confidence": False,
    },
    {
        "chrom": "7",
        "mb": 13,
        "n_het": 6,
        "mean_vaf": 0.31,
        "median_vaf": 0.29,
        "sd_vaf": 0.17,
        "vaf_deviation": -0.19,
        "pct_in_0_40_0_60": 16.7,
        "mean_dp": 91.0,
        "low_confidence": True,
    },
]


@pytest.fixture()
def seen() -> list[tuple[str, list | None]]:
    """Every (sql, params) pair the route pushed down, in order."""
    return []


@pytest.fixture()
def client(tmp_path, monkeypatch, seen):
    def fetch(settings, sql, params=None):
        seen.append((sql, params))
        assert "baf_bins" in sql, sql
        return [dict(row) for row in BAF_ROWS]

    monkeypatch.setattr(queries, "fetch", fetch)
    with TestClient(
        create_app(settings=None, cache=Cache(tmp_path), origins=["http://localhost:5173"])
    ) as running:
        yield running


def data(response) -> object:
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"data", "cached_at", "source"}
    return body["data"]


class TestTheEnvelope:
    def test_the_whole_genome_answers_in_the_standard_envelope(self, client):
        assert data(client.get("/api/genome/baf-bins")) == BAF_ROWS

    def test_it_is_live_rather_than_cached(self, client):
        """The derivation already did the scan, so there is nothing to cache."""
        assert client.get("/api/genome/baf-bins").json()["cached_at"] is None

    def test_the_source_names_the_derived_table(self, client):
        assert client.get("/api/genome/baf-bins").json()["source"] == "pg.results.baf_bins"


class TestTheContigParameter:
    def test_omitting_the_contig_pushes_no_filter_down(self, client, seen):
        client.get("/api/genome/baf-bins")
        sql, params = seen[-1]
        assert "WHERE" not in sql and params is None

    def test_a_bare_contig_is_pushed_down_as_delivered(self, client, seen):
        client.get("/api/genome/baf-bins", params={"chrom": "7"})
        assert seen[-1][1] == ["7"]

    def test_the_chr_prefixed_spelling_is_normalised_to_the_bare_one(self, client, seen):
        """The panel is chr-prefixed and the callset is bare; both spellings must work."""
        client.get("/api/genome/baf-bins", params={"chrom": "chr7"})
        assert seen[-1][1] == ["7"]

    def test_the_contig_is_a_bound_parameter_not_string_interpolation(self, client, seen):
        client.get("/api/genome/baf-bins", params={"chrom": "7"})
        sql, _ = seen[-1]
        assert "chrom = ?" in sql and "'7'" not in sql


class TestTheContract:
    def test_every_column_the_chart_reads_is_selected(self, client, seen):
        client.get("/api/genome/baf-bins")
        sql, _ = seen[-1]
        for column in (
            "chrom",
            "mb",
            "n_het",
            "mean_vaf",
            "median_vaf",
            "sd_vaf",
            "vaf_deviation",
            "pct_in_0_40_0_60",
            "mean_dp",
            "low_confidence",
        ):
            assert column in sql, column

    def test_a_thin_bin_is_served_flagged_rather_than_withheld(self, client):
        rows = data(client.get("/api/genome/baf-bins"))
        thin = [row for row in rows if row["low_confidence"]]
        assert thin and thin[0]["n_het"] < 20

    def test_the_rows_come_back_in_position_order(self, client, seen):
        client.get("/api/genome/baf-bins")
        assert "ORDER BY chrom, mb" in seen[-1][0]
