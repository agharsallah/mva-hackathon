"""`GET /api/panel/background`: the routing, the envelope, the contract the chart reads.

Mocked below the API in the style of `tests/test_viz_karyogram.py`: `queries.fetch` is
replaced, so a failure here means the route, the TABLES registration or the SQL the query
builds is wrong — never that the database was unreachable.

Two rows, both fabricated shapes: one gene sitting inside the band and one outside it on
both axes, plus a NULL z, because "the background had no usable spread" is a state the
contract has to carry and the chart has to render as a gap.
"""

import pytest
from fastapi.testclient import TestClient

from mva.viz import queries, routes_warehouse
from mva.viz.app import create_app
from mva.viz.cache import Cache

ROWS = [
    {
        "gene": "OUTLIER",
        "chrom": "chr5",
        "n_all": 12,
        "n_pass": 6,
        "span_bp": 66509,
        "gene_variants_per_mb": 180.4,
        "gene_pct_pass": 50.0,
        "contig_variants_per_mb": 1596.4,
        "contig_pct_pass": 96.13,
        "genome_variants_per_mb": 1585.3,
        "genome_pct_pass": 95.22,
        "contig_n_bins": 181,
        "contig_bin_mean_density": 1601.2,
        "contig_bin_sd_density": 463.0,
        "contig_bin_mean_pct_pass": 96.28,
        "contig_bin_sd_pct_pass": 11.52,
        "genome_n_bins": 2961,
        "genome_bin_mean_density": 1653.4,
        "genome_bin_sd_density": 774.1,
        "genome_bin_mean_pct_pass": 95.47,
        "genome_bin_sd_pct_pass": 12.84,
        "z_density_vs_contig": -3.07,
        "z_density_vs_genome": -1.9,
        "z_pass_vs_contig": -4.02,
        "z_pass_vs_genome": -3.54,
    },
    {
        "gene": "ORDINARY",
        "chrom": "chr17",
        "n_all": 120,
        "n_pass": 118,
        "span_bp": 65768,
        "gene_variants_per_mb": 1824.6,
        "gene_pct_pass": 98.33,
        "contig_variants_per_mb": 1706.2,
        "contig_pct_pass": 95.1,
        "genome_variants_per_mb": 1585.3,
        "genome_pct_pass": 95.22,
        "contig_n_bins": 1,
        "contig_bin_mean_density": 1824.6,
        "contig_bin_sd_density": None,
        "contig_bin_mean_pct_pass": None,
        "contig_bin_sd_pct_pass": None,
        "genome_n_bins": 2961,
        "genome_bin_mean_density": 1653.4,
        "genome_bin_sd_density": 774.1,
        "genome_bin_mean_pct_pass": 95.47,
        "genome_bin_sd_pct_pass": 12.84,
        "z_density_vs_contig": None,
        "z_density_vs_genome": 0.22,
        "z_pass_vs_contig": None,
        "z_pass_vs_genome": 0.22,
    },
]


@pytest.fixture()
def seen() -> list[tuple[str, list | None]]:
    return []


@pytest.fixture()
def client(tmp_path, monkeypatch, seen):
    def fetch(settings, sql, params=None):
        seen.append((sql, params))
        assert "panel_gene_background" in sql, sql
        return [dict(row) for row in ROWS]

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
    def test_it_answers_in_the_standard_envelope(self, client):
        assert data(client.get("/api/panel/background")) == ROWS

    def test_it_is_live_rather_than_cached(self, client):
        """Eight rows off a derived table; the derivation already paid the scan."""
        assert client.get("/api/panel/background").json()["cached_at"] is None

    def test_the_source_names_the_derived_table(self, client):
        assert (
            client.get("/api/panel/background").json()["source"]
            == "pg.results.panel_gene_background"
        )


class TestTheRegistration:
    def test_it_is_a_plain_table_read_declared_in_the_one_map(self):
        """A new chart over an existing table is one line, not a new handler."""
        function, source = routes_warehouse.TABLES["/panel/background"]
        assert function is queries.panel_background
        assert source == "pg.results.panel_gene_background"

    def test_it_is_tagged_panel_so_the_docs_group_it_with_the_other_gene_routes(self, client):
        paths = client.get("/openapi.json").json()["paths"]
        assert paths["/api/panel/background"]["get"]["tags"] == ["panel"]


class TestTheContract:
    def test_the_most_suppressed_gene_comes_first(self, client, seen):
        """The exhibit's reading is about the outlier, so it must not have to sort."""
        client.get("/api/panel/background")
        assert "ORDER BY z_pass_vs_contig NULLS LAST, gene" in seen[-1][0]

    def test_every_field_the_chart_needs_survives_the_round_trip(self, client):
        row = data(client.get("/api/panel/background"))[0]
        for field in (
            "gene",
            "chrom",
            "gene_variants_per_mb",
            "gene_pct_pass",
            "contig_bin_mean_density",
            "contig_bin_sd_density",
            "contig_bin_mean_pct_pass",
            "contig_bin_sd_pct_pass",
            "genome_bin_mean_density",
            "genome_bin_sd_density",
            "z_density_vs_contig",
            "z_density_vs_genome",
            "z_pass_vs_contig",
            "z_pass_vs_genome",
        ):
            assert field in row, field

    def test_an_unmeasurable_z_stays_null_and_is_never_coerced_to_zero(self, client):
        """Null is "no usable spread in the background", which is not agreement."""
        ordinary = data(client.get("/api/panel/background"))[1]
        assert ordinary["z_density_vs_contig"] is None
        assert ordinary["z_pass_vs_contig"] is None

    def test_the_contig_is_served_chr_prefixed_as_the_panel_spells_it(self, client):
        assert all(
            row["chrom"].startswith("chr") for row in data(client.get("/api/panel/background"))
        )

    def test_the_raw_values_behind_each_z_travel_with_it(self, client):
        """The hover has to show what the z was computed from, so it cannot be a lone
        number: the gene value, the background mean and its spread all ship."""
        outlier = data(client.get("/api/panel/background"))[0]
        assert outlier["gene_pct_pass"] == 50.0
        assert outlier["contig_bin_mean_pct_pass"] == 96.28
        assert outlier["contig_bin_sd_pct_pass"] == 11.52

    def test_no_genomic_position_is_ever_in_the_payload(self, client):
        """Gene-grain aggregates only — this endpoint is safe to export verbatim."""
        for row in data(client.get("/api/panel/background")):
            assert "pos" not in row and "start" not in row and "end" not in row


class TestTheColumnSemantics:
    def test_every_derived_column_of_the_table_carries_a_meaning(self):
        from mva.viz.catalog_columns import meaning

        for column in ROWS[0]:
            assert meaning("panel_gene_background", column), column

    def test_the_pass_z_meaning_says_callability_rather_than_pathogenicity(self):
        from mva.viz.catalog_columns import meaning

        text = meaning("panel_gene_background", "z_pass_vs_contig")
        assert "allability" in text and "pathogenicity" in text
