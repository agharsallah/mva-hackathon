"""``GET /api/panel/clinvar-presence``: the route, the envelope, and what it must not hide.

Mocked below the API exactly as ``test_viz_funnel.py`` is: :func:`mva.viz.queries.fetch` is
replaced, so a failure here means the routing, the two-half payload or the gene filter is
wrong — never that the database was unreachable. The join itself is asserted against the
real SQL in ``tests/test_warehouse_clinvar.py``.

The contract worth defending is what the payload refuses to round off. A gene ClinVar has
classified nothing in must still appear, with a zero rather than a gap. A row that could
never be compared must arrive as ``present: null``, not ``false``. And the lower-bound
caveat has to be reachable from the OpenAPI description, because a reader who only sees
the JSON has no other way to learn that an exact-string match under-counts indels.
"""

import pytest
from fastapi.testclient import TestClient

from mva.viz import queries, readstore
from mva.viz.app import create_app
from mva.viz.cache import Cache

#: Counts are illustrative, not the measured ones. The shape is what matters: a gene with
#: hits, a gene with many P/LP records and none of them called, and a gene ClinVar has
#: classified nothing in at all.
SUMMARY = [
    {"gene": "BUB1B", "n_plp": 84, "n_comparable": 83, "n_uncomparable": 1,
     "n_present": 2, "n_present_pass": 1, "n_present_het": 1, "n_absent": 81},
    {"gene": "TP53", "n_plp": 1147, "n_comparable": 1147, "n_uncomparable": 0,
     "n_present": 0, "n_present_pass": 0, "n_present_het": 0, "n_absent": 1147},
    {"gene": "CEP192", "n_plp": 0, "n_comparable": 0, "n_uncomparable": 0,
     "n_present": 0, "n_present_pass": 0, "n_present_het": 0, "n_absent": 0},
]

#: One row per shape the exhibit has to render differently.
SITES = [
    # present, PASS, heterozygous — the direct-lead shape
    {"gene": "BUB1B", "chrom": "15", "pos": 1000, "ref": "T", "alt": "G",
     "rsid": "rs1", "variation_id": 533901, "clnsig": "Pathogenic/Likely_pathogenic",
     "clnrevstat": "criteria_provided,_multiple_submitters,_no_conflicts",
     "review_stars": 2, "condition": "Mosaic_variegated_aneuploidy_syndrome_1",
     "comparable": True, "present": True, "gt": "0/1", "filter": "PASS",
     "qual": 708.77, "dp": 46, "allele_ix": 1, "vaf": 0.5435,
     "carries_alt": True, "is_het": True},
    # present but suppressed by the caller
    {"gene": "BUB1B", "chrom": "15", "pos": 2000, "ref": "C", "alt": "T",
     "rsid": None, "variation_id": 533902, "clnsig": "Pathogenic",
     "clnrevstat": "criteria_provided,_single_submitter", "review_stars": 1,
     "condition": "not_provided", "comparable": True, "present": True,
     "gt": "1/1", "filter": "LowQual", "qual": 30.0, "dp": 8, "allele_ix": 1,
     "vaf": 0.9, "carries_alt": True, "is_het": False},
    # uncomparable: ClinVar states no alternate allele
    {"gene": "BUB1B", "chrom": "15", "pos": 3000, "ref": "A", "alt": ".",
     "rsid": None, "variation_id": 533903, "clnsig": "Pathogenic",
     "clnrevstat": None, "review_stars": None, "condition": "not_provided",
     "comparable": False, "present": None, "gt": None, "filter": None,
     "qual": None, "dp": None, "allele_ix": None, "vaf": None,
     "carries_alt": None, "is_het": None},
]

#: Columns ``app/src/pages/compare/ClinvarPresence.tsx`` reads off a site row.
SITE_CONTRACT = set(SITES[0])

#: Columns it reads off a summary row.
SUMMARY_CONTRACT = set(SUMMARY[0])


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A TestClient whose only live answer is the ClinVar presence pair of queries."""
    seen: list[tuple[str, list | None]] = []

    def fetch(settings, sql, params=None):
        assert "clinvar_presence" in sql, f"unexpected SQL: {sql}"
        seen.append((sql, params))
        gene = params[0] if params else None
        if "mva_panel_grch38" in sql:
            return [dict(r) for r in SUMMARY if gene in (None, r["gene"])]
        return [dict(r) for r in SITES if gene in (None, r["gene"])]

    monkeypatch.setattr(queries, "fetch", fetch)
    monkeypatch.setattr(readstore, "root", lambda: "s3://test/reads")
    with TestClient(create_app(settings=None, cache=Cache(tmp_path),
                               origins=["http://localhost:5173"])) as running:
        running.seen = seen
        yield running


def body(client, query: str = "") -> dict:
    response = client.get(f"/api/panel/clinvar-presence{query}")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert set(payload) == {"data", "cached_at", "source"}
    return payload


# ── the route ────────────────────────────────────────────────────────────────────────

def test_the_endpoint_answers_in_the_shared_envelope(client):
    assert set(body(client)["data"]) == {"summary", "sites"}


def test_it_is_live_rather_than_cached(client):
    """A derived table of a few thousand rows. A cache would only hide a re-derive."""
    assert body(client)["cached_at"] is None


def test_the_source_names_the_derived_table_and_the_panel_bed(client):
    """The expensive scan happens in `pg-derive`; the request must not repeat it."""
    source = body(client)["source"]
    assert "pg.results.clinvar_presence" in source
    assert "mva_panel_grch38" in source


def test_the_route_is_documented_under_the_panel_tag(client):
    operation = client.get("/openapi.json").json()[
        "paths"]["/api/panel/clinvar-presence"]["get"]
    assert operation["tags"] == ["panel"]


def test_the_description_states_the_lower_bound_caveat(client):
    """The only place a JSON-only reader can learn that indels are under-counted."""
    operation = client.get("/openapi.json").json()[
        "paths"]["/api/panel/clinvar-presence"]["get"]
    text = operation["description"].lower()
    assert "lower bound" in text
    assert "left-alignment" in text or "left-align" in text


def test_the_gene_parameter_is_optional(client):
    operation = client.get("/openapi.json").json()[
        "paths"]["/api/panel/clinvar-presence"]["get"]
    gene = next(p for p in operation["parameters"] if p["name"] == "gene")
    assert gene["required"] is False


# ── the gene filter ──────────────────────────────────────────────────────────────────

def test_a_gene_narrows_both_halves_not_only_the_list(client):
    data = body(client, "?gene=BUB1B")["data"]
    assert [r["gene"] for r in data["summary"]] == ["BUB1B"]
    assert {r["gene"] for r in data["sites"]} == {"BUB1B"}


def test_the_filter_is_a_bound_parameter_not_string_interpolation(client):
    body(client, "?gene=BUB1B")
    for sql, params in client.seen:
        assert "BUB1B" not in sql
        assert params == ["BUB1B"]


def test_an_unknown_gene_is_a_404_rather_than_an_empty_success(client, monkeypatch):
    """Zero rows for a misspelt gene reads exactly like a gene with nothing in it."""
    monkeypatch.setattr(queries, "fetch", lambda *a, **k: [])
    response = client.get("/api/panel/clinvar-presence?gene=NOTAGENE")
    assert response.status_code == 404
    assert "NOTAGENE" in response.json()["detail"]


# ── what the payload must not round off ──────────────────────────────────────────────

def test_a_gene_clinvar_has_classified_nothing_in_still_appears(client):
    """CEP192 is a candidate gene, not an established one. Absence of a prior there is
    expected, and dropping the row would hide that it was checked."""
    summary = {r["gene"]: r for r in body(client)["data"]["summary"]}
    assert summary["CEP192"]["n_plp"] == 0


def test_every_summary_row_carries_exactly_the_declared_columns(client):
    for row in body(client)["data"]["summary"]:
        assert set(row) == SUMMARY_CONTRACT


def test_every_site_row_carries_exactly_the_declared_columns(client):
    for row in body(client)["data"]["sites"]:
        assert set(row) == SITE_CONTRACT


def test_an_uncomparable_row_reaches_the_client_as_null_not_false(client):
    """`present: false` is a measurement. A row that could never match is not one."""
    row = next(r for r in body(client)["data"]["sites"] if r["comparable"] is False)
    assert row["present"] is None
    assert row["carries_alt"] is None and row["is_het"] is None


def test_the_filter_label_travels_with_every_present_site(client):
    """Present is not the same as trustworthy — the exhibit colours on this."""
    for row in body(client)["data"]["sites"]:
        if row["present"]:
            assert row["filter"]


def test_the_review_status_travels_beside_its_star_count(client):
    """Stars are a rendering of the status, so the raw string has to stay auditable."""
    row = next(r for r in body(client)["data"]["sites"] if r["review_stars"] == 2)
    assert row["clnrevstat"] == "criteria_provided,_multiple_submitters,_no_conflicts"


def test_the_site_list_is_the_present_and_uncomparable_rows_only(client):
    """Measured absences live in the counts. The query says so, so the client can too."""
    body(client)
    sites_sql = next(sql for sql, _ in client.seen if "mva_panel_grch38" not in sql)
    assert "present OR p.present IS NULL" in sites_sql
