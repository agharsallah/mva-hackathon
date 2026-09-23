"""The tier-3 lane without Modal: windows in, a fake GPU out, the ledger and checkpoints real.

No patient data: invented DNA windows in a ``tmp_path`` Parquet.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from mva.zoo.adapters.modal_gpu import ModalAdapter, crop
from mva.zoo.modal_budget import BudgetExceededError, Ledger
from mva.zoo.modal_contract import Item, Reply, price, reply
from mva.zoo.record_dna import dna_window_pair
from mva.zoo.types import AlleleRecord

GENOME = "ACGT" * 50


class FakeFasta:
    references = ("1",)

    def get_reference_length(self, reference: str) -> int:
        return len(GENOME)

    def fetch(self, reference: str, start: int, end: int) -> str:
        return GENOME[start:end]


def test_dna_window_centres_the_allele_and_checks_ref() -> None:
    pair = dna_window_pair(FakeFasta(), "chr1", 101, GENOME[100], "T", length=20)
    assert pair is not None
    ref, alt, clipped = pair
    assert len(ref) == 20 and ref[10] == GENOME[100] and alt[10] == "T" and not clipped
    assert dna_window_pair(FakeFasta(), "1", 101, "N", "T", length=20) is None


def test_crop_keeps_the_change_inside() -> None:
    item = Item(allele_id="a", ref="A" * 50 + "C" + "A" * 49, alt="A" * 50 + "G" + "A" * 49,
                center=50)  # fmt: skip
    small = crop(item, 10)
    assert len(small["ref"]) == 10 and small["ref"][small["center"]] == "C"
    assert small["alt"][small["center"]] == "G"


@pytest.fixture
def dna_parquet(tmp_path: Path) -> Path:
    target = tmp_path / "dna.parquet"
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE t AS SELECT * FROM (VALUES "
        "('a1', 'ACGTA', 'ACCTA', 2, false), ('a2', 'ACGTA', 'ACTTA', 2, false), "
        "('a3', 'ACGTA', 'ACATA', 2, true)) v(allele_id, dna_window_ref, dna_window_alt, "
        "center, clipped)"
    )
    con.execute(f"COPY t TO '{target}' (FORMAT parquet)")
    return target


def fake_gpu(calls: list[int]) -> object:
    def send(chunks: list[list[Item]]) -> list[Reply]:
        calls.append(len(chunks))
        return [
            reply(
                [{"allele_id": i["allele_id"], "score": -1.5, "aux": {}} for i in chunk],
                version="v",
                digest="d" * 8,
                gpu="L4",
                seconds=10.0,
                sent=len(chunk),
            )
            for chunk in chunks
        ]

    return send


def test_lane_scores_checkpoints_and_prices(tmp_path: Path, dna_parquet: Path) -> None:
    calls: list[int] = []
    ledger = Ledger(tmp_path / "ledger.jsonl")
    lane = ModalAdapter(name="ntv2", version="v", gpu="L4", batch=1, score_sign=-1,
                        dna_parquet=dna_parquet, work_dir=tmp_path, ledger=ledger,
                        transport=fake_gpu(calls))  # fmt: skip
    records = [AlleleRecord(allele_id=a) for a in ("a1", "a2", "a3")]
    rows = list(lane.score(records))
    assert {r.allele_id for r in rows} == {"a1", "a2"}  # a3's window is clipped
    assert all(r.score == 1.5 and r.venue == "modal:L4" and r.digest for r in rows)
    assert ledger.spent("ntv2") == pytest.approx(2 * price("L4", 10.0))
    again = ModalAdapter(name="ntv2", version="v", gpu="L4", dna_parquet=dna_parquet,
                         work_dir=tmp_path, ledger=ledger, transport=fake_gpu(calls))  # fmt: skip
    assert len(list(again.score(records))) == 2 and calls == [2]  # resumed, nothing re-sent


def test_guard_stops_at_the_lane_share(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl")
    ledger.record("esmc", gpu="H100", seconds=3500.0, items=10, scored=10)
    with pytest.raises(BudgetExceededError):
        ledger.guard("esmc", 1.0)
