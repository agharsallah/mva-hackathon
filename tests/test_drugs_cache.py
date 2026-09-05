"""The cached, polite HTTP client: hit, miss, refresh, retries and the provenance digest.

The real :class:`mva.drugs.cache.Fetcher` runs here — only its ``httpx.Client`` is faked,
by assigning ``_client`` before the first call, which is the seam ``_live`` leaves open.
So the cache key, the on-disk record shape, the retry ladder and the digest roll-up are
all exercised for real. ``min_interval_s`` is zero throughout: the politeness sleep is a
property of the live run, not of these assertions.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mva.drugs.cache import Fetcher, SourceError
from test_drugs_support import FakeClient, FakeReply

URL = "https://example.test/api"


def fetcher(tmp_path: Path, replies: list[FakeReply], **kwargs) -> tuple[Fetcher, FakeClient]:
    client = FakeClient(replies)
    made = Fetcher(source="test", cache_dir=tmp_path, min_interval_s=0.0, **kwargs)
    made._client = client
    return made, client


class TestCaching:
    def test_a_second_identical_call_is_a_cache_hit_and_makes_no_request(
        self, tmp_path: Path
    ) -> None:
        got, client = fetcher(tmp_path, [FakeReply(200, {"n": 1})])
        assert got.get_json(URL, {"q": "a"}) == {"n": 1}
        assert got.get_json(URL, {"q": "a"}) == {"n": 1}
        assert len(client.requests) == 1
        assert got.live_calls == 1
        assert len(got.replies) == 2

    def test_different_params_are_a_different_key(self, tmp_path: Path) -> None:
        got, client = fetcher(tmp_path, [FakeReply(200, {"n": 1}), FakeReply(200, {"n": 2})])
        assert got.get_json(URL, {"q": "a"}) == {"n": 1}
        assert got.get_json(URL, {"q": "b"}) == {"n": 2}
        assert len(client.requests) == 2

    def test_param_order_does_not_change_the_key(self, tmp_path: Path) -> None:
        got, client = fetcher(tmp_path, [FakeReply(200, {"n": 1})])
        got.get_json(URL, {"a": 1, "b": 2})
        got.get_json(URL, {"b": 2, "a": 1})
        assert len(client.requests) == 1

    def test_a_post_body_is_part_of_the_key(self, tmp_path: Path) -> None:
        got, client = fetcher(tmp_path, [FakeReply(200, {"n": 1}), FakeReply(200, {"n": 2})])
        got.post_json(URL, {"query": "one"})
        got.post_json(URL, {"query": "two"})
        assert len(client.requests) == 2

    def test_a_get_and_a_post_to_the_same_url_do_not_collide(self, tmp_path: Path) -> None:
        got, client = fetcher(tmp_path, [FakeReply(200, {"n": 1}), FakeReply(200, {"n": 2})])
        got.get_json(URL, {"x": 1})
        got.post_json(URL, {"x": 1})
        assert len(client.requests) == 2

    def test_refresh_bypasses_the_cache_for_that_call(self, tmp_path: Path) -> None:
        got, client = fetcher(tmp_path, [FakeReply(200, {"n": 1}), FakeReply(200, {"n": 9})])
        assert got.get_json(URL, {"q": "a"}) == {"n": 1}
        assert got.get_json(URL, {"q": "a"}, refresh=True) == {"n": 9}
        assert len(client.requests) == 2
        # ...and the refreshed reply replaced the cached one.
        assert got.get_json(URL, {"q": "a"}) == {"n": 9}

    def test_refresh_on_the_fetcher_applies_to_every_call(self, tmp_path: Path) -> None:
        first, _ = fetcher(tmp_path, [FakeReply(200, {"n": 1})])
        first.get_json(URL, {"q": "a"})
        second, client = fetcher(tmp_path, [FakeReply(200, {"n": 2})], refresh=True)
        assert second.get_json(URL, {"q": "a"}) == {"n": 2}
        assert len(client.requests) == 1

    def test_the_cache_file_records_url_params_status_and_body(self, tmp_path: Path) -> None:
        got, _ = fetcher(tmp_path, [FakeReply(200, {"n": 1}, url="https://example.test/api?q=a")])
        got.get_json(URL, {"q": "a"})
        path = got.path_for("GET", URL, {"q": "a"})
        record = json.loads(path.read_text(encoding="utf-8"))
        assert record["status"] == 200
        assert record["params"] == {"q": "a"}
        assert record["body"] == {"n": 1}
        assert record["retrieved_at"].endswith("+00:00")

    def test_a_corrupt_cache_file_is_a_miss_not_a_crash(self, tmp_path: Path) -> None:
        got, client = fetcher(tmp_path, [FakeReply(200, {"n": 1})])
        path = got.path_for("GET", URL, None)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not json", encoding="utf-8")
        assert got.get_json(URL) == {"n": 1}
        assert len(client.requests) == 1


class TestErrors:
    def test_a_500_is_retried_then_succeeds(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr("time.sleep", lambda _s: None)
        got, client = fetcher(tmp_path, [FakeReply(500, {}), FakeReply(200, {"n": 1})])
        assert got.get_json(URL) == {"n": 1}
        assert len(client.requests) == 2

    def test_three_failures_raise_a_source_error_naming_the_url(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.setattr("time.sleep", lambda _s: None)
        got, _ = fetcher(tmp_path, [FakeReply(429, {}) for _ in range(3)])
        with pytest.raises(SourceError) as caught:
            got.get_json(URL)
        assert caught.value.url == URL
        assert "429" in str(caught.value)

    def test_a_404_raises_unless_the_caller_allows_it(self, tmp_path: Path) -> None:
        got, _ = fetcher(tmp_path, [FakeReply(404, {"error": "nope"})])
        with pytest.raises(SourceError):
            got.get_json(URL, {"q": "a"})

    def test_an_allowed_404_returns_the_body_and_is_cached(self, tmp_path: Path) -> None:
        got, client = fetcher(tmp_path, [FakeReply(404, {"error": "nope"})])
        assert got.get_json(URL, {"q": "a"}, allow_status=(404,)) == {"error": "nope"}
        assert got.get_json(URL, {"q": "a"}, allow_status=(404,)) == {"error": "nope"}
        assert len(client.requests) == 1

    def test_a_cached_error_still_raises_when_not_allowed(self, tmp_path: Path) -> None:
        got, _ = fetcher(tmp_path, [FakeReply(404, {"error": "nope"})])
        got.get_json(URL, {"q": "a"}, allow_status=(404,))
        with pytest.raises(SourceError):
            got.get_json(URL, {"q": "a"})


class TestProvenance:
    def test_the_digest_is_stable_and_order_free(self, tmp_path: Path) -> None:
        one, _ = fetcher(tmp_path / "a", [FakeReply(200, {"n": 1}), FakeReply(200, {"n": 2})])
        one.get_json(URL, {"q": "a"})
        one.get_json(URL, {"q": "b"})

        two, _ = fetcher(tmp_path / "b", [FakeReply(200, {"n": 2}), FakeReply(200, {"n": 1})])
        two.get_json(URL, {"q": "b"})
        two.get_json(URL, {"q": "a"})

        assert one.digest == two.digest

    def test_a_different_body_changes_the_digest(self, tmp_path: Path) -> None:
        one, _ = fetcher(tmp_path / "a", [FakeReply(200, {"n": 1})])
        one.get_json(URL)
        two, _ = fetcher(tmp_path / "b", [FakeReply(200, {"n": 99})])
        two.get_json(URL)
        assert one.digest != two.digest

    def test_the_window_spans_every_reply_used(self, tmp_path: Path) -> None:
        got, _ = fetcher(tmp_path, [FakeReply(200, {"n": 1}), FakeReply(200, {"n": 2})])
        got.get_json(URL, {"q": "a"})
        got.get_json(URL, {"q": "b"})
        window = got.window
        assert window is not None
        assert window[0] <= window[1]

    def test_no_replies_means_no_window(self, tmp_path: Path) -> None:
        assert Fetcher(source="test", cache_dir=tmp_path).window is None
