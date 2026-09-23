"""ESM-C 600M on a Modal GPU — the zoo's second protein language model, scored like ESM2.

**What it is.** ESM-C ("ESM Cambrian", EvolutionaryScale, Dec 2024) is a masked protein
language model (a next-token model over amino acids, trained to fill in hidden residues).
It is ESM2's successor: similar size (600M parameters), trained on a larger protein corpus,
and — like ESM2 — on no variant labels, so it is catalogue-free.

**What it computes.** The *same* recipe as the ESM2 lane
(:func:`mva.zoo.adapters.local_process.masked_marginals`), so the two lanes are an
apples-to-apples agreement test:

    published = log P(alt residue | ref window, changed position masked)
              − log P(ref residue | same masked window)

≤ 0 for a substitution the model finds less plausible — more negative = more damaging — so
the card sets ``score_sign = -1``. Precision is float32 (the library's ``from_pretrained``
would cast to bfloat16 on a GPU; the ESM2 lane ran float32 on CPU, and so does this one).

**What crosses the wire.** ``allele_id``, the two 129-residue windows, ``center``. Nothing is
kept in the container; the volume holds weights only.

**Licence.** EvolutionaryScale Cambrian non-commercial licence (hackathon use is
non-commercial). The Hugging Face repository is not gated: no token, no secret.

Deploy / smoke / stop only through ``tools/modal_trace.py`` (recipe: ``README.md`` here).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, NamedTuple

import modal

from mva.zoo.modal_contract import Item, Reply, ScoredItem, app_name, reply

from . import _common

KEY = "esmc"
#: The published weights, pinned to the commit read from the Hugging Face API on 2026-09-23.
#: The repository now answers as ``biohub/``; the old ``EvolutionaryScale/`` name redirects.
HF_REPO = "biohub/esmc-600m-2024-12"
HF_REVISION = "e4d83bc7e10fd55c92e598e545f4a76bf04a6e5c"
WEIGHTS_FILE = "data/weights/esmc_600m_2024_12_v0.pth"
ESM_VERSION = "3.1.1"
GPU = "L4"
VERSION = f"esmc_600m esm=={ESM_VERSION} hf:{HF_REPO}@{HF_REVISION[:12]}"
WEIGHTS = Path("/weights")
#: Rows per forward pass inside one call. 64 windows of 129 residues are a few hundred MB of
#: activations beside 2.4 GB of float32 weights on a 24 GB L4.
FORWARD_BATCH = 64

#: The 20 canonical residues plus the ambiguity letters ESM-C's vocabulary carries.
RESIDUES = frozenset("ACDEFGHIKLMNPQRSTVWYXBUZO")

app = modal.App(app_name(KEY))

image = _common.with_mva(
    modal.Image.debian_slim(python_version="3.11")
    .uv_pip_install(
        f"esm=={ESM_VERSION}",
        "torch==2.4.1",
        "huggingface-hub==0.36.0",
        "fastapi[standard]==0.115.4",
    )
    .env({"HF_HOME": str(WEIGHTS / "hf"), "HF_XET_HIGH_PERFORMANCE": "1"}),
    KEY,
)


# ── pure logic (no torch, no modal): what can be scored, and how ─────────────────────────


class Planned(NamedTuple):
    """One item that passed the checks: the window to mask, where, and the two residues."""

    allele_id: str
    window: str
    spot: int
    ref: str
    alt: str


def plan(items: Sequence[Item]) -> list[Planned]:
    """The items this lane can score — one substituted residue, at ``center``, both canonical.

    Anything else (length change, several differences, ``center`` off the window, a stop or
    unknown letter at the changed spot) is skipped and counted in the reply's ``skipped``.
    """
    out: list[Planned] = []
    for item in items:
        ref, alt, spot = item["ref"], item["alt"], int(item["center"])
        if len(ref) != len(alt) or not 0 <= spot < len(ref):
            continue
        if ref[spot] == alt[spot] or ref[spot] not in RESIDUES or alt[spot] not in RESIDUES:
            continue
        if sum(a != b for a, b in zip(ref, alt, strict=True)) != 1:
            continue
        if not set(ref) <= RESIDUES:
            continue
        out.append(Planned(item["allele_id"], ref, spot, ref[spot], alt[spot]))
    return out


def by_length(planned: Sequence[Planned], batch: int) -> list[list[Planned]]:
    """Forward-pass groups of one window length each, so no row carries padding."""
    groups: dict[int, list[Planned]] = {}
    for row in planned:
        groups.setdefault(len(row.window), []).append(row)
    return [
        rows[i : i + batch]
        for _, rows in sorted(groups.items())
        for i in range(0, len(rows), max(1, batch))
    ]


def llr(log_probs: dict[str, float], ref: str, alt: str) -> float:
    """``log P(alt) − log P(ref)`` read off one position's distribution."""
    return float(log_probs[alt] - log_probs[ref])


def _digest(root: Path) -> str:
    """The weights digest, measured once per download and kept beside the weights.

    Hashing 2.4 GB on every cold start is minutes of billed GPU idling; the ESM2 lane keeps
    its digest beside its weights for the same reason. The file is keyed by size and mtime,
    so replaced weights are re-hashed.
    """
    import json

    weights = root / WEIGHTS_FILE
    stamp = f"{weights.stat().st_size}:{weights.stat().st_mtime_ns}"
    memo = root / "digest.json"
    if memo.exists():
        kept = json.loads(memo.read_text())
        if kept.get("stamp") == stamp:
            return str(kept["sha256"])
    value = _common.sha256_tree(root, suffixes=(".pth",))
    memo.write_text(json.dumps({"sha256": value, "stamp": stamp}))
    _common.weights_volume(KEY).commit()
    return value


# ── the container ───────────────────────────────────────────────────────────────────────


@app.cls(
    image=image,
    gpu=GPU,
    volumes={str(WEIGHTS): _common.weights_volume(KEY)},
    scaledown_window=_common.SCALEDOWN_SECONDS,
    timeout=20 * _common.MINUTES,
    max_containers=4,
)
class Scorer:
    @modal.enter()
    def load(self) -> None:
        import torch
        from esm.models.esmc import ESMC
        from esm.tokenization import get_esmc_model_tokenizers
        from huggingface_hub import snapshot_download

        torch.set_grad_enabled(False)
        root = WEIGHTS / "snapshot"
        if not (root / WEIGHTS_FILE).exists():
            snapshot_download(HF_REPO, revision=HF_REVISION, local_dir=str(root))
            _common.weights_volume(KEY).commit()
        self.digest = _digest(root)
        tokenizer = get_esmc_model_tokenizers()
        with torch.device("cuda"):
            model = ESMC(d_model=1152, n_heads=18, n_layers=36, tokenizer=tokenizer).eval()
        state = torch.load(root / WEIGHTS_FILE, map_location="cuda", weights_only=True)
        model.load_state_dict(state)
        self.model, self.tokenizer = model, tokenizer
        self.gpu = GPU

    def _score(self, items: list[Item]) -> Reply:
        import torch

        with _common.timed() as timer:
            scores: list[ScoredItem] = []
            mask = self.tokenizer.mask_token_id
            for group in by_length(plan(items), FORWARD_BATCH):
                windows = [row.window for row in group]
                ids = self.tokenizer(windows, return_tensors="pt")["input_ids"].to("cuda")
                for n, row in enumerate(group):
                    ids[n, row.spot + 1] = mask  # <cls> is token 0: residue i is token i+1
                logits = self.model(sequence_tokens=ids).sequence_logits.float()
                log_probs = torch.log_softmax(logits, dim=-1)
                for n, row in enumerate(group):
                    at = log_probs[n, row.spot + 1]
                    ref_id = self.tokenizer.convert_tokens_to_ids(row.ref)
                    alt_id = self.tokenizer.convert_tokens_to_ids(row.alt)
                    value = llr({row.ref: float(at[ref_id]), row.alt: float(at[alt_id])},
                                row.ref, row.alt)  # fmt: skip
                    scores.append(ScoredItem(allele_id=row.allele_id, score=value,
                                             aux={"llr": value}))  # fmt: skip
            torch.cuda.synchronize()
        return reply(scores, version=VERSION, digest=self.digest, gpu=self.gpu,
                     seconds=timer.seconds, sent=len(items))  # fmt: skip

    @modal.method()
    def score_batch(self, items: list[Item]) -> Reply:
        return self._score(items)

    @modal.fastapi_endpoint(method="POST", requires_proxy_auth=True)
    def score(self, body: dict[str, Any]) -> dict[str, Any]:
        # A plain dict, not ``Reply``: FastAPI cannot build a response model from a
        # ``typing.TypedDict`` on Python 3.11. The shape is the same.
        return dict(self._score(list(body.get("items", []))))

    @modal.fastapi_endpoint(method="GET", requires_proxy_auth=True)
    def health(self) -> dict[str, str]:
        return {"model": KEY, "version": VERSION, "digest": self.digest, "gpu": self.gpu}


#: A public reference protein fragment — human ubiquitin (UniProt P0CG48, residues 1–76),
#: nothing from the patient. The smoke substitutes one residue at a time.
UBIQUITIN = "MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG"


def smoke_items() -> list[Item]:
    """Eight synthetic substitutions on ubiquitin, plus one malformed item to test skipping."""
    swaps = [(0, "A"), (6, "P"), (22, "A"), (43, "W"), (47, "E"), (67, "A"), (70, "D"), (75, "A")]
    items = [
        Item(
            allele_id=f"smoke-{spot}{alt}",
            ref=UBIQUITIN,
            alt=UBIQUITIN[:spot] + alt + UBIQUITIN[spot + 1 :],
            center=spot,
        )
        for spot, alt in swaps
    ]
    items.append(Item(allele_id="smoke-bad", ref=UBIQUITIN, alt=UBIQUITIN, center=3))
    return items


@app.local_entrypoint()
def smoke() -> None:
    import json

    out = Scorer().score_batch.remote(smoke_items())
    print(json.dumps(out, indent=2))
