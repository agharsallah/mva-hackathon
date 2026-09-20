"""Tier-2 lane: a model that actually **runs**, here, on this laptop's CPU.

Every other lane in the zoo is a lookup — somebody else ran a model and published a table.
This one loads weights and does the arithmetic, and that changes what the lane *means*: a
lookup can only answer for variants its publisher enumerated, while a model that runs answers
for anything you can hand it. ESM2 (Lin 2023, MIT) is the case this was built for.

**What it computes, in plain words.** A **protein language model** is a next-token model over
amino acids: show it a protein with one residue hidden and it gives a probability for each of
the twenty letters that could go there. It was trained on ~65 million natural protein
sequences and on nothing else — no ClinVar, no HGMD, no variant labels at all — so its opinion
is genuinely independent of the catalogues the other lanes' publishers trained on.

The number is the **masked-marginal log-likelihood ratio** (Meier 2021's scoring recipe, the
standard one for this task):

    score_published = log P(mutant residue | window with that position masked)
                    − log P(reference residue | same masked window)

One forward pass per allele, both terms read off the *same* distribution, so the two residues
are compared under identical context. It is ≤ 0 for a substitution the model finds less
plausible than the reference — **more negative = more damaging** — which is the opposite of
the zoo's convention, so the card sets ``score_sign = -1`` and every cached score still means
"higher = more damaging".

**What it needs, and where that comes from.** The windows: ``protein_window_ref`` and
``protein_window_alt``, built by :mod:`mva.zoo.record_window` and stored **only** in
``build/<prefix>/records.parquet``. They are patient sequence, so
:func:`~mva.zoo.adapters.records_from_parquet` deliberately does not read them and the
:class:`~mva.zoo.types.AlleleRecord` objects the workflow passes around carry ``None``. This
lane reads them itself, from the file, for the ids it was asked about — the documented
exception, and the reason this module takes ``records_parquet``.

**Checkpointing.** Hours of CPU is not something to lose to a closed lid: every batch is
written to ``build/<prefix>/<key>/batch-NNNNN.jsonl`` as it finishes, and a re-run subtracts
what those files answer before it loads the weights at all.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..types import Adapter, AlleleRecord, Coverage, RemoteJob, ScoreRow, Tier
from . import DEFAULT_RECORDS, coverage_from_ids

__all__ = ["DEFAULT_WORK", "LocalProcessAdapter", "build", "masked_marginals"]

#: Where a tier-2 lane keeps its checkpoints and its weights digest.
DEFAULT_WORK = Path("build/it4")

#: Alleles per forward pass. Eight 129-residue windows fit comfortably in 16 GiB beside a
#: 650M-parameter model; the card may raise or lower it.
DEFAULT_BATCH = 8


@dataclass
class LocalProcessAdapter:
    """A masked protein language model, loaded once and run over the record set's windows."""

    name: str
    version: str
    checkpoint_id: str
    records_parquet: Path = DEFAULT_RECORDS
    work_dir: Path = DEFAULT_WORK
    batch: int = DEFAULT_BATCH
    score_sign: int = -1
    licence: str = ""
    digest: str = ""
    limit: int | None = None
    connection: Any = None
    tier: Tier = 2
    catalogue_adjacent: bool = False
    venue: str = "laptop"
    progress: Any = None
    _model: Any = None
    _tokenizer: Any = None
    _cache: dict[str, float] = field(default_factory=dict)
    _loaded: bool = False

    # ── where the work is kept ───────────────────────────────────────────────────────

    @property
    def directory(self) -> Path:
        return self.work_dir / self.name

    @property
    def source_ref(self) -> str:
        return self.checkpoint_id

    def load_checkpoints(self) -> dict[str, float]:
        """Every allele an earlier run already scored, read back from the JSONL batches."""
        if self._loaded:
            return self._cache
        if self.directory.is_dir():
            for path in sorted(self.directory.glob("batch-*.jsonl")):
                for line in path.read_text().splitlines():
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    self._cache[str(row["allele_id"])] = float(row["score"])
        self._loaded = True
        return self._cache

    def _append(self, index: int, scored: dict[str, float]) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"batch-{index:05d}.jsonl"
        path.write_text(
            "".join(
                json.dumps({"allele_id": allele, "score": value}) + "\n"
                for allele, value in scored.items()
            )
        )
        return path

    def _next_index(self) -> int:
        names = sorted(self.directory.glob("batch-*.jsonl")) if self.directory.is_dir() else []
        return int(names[-1].stem.split("-")[1]) + 1 if names else 0

    # ── the weights ──────────────────────────────────────────────────────────────────

    def weights_digest(self) -> str:
        """SHA-256 of the downloaded weights file, measured once and remembered.

        A model card that names a checkpoint is a promise about *which bytes ran*; hashing
        the snapshot is how that promise is kept. The digest is cached beside the batches
        because hashing 2.6 GB every run would be a minute of nothing.
        """
        if self.digest:
            return self.digest
        remembered = self.directory / "weights.digest.json"
        if remembered.exists():
            self.digest = str(json.loads(remembered.read_text())["sha256"])
            return self.digest
        path = self._weights_path()
        if path is None:
            return ""
        sha = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                sha.update(block)
        self.digest = sha.hexdigest()
        self.directory.mkdir(parents=True, exist_ok=True)
        remembered.write_text(
            json.dumps({"sha256": self.digest, "file": path.name, "checkpoint": self.checkpoint_id})
        )
        return self.digest

    def _weights_path(self) -> Path | None:
        from huggingface_hub import snapshot_download

        snapshot = Path(snapshot_download(self.checkpoint_id))
        for name in ("model.safetensors", "pytorch_model.bin"):
            if (snapshot / name).exists():
                return snapshot / name
        return None

    def _load(self) -> tuple[Any, Any]:
        if self._model is None:
            import torch
            from transformers import AutoModelForMaskedLM, AutoTokenizer

            torch.set_grad_enabled(False)
            self._tokenizer = AutoTokenizer.from_pretrained(self.checkpoint_id)
            self._model = AutoModelForMaskedLM.from_pretrained(self.checkpoint_id)
            self._model.eval()
        return self._model, self._tokenizer

    # ── the windows ──────────────────────────────────────────────────────────────────

    def windows(self, allele_ids: Sequence[str]) -> dict[str, tuple[str, str]]:
        """Read the window pair of each id straight from the record Parquet under ``build/``."""
        import duckdb

        source = Path(self.records_parquet)
        if not source.exists():
            raise FileNotFoundError(
                f"{self.name}: no record set at {source}; run `mva-zoo records` first"
            )
        con = self.connection or duckdb.connect()
        rows = con.execute(
            "SELECT allele_id, protein_window_ref, protein_window_alt FROM read_parquet(?) "
            "WHERE protein_window_ref IS NOT NULL AND protein_window_alt IS NOT NULL",
            [str(source)],
        ).fetchall()
        wanted = set(allele_ids)
        return {str(row[0]): (str(row[1]), str(row[2])) for row in rows if str(row[0]) in wanted}

    # ── the Adapter protocol ─────────────────────────────────────────────────────────

    def coverage(self, records: Sequence[AlleleRecord]) -> Coverage:
        """What this lane *can* score: the records that carry a window pair.

        Loading the weights is not required to answer that, which is the point — coverage is
        a property of the input, and a lane that cannot see an allele should say so in
        seconds rather than after an hour of inference.
        """
        have = self.windows([record.allele_id for record in records])
        return coverage_from_ids(self.name, records, set(have))

    def score(self, records: Sequence[AlleleRecord]) -> Iterator[ScoreRow]:
        done = dict(self.load_checkpoints())
        pairs = self.windows([record.allele_id for record in records])
        pending = [allele for allele in pairs if allele not in done]
        if self.limit is not None:
            pending = pending[: self.limit]
        index = self._next_index()
        started = time.time()
        for start in range(0, len(pending), self.batch):
            chunk = pending[start : start + self.batch]
            scored = self._score_chunk({allele: pairs[allele] for allele in chunk})
            self._append(index, scored)
            done.update(scored)
            index += 1
            if self.progress:
                elapsed = time.time() - started
                rate = (start + len(chunk)) / elapsed if elapsed else 0.0
                self.progress(
                    f"    {start + len(chunk):,}/{len(pending):,} alleles, "
                    f"{rate:.2f}/s, {elapsed:.0f}s elapsed"
                )
        digest = self.weights_digest()
        for record in records:
            if record.allele_id not in done:
                continue
            published = done[record.allele_id]
            yield ScoreRow(
                allele_id=record.allele_id,
                model=self.name,
                version=self.version,
                score=published * (1 if self.score_sign >= 0 else -1),
                aux={"llr": published, "checkpoint": self.checkpoint_id},
                digest=digest,
                venue=self.venue,
                licence=self.licence,
            )

    def submit(self, records: Sequence[AlleleRecord]) -> RemoteJob:
        raise NotImplementedError(f"{self.name} runs locally — call score()")

    def _score_chunk(self, pairs: dict[str, tuple[str, str]]) -> dict[str, float]:
        model, tokenizer = self._load()
        return masked_marginals(model, tokenizer, pairs)


def changed_index(reference: str, mutant: str) -> int:
    """Where the two windows differ. ``-1`` if they differ nowhere or in more than one place.

    Deriving the position instead of carrying it means the lane needs no radius, no offset
    and no assumption about clamping at a protein's terminus: the windows themselves say
    where the change is.
    """
    if len(reference) != len(mutant):
        return -1
    differing = [i for i, (a, b) in enumerate(zip(reference, mutant, strict=True)) if a != b]
    return differing[0] if len(differing) == 1 else -1


def masked_marginals(
    model: Any, tokenizer: Any, pairs: dict[str, tuple[str, str]]
) -> dict[str, float]:
    """``log P(mutant) − log P(reference)`` at the changed position, one forward pass per batch.

    The reference window is tokenised, the changed position replaced by the tokenizer's mask
    token, and the model's distribution at that position read for both residues. ESM2's
    tokenizer prepends a class token, so residue *i* of the window is token *i + 1*.
    """
    alleles = [allele for allele, (ref, alt) in pairs.items() if changed_index(ref, alt) >= 0]
    if not alleles:
        return {}
    import torch

    windows = [pairs[allele][0] for allele in alleles]
    spots = [changed_index(*pairs[allele]) for allele in alleles]
    encoded = tokenizer(windows, return_tensors="pt", padding=True)
    ids = encoded["input_ids"].clone()
    for row, spot in enumerate(spots):
        ids[row, spot + 1] = tokenizer.mask_token_id
    logits = model(input_ids=ids, attention_mask=encoded["attention_mask"]).logits
    log_probs = torch.log_softmax(logits, dim=-1)
    scored: dict[str, float] = {}
    for row, allele in enumerate(alleles):
        reference, mutant = pairs[allele]
        spot = spots[row]
        at = log_probs[row, spot + 1]
        ref_token = tokenizer.convert_tokens_to_ids(reference[spot])
        alt_token = tokenizer.convert_tokens_to_ids(mutant[spot])
        scored[allele] = float(at[alt_token] - at[ref_token])
    return scored


def build(card: Any, *, connection: Any = None, records_parquet: Path = DEFAULT_RECORDS) -> Adapter:
    """Build the lane one model card describes.

    ``params.checkpoint`` is the published artefact this lane runs — a Hugging Face repo id,
    recorded in the card so the report can name exactly which weights produced the numbers.
    ``params.entrypoint`` is the roster's older, coarser name for the same thing and is used
    only if no checkpoint is given.
    """
    params = dict(getattr(card, "params", {}) or {})
    checkpoint = str(params.get("checkpoint") or getattr(card, "version", "") or "")
    limit = params.get("limit")
    return LocalProcessAdapter(
        name=str(card.key),
        version=str(card.version),
        checkpoint_id=checkpoint,
        records_parquet=Path(str(params.get("records_parquet") or records_parquet)),
        work_dir=Path(str(params.get("work_dir") or DEFAULT_WORK)),
        batch=int(params.get("batch", DEFAULT_BATCH) or DEFAULT_BATCH),
        score_sign=int(params.get("score_sign", -1) or -1),
        licence=str(getattr(card, "licence", "") or ""),
        digest=str(params.get("digest", "") or ""),
        limit=int(limit) if limit else None,
        connection=connection,
        tier=2,
        catalogue_adjacent=bool(getattr(card, "catalogue_adjacent", False)),
    )
