"""``GET /api/callset/funnel``: the route, the envelope, and the contract the chart reads.

Mocked below the API exactly as ``test_viz_api.py`` is: :func:`mva.viz.queries.fetch` is
replaced, so a failure here means the routing, the ordering or the envelope is wrong —
never that the database was unreachable.

The contract worth defending is the *honesty* of the payload, not its plumbing. A funnel
that silently mixes two scopes, or divides a panel count by a genome count, is a chart
that lies at a glance. So the tests below assert that the scope column survives the round
trip, that ``of_previous_pct`` reaches the client as ``null`` where the row is not a
subset of the row above, and that the source string names the derived table rather than
the callset.
"""

import pytest
from fastapi.testclient import TestClient

from mva.viz import queries, readstore
from mva.viz.app import create_app
from mva.viz.cache import Cache

#: What the fake ``fetch`` returns for the funnel table: the two-scope shape, the two null
#: shares, and a note. Counts are illustrative, not the measured ones — this file tests
#: the route, and the measured numbers are asserted against the real SQL in
#: ``tests/test_warehouse_funnel.py``.
FUNNEL_ROWS = [
    {
        "stage_no": 1,
        "stage": "records called",
        "scope": "genome",
        "n": 1000,
        "of_previous_pct": None,
        "note": "COUNT(*) over the delivered callset.",
    },
    {
        "stage_no": 2,
        "stage": "FILTER = PASS",
        "scope": "genome",
        "n": 900,
        "of_previous_pct": 90.0,
        "note": "The caller's own veto.",
    },
    {
        "stage_no": 3,
        "stage": "heterozygous call",
        "scope": "genome",
        "n": 500,
        "of_previous_pct": 55.5556,
        "note": "GT names two different non-missing alleles.",
    },
    {
        "stage_no": 4,
        "stage": "inside a panel interval",
        "scope": "panel",
        "n": 40,
        "of_previous_pct": None,
        "note": "SCOPE CHANGE — annotation exists only inside the 8-gene panel.",
    },
    {
        "stage_no": 5,
        "stage": "VEP-annotated allele",
        "scope": "panel",
        "n": 42,
        "of_previous_pct": 105.0,
        "note": "Unit changes from record to allele.",
    },
    {
        "stage_no": 6,
        "stage": "rare in gnomAD",
        "scope": "panel",
        "n": 6,
        "of_previous_pct": 14.2857,
        "note": "gnomAD AF below 0.01 or absent entirely.",
    },
    {
        "stage_no": 7,
        "stage": "protein-altering",
        "scope": "panel",
        "n": 2,
        "of_previous_pct": 33.3333,
        "note": "VEP IMPACT HIGH or MODERATE.",
    },
    {
        "stage_no": 8,
        "stage": "in a gene carrying two or more",
        "scope": "panel",
        "n": 2,
        "of_previous_pct": 100.0,
        "note": "The compound-heterozygous shape. Phase unproven.",
    },
    {
        "stage_no": 9,
        "stage": "candidate pairs",
        "scope": "panel",
        "n": 1,
        "of_previous_pct": None,
        "note": "Every within-gene pairing: k*(k-1)/2 per gene.",
    },
]

#: Columns the chart and the table in ``app/src/pages/compare/CandidateFunnel.tsx`` read.
CONTRACT = {"stage_no", "stage", "scope", "n", "of_previous_pct", "note"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A TestClient whose only live answer is the funnel table."""

    def fetch(settings, sql, params=None):
        assert "candidate_funnel" in sql, f"unexpected SQL: {sql}"
        assert "ORDER BY stage_no" in sql, "the funnel is meaningless out of stage order"
        return [dict(row) for row in FUNNEL_ROWS]

    monkeypatch.setattr(queries, "fetch", fetch)
    monkeypatch.setattr(readstore, "root", lambda: "s3://test/reads")
    with TestClient(
        create_app(settings=None, cache=Cache(tmp_path), origins=["http://localhost:5173"])
    ) as running:
        yield running


def body(client) -> dict:
    response = client.get("/api/callset/funnel")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert set(payload) == {"data", "cached_at", "source"}
    return payload


def rows(client) -> list[dict]:
    return body(client)["data"]


# ── the route ────────────────────────────────────────────────────────────────────────


def test_the_endpoint_answers_in_the_shared_envelope(client):
    assert len(rows(client)) == len(FUNNEL_ROWS)


def test_it_is_live_rather_than_cached(client):
    """Nine rows off a derived table. A cache here would only hide a re-derive."""
    assert body(client)["cached_at"] is None


def test_the_source_names_the_derived_table_not_the_callset(client):
    """The expensive scan happens in ``pg-derive``; the request must not repeat it."""
    assert body(client)["source"] == "pg.results.candidate_funnel"


def test_the_route_is_documented_under_the_callset_tag(client):
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/api/callset/funnel"]["get"]
    assert operation["tags"] == ["callset"]


# ── the contract the chart reads ─────────────────────────────────────────────────────


def test_every_row_carries_exactly_the_six_declared_columns(client):
    for row in rows(client):
        assert set(row) == CONTRACT


def test_the_stages_arrive_in_pipeline_order(client):
    assert [row["stage_no"] for row in rows(client)] == list(range(1, 10))


def test_both_scopes_survive_the_round_trip(client):
    """The scope column is what stops the chart implying a genome-wide ranking."""
    scopes = [row["scope"] for row in rows(client)]
    assert set(scopes) == {"genome", "panel"}
    assert scopes == sorted(scopes, key=lambda s: 0 if s == "genome" else 1), (
        "the genome stages come first; a panel stage between them would be a lie"
    )


def test_a_non_nested_stage_reaches_the_client_as_null_not_zero(client):
    """`0 %` would draw a cliff that did not happen. The client renders null as n/a."""
    shares = {row["stage_no"]: row["of_previous_pct"] for row in rows(client)}
    assert shares[1] is None and shares[4] is None and shares[9] is None
    assert shares[2] == 90.0


def test_the_scope_change_is_labelled_in_the_payload_not_only_in_the_chart(client):
    """A reader who only ever sees the JSON still has to be told where the scope narrows."""
    first_panel = next(row for row in rows(client) if row["scope"] == "panel")
    assert "SCOPE CHANGE" in first_panel["note"]


def test_every_stage_explains_itself(client):
    """A funnel row is a claim that a filter is justified; the note is the justification."""
    for row in rows(client):
        assert row["note"].strip()


def test_no_stage_reports_a_null_count(client):
    """An empty stage is a finding and must arrive as 0, never as a blank the chart skips."""
    for row in rows(client):
        assert isinstance(row["n"], int)
