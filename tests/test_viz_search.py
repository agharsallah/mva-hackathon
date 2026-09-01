"""The universal search: query classification, the two resolvers, and the region read.

Nothing here reaches the network or the database. Ensembl is an ``httpx.MockTransport``
whose replies are trimmed copies of live ones recorded in
``docs/step-0/methodology/042-universal-search.md``; the warehouse is a fake ``fetch``
matched on a SQL fragment, in the style of ``tests/test_viz_api.py``.

**Every position in this file is fabricated**, with one class of exception: the two
Ensembl replies carry public dbSNP and Ensembl reference coordinates, which are published
data and already appear in ``tests/test_annotate_vep.py``. No proband position is here —
the live ones exist only in the cache under gitignored ``build/``.
"""

import httpx
import pytest
from fastapi.testclient import TestClient

from mva.viz import queries, readstore, routes_warehouse, search, search_resolve
from mva.viz.app import create_app
from mva.viz.cache import Cache
from mva.viz.genestructure import EnsemblError
from mva.viz.search import MAX_SPAN, NotFound, SpanTooLarge, Unparseable

# ── Ensembl replies, trimmed from live ones (public reference coordinates) ───────────

RS_REPLY = {
    "name": "rs137852899",
    "mappings": [
        # dbSNP also places variants on patches; the resolver must skip the non-chromosome
        # placement and take the GRCh38 chromosome one.
        {"seq_region_name": "CHR_HSCHR12_2_CTG2", "assembly_name": "GRCh38",
         "coord_system": "scaffold", "start": 999, "end": 999},
        {"seq_region_name": "12", "assembly_name": "GRCh38", "coord_system": "chromosome",
         "start": 101764236, "end": 101764236, "strand": 1, "allele_string": "C/T"},
    ],
}

SYMBOL_REPLY = {
    "id": "ENSG00000155657", "display_name": "TTN", "seq_region_name": "2",
    "assembly_name": "GRCh38", "start": 178525989, "end": 178830802, "strand": -1,
    "biotype": "protein_coding",
}

#: Ensembl's verified reply for an unknown rsID: **400**, not 404, with an ``error`` key.
UNKNOWN_REPLY = {"error": "rs99999999 not found for human"}


def client_for(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def replies(**by_fragment):
    """A transport answering on a fragment of the request path."""

    def handler(request: httpx.Request) -> httpx.Response:
        for fragment, (status, body) in by_fragment.items():
            if fragment in str(request.url):
                return httpx.Response(status, json=body)
        raise AssertionError(f"unexpected Ensembl call: {request.url}")

    return handler


# ── classification: shape alone, nothing looked up ───────────────────────────────────

class TestClassify:
    @pytest.mark.parametrize("query", [
        "15:40100000-40200000", "chr15:40100000-40200000", "CHR15:40100000-40200000",
        "15:40,100,000-40,200,000", "15:40100000..40200000", "15:40100000–40200000",
        "X:1000-2000", "chrM:1-500", "MT:1-500", " 15:100-200 ",
    ])
    def test_every_region_spelling_is_a_region(self, query):
        assert search.classify(query) == "region"

    def test_a_bare_point_is_a_region(self):
        assert search.classify("15:40100000") == "region"

    @pytest.mark.parametrize("query", ["rs137852899", "RS137852899", " rs1 "])
    def test_an_rsid_is_an_rsid(self, query):
        assert search.classify(query) == "rsid"

    @pytest.mark.parametrize("query", ["BUB1B", "TP53", "bub1b", "C1orf109", "HLA-A"])
    def test_a_symbol_is_a_gene(self, query):
        assert search.classify(query) == "gene"

    def test_rs_without_digits_is_a_gene_not_an_rsid(self):
        # RSPH1 is a real gene. Requiring digits after `rs` is what keeps it one.
        assert search.classify("RSPH1") == "gene"

    @pytest.mark.parametrize("query", ["", "   ", "15:", "-", "15:abc-def", "drop table",
                                       "chr99:1-2", "??"])
    def test_anything_else_is_refused_by_name(self, query):
        with pytest.raises(Unparseable):
            search.classify(query)

    def test_the_refusal_names_all_three_forms(self):
        with pytest.raises(Unparseable) as raised:
            search.classify("!!!")
        for example in search.EXAMPLES:
            assert example in str(raised.value)


class TestParseRegion:
    def test_the_chr_prefix_is_stripped_through_the_one_bridge(self):
        assert search.parse_region("chr15:100-200") == ("15", 100, 200)

    def test_mt_becomes_the_callsets_spelling(self):
        assert search.parse_region("chrMT:1-9")[0] == "M"

    def test_separators_are_tolerated(self):
        assert search.parse_region("15:40_100_000-40 200 000") == ("15", 40100000, 40200000)

    def test_a_point_is_widened_by_flank_on_both_sides(self):
        chrom, start, end = search.parse_region("15:50000")
        assert (chrom, start, end) == ("15", 50000 - search.FLANK, 50000 + search.FLANK)

    def test_a_point_near_the_contig_start_is_clamped_to_one(self):
        assert search.parse_region("15:10")[1] == 1

    def test_a_reversed_region_is_refused_rather_than_swapped(self):
        with pytest.raises(Unparseable):
            search.parse_region("15:200-100")


class TestSpanCap:
    def test_the_cap_itself_is_allowed(self):
        search.check_span(1, MAX_SPAN)

    def test_one_base_over_is_refused(self):
        with pytest.raises(SpanTooLarge):
            search.check_span(1, MAX_SPAN + 1)

    def test_the_message_carries_the_cap_so_the_ui_can_show_it(self):
        with pytest.raises(SpanTooLarge) as raised:
            search.check_span(1, 100_000_000)
        assert f"{MAX_SPAN:,}" in str(raised.value)

    def test_a_region_query_wider_than_the_cap_is_refused_at_resolution(self):
        with pytest.raises(SpanTooLarge):
            search.region_query("1:1-99000000")


# ── the resolvers, with Ensembl mocked and the warehouse faked ───────────────────────

def fake_fetch(monkeypatch, answers):
    """Replace ``queries.fetch`` with a fragment-matched lookup, recording every call."""
    calls = []

    def fetch(settings, sql, params=None):
        calls.append((sql, params))
        for fragment, rows in answers.items():
            if fragment in sql:
                return [dict(row) for row in rows]
        return []

    monkeypatch.setattr(queries, "fetch", fetch)
    return calls


class TestResolveRegion:
    def test_a_region_never_opens_a_client_or_touches_the_database(self, monkeypatch):
        calls = fake_fetch(monkeypatch, {})

        def refuse(*args, **kwargs):
            raise AssertionError("a region must not reach Ensembl")

        found = search_resolve.resolve("chr15:100-200", settings=None,
                                       client=client_for(refuse))
        assert (found.kind, found.chrom, found.start, found.end) == ("region", "15", 100, 200)
        assert found.source == search.SOURCE_QUERY
        assert found.note is None
        assert calls == []


class TestResolveGene:
    def test_the_panel_answers_first_and_ensembl_is_never_called(self, monkeypatch):
        fake_fetch(monkeypatch, {"mva_panel_grch38": [
            {"chrom": "chr15", "start": 1000, "end": 2000}]})

        def refuse(*args, **kwargs):
            raise AssertionError("a panel gene must not reach Ensembl")

        found = search_resolve.resolve("BUB1B", settings=object(),
                                       client=client_for(refuse))
        assert (found.kind, found.chrom, found.start, found.end) == ("gene", "15", 1000, 2000)
        assert found.source == search_resolve.SOURCE_PANEL
        assert "20 kb" in (found.note or "")

    def test_an_off_panel_symbol_falls_through_to_ensembl(self, monkeypatch):
        fake_fetch(monkeypatch, {})  # the panel knows nothing
        found = search_resolve.resolve(
            "TTN", settings=object(),
            client=client_for(replies(**{"lookup/symbol": (200, SYMBOL_REPLY)})))
        assert found.kind == "gene"
        assert found.chrom == "2"
        assert found.source == search_resolve.SOURCE_ENSEMBL_SYMBOL
        assert "unpadded" in (found.note or "")

    def test_a_symbol_ensembl_rejects_is_not_found_not_an_outage(self, monkeypatch):
        fake_fetch(monkeypatch, {})
        with pytest.raises(NotFound):
            search_resolve.resolve(
                "NOTAGENE", settings=object(),
                client=client_for(replies(**{"lookup/symbol": (
                    400, {"error": "No valid lookup found for symbol NOTAGENE"})})))

    def test_ensembl_down_is_an_outage_not_a_missing_gene(self, monkeypatch):
        fake_fetch(monkeypatch, {})

        def broken(request):
            raise httpx.ConnectError("connection refused")

        with pytest.raises(EnsemblError):
            search_resolve.resolve("TTN", settings=object(), client=client_for(broken))

    def test_a_five_hundred_is_an_outage_too(self, monkeypatch):
        fake_fetch(monkeypatch, {})
        with pytest.raises(EnsemblError):
            search_resolve.resolve(
                "TTN", settings=object(),
                client=client_for(replies(**{"lookup/symbol": (500, {"error": "boom"})})))


class TestResolveRsid:
    def test_the_callset_answers_first_and_ensembl_is_never_called(self, monkeypatch):
        fake_fetch(monkeypatch, {"variants_raw": [{"chrom": "15", "pos": "500000"}]})

        def refuse(*args, **kwargs):
            raise AssertionError("an rsID in the callset must not reach Ensembl")

        found = search_resolve.resolve("rs137852899", settings=object(),
                                       client=client_for(refuse))
        assert found.kind == "rsid"
        assert (found.chrom, found.start, found.end) == (
            "15", 500000 - search.FLANK, 500000 + search.FLANK)
        assert found.source == search_resolve.SOURCE_CALLSET

    def test_the_scan_is_an_exact_match_because_no_id_is_semicolon_packed(self, monkeypatch):
        calls = fake_fetch(monkeypatch, {"variants_raw": [{"chrom": "1", "pos": "9"}]})
        search_resolve.resolve("rs1", settings=object(),
                               client=client_for(lambda r: httpx.Response(200, json={})))
        sql, params = calls[0]
        assert "id = ?" in sql and "LIKE" not in sql
        assert params == ["rs1"]

    def test_the_query_is_lowercased_so_RS_and_rs_hit_the_same_row(self, monkeypatch):
        calls = fake_fetch(monkeypatch, {"variants_raw": [{"chrom": "1", "pos": "9"}]})
        search_resolve.resolve("RS137852899", settings=object(),
                               client=client_for(lambda r: httpx.Response(200, json={})))
        assert calls[0][1] == ["rs137852899"]

    def test_absent_from_the_callset_falls_through_to_ensembl_and_says_so(self, monkeypatch):
        fake_fetch(monkeypatch, {})  # the scan finds nothing
        found = search_resolve.resolve(
            "rs137852899", settings=object(),
            client=client_for(replies(**{"variation/human": (200, RS_REPLY)})))
        assert found.source == search_resolve.SOURCE_ENSEMBL_RSID
        assert found.chrom == "12"
        # The distinction the whole two-stage design exists for.
        assert "never called" in (found.note or "")

    def test_a_scaffold_placement_is_skipped_for_the_chromosome_one(self, monkeypatch):
        fake_fetch(monkeypatch, {})
        found = search_resolve.resolve(
            "rs137852899", settings=object(),
            client=client_for(replies(**{"variation/human": (200, RS_REPLY)})))
        assert found.start == 101764236 - search.FLANK

    def test_an_unknown_rsid_is_not_found_even_though_ensembl_says_400(self, monkeypatch):
        fake_fetch(monkeypatch, {})
        with pytest.raises(NotFound) as raised:
            search_resolve.resolve(
                "rs99999999", settings=object(),
                client=client_for(replies(**{"variation/human": (400, UNKNOWN_REPLY)})))
        assert "not found for human" in str(raised.value)

    def test_a_reply_with_no_grch38_chromosome_is_not_found(self, monkeypatch):
        fake_fetch(monkeypatch, {})
        stale = {"mappings": [{"seq_region_name": "12", "assembly_name": "GRCh37",
                               "coord_system": "chromosome", "start": 1}]}
        with pytest.raises(NotFound):
            search_resolve.resolve(
                "rs1", settings=object(),
                client=client_for(replies(**{"variation/human": (200, stale)})))


# ── the region read ──────────────────────────────────────────────────────────────────

RAW = [
    {"pos": "1500", "id": "rs1", "ref": "T", "alt": "C", "qual": "812.5",
     "filter": "PASS", "format": "GT:AD:DP:GQ", "sample_call": "0/1:20,18:38:99"},
    {"pos": "1600", "id": ".", "ref": "G", "alt": "A,T", "qual": "44.0",
     "filter": "LowQual", "format": "GT:AD:DP:GQ", "sample_call": "1/2:3,9,7:19:41"},
]


class TestRegionRead:
    def test_the_contig_is_pushed_down_before_the_position_range(self, monkeypatch):
        calls = fake_fetch(monkeypatch, {"variants_raw": RAW})
        search.region(object(), "chr15", 1000, 2000)
        sql, params = calls[0]
        assert sql.index("chrom = ?") < sql.index("CAST(pos AS BIGINT) BETWEEN")
        assert params == ["15", 1000, 2000]

    def test_the_echo_names_the_window_the_payload_is_for(self, monkeypatch):
        fake_fetch(monkeypatch, {"variants_raw": RAW})
        found = search.region(object(), "chr15", 1000, 2000)
        assert (found["chrom"], found["start"], found["end"], found["n"]) == \
               ("15", 1000, 2000, 2)

    def test_a_dot_id_becomes_null_rather_than_a_literal_dot(self, monkeypatch):
        fake_fetch(monkeypatch, {"variants_raw": RAW})
        rows = search.region(object(), "15", 1000, 2000)["variants"]
        assert rows[0]["id"] == "rs1"
        assert rows[1]["id"] is None

    def test_a_multiallelic_site_reports_no_single_alt_depth(self, monkeypatch):
        fake_fetch(monkeypatch, {"variants_raw": RAW})
        rows = search.region(object(), "15", 1000, 2000)["variants"]
        assert rows[1]["alt"] == "A,T"          # comma-packed, exactly as delivered
        assert rows[1]["ad_alt"] is None
        assert rows[1]["vaf"] is None

    def test_the_row_shape_is_the_documented_one(self, monkeypatch):
        fake_fetch(monkeypatch, {"variants_raw": RAW})
        rows = search.region(object(), "15", 1000, 2000)["variants"]
        assert set(rows[0]) == {"pos", "id", "ref", "alt", "qual", "filter", "gt", "dp",
                                "ad_ref", "ad_alt", "vaf", "gq"}

    def test_an_unspellable_contig_is_refused_before_any_query(self, monkeypatch):
        calls = fake_fetch(monkeypatch, {"variants_raw": RAW})
        with pytest.raises(Unparseable):
            search.region(object(), "chr99", 1, 100)
        assert calls == []

    def test_a_window_over_the_cap_is_refused_before_any_query(self, monkeypatch):
        calls = fake_fetch(monkeypatch, {"variants_raw": RAW})
        with pytest.raises(SpanTooLarge):
            search.region(object(), "15", 1, MAX_SPAN + 2)
        assert calls == []


# ── the HTTP surface ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def api(tmp_path, monkeypatch):
    """The whole app, with the warehouse faked and Ensembl genuinely unreachable.

    The panel answers for ``BUB1B`` only, so an off-panel symbol really does fall through
    to the Ensembl path — which is how the outage status is exercised over HTTP.
    """

    def fetch(settings, sql, params=None):
        if "mva_panel_grch38" in sql:
            return ([{"chrom": "chr15", "start": 1000, "end": 2000}]
                    if params == ["BUB1B"] else [])
        if "variants_raw" in sql:
            return [dict(row) for row in RAW]
        return []

    monkeypatch.setattr(queries, "fetch", fetch)
    monkeypatch.setattr(routes_warehouse, "overview", lambda settings: {})
    monkeypatch.setattr(readstore, "root", lambda: "s3://test/reads")
    with TestClient(create_app(settings=None, cache=Cache(tmp_path),
                               origins=["http://localhost:5173"])) as running:
        yield running


def envelope(response):
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"data", "cached_at", "source"}
    assert body["source"]
    return body


class TestSearchEndpoint:
    def test_a_region_resolves_live_and_uncached(self, api):
        body = envelope(api.get("/api/search", params={"q": "chr15:1000-2000"}))
        assert body["cached_at"] is None
        assert body["data"]["kind"] == "region"
        assert body["data"]["chrom"] == "15"

    def test_the_envelope_source_is_the_resolver_that_answered(self, api):
        body = envelope(api.get("/api/search", params={"q": "BUB1B"}))
        assert body["source"] == body["data"]["source"] == search_resolve.SOURCE_PANEL

    def test_a_looked_up_resolution_is_cached_and_refreshable(self, api):
        first = envelope(api.get("/api/search", params={"q": "BUB1B"}))
        assert first["cached_at"] is not None
        again = envelope(api.get("/api/search", params={"q": "BUB1B", "refresh": "true"}))
        assert again["data"] == first["data"]

    def test_the_payload_carries_every_documented_field(self, api):
        data = envelope(api.get("/api/search", params={"q": "BUB1B"}))["data"]
        assert set(data) == {"kind", "chrom", "start", "end", "label", "source", "note"}

    def test_an_unparseable_query_is_422_naming_the_three_forms(self, api):
        response = api.get("/api/search", params={"q": "!!!"})
        assert response.status_code == 422
        assert "rs137852899" in response.json()["detail"]

    def test_a_region_wider_than_the_cap_is_422_carrying_the_cap(self, api):
        response = api.get("/api/search", params={"q": "1:1-99000000"})
        assert response.status_code == 422
        assert f"{MAX_SPAN:,}" in response.json()["detail"]

    def test_ensembl_unreachable_is_502_not_a_guessed_coordinate(self, api, monkeypatch):
        # Still hermetic: 127.0.0.1:1 refuses the connection without a packet leaving the
        # machine, so this is the real client on the real code path, not a stubbed error.
        monkeypatch.setattr(search_resolve, "ENSEMBL_BASE", "http://127.0.0.1:1")
        response = api.get("/api/search", params={"q": "TTN"})
        assert response.status_code == 502
        assert "127.0.0.1:1" in response.json()["detail"]

    def test_a_name_no_authority_knows_is_404(self, api, monkeypatch):
        def missing(*args, **kwargs):
            raise NotFound("Ensembl does not know 'NOTAGENE'")

        monkeypatch.setattr(search_resolve, "resolve", missing)
        response = api.get("/api/search", params={"q": "NOTAGENE"})
        assert response.status_code == 404
        assert "NOTAGENE" in response.json()["detail"]


class TestRegionEndpoint:
    def test_it_answers_the_window_and_caches_it(self, api):
        body = envelope(api.get("/api/callset/region",
                                params={"chrom": "chr15", "start": 1000, "end": 2000}))
        assert body["cached_at"] is not None
        assert body["data"]["n"] == 2
        assert body["source"] == search.REGION_SOURCE

    def test_the_cache_key_separates_two_different_windows(self, api, tmp_path):
        api.get("/api/callset/region", params={"chrom": "15", "start": 1, "end": 100})
        api.get("/api/callset/region", params={"chrom": "15", "start": 200, "end": 300})
        keys = sorted(path.name for path in tmp_path.glob("region-*.json"))
        assert keys == ["region-15-1-100.json", "region-15-200-300.json"]

    def test_a_bad_contig_is_422(self, api):
        response = api.get("/api/callset/region",
                           params={"chrom": "chr99", "start": 1, "end": 100})
        assert response.status_code == 422

    def test_a_window_over_the_cap_is_422_with_the_cap_in_the_message(self, api):
        response = api.get("/api/callset/region",
                           params={"chrom": "15", "start": 1, "end": MAX_SPAN + 2})
        assert response.status_code == 422
        assert f"{MAX_SPAN:,}" in response.json()["detail"]

    def test_an_empty_window_is_a_finding_not_an_error(self, api, monkeypatch):
        fake_fetch(monkeypatch, {})  # nothing in the callset there
        body = envelope(api.get("/api/callset/region",
                                params={"chrom": "7", "start": 5000, "end": 6000}))
        assert body["data"]["n"] == 0
        assert body["data"]["variants"] == []
