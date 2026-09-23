"""Evo 2 1B (``evo2_1b_base``, Arc Institute) on a Modal H100 — the zoo's DNA language model lane.

**What it scores.** Evo 2 is an autoregressive DNA language model (it reads bases left to
right and predicts the next one). The zero-shot variant score is the Evo 2 authors' BRCA1
notebook recipe (``notebooks/brca1/brca1_zero_shot_vep.ipynb`` in github.com/ArcInstitute/evo2,
read 2026-09-23): the model's **mean per-token log-likelihood** of the alt window minus that
of the ref window. Negative = the alt window is less plausible DNA = more damaging, so the card
sets ``score_sign = -1``. The summed (not averaged) delta is kept in ``aux.delta_sum``; for a
same-length change (an SNV) the two differ by the constant factor ``len - 1``, for an indel
the mean is the length-normalised one.

**Why an H100.** The 1B checkpoint needs FP8 input projections through NVIDIA Transformer
Engine, and FP8 needs a Hopper GPU (Evo 2 README, "FP8 and Transformer Engine requirements").
The image is NVIDIA's NGC PyTorch container — the base the Evo 2 Dockerfile itself uses —
because it ships Transformer Engine and flash-attn prebuilt; ``pip install evo2`` goes on top.

Deploy and run only through ``tools/modal_trace.py`` (the audit trail). The smoke entrypoint
scores random bases only — never a patient window.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import modal

from mva.zoo.modal_apps import _common
from mva.zoo.modal_contract import Item, Reply, ScoredItem, app_name, reply

__all__ = ["CHECKPOINT", "GPU", "MAX_LEN", "app", "fit", "pad_to", "smoke"]

KEY = "evo2"
CHECKPOINT = "evo2_1b_base"
GPU = "H100"
#: The 1B base model's trained context (``configs/evo2-1b-8k.yml``: ``max_seqlen: 8192``).
MAX_LEN = 8192
#: Sequences per forward pass. Two per item (ref, alt), so 8 = four alleles per pass.
FORWARD_SEQS = 8
#: FP8 GEMMs want the token count in multiples of 16; the pad goes on the right of a causal
#: model, so it never changes the log-probabilities of the real bases before it.
PAD_MULTIPLE = 128

NGC_IMAGE = "nvcr.io/nvidia/pytorch:25.04-py3"
PINS = ("evo2==0.6.0", "vtx==1.1.0", "fastapi[standard]==0.116.1")

app = modal.App(app_name(KEY))
weights = _common.weights_volume(KEY)
image = _common.with_mva(
    modal.Image.from_registry(NGC_IMAGE)
    .entrypoint([])
    .pip_install(*PINS)
    .env({"HF_HOME": "/weights/hf", "TOKENIZERS_PARALLELISM": "false"}),
    KEY,
)


# ── pure helpers (no torch, testable on the laptop) ──────────────────────────────────


def fit(item: Item, max_len: int = MAX_LEN) -> tuple[Item, bool]:
    """Re-crop both windows centrally so neither exceeds ``max_len`` (an insertion's alt
    window can be longer than the ref's). Returns the item and whether it was cropped."""
    delta = len(item["alt"]) - len(item["ref"])
    if max(len(item["ref"]), len(item["alt"])) <= max_len:
        return item, False
    length = max_len - max(0, delta)
    start = max(0, min(item["center"] - length // 2, len(item["ref"]) - length))
    return (
        Item(
            allele_id=item["allele_id"],
            ref=item["ref"][start : start + length],
            alt=item["alt"][start : start + length + delta],
            center=item["center"] - start,
        ),
        True,
    )


def pad_to(length: int, multiple: int = PAD_MULTIPLE) -> int:
    return -(-length // multiple) * multiple


def synthetic_items(n: int, length: int, seed: int = 7) -> list[Item]:
    """Random bases with a change at the centre: SNVs, plus one insertion and one deletion."""
    rng = random.Random(seed)
    out: list[Item] = []
    for i in range(n):
        ref = "".join(rng.choice("ACGT") for _ in range(length))
        c = length // 2
        if i == n - 2:
            alt = ref[: c + 1] + "".join(rng.choice("ACGT") for _ in range(6)) + ref[c + 1 :]
        elif i == n - 1:
            alt = ref[: c + 1] + ref[c + 7 :]
        else:
            alt = ref[:c] + rng.choice([b for b in "ACGT" if b != ref[c]]) + ref[c + 1 :]
        out.append(Item(allele_id=f"synthetic-{i}", ref=ref, alt=alt, center=c))
    return out


# ── the container ────────────────────────────────────────────────────────────────────


@app.cls(
    image=image,
    gpu=GPU,
    volumes={"/weights": weights},
    scaledown_window=_common.SCALEDOWN_SECONDS,
    timeout=30 * _common.MINUTES,
    max_containers=4,
)
class Scorer:
    @modal.enter()
    def load(self) -> None:
        import evo2
        from evo2 import Evo2

        self.model = Evo2(CHECKPOINT)
        weights.commit()
        snapshots = sorted(
            Path("/weights/hf/hub").glob(f"models--arcinstitute--{CHECKPOINT}/snapshots/*")
        )
        self.revision = snapshots[-1].name if snapshots else "unknown"
        cached = Path(f"/weights/digest-{self.revision}.txt")
        if cached.exists():
            self.digest = cached.read_text().strip()
        else:
            self.digest = _common.sha256_tree(Path("/weights/hf"))
            cached.write_text(self.digest)
            weights.commit()
        self.version = (
            f"{CHECKPOINT}@hf:{self.revision[:12]}+evo2-{getattr(evo2, '__version__', '0.6.0')}"
        )

    def _loglik(self, seqs: list[str]) -> list[tuple[float, int]]:
        """(sum of per-token log-probs, tokens scored) for each sequence, one padded pass."""
        import torch

        tok = self.model.tokenizer
        width = pad_to(max(len(s) for s in seqs))
        rows = [tok.tokenize(s) + [tok.pad_id] * (width - len(s)) for s in seqs]
        ids = torch.tensor(rows, dtype=torch.long, device="cuda:0")
        with torch.inference_mode():
            logits, _ = self.model.model(ids)
            logp = torch.log_softmax(logits[:, :-1].float(), dim=-1)
            tokens = torch.gather(logp, 2, ids[:, 1:].unsqueeze(-1)).squeeze(-1)
        out: list[tuple[float, int]] = []
        for row, seq in zip(tokens, seqs, strict=True):
            n = len(seq) - 1
            out.append((float(row[:n].sum().item()), n))
        return out

    def _score(self, items: list[Item]) -> tuple[list[ScoredItem], dict[str, int]]:
        prepared = [fit(item) for item in items]
        seqs = [s for item, _ in prepared for s in (item["ref"], item["alt"])]
        lls: list[tuple[float, int] | None] = []
        errors: dict[str, int] = {}
        for i in range(0, len(seqs), FORWARD_SEQS):
            chunk = seqs[i : i + FORWARD_SEQS]
            try:
                lls.extend(self._loglik(chunk))
            except Exception as error:  # an OOM or a kernel shape error: retry one at a time
                errors[type(error).__name__] = errors.get(type(error).__name__, 0) + 1
                for seq in chunk:
                    try:
                        lls.extend(self._loglik([seq]))
                    except Exception as single:  # the item is skipped, counted by type
                        errors[type(single).__name__] = errors.get(type(single).__name__, 0) + 1
                        lls.append(None)
        scores: list[ScoredItem] = []
        for k, (item, cropped) in enumerate(prepared):
            ref, alt = lls[2 * k], lls[2 * k + 1]
            if ref is None or alt is None:
                continue
            mean = alt[0] / alt[1] - ref[0] / ref[1]
            aux: dict[str, Any] = {
                "delta_sum": alt[0] - ref[0],
                "delta_mean": mean,
                "ll_ref_mean": ref[0] / ref[1],
                "tokens_ref": ref[1] + 1,
                "tokens_alt": alt[1] + 1,
                "recropped": cropped,
                "reduce": "mean",
            }
            scores.append(ScoredItem(allele_id=item["allele_id"], score=mean, aux=aux))
        return scores, errors

    def _reply(self, items: list[Item]) -> Reply:
        with _common.timed() as timer:
            scores, errors = self._score(items)
        if errors:
            print(f"evo2 errors by type: {errors}")  # counts only, never a sequence
        return reply(
            scores,
            version=self.version,
            digest=self.digest,
            gpu=GPU,
            seconds=timer.seconds,
            sent=len(items),
        )

    @modal.method()
    def score_batch(self, items: list[Item]) -> Reply:
        return self._reply(items)

    @modal.fastapi_endpoint(method="POST", requires_proxy_auth=True)
    def score(self, body: dict[str, Any]) -> Reply:
        items = [
            Item(
                allele_id=str(x["allele_id"]),
                ref=str(x["ref"]),
                alt=str(x["alt"]),
                center=int(x["center"]),
            )
            for x in body.get("items", [])
        ]
        return self._reply(items)

    @modal.fastapi_endpoint(method="GET", requires_proxy_auth=True)
    def health(self) -> dict[str, str]:
        return {"model": CHECKPOINT, "version": self.version, "digest": self.digest, "gpu": GPU}


@app.local_entrypoint()
def smoke(n: int = 8, length: int = 1024) -> None:
    """Score ``n`` random-base items of ``length`` bases, twice, and print both replies.

    The repeat is the determinism check (FP8 delayed scaling keeps state across passes)."""
    items = synthetic_items(n, length)
    scorer = Scorer()
    first = scorer.score_batch.remote(items)
    again = scorer.score_batch.remote(list(reversed(items)))
    spread = max(
        abs(a["score"] - b["score"])
        for a in first["scores"]
        for b in again["scores"]
        if a["allele_id"] == b["allele_id"]
    )
    print({k: first[k] for k in ("version", "digest", "gpu", "seconds", "skipped")})
    for row in first["scores"]:
        print(row["allele_id"], round(row["score"], 6), round(row["aux"]["delta_sum"], 4))
    print(f"repeat seconds {again['seconds']}, max |score diff| across passes {spread:.3e}")
