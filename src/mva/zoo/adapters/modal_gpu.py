"""Tier-3 lane: a model that runs on a **Modal GPU**, called from the laptop by name.

The laptop half of :mod:`mva.zoo.modal_contract`. The container half is one app per lane
under :mod:`mva.zoo.modal_apps` (``mva-zoo-<key>``, class ``Scorer``, method
``score_batch``), deployed once; this adapter looks it up with ``modal.Cls.from_name`` and
maps batches of windows over it.

**What leaves the laptop:** an ``allele_id`` and two windows per item, and where the change
sits in them. Windows come from ``build/`` — DNA windows from
``build/it4/dna-windows.parquet`` (:mod:`mva.zoo.record_dna`), protein windows from the
record Parquet (:mod:`mva.zoo.record_window`). No coordinate, gene or HGVS string is sent.

**What keeps the run honest:**

* every reply is checkpointed to ``build/it4/<key>/batch-NNNNN.jsonl`` before the next wave,
  so a killed run resumes with what it had (the ESM2 lane's rule);
* every reply is priced into the ledger (:mod:`mva.zoo.modal_budget`) and the ledger is
  asked *before* each wave whether it can afford it — a lane stops at its share of the cap;
* every wave is logged to ``<work_dir>/modal/<key>.log`` with items, seconds, dollars.

The remote call is injectable (``transport``), which is how the tests run without Modal.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..modal_budget import BudgetExceededError, Ledger
from ..modal_contract import CLASS_NAME, METHOD, Item, Reply, app_name
from ..types import Adapter, AlleleRecord, Coverage, RemoteJob, ScoreRow, Tier
from . import DEFAULT_RECORDS, coverage_from_ids

__all__ = ["DEFAULT_DNA", "ModalAdapter", "Transport", "build", "crop", "modal_transport"]

DEFAULT_DNA = Path("build/it4/dna-windows.parquet")
DEFAULT_WORK = Path("build/it4")

#: ``chunks -> replies``: the one seam between this module and Modal.
Transport = Callable[[list[list[Item]]], Iterable[Reply]]


def modal_transport(key: str) -> Transport:
    """Map chunks over the deployed ``mva-zoo-<key>`` app, replies in completion order."""

    def send(chunks: list[list[Item]]) -> Iterable[Reply]:
        import modal

        scorer = modal.Cls.from_name(app_name(key), CLASS_NAME)()
        method = getattr(scorer, METHOD)
        yield from method.map(chunks, order_outputs=False)

    return send


def crop(item: Item, length: int | None) -> Item:
    """A central crop to ``length`` bases/residues that keeps the change inside the window."""
    if not length or len(item["ref"]) <= length:
        return item
    start = max(0, item["center"] - length // 2)
    delta = len(item["alt"]) - len(item["ref"])
    return Item(
        allele_id=item["allele_id"],
        ref=item["ref"][start : start + length],
        alt=item["alt"][start : start + length + delta],
        center=item["center"] - start,
    )


def _logger(key: str, directory: Path) -> logging.Logger:
    """One file logger per lane *and* log directory, so a test's tmp_path never writes into
    the real lane log under ``build/``."""
    log = logging.getLogger(f"mva.zoo.modal.{key}.{abs(hash(str(directory)))}")
    if not log.handlers:
        directory.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(directory / f"{key}.log")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)
    return log


@dataclass
class ModalAdapter:
    name: str
    version: str
    needs: str = "dna"  # "dna" | "protein"
    gpu: str = "H100"
    batch: int = 64
    wave: int = 16
    window: int | None = None
    score_sign: int = 1
    licence: str = ""
    limit: int | None = None
    records_parquet: Path = DEFAULT_RECORDS
    dna_parquet: Path = DEFAULT_DNA
    work_dir: Path = DEFAULT_WORK
    ledger: Ledger = field(default_factory=Ledger)
    transport: Transport | None = None
    progress: Any = None
    connection: Any = None
    tier: Tier = 3
    catalogue_adjacent: bool = False
    digest: str = ""
    _done: dict[str, tuple[float, dict[str, Any]]] = field(default_factory=dict)

    @property
    def venue(self) -> str:
        return f"modal:{self.gpu}"

    @property
    def source_ref(self) -> str:
        return app_name(self.name)

    @property
    def directory(self) -> Path:
        return self.work_dir / self.name

    # ── inputs ───────────────────────────────────────────────────────────────────────

    def items(self, allele_ids: Sequence[str]) -> dict[str, Item]:
        """The wire items for the ids asked about, read straight from ``build/``."""
        import duckdb

        con = self.connection or duckdb.connect()
        if self.needs == "dna":
            sql = (
                "SELECT allele_id, dna_window_ref, dna_window_alt, center "
                "FROM read_parquet(?) WHERE NOT clipped"
            )
            source = self.dna_parquet
        else:
            sql = (
                "SELECT allele_id, protein_window_ref, protein_window_alt, NULL FROM "
                "read_parquet(?) WHERE protein_window_ref IS NOT NULL "
                "AND protein_window_alt IS NOT NULL"
            )
            source = self.records_parquet
        if not Path(source).exists():
            raise FileNotFoundError(f"{self.name}: no windows at {source}")
        wanted = set(allele_ids)
        out: dict[str, Item] = {}
        for allele, ref, alt, center in con.execute(sql, [str(source)]).fetchall():
            if str(allele) not in wanted:
                continue
            spot = int(center) if center is not None else _changed(str(ref), str(alt))
            if spot < 0:
                continue
            item = Item(allele_id=str(allele), ref=str(ref), alt=str(alt), center=spot)
            out[str(allele)] = crop(item, self.window)
        return out

    # ── checkpoints ──────────────────────────────────────────────────────────────────

    def load_checkpoints(self) -> dict[str, tuple[float, dict[str, Any]]]:
        if not self._done and self.directory.is_dir():
            for path in sorted(self.directory.glob("batch-*.jsonl")):
                for line in path.read_text().splitlines():
                    if line.strip():
                        row = json.loads(line)
                        self._done[row["allele_id"]] = (float(row["score"]), row.get("aux", {}))
                        self.digest = self.digest or str(row.get("digest", ""))
        return self._done

    def _save(self, reply: Reply) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        names = sorted(self.directory.glob("batch-*.jsonl"))
        index = int(names[-1].stem.split("-")[1]) + 1 if names else 0
        lines = [
            json.dumps({**row, "digest": reply["digest"], "version": reply["version"]})
            for row in reply["scores"]
        ]
        (self.directory / f"batch-{index:05d}.jsonl").write_text("\n".join(lines) + "\n")
        for row in reply["scores"]:
            self._done[row["allele_id"]] = (float(row["score"]), row["aux"])
        self.digest = reply["digest"] or self.digest

    # ── the Adapter protocol ─────────────────────────────────────────────────────────

    def coverage(self, records: Sequence[AlleleRecord]) -> Coverage:
        have = self.items([record.allele_id for record in records])
        return coverage_from_ids(self.name, records, set(have))

    def run_remote(self, records: Sequence[AlleleRecord]) -> dict[str, int | float]:
        """Send what is not yet checkpointed, wave by wave, until done or out of budget."""
        log = _logger(self.name, self.work_dir / "modal")
        done = self.load_checkpoints()
        items = self.items([record.allele_id for record in records])
        pending = [items[a] for a in items if a not in done]
        if self.limit is not None:
            pending = pending[: self.limit]
        chunks = [pending[i : i + self.batch] for i in range(0, len(pending), self.batch)]
        send = self.transport or modal_transport(self.name)
        log.info("start %s: %d pending in %d chunks (%s)", self.name, len(pending), len(chunks),
                 self.venue)  # fmt: skip
        sent = scored = 0
        started = time.time()
        for start in range(0, len(chunks), self.wave):
            wave = chunks[start : start + self.wave]
            n = sum(len(c) for c in wave)
            per_item = self.ledger.usd_per_item(self.name)
            try:
                self.ledger.guard(self.name, (per_item or 0.0) * n)
            except BudgetExceededError as stop:
                log.warning("stopped: %s", stop)
                if self.progress:
                    self.progress(f"    stopped: {stop}")
                break
            for reply in send(wave):
                self._save(reply)
                row = self.ledger.record(
                    self.name, gpu=reply["gpu"], seconds=reply["seconds"],
                    items=len(reply["scores"]) + reply["skipped"], scored=len(reply["scores"]),
                )  # fmt: skip
                sent += row["items"]
                scored += row["scored"]
            message = (
                f"{sent:,}/{len(pending):,} sent, {scored:,} scored, "
                f"${self.ledger.spent(self.name):.3f} lane, {time.time() - started:.0f}s"
            )
            log.info(message)
            if self.progress:
                self.progress(f"    {message}")
        return {"pending": len(pending), "sent": sent, "scored": scored,
                "usd": self.ledger.spent(self.name)}  # fmt: skip

    def score(self, records: Sequence[AlleleRecord]) -> Iterator[ScoreRow]:
        self.run_remote(records)
        sign = 1 if self.score_sign >= 0 else -1
        for record in records:
            hit = self._done.get(record.allele_id)
            if hit is None:
                continue
            published, aux = hit
            yield ScoreRow(
                allele_id=record.allele_id,
                model=self.name,
                version=self.version,
                score=published * sign,
                aux={**aux, "published": published},
                digest=self.digest,
                venue=self.venue,
                licence=self.licence,
            )

    def submit(self, records: Sequence[AlleleRecord]) -> RemoteJob:
        raise NotImplementedError(
            f"{self.name}: score() maps and collects synchronously, checkpointing every reply"
        )


def _changed(reference: str, mutant: str) -> int:
    if len(reference) != len(mutant):
        return -1
    spots = [i for i, (a, b) in enumerate(zip(reference, mutant, strict=True)) if a != b]
    return spots[0] if len(spots) == 1 else -1


def build(card: Any, *, connection: Any = None, records_parquet: Path = DEFAULT_RECORDS) -> Adapter:
    """The lane a ``source = "modal"`` card describes. ``params.needs`` picks the windows."""
    params = dict(getattr(card, "params", {}) or {})
    needs = [str(n) for n in params.get("needs", [])]
    window = params.get("window")
    limit = params.get("limit")
    return ModalAdapter(
        name=str(card.key),
        version=str(card.version),
        needs="protein" if any(n.startswith("protein") for n in needs) else "dna",
        gpu=str(params.get("gpu", "H100")),
        batch=int(params.get("batch", 64)),
        wave=int(params.get("wave", 16)),
        window=int(window) if window else None,
        score_sign=int(params.get("score_sign", 1) or 1),
        licence=str(getattr(card, "licence", "") or ""),
        limit=int(limit) if limit else None,
        records_parquet=records_parquet,
        connection=connection,
        catalogue_adjacent=bool(getattr(card, "catalogue_adjacent", False)),
    )
