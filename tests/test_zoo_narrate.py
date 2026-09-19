"""Section 6, generated: the rows, the prompt, the two modes and what gets stored.

No test here spawns a process or opens a socket. Both modes are exercised through
:class:`mva.zoo.narrate_modes.FakeTransport` and through their own reply parsers, which is
what lets the ``nebius`` mode be tested on a machine that has no ``NEBIUS_API_KEY``.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from mva.zoo import narrate, report
from mva.zoo.narrate_check import check_narrative
from mva.zoo.narrate_modes import (
    ClaudeCodeTransport,
    FakeTransport,
    LlmSettings,
    NebiusTransport,
    _reply_from_claude_json,
    _reply_from_litellm,
    build_transport,
)
from mva.zoo.narrate_rows import build_prompt, citable_rows

REPORT = {
    "model": "demo",
    "run_id": "demo-0001",
    "sections": {
        "inputs": {
            "scored": 27,
            "total": 200,
            "fraction": 0.135,
            "by_consequence": [
                {"consequence": "missense_variant", "scored": 27, "total": 40, "fraction": 0.675},
                {"consequence": "stop_gained", "scored": 0, "total": 30, "fraction": 0.0},
                {"consequence": "mature_miRNA_variant", "scored": 0, "total": 1, "fraction": 0.0},
            ],
        },
        "distribution": {
            "n": 27,
            "min": 0.01,
            "mean": 0.12,
            "max": 0.99,
            "quantiles": {"p01": 0.02, "p50": 0.08, "p90": 0.21, "p99": 0.81},
            "marks": [
                {"allele_id": "aaaa", "role": "left", "score": None, "percentile": None},
                {"allele_id": "bbbb", "role": "right", "score": 0.92, "percentile": 0.47},
            ],
        },
        "confirmed_pair": {
            "gene": "BUB1B",
            "rank": None,
            "n_ranked": 10333,
            "percentile": None,
            "left_percentile": None,
            "right_percentile": 0.47,
            "mode": "catalogue-free",
        },
        "clinical": {"sentence": "Against the child's 8 HPO terms, `BUB1B` ranks #14 of 5267."},
    },
}


def ids(rows) -> set[str]:
    return {row["id"] for row in rows}


class TestCitableRows:
    def test_the_ids_the_prompt_promises_are_all_there(self):
        found = ids(citable_rows(REPORT))
        assert {
            "cov.scored",
            "cov.total",
            "cov.fraction",
            "cov.missense_variant",
            "dist.n",
            "dist.p90",
            "dist.mark.left",
            "dist.mark.right",
            "pair.gene",
            "pair.rank",
            "pair.left_percentile",
            "pair.mode",
            "hpo.rank",
        } <= found

    def test_a_class_the_lane_scored_is_kept_however_small(self):
        assert "cov.stop_gained" in ids(citable_rows(REPORT))  # 15 % of the set, 0 scored

    def test_a_tiny_class_the_lane_never_scored_is_left_out_of_the_prompt(self):
        assert "cov.mature_miRNA_variant" not in ids(citable_rows(REPORT))

    def test_a_lane_with_no_opinion_says_so_in_words_rather_than_a_null(self):
        rank_row = next(row for row in citable_rows(REPORT) if row["id"] == "pair.rank")
        assert "no rank" in rank_row["text"]

    def test_a_case_with_no_confirmed_gene_has_no_gene_row(self):
        payload = json.loads(json.dumps(REPORT))
        payload["sections"]["confirmed_pair"]["gene"] = None
        assert "pair.gene" not in ids(citable_rows(payload))

    def test_the_rows_carry_no_score_the_report_json_does_not(self):
        # The JSON computes, the prompt prints — the same rule the renderer obeys.
        text = " ".join(row["text"] for row in citable_rows(REPORT))
        assert "0.92" in text and "0.99" in text
        assert "0.93" not in text


class TestPrompt:
    def test_the_prompt_is_the_rules_plus_the_rows_and_nothing_else(self):
        rows = citable_rows(REPORT)
        prompt = build_prompt(rows, max_words=200)
        assert "at most 200 words" in prompt
        assert "Do not rank anything" in prompt
        for row in rows:
            assert f"[{row['id']}]" in prompt

    def test_the_word_budget_is_the_config_s_not_a_constant(self):
        assert "at most 75 words" in build_prompt(citable_rows(REPORT), max_words=75)

    def test_the_prompt_never_asks_which_gene_or_pair_is_the_answer(self):
        prompt = build_prompt(citable_rows(REPORT)).lower()
        assert "which gene" not in prompt
        assert "causal" not in prompt
        assert "diagnos" not in prompt


class TestModes:
    def test_mode_none_calls_nothing_and_returns_nothing(self):
        assert build_transport("none") is None
        assert narrate.narrate_report(REPORT, mode="none") is None

    def test_an_unknown_mode_stops_the_run(self):
        with pytest.raises(ValueError, match="unknown llm mode"):
            build_transport("gpt-by-post")

    def test_claude_code_is_the_transport_for_its_mode(self):
        transport = build_transport("claude-code", model="opus")
        assert isinstance(transport, ClaudeCodeTransport)
        assert transport.model == "opus"

    def test_nebius_is_the_transport_for_its_mode_and_carries_the_temperature(self):
        transport = build_transport("nebius", model="Qwen/Q", temperature=0.0)
        assert isinstance(transport, NebiusTransport)
        assert (transport.model, transport.temperature) == ("Qwen/Q", 0.0)

    def test_nebius_without_a_key_says_so_rather_than_calling_anything(self, monkeypatch):
        monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="NEBIUS_API_KEY"):
            NebiusTransport()("a prompt")

    def test_the_claude_reply_parser_takes_the_text_the_model_id_and_the_cost(self):
        reply = _reply_from_claude_json(
            json.dumps(
                {
                    "result": "  the prose  ",
                    "modelUsage": {"claude-opus-5[1m]": {"inputTokens": 2}},
                    "duration_ms": 1674,
                    "total_cost_usd": 0.06,
                    "is_error": False,
                }
            ),
            seconds=9.9,
        )
        assert (reply.text, reply.model_id, reply.seconds) == (
            "the prose",
            "claude-opus-5[1m]",
            1.674,
        )
        assert reply.dollars == 0.06

    def test_a_claude_error_reply_is_raised_not_stored_as_a_narrative(self):
        with pytest.raises(RuntimeError, match="reported an error"):
            _reply_from_claude_json(json.dumps({"is_error": True, "result": "boom"}), 0.0)

    def test_non_json_from_the_cli_is_a_clear_error(self):
        with pytest.raises(RuntimeError, match="did not return JSON"):
            _reply_from_claude_json("not json at all", 0.0)

    def test_the_litellm_reply_parser_reads_the_openai_shape(self):
        reply = _reply_from_litellm(
            {
                "model": "nebius/Qwen/Q",
                "choices": [{"message": {"content": " hello "}}],
                "usage": {"total_tokens": 12},
                "id": "abc",
            },
            seconds=1.5,
            fallback_model="Qwen/Q",
        )
        assert (reply.text, reply.model_id, reply.seconds) == ("hello", "nebius/Qwen/Q", 1.5)


class TestLlmSettings:
    def test_the_shipped_config_block_parses(self):
        settings = LlmSettings.load(Path("src/mva/zoo/zoo.example.toml"))
        assert (settings.mode, settings.temperature, settings.max_words) == ("none", 0.0, 200)

    def test_a_config_without_an_llm_block_is_mode_none(self, tmp_path):
        path = tmp_path / "case.toml"
        path.write_text('[case]\nlabel = "x"\n', encoding="utf-8")
        assert LlmSettings.load(path).mode == "none"

    def test_the_block_selects_its_own_transport(self, tmp_path):
        path = tmp_path / "case.toml"
        path.write_text('[llm]\nmode = "claude-code"\nmodel = "opus"\n', encoding="utf-8")
        assert isinstance(LlmSettings.load(path).transport(), ClaudeCodeTransport)


GOOD = (
    "This lane scored a bit over a quarter of the record set [cov.fraction]. "
    "Most of its scores sit low, with the p90 far under the top of its range [dist.p90]. "
    "It never scored one half of the pair, so it has no rank for it [pair.rank]."
)


def fake(text: str, *, mode: str = "claude-code", model_id: str = "test-model") -> FakeTransport:
    return FakeTransport(answer=lambda _prompt: text, mode=mode, model_id=model_id)


class TestNarrateOneReport:
    def test_a_good_reply_is_recorded_with_its_counts(self):
        result = narrate.narrate_report(REPORT, transport=fake(GOOD))
        assert result is not None
        assert (result.model, result.mode, result.llm_model_id) == (
            "demo",
            "claude-code",
            "test-model",
        )
        assert (result.cited_sentences, result.uncited_sentences) == (3, 0)
        assert result.uncited_rate == 0.0
        assert result.run_id == "demo-0001"

    def test_the_stored_prompt_is_the_prompt_that_was_sent(self):
        seen: list[str] = []

        def answer(prompt: str) -> str:
            seen.append(prompt)
            return GOOD

        result = narrate.narrate_report(REPORT, transport=FakeTransport(answer=answer))
        assert result is not None
        assert result.prompt == seen[0]

    def test_an_uncited_reply_is_stored_and_counted_not_discarded(self):
        result = narrate.narrate_report(REPORT, transport=fake("It looks fine to me."))
        assert result is not None
        assert result.uncited_sentences == 1
        assert result.uncited_rate == 1.0

    def test_the_badge_names_the_mode_the_model_and_the_citation_count(self):
        result = narrate.narrate_report(REPORT, transport=fake(GOOD))
        assert result is not None
        marker = result.marker()
        assert "llm:claude-code" in marker
        assert "model:test-model" in marker
        assert "cited 3/3" in marker

    def test_the_hand_written_version_is_a_narrative_too(self):
        kept = narrate.hand_written(
            REPORT, "A human wrote this [cov.fraction].", dated="2026-09-19"
        )
        assert (kept.mode, kept.llm_model_id, kept.prompt) == ("hand", "human", "")
        assert kept.cited_sentences == 1
        assert kept.marker() == "<!-- interpretation: hand-written 2026-09-19 | llm:none -->"


class TestRunOverACase:
    """The whole pass: read the JSON, keep the hand, generate, rewrite both files."""

    def setup_case(self, tmp_path: Path) -> tuple[Path, Path]:
        json_dir, reports_dir = tmp_path / "json", tmp_path / "md"
        json_dir.mkdir()
        reports_dir.mkdir()
        (json_dir / "demo.json").write_text(json.dumps(REPORT), encoding="utf-8")
        payload = json.loads(json.dumps(REPORT))
        payload["sections"]["interpretation"] = {
            "marker": "<!-- interpretation: hand-written 2026-09-19 | llm:none -->",
            "text": "The hand-written reading of this lane [cov.fraction].",
            "llm_mode": "none",
        }
        (reports_dir / "demo.md").write_text(report.render_model_report(payload), encoding="utf-8")
        return json_dir, reports_dir

    def test_both_versions_survive_and_the_generated_one_leads(self, tmp_path):
        json_dir, reports_dir = self.setup_case(tmp_path)
        result = narrate.run_narrate(
            json_dir=json_dir,
            reports_dir=reports_dir,
            settings=LlmSettings(mode="claude-code", max_words=200),
            transport=fake(GOOD),
        )
        assert [item.mode for item in result.narratives] == ["claude-code", "hand"]
        text = (reports_dir / "demo.md").read_text(encoding="utf-8")
        assert "### 6.1 Generated — mode `claude-code`" in text
        assert "### 6.2 Hand-written" in text
        assert "The hand-written reading of this lane" in text
        assert GOOD.split(".", maxsplit=1)[0] in text

    def test_the_stored_json_carries_both_versions_so_a_re_render_keeps_them(self, tmp_path):
        json_dir, reports_dir = self.setup_case(tmp_path)
        narrate.run_narrate(
            json_dir=json_dir,
            reports_dir=reports_dir,
            settings=LlmSettings(mode="claude-code"),
            transport=fake(GOOD),
        )
        block = json.loads((json_dir / "demo.json").read_text())["sections"]["interpretation"]
        assert block["llm_mode"] == "claude-code"
        assert [item["llm_mode"] for item in block["alternatives"]] == ["hand"]
        assert "### 6.2 Hand-written" in report.render_model_report(
            json.loads((json_dir / "demo.json").read_text())
        )

    def test_only_the_named_lanes_are_narrated(self, tmp_path):
        json_dir, reports_dir = self.setup_case(tmp_path)
        (json_dir / "other.json").write_text(
            json.dumps({**REPORT, "model": "other"}), encoding="utf-8"
        )
        result = narrate.run_narrate(
            json_dir=json_dir,
            reports_dir=reports_dir,
            settings=LlmSettings(mode="claude-code"),
            models=["demo"],
            transport=fake(GOOD),
        )
        assert {item.model for item in result.narratives} == {"demo"}

    def test_mode_none_leaves_the_hand_written_report_exactly_as_it_was(self, tmp_path):
        json_dir, reports_dir = self.setup_case(tmp_path)
        before = (reports_dir / "demo.md").read_text(encoding="utf-8")
        result = narrate.run_narrate(
            json_dir=json_dir, reports_dir=reports_dir, settings=LlmSettings(mode="none")
        )
        # One version means no sub-headings: a report that has never been narrated renders
        # exactly as it did before the slot learned to hold a list.
        assert [item.mode for item in result.narratives] == ["hand"]
        assert (reports_dir / "demo.md").read_text(encoding="utf-8") == before


@pytest.fixture
def connection():
    """A DuckDB stand-in for the warehouse: ``results`` for rows, ``warehouse`` for lineage."""
    con = duckdb.connect()
    con.execute("ATTACH ':memory:' AS pg")
    con.execute("CREATE SCHEMA pg.results")
    con.execute("CREATE SCHEMA pg.warehouse")
    return con


class TestStorage:
    def test_a_narrative_row_holds_the_prompt_the_reply_and_the_counts(self, connection):
        item = narrate.narrate_report(REPORT, transport=fake(GOOD), run_id="r-1")
        assert item is not None
        written = narrate.write_narratives(
            connection, "results", [item], run_id="r-1", table="demo_narratives"
        )
        assert written == 1
        row = connection.execute(
            "SELECT model, run_id, mode, llm_model_id, words, cited_sentences, "
            "uncited_sentences FROM pg.results.demo_narratives"
        ).fetchone()
        assert row[:4] == ("demo", "r-1", "claude-code", "test-model")
        assert row[5:] == (3, 0)

    def test_the_table_name_comes_from_the_case_prefix_not_a_constant(self, connection):
        item = narrate.hand_written(REPORT, "Prose [cov.fraction].")
        narrate.write_narratives(connection, "results", [item], table="othercase_narratives")
        assert connection.execute(
            "SELECT count(*) FROM pg.results.othercase_narratives"
        ).fetchone() == (1,)

    def test_a_lineage_edge_is_recorded_for_the_write(self, connection):
        item = narrate.hand_written(REPORT, "Prose [cov.fraction].")
        narrate.write_narratives(
            connection, "results", [item], run_id="r-1", table="demo_narratives"
        )
        rows = connection.execute(
            "SELECT target_table, transform FROM pg.warehouse.data_lineage"
        ).fetchall()
        assert rows and rows[0][0] == "demo_narratives"
        assert "narrate" in rows[0][1]


class TestTheClaimP47:
    """``P4-7``: an interpretation's sentences resolve to rows, at most 10 % uncited."""

    def test_a_clean_reply_is_under_the_ten_percent_bar(self):
        result = check_narrative(GOOD, citable_rows(REPORT), max_words=200)
        assert result.uncited_rate <= 0.10

    def test_a_reply_that_names_a_gene_the_rows_never_gave_it_fails_the_check(self):
        bad = GOOD + " The real answer is CEP57 [pair.gene]."
        assert check_narrative(bad, citable_rows(REPORT)).new_names == ("CEP57",)
