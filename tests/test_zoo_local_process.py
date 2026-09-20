"""The tier-2 lane: a model that runs, and everything around it that must not need one.

No weights are loaded here. The lane's *mechanics* — which alleles it can see, where it
reads the windows from, how it checkpoints, how it names its digest, how the published sign
is flipped — are all separable from the arithmetic, and a test that downloaded 2.6 GB would
never run in CI. The arithmetic itself is tested against a **fake model and tokenizer** whose
log-probabilities are chosen by hand, so the masked-marginal formula is checked against
numbers a reader can verify with a pen.

No patient data: the windows are invented letters in a ``tmp_path`` Parquet.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb
import pytest

from mva.zoo import adapters
from mva.zoo.adapters import local_process
from mva.zoo.adapters.local_process import LocalProcessAdapter
from mva.zoo.types import AlleleRecord

WINDOW = "MKVLAAGIVGLNQYLERSTDW"


def record(allele: str, consequence: str = "missense_variant") -> AlleleRecord:
    return AlleleRecord(allele_id=allele, consequence=consequence)


@pytest.fixture
def records_parquet(tmp_path: Path) -> Path:
    """Three records; two carry a window pair, one does not — the shape the real file has."""
    target = tmp_path / "records.parquet"
    mutant = WINDOW[:10] + "W" + WINDOW[11:]
    con = duckdb.connect()
    con.execute(
        "CREATE TEMP TABLE r (allele_id VARCHAR, consequence VARCHAR, "
        "protein_window_ref VARCHAR, protein_window_alt VARCHAR)"
    )
    con.executemany(
        "INSERT INTO r VALUES (?, ?, ?, ?)",
        [
            ["a", "missense_variant", WINDOW, mutant],
            ["b", "missense_variant", WINDOW, WINDOW[:3] + "P" + WINDOW[4:]],
            ["c", "stop_gained", None, None],
        ],
    )
    con.execute("COPY (SELECT * FROM r) TO ? (FORMAT parquet)", [str(target)])
    con.close()
    return target


@pytest.fixture
def lane(tmp_path: Path, records_parquet: Path) -> LocalProcessAdapter:
    return LocalProcessAdapter(
        name="esm2",
        version="esm2_t33_650M_UR50D",
        checkpoint_id="facebook/esm2_t33_650M_UR50D",
        records_parquet=records_parquet,
        work_dir=tmp_path / "work",
        digest="d" * 64,
        licence="MIT",
    )


class TestWhatItCanSee:
    def test_only_records_carrying_a_window_pair_are_covered(
        self, lane: LocalProcessAdapter
    ) -> None:
        cover = lane.coverage([record("a"), record("b"), record("c", "stop_gained")])
        assert cover.scored == 2 and cover.total == 3
        assert cover.by_consequence["stop_gained"] == (0, 1)

    def test_coverage_needs_no_weights(self, lane: LocalProcessAdapter) -> None:
        lane.coverage([record("a")])
        assert lane._model is None

    def test_a_missing_record_set_names_the_command_that_makes_it(self, tmp_path: Path) -> None:
        lane = LocalProcessAdapter(
            name="esm2", version="v", checkpoint_id="x", records_parquet=tmp_path / "no.parquet"
        )
        with pytest.raises(FileNotFoundError, match="mva-zoo records"):
            lane.coverage([record("a")])

    def test_the_windows_are_read_from_the_file_not_the_record(
        self, lane: LocalProcessAdapter
    ) -> None:
        pairs = lane.windows(["a", "b", "c"])
        assert set(pairs) == {"a", "b"}
        assert pairs["a"][0] == WINDOW


class TestChangedIndex:
    def test_it_finds_the_one_differing_residue(self) -> None:
        assert local_process.changed_index("MKVL", "MKPL") == 2

    def test_two_differences_are_refused(self) -> None:
        assert local_process.changed_index("MKVL", "MAPL") == -1

    def test_no_difference_is_refused(self) -> None:
        assert local_process.changed_index("MKVL", "MKVL") == -1

    def test_different_lengths_are_refused(self) -> None:
        assert local_process.changed_index("MKVL", "MKV") == -1


class FakeTokenizer:
    """Enough of a tokenizer to drive the formula: one id per letter, plus cls and mask."""

    mask_token_id = 32

    def __init__(self) -> None:
        self.letters = "ACDEFGHIKLMNPQRSTVWY"

    def __call__(self, windows: list[str], **_: Any) -> dict[str, Any]:
        import torch

        width = max(len(w) for w in windows)
        ids = torch.zeros((len(windows), width + 1), dtype=torch.long)
        mask = torch.ones_like(ids)
        for row, window in enumerate(windows):
            for column, letter in enumerate(window):
                ids[row, column + 1] = self.convert_tokens_to_ids(letter)
        return {"input_ids": ids, "attention_mask": mask}

    def convert_tokens_to_ids(self, token: str) -> int:
        return self.letters.index(token) + 1 if token in self.letters else 31


class FakeModel:
    """Returns a fixed logit vector at every position: letter *i* gets logit ``-i``."""

    def __init__(self) -> None:
        self.calls: list[Any] = []

    def __call__(self, *, input_ids: Any, attention_mask: Any) -> Any:
        import torch

        self.calls.append(input_ids.clone())
        rows, width = input_ids.shape
        logits = torch.zeros((rows, width, 40))
        for token in range(40):
            logits[:, :, token] = -float(token)
        return type("Out", (), {"logits": logits})()


class TestMaskedMarginals:
    def test_the_score_is_the_difference_of_two_log_probabilities(self) -> None:
        torch = pytest.importorskip("torch")
        assert torch is not None
        pairs = {"a": ("MKVL", "MKPL")}
        scored = local_process.masked_marginals(FakeModel(), FakeTokenizer(), pairs)
        # logit(token) = -token, so log P(x) - log P(y) = (-id(x)) - (-id(y)) = id(y) - id(x).
        letters = FakeTokenizer().letters
        expected = float((letters.index("V") + 1) - (letters.index("P") + 1))
        assert scored["a"] == pytest.approx(expected)

    def test_the_changed_position_is_masked_before_the_forward_pass(self) -> None:
        pytest.importorskip("torch")
        model = FakeModel()
        local_process.masked_marginals(model, FakeTokenizer(), {"a": ("MKVL", "MKPL")})
        # window index 2 is token index 3 (the class token shifts everything by one)
        assert int(model.calls[0][0, 3]) == FakeTokenizer.mask_token_id

    def test_a_pair_that_differs_nowhere_is_skipped_not_scored(self) -> None:
        pytest.importorskip("torch")
        assert (
            local_process.masked_marginals(FakeModel(), FakeTokenizer(), {"a": ("MK", "MK")}) == {}
        )

    def test_an_empty_batch_never_touches_the_model(self) -> None:
        model = FakeModel()
        assert local_process.masked_marginals(model, FakeTokenizer(), {}) == {}
        assert model.calls == []


class TestCheckpointAndSign:
    def _seed(self, lane: LocalProcessAdapter, scores: dict[str, float]) -> None:
        lane.directory.mkdir(parents=True, exist_ok=True)
        (lane.directory / "batch-00000.jsonl").write_text(
            "".join(json.dumps({"allele_id": k, "score": v}) + "\n" for k, v in scores.items())
        )

    def test_a_checkpointed_allele_is_never_recomputed(self, lane: LocalProcessAdapter) -> None:
        self._seed(lane, {"a": -3.0, "b": -1.0})
        rows = list(lane.score([record("a"), record("b")]))
        assert lane._model is None  # nothing loaded: every allele was already answered
        assert {row.allele_id for row in rows} == {"a", "b"}

    def test_the_published_sign_is_flipped_and_the_raw_number_kept(
        self, lane: LocalProcessAdapter
    ) -> None:
        self._seed(lane, {"a": -3.5})
        row = next(iter(lane.score([record("a")])))
        assert row.score == 3.5
        assert row.aux["llr"] == -3.5
        assert row.aux["checkpoint"] == "facebook/esm2_t33_650M_UR50D"

    def test_score_sign_one_leaves_the_publisher_s_direction(
        self, tmp_path: Path, records_parquet: Path
    ) -> None:
        lane = LocalProcessAdapter(
            name="esm2",
            version="v",
            checkpoint_id="x",
            records_parquet=records_parquet,
            work_dir=tmp_path / "w",
            score_sign=1,
            digest="d" * 64,
        )
        self._seed(lane, {"a": -3.5})
        assert next(iter(lane.score([record("a")]))).score == -3.5

    def test_every_row_carries_its_provenance(self, lane: LocalProcessAdapter) -> None:
        self._seed(lane, {"a": -1.0})
        row = next(iter(lane.score([record("a")])))
        assert row.model == "esm2" and row.venue == "laptop" and row.licence == "MIT"
        assert row.digest == "d" * 64

    def test_batches_are_numbered_after_the_ones_on_disk(self, lane: LocalProcessAdapter) -> None:
        self._seed(lane, {"a": -1.0})
        assert lane._next_index() == 1

    def test_a_remembered_digest_is_read_back_without_the_network(
        self, lane: LocalProcessAdapter
    ) -> None:
        lane.digest = ""
        lane.directory.mkdir(parents=True, exist_ok=True)
        (lane.directory / "weights.digest.json").write_text(json.dumps({"sha256": "a" * 64}))
        assert lane.weights_digest() == "a" * 64

    def test_it_is_a_local_lane_so_submit_refuses(self, lane: LocalProcessAdapter) -> None:
        with pytest.raises(NotImplementedError, match="runs locally"):
            lane.submit([record("a")])


class TestBuildFromCard:
    def test_the_factory_reaches_this_lane_by_name(self, records_parquet: Path) -> None:
        card = type(
            "Card",
            (),
            {
                "key": "esm2",
                "version": "esm2_t33_650M_UR50D",
                "adapter": "local_process",
                "licence": "MIT",
                "catalogue_adjacent": False,
                "params": {"checkpoint": "facebook/esm2_t33_650M_UR50D", "batch": 4},
            },
        )()
        lane = adapters.build(card, records_parquet=records_parquet)
        assert isinstance(lane, LocalProcessAdapter)
        assert lane.batch == 4 and lane.tier == 2
        assert lane.checkpoint_id == "facebook/esm2_t33_650M_UR50D"
        assert lane.score_sign == -1

    def test_the_roster_fragment_enables_esm2_with_a_checkpoint(self) -> None:
        from mva.zoo import registry

        card = registry.load()["esm2"]
        assert card.enabled and card.tier == 2 and card.adapter == "local_process"
        assert card.params["checkpoint"] == "facebook/esm2_t33_650M_UR50D"
        assert card.params["score_sign"] == -1
        assert card.catalogue_adjacent is False
