"""Tier-3 lane ``mva-zoo-ntv2``: Nucleotide Transformer v2 500M on a Modal GPU.

**What it scores.** NT-v2 is a masked DNA language model (a BERT over non-overlapping 6-base
words, *6-mers*). The published zero-shot recipe (Dalla-Torre et al., Nature Methods 2024,
PMID 39609566) compares the model's *embeddings* (its internal vector for a sequence) of the
reference and the mutated window. This lane's score is that comparison:

* ``score`` = **cosine distance** ``1 - cos(mean_ref, mean_alt)`` between the mean final-layer
  embeddings of the two windows. 0 = the model sees no change; higher = more changed, which
  the card reads as "more damaging" (``score_sign = +1``). It needs no token alignment, so it
  scores SNVs and indels alike.
* ``aux.llr`` (SNV-like changes only) = masked-token log-likelihood ratio at the 6-mer holding
  the change: mask that token in the reference window, read
  ``log P(alt 6-mer) - log P(ref 6-mer)``. Negative = the model finds the mutant word unlikely.
* ``aux.l2`` = Euclidean distance of the same mean embeddings; ``aux.cos_local`` = cosine
  distance over the tokens within :data:`LOCAL` tokens of the change.

**Precision** (:data:`PRECISION`). An SNV moves a mean over ~1,000 tokens by very little, so
half precision is a risk to the signal. ``"fp32"`` runs float32 with TF32 off; ``"fp16"`` runs
the matmuls under ``torch.autocast`` (weights, softmax and norms stay float32). Which one the
case used, and how far fp16 is from fp32 on the same alleles, is measured in entry 144.

Nothing patient-specific is logged or kept: windows arrive, scores leave.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from typing import Any

import modal

from mva.zoo import modal_contract as contract
from mva.zoo.modal_apps import _common

KEY = "ntv2"
MODEL_ID = "InstaDeepAI/nucleotide-transformer-v2-500m-multi-species"
#: The Hugging Face commit the weights are pulled at (read from the Hub API, 2026-09-23).
REVISION = "06615c1660c892fc199840c18123f8385b3542a8"
VERSION = f"{MODEL_ID}@{REVISION}"
GPU = "L4"
K = 6
#: NT-v2's positional table: 2,048 tokens including the leading CLS token.
MAX_TOKENS = 2048
#: ± tokens around the change for ``aux.cos_local``.
LOCAL = 16
#: Sequences per forward pass inside one call.
MICRO_BATCH = 8
#: The HTTP endpoint spends GPU budget: cap one request.
HTTP_MAX_ITEMS = 64
WEIGHTS = "/weights"
#: "fp32" or "fp16" — see the module docstring; recorded in every item's ``aux.precision``.
PRECISION = "fp16"
_ACGT = frozenset("ACGT")

# ── pure helpers (no torch; unit-tested) ─────────────────────────────────────────────────


def clean(seq: str) -> str:
    """Upper-case; any letter outside ACGTN becomes N (NT-v2's vocabulary has no IUPAC codes)."""
    return "".join(c if c in "ACGTN" else "N" for c in seq.upper())


def kmer_spans(seq: str, k: int = K) -> list[tuple[int, int]]:
    """NT-v2's tokenisation as ``(start, end)`` spans: greedy left-to-right ``k``-mers of ACGT,
    and one single-letter token wherever a full ACGT ``k``-mer does not fit (an N, the tail)."""
    spans: list[tuple[int, int]] = []
    i = 0
    while i < len(seq):
        word = seq[i : i + k]
        step = k if len(word) == k and _ACGT.issuperset(word) else 1
        spans.append((i, i + step))
        i += step
    return spans


def token_at(spans: Sequence[tuple[int, int]], offset: int) -> int:
    """Index of the span holding base ``offset`` (-1 if none)."""
    for index, (start, end) in enumerate(spans):
        if start <= offset < end:
            return index
    return -1


def llr_site(ref: str, alt: str, center: int) -> int:
    """The token whose masking yields a clean LLR, or -1: equal length, identical token
    boundaries, and every changed base inside the one token that holds ``center``."""
    if len(ref) != len(alt) or ref == alt:
        return -1
    spans = kmer_spans(ref)
    if spans != kmer_spans(alt):
        return -1
    site = token_at(spans, center)
    if site < 0:
        return -1
    start, end = spans[site]
    changed = [i for i, (a, b) in enumerate(zip(ref, alt, strict=True)) if a != b]
    return site if all(start <= i < end for i in changed) and end - start == K else -1


def encode(seq: str, vocab: Mapping[str, int], cls_id: int) -> list[int]:
    """Token ids with the leading CLS, truncated on the right to :data:`MAX_TOKENS`."""
    ids = [cls_id] + [vocab[seq[a:b]] for a, b in kmer_spans(seq)]
    return ids[:MAX_TOKENS]


def synthetic_items(seed: int = 7, length: int = 6144) -> list[contract.Item]:
    """Random-base smoke items (never patient sequence): SNV, identity, indels, N, MNV."""
    rng = random.Random(seed)
    base = "".join(rng.choice("ACGT") for _ in range(length))
    c = length // 2
    swap = {"A": "C", "C": "G", "G": "T", "T": "A"}

    def item(name: str, alt: str) -> contract.Item:
        return contract.Item(allele_id=f"synthetic-{name}", ref=base, alt=alt, center=c)

    with_n = base[: c - 40] + "N" + base[c - 39 :]
    return [
        item("snv", base[:c] + swap[base[c]] + base[c + 1 :]),
        item("identity", base),
        item("del3", base[:c] + base[c + 3 :]),
        item("ins2", base[:c] + "GA" + base[c:]),
        contract.Item(
            allele_id="synthetic-snv-mid-token",
            ref=base,
            alt=base[: c + 3] + swap[base[c + 3]] + base[c + 4 :],
            center=c + 3,
        ),
        contract.Item(
            allele_id="synthetic-n-flank",
            ref=with_n,
            alt=with_n[:c] + swap[with_n[c]] + with_n[c + 1 :],
            center=c,
        ),
        item("mnv2", base[:c] + swap[base[c]] + swap[base[c + 1]] + base[c + 2 :]),
        item("del30", base[:c] + base[c + 30 :]),
    ]


# ── the Modal app ────────────────────────────────────────────────────────────────────────

app = modal.App(contract.app_name(KEY))

image = _common.with_mva(
    modal.Image.debian_slim(python_version="3.11")
    .uv_pip_install(
        "torch==2.5.1",
        "transformers==4.46.3",
        "huggingface_hub==0.26.5",
        "safetensors==0.4.5",
        "numpy==2.1.3",
        "fastapi[standard]==0.115.6",
    )
    .env({"HF_HUB_DISABLE_TELEMETRY": "1", "TOKENIZERS_PARALLELISM": "false"}),
    KEY,
)

volume = _common.weights_volume(KEY)


@app.cls(
    image=image,
    gpu=GPU,
    volumes={WEIGHTS: volume},
    scaledown_window=_common.SCALEDOWN_SECONDS,
    timeout=20 * _common.MINUTES,
    max_containers=4,
)
class Scorer:
    @modal.enter()
    def load(self) -> None:
        from pathlib import Path

        import torch
        from huggingface_hub import snapshot_download
        from transformers import AutoModelForMaskedLM, AutoTokenizer

        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        path = Path(WEIGHTS) / KEY / REVISION
        if not (path / "model.safetensors").exists():
            snapshot_download(
                MODEL_ID,
                revision=REVISION,
                local_dir=str(path),
                allow_patterns=["*.json", "*.py", "*.txt", "model.safetensors"],
            )
            volume.commit()
        self.digest = _common.sha256_tree(path, suffixes=(".safetensors",))
        self.tokenizer = AutoTokenizer.from_pretrained(str(path), trust_remote_code=True)
        self.model = (
            AutoModelForMaskedLM.from_pretrained(str(path), trust_remote_code=True)
            .to("cuda", dtype=torch.float32)
            .eval()
        )
        self.vocab = dict(self.tokenizer.get_vocab())
        self.cls_id = int(self.tokenizer.cls_token_id)
        self.mask_id = int(self.tokenizer.mask_token_id)
        self.pad_id = int(self.tokenizer.pad_token_id)
        self._check_tokeniser()

    def _check_tokeniser(self) -> None:
        """Our span tokeniser must agree with the published one, or the LLR site is wrong."""
        rng = random.Random(0)
        probe = "".join(rng.choices("ACGT", k=14)) + "NN" + "".join(rng.choices("ACGT", k=13))
        theirs = list(self.tokenizer(probe)["input_ids"])
        eos = self.tokenizer.eos_token_id
        if eos is not None and theirs and theirs[-1] == eos:
            theirs = theirs[:-1]
        ours = encode(probe, self.vocab, self.cls_id)
        if theirs != ours:
            raise RuntimeError(f"tokeniser mismatch: ours {ours} vs published {theirs}")

    def _forward(self, batch: list[list[int]], masked: bool) -> list[Any]:
        """Per sequence: (mean embedding, token embeddings) or full log-probs if ``masked``."""
        import torch

        out: list[Any] = [None] * len(batch)
        order = sorted(range(len(batch)), key=lambda i: len(batch[i]))
        for start in range(0, len(order), MICRO_BATCH):
            chunk = order[start : start + MICRO_BATCH]
            width = max(len(batch[i]) for i in chunk)
            ids = torch.full((len(chunk), width), self.pad_id, dtype=torch.long)
            mask = torch.zeros((len(chunk), width), dtype=torch.long)
            for row, i in enumerate(chunk):
                ids[row, : len(batch[i])] = torch.tensor(batch[i])
                mask[row, : len(batch[i])] = 1
            half = torch.autocast("cuda", dtype=torch.float16, enabled=PRECISION == "fp16")
            with torch.inference_mode(), half:
                res = self.model(
                    input_ids=ids.cuda(),
                    attention_mask=mask.cuda(),
                    output_hidden_states=not masked,
                )
            for row, i in enumerate(chunk):
                n = len(batch[i])
                if masked:
                    out[i] = res.logits[row, :n].float().log_softmax(-1).cpu()
                else:
                    tokens = res.hidden_states[-1][row, 1:n].double().cpu()
                    out[i] = (tokens.mean(0), tokens)
        return out

    def _score(self, items: list[contract.Item]) -> list[contract.ScoredItem]:
        import torch

        refs: list[list[int]] = []
        alts: list[list[int]] = []
        masked: list[list[int]] = []
        sites: list[tuple[int, int, int, int] | None] = []
        for it in items:
            ref, alt = clean(it["ref"]), clean(it["alt"])
            refs.append(encode(ref, self.vocab, self.cls_id))
            alts.append(encode(alt, self.vocab, self.cls_id))
            site = llr_site(ref, alt, it["center"])
            if site >= 0 and site + 1 < len(refs[-1]):
                spans = kmer_spans(ref)
                a, b = spans[site]
                ids = list(refs[-1])
                ids[site + 1] = self.mask_id
                masked.append(ids)
                sites.append(
                    (len(masked) - 1, site + 1, self.vocab[ref[a:b]], self.vocab[alt[a:b]])
                )
            else:
                sites.append(None)
        emb_ref = self._forward(refs, masked=False)
        emb_alt = self._forward(alts, masked=False)
        logp = self._forward(masked, masked=True) if masked else []
        scored: list[contract.ScoredItem] = []
        cos = torch.nn.functional.cosine_similarity
        for i, it in enumerate(items):
            (mr, tr), (ma, ta) = emb_ref[i], emb_alt[i]
            if min(tr.shape[0], ta.shape[0]) == 0:
                continue
            centre = token_at(kmer_spans(clean(it["ref"])), it["center"])
            lo, hi = max(0, centre - LOCAL), centre + LOCAL + 1
            local = 1.0 - float(cos(tr[lo:hi].mean(0), ta[lo:hi].mean(0), dim=0))
            aux: dict[str, Any] = {
                "l2": float(torch.linalg.vector_norm(mr - ma)),
                "cos_local": local,
                "tokens_ref": int(tr.shape[0]),
                "tokens_alt": int(ta.shape[0]),
                "llr": None,
                "precision": PRECISION,
            }
            hit = sites[i]
            if hit is not None:
                row, pos, r_id, a_id = hit
                aux["llr"] = float(logp[row][pos, a_id] - logp[row][pos, r_id])
            distance = 1.0 - float(cos(mr, ma, dim=0))
            scored.append(contract.ScoredItem(allele_id=it["allele_id"], score=distance, aux=aux))
        return scored

    def _reply(self, items: list[contract.Item]) -> contract.Reply:
        import torch

        with _common.timed() as timer:
            scores = self._score(items)
            torch.cuda.synchronize()
        return contract.reply(
            scores,
            version=VERSION,
            digest=self.digest,
            gpu=GPU,
            seconds=timer.seconds,
            sent=len(items),
        )

    @modal.method()
    def score_batch(self, items: list[contract.Item]) -> contract.Reply:
        return self._reply(items)

    # No TypedDict return annotations on the endpoints: FastAPI would turn them into pydantic
    # response models, which reject ``typing.TypedDict`` before Python 3.12.
    @modal.fastapi_endpoint(method="POST", requires_proxy_auth=True)
    def score(self, body: dict[str, Any]) -> dict[str, Any]:
        items = [
            contract.Item(
                allele_id=str(x["allele_id"]),
                ref=str(x["ref"]),
                alt=str(x["alt"]),
                center=int(x["center"]),
            )
            for x in body.get("items", [])[:HTTP_MAX_ITEMS]
        ]
        return dict(self._reply(items))

    @modal.fastapi_endpoint(method="GET", requires_proxy_auth=True)
    def health(self) -> dict[str, Any]:
        return {"model": MODEL_ID, "version": VERSION, "digest": self.digest, "gpu": GPU}


@app.local_entrypoint()
def smoke() -> None:
    """Score eight random-base items (never a patient window) and print the reply."""
    import json

    reply = Scorer().score_batch.remote(synthetic_items())
    print(json.dumps(reply, indent=1))
