"""The viz API's HTTP surface: the envelope, the cache, CORS, and the proxy's 503.

Mocked below the API, exactly as `test_reads_api.py` is: `queries.fetch` and the
read-store functions are replaced, so a failure here means the routing, the envelope or
the caching is wrong — never that the database was unreachable.

Positions in this file are fabricated. The real ones live only in the cache under
gitignored `build/`.
"""

import pytest
from fastapi.testclient import TestClient

from mva.viz import queries, readstore, routes_warehouse
from mva.viz.app import cors_origins, create_app
from mva.viz.cache import Cache
from mva.viz.proxy import Reply, Unreachable, Upstream
from mva.warehouse.settings import DEFAULTS

#: What the fake `fetch` returns, matched on a fragment of the SQL.
ANSWERS = {
    "allele_balance_flags": [{"chrom": "8", "n_het": 100, "mean_vaf": 0.51,
                              "balance_call": "flagged"}],
    "contig_density": [{"chrom": "1", "length": 248956422, "n_records": 383428}],
    "variant_density_bins": [{"chrom": "15", "mb": 40, "n": 900, "pass_n": 870,
                              "low_qual_n": 4, "mean_qual": 812.5}],
    "filter_impact": [{"filter_value": "PASS", "count": 4740790, "impact_rank": 1}],
    "genotype counts": [{"label": "0/1", "count": 3047077}],
    "stats_dp": [{"bin": 44, "count": 100000, "pct": 2.0}],
    "stats_st": [{"sub_type": "A>G", "count": 656121, "is_transition": True}],
    "stats_idd": [{"length": -1, "count": 225128}],
    "stats_tstv": [{"ts": 2698356, "tv": 1390270, "ratio": 1.94}],
    "data_lineage": [{"target_table": "variants_raw", "tool": "mva-warehouse"}],
    "derivation_runs": [{"derivation": "variant_density_bins", "n_rows": 2961}],
    "source_objects": [{"file_name": "proband.vcf.gz", "hash_verified": True}],
    "probe_ledger": [],
    "panel_gene_density": [{"gene": "BUB1B", "chrom": "chr15", "start": 1000,
                            "end": 2000, "n_all": 200, "n_pass": 190,
                            "n_filtered": 10, "span_bp": 1000,
                            "variants_per_mb": 200.0, "pct_pass": 95.0}],
    "mva_panel_grch38": [{"chrom": "chr15", "start": 1000, "end": 2000}],
    "panel_gene_constraint": [{"gene": "BUB1B", "chrom": "chr15", "n_all": 80,
                               "n_pass": 76, "loeuf": 0.707, "pli": 2.6e-14,
                               "clinvar_plp": 84, "clinvar_vus": 1486,
                               "clinvar_benign": 844}],
    "panel_candidates": [{"chrom": "15", "pos": 1500, "ref": "T", "alt": "C",
                          "gene": "BUB1B", "consequence": "missense_variant",
                          "impact": "MODERATE", "gnomad_af": None, "qual": 812.5,
                          "filter": "PASS", "gt": "0/1", "dp": 38, "vaf": 0.4737,
                          "is_rare_recessive": True, "is_protein_altering": True}],
    "qc_observed_expected": [{"metric": "tstv_genome_wide", "label": "Ts/Tv",
                              "observed": 1.94, "expected_low": 2.0,
                              "expected_high": 2.1, "unit": "ratio",
                              "verdict": "below", "source": "Betschart 2024",
                              "observed_from": "stats_summary TSTV"}],
    "variants_raw": [{"pos": "1500", "ref": "T", "alt": "C", "qual": "812.5",
                      "filter": "PASS", "format": "GT:AD:DP:GQ",
                      "sample_call": "0/1:20,18:38:99"}],
}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    def fetch(settings, sql, params=None):
        for fragment, answer in ANSWERS.items():
            if fragment in sql:
                return [dict(row) for row in answer]
        raise AssertionError(f"unexpected SQL: {sql}")

    monkeypatch.setattr(queries, "fetch", fetch)
    monkeypatch.setattr(routes_warehouse, "overview",
                        lambda settings: {"total_variants": 5012204})
    monkeypatch.setattr(readstore, "root", lambda: "s3://test/reads")
    monkeypatch.setattr(readstore, "runs",
                        lambda: [{"lane": 1, "read_num": 1, "reads": 5}])
    monkeypatch.setattr(readstore, "partitions",
                        lambda: [{"lane": 1, "read_num": 1, "shards": 34,
                                  "reads": 136586642, "gib": 7.6}])
    with TestClient(create_app(settings=None, cache=Cache(tmp_path),
                               origins=["http://localhost:5173"])) as running:
        yield running


def data(response) -> object:
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"data", "cached_at", "source"}
    assert body["source"]
    return body["data"]


# ── the envelope ─────────────────────────────────────────────────────────────────────

def test_health_is_the_one_route_without_an_envelope(client):
    assert client.get("/health").json() == {"ok": True, "service": "mva-viz-api"}


@pytest.mark.parametrize("path", [
    "/api/genome/allele-balance", "/api/genome/contig-density",
    "/api/genome/density-bins", "/api/callset/filters", "/api/callset/genotypes",
    "/api/callset/depth-distribution", "/api/callset/substitutions",
    "/api/callset/tstv", "/api/callset/indel-lengths", "/api/panel/genes",
    "/api/callset/observed-expected", "/api/panel/constraint",
    "/api/panel/annotations",
    "/api/provenance/lineage", "/api/provenance/derivations",
    "/api/provenance/sources", "/api/probe/ledger",
    "/api/reads/runs", "/api/reads/partitions",
])
def test_every_endpoint_answers_in_the_same_envelope(client, path):
    assert data(client.get(path)) is not None


def test_a_live_endpoint_reports_no_cache_instant(client):
    assert client.get("/api/callset/genotypes").json()["cached_at"] is None


def test_the_source_names_the_table_the_numbers_came_from(client):
    body = client.get("/api/callset/depth-distribution").json()
    assert body["source"] == "pg.results.stats_dp"


def test_an_empty_table_is_an_empty_list_not_an_error(client):
    """The probe ledger has no rows yet; the UI must get [] and render its empty state."""
    assert data(client.get("/api/probe/ledger")) == []


def test_tstv_is_a_single_object_not_a_list(client):
    assert data(client.get("/api/callset/tstv")) == {"ts": 2698356, "tv": 1390270,
                                                     "ratio": 1.94}


# ── query parameters ─────────────────────────────────────────────────────────────────

def test_density_bins_pushes_the_chromosome_into_the_query(client, monkeypatch):
    seen = {}

    def spy(settings, sql, params=None):
        seen["sql"], seen["params"] = sql, params
        return []

    monkeypatch.setattr(queries, "fetch", spy)
    client.get("/api/genome/density-bins", params={"chrom": "15"})
    assert "WHERE chrom = ?" in seen["sql"] and seen["params"] == ["15"]


def test_a_chr_prefixed_chromosome_is_normalised_before_the_query(client, monkeypatch):
    """The panel says chr15, the callset says 15. Passing chr15 through matches nothing."""
    seen = {}

    def spy(settings, sql, params=None):
        seen["params"] = params
        return []

    monkeypatch.setattr(queries, "fetch", spy)
    client.get("/api/genome/density-bins", params={"chrom": "chr15"})
    assert seen["params"] == ["15"]


def test_panel_genes_merges_the_bed_annotation_onto_the_density_row(client):
    row = data(client.get("/api/panel/genes"))[0]
    assert row["gene"] == "BUB1B"
    assert row["ensembl_id"] == "ENSG00000156970"  # from the committed panel BED
    assert row["note"]
    assert row["start"] == 1000 and row["end"] == 2000


def test_panel_constraint_merges_the_bed_annotation_like_panel_genes_does(client):
    row = data(client.get("/api/panel/constraint"))[0]
    assert row["gene"] == "BUB1B" and row["loeuf"] == 0.707
    assert row["ensembl_id"] == "ENSG00000156970"  # from the committed panel BED
    assert row["note"]


def test_panel_annotations_without_a_gene_returns_the_whole_panel(client, monkeypatch):
    seen = {}

    def spy(settings, sql, params=None):
        seen["sql"], seen["params"] = sql, params
        return ANSWERS["panel_candidates"]

    monkeypatch.setattr(queries, "fetch", spy)
    assert data(client.get("/api/panel/annotations"))[0]["gene"] == "BUB1B"
    assert "WHERE gene" not in seen["sql"] and seen["params"] is None


def test_panel_annotations_pushes_the_gene_into_the_query(client, monkeypatch):
    seen = {}

    def spy(settings, sql, params=None):
        seen["sql"], seen["params"] = sql, params
        return ANSWERS["panel_candidates"]

    monkeypatch.setattr(queries, "fetch", spy)
    client.get("/api/panel/annotations", params={"gene": "BUB1B"})
    assert "WHERE gene = ?" in seen["sql"] and seen["params"] == ["BUB1B"]


def test_an_unknown_gene_in_annotations_is_a_404_not_an_empty_list(client, monkeypatch):
    monkeypatch.setattr(queries, "fetch", lambda settings, sql, params=None: [])
    response = client.get("/api/panel/annotations", params={"gene": "NOTAGENE"})
    assert response.status_code == 404
    assert "NOTAGENE" in response.json()["detail"]


def test_an_empty_panel_is_an_empty_list_when_no_gene_was_asked_for(client, monkeypatch):
    """No gene means no lookup, so an empty table is a chart's empty state, not a 404."""
    monkeypatch.setattr(queries, "fetch", lambda settings, sql, params=None: [])
    assert data(client.get("/api/panel/annotations")) == []


def test_observed_expected_carries_both_the_measurement_and_the_range(client):
    row = data(client.get("/api/callset/observed-expected"))[0]
    assert row["observed"] == 1.94 and row["expected_low"] == 2.0
    assert row["verdict"] == "below" and row["observed_from"]


# ── the locus route: the one that reads the callset ──────────────────────────────────

def test_locus_decodes_the_packed_genotype_and_caches_the_result(client):
    body = client.get("/api/panel/locus", params={"gene": "BUB1B"}).json()
    row = body["data"][0]
    assert row["pos"] == 1500 and row["qual"] == 812.5
    assert (row["ad_ref"], row["ad_alt"]) == (20, 18)
    assert row["vaf"] == pytest.approx(18 / 38, abs=1e-4)
    assert body["cached_at"] is not None  # cached, per the contract


def test_a_second_locus_request_is_served_from_disk(client, monkeypatch):
    first = client.get("/api/panel/locus", params={"gene": "BUB1B"}).json()

    def refuse(settings, sql, params=None):
        raise AssertionError("the callset must not be read twice")

    monkeypatch.setattr(queries, "fetch", refuse)
    second = client.get("/api/panel/locus", params={"gene": "BUB1B"}).json()
    assert second == first


def test_refresh_busts_the_cache(client, monkeypatch):
    client.get("/api/panel/locus", params={"gene": "BUB1B"})

    def emptied(settings, sql, params=None):
        # the gene still resolves; the region simply has no variants this time
        return [] if "variants_raw" in sql else ANSWERS["mva_panel_grch38"]

    monkeypatch.setattr(queries, "fetch", emptied)
    rebuilt = client.get("/api/panel/locus",
                         params={"gene": "BUB1B", "refresh": "true"}).json()
    assert rebuilt["data"] == []


def test_an_unknown_gene_is_a_404_not_an_empty_chart(client, monkeypatch):
    monkeypatch.setattr(queries, "fetch", lambda settings, sql, params=None: [])
    response = client.get("/api/panel/locus", params={"gene": "NOTAGENE"})
    assert response.status_code == 404
    assert "NOTAGENE" in response.json()["detail"]


def test_a_gene_name_that_could_escape_the_cache_directory_is_refused(client):
    assert client.get("/api/panel/locus",
                      params={"gene": "../../etc/passwd"}).status_code == 422


# ── the read store ───────────────────────────────────────────────────────────────────

def test_flowcell_is_cached_and_names_its_shard(client, monkeypatch):
    calls = []

    def flowcell(lane, read, shard):
        calls.append((lane, read, shard))
        return [{"tile": 1101, "xb": 3, "yb": 4, "n": 170}]

    monkeypatch.setattr(readstore, "flowcell", flowcell)
    first = client.get("/api/reads/flowcell", params={"lane": 1, "read": 1}).json()
    assert first["data"][0]["tile"] == 1101
    assert "lane=1/read=1" in first["source"] and first["cached_at"]
    client.get("/api/reads/flowcell", params={"lane": 1, "read": 1})
    assert calls == [(1, 1, 0)]  # the second request never reached the store


def test_each_shard_gets_its_own_cache_entry(client, monkeypatch):
    monkeypatch.setattr(readstore, "flowcell",
                        lambda lane, read, shard: [{"shard": shard}])
    for shard in (0, 1):
        body = client.get("/api/reads/flowcell",
                          params={"lane": 1, "read": 1, "shard": shard}).json()
        assert body["data"] == [{"shard": shard}]


def test_a_lane_outside_the_flowcell_is_rejected_before_any_query(client):
    assert client.get("/api/reads/flowcell",
                      params={"lane": 9, "read": 1}).status_code == 422


def test_a_missing_shard_is_a_404(client, monkeypatch):
    def missing(lane, read, shard):
        raise LookupError("shard 99 out of range")

    monkeypatch.setattr(readstore, "flowcell", missing)
    response = client.get("/api/reads/flowcell",
                          params={"lane": 1, "read": 1, "shard": 99})
    assert response.status_code == 404


def test_the_slow_quality_endpoints_are_cached(client, monkeypatch):
    calls = []
    monkeypatch.setattr(readstore, "cycle_quality",
                        lambda: calls.append("q") or [{"cycle": 1, "mean_q": 36.2}])
    monkeypatch.setattr(readstore, "quality_levels",
                        lambda: [{"phred": 37, "count": 10}])
    assert client.get("/api/reads/cycle-quality").json()["cached_at"]
    client.get("/api/reads/cycle-quality")
    assert len(calls) == 1
    assert data(client.get("/api/reads/quality-levels"))[0]["phred"] == 37


# ── the proxy ────────────────────────────────────────────────────────────────────────

class Down(Upstream):
    """An upstream that is not running — the current state of `mva-reads-api`."""

    async def request(self, *args, **kwargs):
        raise Unreachable("http://127.0.0.1:8765")


class Fake(Upstream):
    def __init__(self, status=200, body=None):
        self.status, self.body, self.calls = status, body or {}, []

    async def request(self, method, path, *, params=None, json=None, timeout=30.0):
        self.calls.append({"method": method, "path": path, "params": params,
                           "json": json, "timeout": timeout})
        return Reply(self.status, self.body)


def proxied(tmp_path, upstream) -> TestClient:
    return TestClient(create_app(settings=None, cache=Cache(tmp_path),
                                 origins=[], upstream=upstream))


PROXY_ROUTES = [
    ("post", "/api/probe/count", {"probes": [{"sequence": "ACGT"}]}),
    ("post", "/api/probe/scan", {"probes": [{"sequence": "ACGT"}]}),
    ("get", "/api/jobs", None),
    ("get", "/api/jobs/abc123", None),
    ("get", "/api/jobs/abc123/wait", None),
    ("post", "/api/jobs/abc123/cancel", None),
]


@pytest.mark.parametrize("method,path,body", PROXY_ROUTES)
def test_an_unreachable_reads_api_is_a_503_naming_the_url(tmp_path, method, path, body):
    with proxied(tmp_path, Down()) as client:
        response = getattr(client, method)(path, json=body) if body else \
            getattr(client, method)(path)
        assert response.status_code == 503
        assert response.json() == {
            "detail": "reads API unreachable at http://127.0.0.1:8765"}


def test_a_job_comes_back_in_the_same_envelope_as_everything_else(tmp_path):
    job = {"id": "abc123", "verb": "count", "state": "queued", "result": None}
    upstream = Fake(202, job)
    with proxied(tmp_path, upstream) as client:
        body = client.post("/api/probe/count",
                           json={"probes": [{"sequence": "ACGT", "name": "a"}]}).json()
    assert body["data"] == job
    assert body["source"].endswith("/count")
    assert upstream.calls[0]["json"] == {"probes": [{"sequence": "ACGT", "name": "a"}]}


def test_the_scan_limit_is_forwarded_only_when_given(tmp_path):
    upstream = Fake(202, {"id": "x"})
    with proxied(tmp_path, upstream) as client:
        client.post("/api/probe/scan", json={"probes": [{"sequence": "ACGT"}]})
        client.post("/api/probe/scan",
                    json={"probes": [{"sequence": "ACGT"}], "limit": 5})
    assert "limit" not in upstream.calls[0]["json"]
    assert upstream.calls[1]["json"]["limit"] == 5


def test_the_long_poll_gets_a_longer_client_timeout_than_it_asks_for(tmp_path):
    """A 290 s upstream wait behind a 30 s client timeout would always time out."""
    upstream = Fake(200, {"id": "x", "state": "running"})
    with proxied(tmp_path, upstream) as client:
        client.get("/api/jobs/x/wait", params={"timeout": 120})
    assert upstream.calls[0]["params"] == {"timeout": 120}
    assert upstream.calls[0]["timeout"] > 290


def test_a_wait_beyond_the_upstream_cap_is_refused_here(tmp_path):
    with proxied(tmp_path, Fake()) as client:
        assert client.get("/api/jobs/x/wait",
                          params={"timeout": 900}).status_code == 422


def test_an_upstream_error_keeps_its_status_and_its_reason(tmp_path):
    with proxied(tmp_path, Fake(409, {"detail": "job already finished"})) as client:
        response = client.post("/api/jobs/x/cancel")
    assert response.status_code == 409
    assert response.json()["detail"] == "job already finished"


def test_unset_job_filters_are_dropped_rather_than_sent_empty(tmp_path):
    upstream = Fake(200, [])
    with proxied(tmp_path, upstream) as client:
        client.get("/api/jobs", params={"state": "done"})
    assert upstream.calls[0]["params"] == {"state": "done", "verb": None}


# ── CORS ─────────────────────────────────────────────────────────────────────────────

def test_the_dev_server_origin_is_allowed(client):
    response = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_both_spellings_of_loopback_are_allowed_by_default():
    """`localhost` and `127.0.0.1` are different origins to a browser.

    Read from :data:`DEFAULTS`, not from ``cors_origins()``: the no-argument call resolves
    the developer's own ``.env``, which legitimately adds origins and is not under test.
    """
    assert cors_origins(DEFAULTS["MVA_VIZ_CORS"]) == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    assert cors_origins("http://a, http://b ,") == ["http://a", "http://b"]


def test_a_drifted_dev_server_port_is_still_allowed(client):
    """Vite takes 5174 when 5173 is busy; a port-exact list reads that as "api down"."""
    response = client.get("/health", headers={"Origin": "http://127.0.0.1:5174"})
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5174"


def test_a_non_loopback_origin_is_not_allowed(client):
    """The regex widens loopback only — it must not open the API to the network."""
    response = client.get("/health", headers={"Origin": "http://evil.example:5173"})
    assert "access-control-allow-origin" not in response.headers
