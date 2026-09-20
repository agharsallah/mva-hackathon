"""The merged report's narrative: the rows it is written from, and the round trip.

Section 6 of a per-model report and section 5 of the merged one obey the same rules, so these
tests live beside :mod:`tests.test_zoo_narrate` rather than inside it — the file was over the
600-line cap for test modules, and "one lane's report" and "every lane at once" are two
stories.

No test here spawns a process or opens a socket.
"""

from __future__ import annotations

from mva.zoo import narrate
from mva.zoo.narrate_modes import FakeTransport, LlmSettings


def fake(text: str, *, mode: str = "claude-code", model_id: str = "test-model") -> FakeTransport:
    """The same two-line double :mod:`tests.test_zoo_narrate` uses; no process, no socket."""
    return FakeTransport(answer=lambda _prompt: text, mode=mode, model_id=model_id)


MERGED = {
    "run_id": "demo-0001",
    "method": "fusion+synthesis",
    "rrf_k": 60,
    "lanes": [
        {
            "model": "demo",
            "n_ranked": 100,
            "unscored_pairs": 20,
            "scored_alleles": 27,
            "catalogue_adjacent": False,
            "confirmed": {"rank": None, "percentile": None},
        },
        {
            "model": "other",
            "n_ranked": 200,
            "unscored_pairs": 3,
            "scored_alleles": 180,
            "catalogue_adjacent": True,
            "confirmed": {"rank": 12, "percentile": 6.0},
        },
    ],
    "agreement": {
        "models": ["demo", "other"],
        "cells": [
            {"a": "demo", "b": "demo", "rho": 1.0, "n": 27},
            {"a": "demo", "b": "other", "rho": 0.31, "n": 25},
        ],
    },
    "consensus": {
        "catalogue_free": {
            "lanes": ["demo"],
            "excluded_lanes": ["other"],
            "k": 60,
            "rank": 900,
            "n_pairs": 1000,
            "fused_score": 8.3e-05,
        },
        "all_lanes": {
            "lanes": ["demo", "other"],
            "excluded_lanes": [],
            "k": 60,
            "rank": 800,
            "n_pairs": 1100,
            "fused_score": 9.0e-05,
        },
    },
    "disagreements": [
        {
            "allele_id": "aaaa",
            "high_model": "other",
            "high_percentile": 0.5,
            "low_model": "demo",
            "low_percentile": 70.0,
        }
    ],
}

SYNTHESIS = (
    "One lane abstained rather than voting the pair down [lane.demo.rank]. "
    "The two lanes barely agree on the alleles they share [rho.demo.other]. "
    "Excluding the catalogue-trained lane moves the fused rank hardly at all "
    "[rrf.free.rank][rrf.all.rank]."
)


class TestMergedRows:
    def test_the_ids_the_synthesis_prompt_promises(self):
        from mva.zoo.narrate_rows import merged_rows

        found = {row["id"] for row in merged_rows(MERGED, {"demo": "a reading"})}
        assert {
            "method",
            "lane.demo.rank",
            "lane.other.rank",
            "rho.demo.other",
            "rrf.free.rank",
            "rrf.all.rank",
            "disagree.n",
            "interp.demo",
        } <= found

    def test_the_matrix_diagonal_and_the_mirror_are_not_rows(self):
        from mva.zoo.narrate_rows import merged_rows

        found = {row["id"] for row in merged_rows(MERGED)}
        assert "rho.demo.demo" not in found
        assert "rho.other.demo" not in found

    def test_a_lane_with_no_rank_says_abstained_rather_than_null(self):
        from mva.zoo.narrate_rows import merged_rows

        row = next(r for r in merged_rows(MERGED) if r["id"] == "lane.demo.rank")
        assert "no rank" in row["text"]

    def test_a_catalogue_adjacent_lane_is_named_as_one(self):
        from mva.zoo.narrate_rows import merged_rows

        row = next(r for r in merged_rows(MERGED) if r["id"] == "lane.other.rank")
        assert "catalogue-adjacent" in row["text"]

    def test_the_synthesis_prompt_forbids_ranking_and_carries_the_rows(self):
        from mva.zoo.narrate_rows import build_merge_prompt, merged_rows

        rows = merged_rows(MERGED, {"demo": "a reading"})
        prompt = build_merge_prompt(rows, max_words=200)
        assert "Do not rank anything" in prompt
        assert "cite the lane you are building on" in prompt
        for row in rows:
            assert f"[{row['id']}]" in prompt


class TestNarrateMerged:
    def test_the_synthesis_is_checked_against_the_merged_rows(self):
        item = narrate.narrate_merged(
            MERGED,
            {"demo": "a reading"},
            settings=LlmSettings(mode="claude-code"),
            transport=fake(SYNTHESIS),
        )
        assert item is not None
        assert (item.cited_sentences, item.uncited_sentences) == (3, 0)
        assert item.model == "merged"
        assert item.run_id == "demo-0001"

    def test_mode_none_synthesises_nothing(self):
        assert narrate.narrate_merged(MERGED, settings=LlmSettings(mode="none")) is None


class TestMergedRender:
    def test_one_narrative_renders_as_it_always_did(self):
        from mva.zoo.merge_render import render_merged

        text = render_merged(MERGED, "A hand-written paragraph.", dated="2026-09-19")
        assert "<!-- narrative: hand-written 2026-09-19 -->" in text
        assert "### 5.1" not in text

    def test_two_versions_render_side_by_side_with_badges(self):
        from mva.zoo.merge_render import render_merged

        item = narrate.narrate_merged(
            MERGED, settings=LlmSettings(mode="claude-code"), transport=fake(SYNTHESIS)
        )
        assert item is not None
        versions = [
            narrate.interpretation_block(item),
            {
                "marker": "<!-- narrative: hand-written 2026-09-18 -->",
                "text": "By hand.",
                "llm_mode": "hand",
            },
        ]
        text = render_merged(MERGED, versions[0]["text"], narratives=versions)
        assert "### 5.1 Synthesised — mode `claude-code`, model `test-model`, 3/3" in text
        assert "### 5.2 Hand-written" in text
        assert "By hand." in text


class TestMergedNarrativeRoundTrip:
    """The merged report's section 5 must survive a re-render, exactly as section 6 does."""

    def versions(self) -> list[dict]:
        item = narrate.narrate_merged(
            MERGED, settings=LlmSettings(mode="claude-code"), transport=fake(SYNTHESIS)
        )
        assert item is not None
        return [
            narrate.interpretation_block(item, "narrative"),
            {
                "marker": "<!-- narrative: hand-written 2026-09-18 -->",
                "text": "By hand.",
                "llm_mode": "hand",
            },
        ]

    def test_the_merged_slot_is_marked_narrative_not_interpretation(self):
        marker = self.versions()[0]["marker"]
        assert marker.startswith("<!-- narrative: synthesised")
        assert "llm:claude-code" in marker
        assert "cited 3/3" in marker

    def test_every_version_round_trips_out_of_the_rendered_file(self, tmp_path):
        from mva.zoo.merge_render import existing_narratives, render_merged

        versions = self.versions()
        path = tmp_path / "report.md"
        path.write_text(
            render_merged(MERGED, versions[0]["text"], narratives=versions), encoding="utf-8"
        )
        back = existing_narratives(path)
        assert [block["llm_mode"] for block in back] == ["claude-code", "hand"]
        assert back[0]["llm_model_id"] == "test-model"
        assert (back[0]["cited_sentences"], back[0]["uncited_sentences"]) == (3, 0)
        assert back[1]["text"] == "By hand."

    def test_a_re_render_from_what_was_read_back_is_stable(self, tmp_path):
        from mva.zoo.merge_render import existing_narratives, render_merged

        versions = self.versions()
        path = tmp_path / "report.md"
        path.write_text(
            render_merged(MERGED, versions[0]["text"], narratives=versions), encoding="utf-8"
        )
        first = path.read_text(encoding="utf-8")
        back = existing_narratives(path)
        path.write_text(render_merged(MERGED, back[0]["text"], narratives=back), encoding="utf-8")
        assert path.read_text(encoding="utf-8") == first

    def test_a_file_with_no_narrative_reads_back_empty(self, tmp_path):
        from mva.zoo.merge_render import existing_narratives

        assert existing_narratives(tmp_path / "absent.md") == []
