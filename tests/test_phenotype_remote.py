"""Tests for the two hosted cross-checks: parsing, retries, and refusing to raise.

No test here reaches the network. The transport is an ``httpx.MockTransport`` and the
sleep function is a recorder, so a rate-limit test costs no wall-clock — the same
discipline ``tests/test_annotate_vep.py`` applies to the VEP client, for the same reason.

The property under test throughout is that **a cross-check never costs the run**. These
services are corroboration; a run that died because a third-party API was rebooting would
be the worst possible trade.
"""

import httpx
import pytest

from mva.phenotype import remote

TERMS = ("HP:0002859", "HP:0000121")


class Recorder:
    """A stand-in for ``time.sleep`` that records instead of waiting."""

    def __init__(self) -> None:
        self.waits: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.waits.append(seconds)


def client_for(handler, **kwargs) -> remote.RemoteClient:
    return remote.RemoteClient(
        base_url="https://example.invalid",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=Recorder(),
        **kwargs,
    )


# ── Phen2Gene ────────────────────────────────────────────────────────────────────────

PHEN2GENE_REPLY = {
    "results": [
        {"Gene": "BUB1B", "Rank": "1", "Score": "1.0", "Status": "SeedGene"},
        {"Gene": "trip13", "Rank": "2", "Score": "0.42", "Status": "SeedGene"},
    ],
    "errors": [],
}


def test_phen2gene_parses_its_string_ranks_and_scores_into_numbers() -> None:
    """The service returns both as strings; a rank is not a number until it is parsed."""
    ranking = remote.phen2gene(
        TERMS, client=client_for(lambda r: httpx.Response(200, json=PHEN2GENE_REPLY))
    )
    assert ranking.ok
    assert ranking.genes[0] == remote.RemoteGene("BUB1B", 1, 1.0)
    assert ranking.rank_of("BUB1B") == 1


def test_phen2gene_uppercases_symbols_so_the_join_cannot_miss_on_case() -> None:
    ranking = remote.phen2gene(
        TERMS, client=client_for(lambda r: httpx.Response(200, json=PHEN2GENE_REPLY))
    )
    assert ranking.rank_of("TRIP13") == 2


def test_phen2gene_sends_the_terms_semicolon_joined() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.url.params)
        return httpx.Response(200, json=PHEN2GENE_REPLY)

    remote.phen2gene(TERMS, client=client_for(handler))
    assert seen["HPO_list"] == "HP:0002859;HP:0000121"
    assert seen["weight_model"] == remote.DEFAULT_WEIGHT_MODEL


def test_phen2gene_echoes_the_query_back_so_a_stored_result_names_it() -> None:
    ranking = remote.phen2gene(
        TERMS, client=client_for(lambda r: httpx.Response(200, json=PHEN2GENE_REPLY))
    )
    assert ranking.terms == TERMS


def test_phen2gene_respects_a_limit() -> None:
    ranking = remote.phen2gene(
        TERMS, client=client_for(lambda r: httpx.Response(200, json=PHEN2GENE_REPLY)), limit=1
    )
    assert len(ranking) == 1


def test_a_row_with_no_gene_name_is_skipped_rather_than_ranked() -> None:
    reply = {"results": [{"Rank": "1"}, {"Gene": "BUB1B", "Rank": "2", "Score": "0.5"}]}
    ranking = remote.phen2gene(TERMS, client=client_for(lambda r: httpx.Response(200, json=reply)))
    assert [gene.symbol for gene in ranking.genes] == ["BUB1B"]


# ── Monarch semsim ───────────────────────────────────────────────────────────────────


MONARCH_REPLY = [
    {"subject": {"id": "HGNC:1149", "symbol": "BUB1B"}, "score": 8.9},
    {"subject": {"id": "HGNC:11679", "symbol": "tp53"}, "score": 4.1},
]


def test_monarch_reads_the_symbol_out_of_the_subject_object() -> None:
    ranking = remote.monarch_semsim(
        TERMS, client=client_for(lambda r: httpx.Response(200, json=MONARCH_REPLY))
    )
    assert ranking.ok
    assert [gene.symbol for gene in ranking.genes] == ["BUB1B", "TP53"]
    assert ranking.genes[0].score == pytest.approx(8.9)


def test_monarch_preserves_the_services_own_ordering() -> None:
    """Its score scale is not ours. Re-sorting would invent a ranking rather than read one."""
    reply = [
        {"subject": {"symbol": "LOW"}, "score": 1.0},
        {"subject": {"symbol": "HIGH"}, "score": 9.0},
    ]
    ranking = remote.monarch_semsim(
        TERMS, client=client_for(lambda r: httpx.Response(200, json=reply))
    )
    assert [gene.symbol for gene in ranking.genes] == ["LOW", "HIGH"]


def test_monarch_accepts_a_wrapped_result_list() -> None:
    """The service has returned both a bare list and an object wrapping one."""
    reply = {"items": [{"subject": {"symbol": "BUB1B"}, "score": 0.5}]}
    ranking = remote.monarch_semsim(
        TERMS, client=client_for(lambda r: httpx.Response(200, json=reply))
    )
    assert ranking.rank_of("BUB1B") == 1


def test_a_subject_with_no_symbol_is_skipped() -> None:
    reply = [{"subject": {"id": "HGNC:1"}}, {"subject": {"symbol": "BUB1B"}, "score": 1.0}]
    ranking = remote.monarch_semsim(
        TERMS, client=client_for(lambda r: httpx.Response(200, json=reply))
    )
    assert [gene.symbol for gene in ranking.genes] == ["BUB1B"]


def test_monarch_posts_the_termset_and_asks_for_human_genes() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen.update(json.loads(request.content))
        return httpx.Response(200, json=[])

    remote.monarch_semsim(TERMS, client=client_for(handler))
    assert seen["termset"] == list(TERMS)
    assert seen["group"] == remote.HUMAN_GENES


def test_monarch_clamps_the_limit_to_what_the_service_returns() -> None:
    """Asking for more silently returns the cap, so the window is stated rather than hoped for."""
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen.update(json.loads(request.content))
        return httpx.Response(200, json=[])

    remote.monarch_semsim(TERMS, client=client_for(handler), limit=5000)
    assert seen["limit"] == remote.MONARCH_MAX_RESULTS


# ── failure is a normal outcome, never an exception ──────────────────────────────────


def test_a_server_error_returns_an_empty_ranking_carrying_the_reason() -> None:
    """A blank cross-check must read as "unreachable", never as "disagreed"."""
    ranking = remote.phen2gene(
        TERMS, client=client_for(lambda r: httpx.Response(500, text="boom"), max_attempts=2)
    )
    assert not ranking.ok
    assert ranking.genes == ()
    assert "gave up after 2 attempts" in (ranking.error or "")


def test_a_client_error_is_reported_without_retrying() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(404, text="no such route")

    ranking = remote.phen2gene(TERMS, client=client_for(handler))
    assert not ranking.ok
    assert len(calls) == 1  # retrying a 404 cannot help


def test_a_transport_failure_is_caught_rather_than_raised() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("name resolution failed")

    ranking = remote.monarch_semsim(TERMS, client=client_for(handler, max_attempts=2))
    assert not ranking.ok
    assert "ConnectError" in (ranking.error or "")


def test_a_two_hundred_carrying_html_is_reported_not_retried() -> None:
    """What a captive portal or an error page looks like. Retrying cannot fix it."""
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(200, text="<html>maintenance</html>")

    ranking = remote.phen2gene(TERMS, client=client_for(handler))
    assert not ranking.ok
    assert "unparseable JSON" in (ranking.error or "")
    assert len(calls) == 1


def test_a_rate_limit_waits_exactly_as_long_as_the_server_asked() -> None:
    """Guessing shorter is how a client gets throttled for the rest of the hour."""
    sleeper = Recorder()
    replies = [
        httpx.Response(429, headers={"Retry-After": "7"}),
        httpx.Response(200, json=PHEN2GENE_REPLY),
    ]
    transport = remote.RemoteClient(
        base_url="https://example.invalid",
        client=httpx.Client(transport=httpx.MockTransport(lambda r: replies.pop(0))),
        sleep=sleeper,
    )
    ranking = remote.phen2gene(TERMS, client=transport)
    assert ranking.ok
    assert sleeper.waits == [7.0]


def test_a_rate_limit_without_a_usable_header_falls_back_to_backoff() -> None:
    sleeper = Recorder()
    replies = [
        httpx.Response(429, headers={"Retry-After": "soon"}),
        httpx.Response(200, json=PHEN2GENE_REPLY),
    ]
    transport = remote.RemoteClient(
        base_url="https://example.invalid",
        client=httpx.Client(transport=httpx.MockTransport(lambda r: replies.pop(0))),
        sleep=sleeper,
        backoff=1.0,
    )
    remote.phen2gene(TERMS, client=transport)
    assert sleeper.waits == [1.0]


def test_backoff_grows_exponentially_and_is_bounded() -> None:
    sleeper = Recorder()
    transport = remote.RemoteClient(
        base_url="https://example.invalid",
        client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503))),
        sleep=sleeper,
        max_attempts=4,
        backoff=1.0,
    )
    remote.phen2gene(TERMS, client=transport)
    assert sleeper.waits == [1.0, 2.0, 4.0, 8.0]


def test_a_ranking_that_failed_reports_no_rank_for_any_gene() -> None:
    ranking = remote.RemoteRanking("phen2gene", error="unreachable")
    assert ranking.rank_of("BUB1B") is None
    assert len(ranking) == 0


def test_the_client_only_closes_a_connection_it_created() -> None:
    """A caller sharing one client across both services must not have it closed underneath."""
    shared = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=[])))
    transport = remote.RemoteClient(
        base_url="https://example.invalid", client=shared, sleep=Recorder()
    )
    transport.close()
    assert not shared.is_closed
