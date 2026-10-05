"""The spend ledger: every Modal call priced, appended, and checked against the cap.

A GPU lane that runs out of money halfway should stop with what it has, not overrun. The
ledger is a JSONL file under ``build/modal/`` — one line per remote call, never edited —
and :func:`guard` is asked *before* every wave of calls: "would this wave, padded by
:data:`~mva.zoo.modal_contract.OVERHEAD_FACTOR`, push the lane past its share or the step
past the cap?". :func:`billing_report` asks Modal itself, for the reconciliation.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .modal_contract import CAP_USD, LANE_BUDGET_USD, OVERHEAD_FACTOR, price

__all__ = ["DEFAULT_LEDGER", "BudgetExceededError", "Ledger", "billing_report"]

DEFAULT_LEDGER = Path("build/modal/ledger.jsonl")


class BudgetExceededError(RuntimeError):
    """The next wave would overrun the lane's share or the step's cap."""


@dataclass
class Ledger:
    path: Path = DEFAULT_LEDGER
    cap_usd: float = CAP_USD

    def rows(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text().splitlines() if line.strip()]

    def spent(self, model: str | None = None) -> float:
        return sum(
            float(row["usd"]) for row in self.rows() if model is None or row["model"] == model
        )

    def record(
        self, model: str, *, gpu: str, seconds: float, items: int, scored: int, note: str = ""
    ) -> dict[str, Any]:
        row = {
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
            "model": model,
            "gpu": gpu,
            "seconds": round(seconds, 3),
            "usd": round(price(gpu, seconds), 6),
            "items": items,
            "scored": scored,
            "note": note,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as handle:
            handle.write(json.dumps(row) + "\n")
        return row

    def usd_per_item(self, model: str) -> float | None:
        """What one item has cost this lane so far — the basis of every later estimate."""
        rows = [row for row in self.rows() if row["model"] == model and row["items"]]
        items = sum(int(row["items"]) for row in rows)
        return sum(float(row["usd"]) for row in rows) / items if items else None

    def guard(self, model: str, estimate_usd: float) -> None:
        """Raise before a wave that would overrun; the message says which limit and by how much."""
        padded = estimate_usd * OVERHEAD_FACTOR
        lane_cap = LANE_BUDGET_USD.get(model, self.cap_usd)
        lane = self.spent(model)
        total = self.spent()
        if lane + padded > lane_cap:
            raise BudgetExceededError(
                f"{model}: ${lane:.2f} spent + ${padded:.2f} next wave > lane share ${lane_cap:.2f}"
            )
        if total + padded > self.cap_usd:
            raise BudgetExceededError(
                f"step 8: ${total:.2f} spent + ${padded:.2f} next wave > cap ${self.cap_usd:.2f}"
            )


def billing_report(since: str = "today") -> Any:
    """``modal billing report --for <since> --json`` — Modal's own number, for reconciliation."""
    out = subprocess.run(
        ["modal", "billing", "report", "--for", since, "--json"],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(out.stdout or "[]")
