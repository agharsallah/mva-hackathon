"""The tier-3 contract: what the laptop sends a Modal GPU lane, and what comes back.

Pinned here so both halves import one definition: :mod:`mva.zoo.adapters.modal_gpu` (the
laptop side, which never imports ``modal`` at module level) and every app under
:mod:`mva.zoo.modal_apps` (the container side). Pure data — no ``modal``, no ``torch``.

**The wire shape, in plain words.** One call carries a batch of *items*; each item is an
allele id plus two sequence windows and where the change sits in them. Nothing else crosses
the wire: no chromosome, no position, no gene, no HGVS. The reply carries one score per item
it could score, the weights digest the container measured, and the GPU seconds it spent — so
the laptop's ledger can price every call without trusting a dashboard.

**Money.** :data:`GPU_USD_PER_SECOND` is Modal's published per-second GPU rate, read from
``modal.com/pricing`` on 2026-09-23. It prices the ledger; ``modal billing report`` is the
reconciliation, and the two are both quoted in step 8's entries.
"""

from __future__ import annotations

from typing import Any, TypedDict

__all__ = [
    "APP_PREFIX",
    "CAP_USD",
    "CLASS_NAME",
    "GPU_USD_PER_SECOND",
    "LANE_BUDGET_USD",
    "METHOD",
    "OVERHEAD_FACTOR",
    "WEIGHTS_VOLUME",
    "Item",
    "Reply",
    "ScoredItem",
    "app_name",
    "price",
    "reply",
]

#: One Modal app per lane: ``mva-zoo-<key>``. One app per lane so a deploy of one lane never
#: replaces another's functions, and ``modal app stop`` can end one lane alone.
APP_PREFIX = "mva-zoo-"

#: Every lane app exposes one class with this name, and this method on it.
CLASS_NAME = "Scorer"
METHOD = "score_batch"

#: Weights live in one Modal Volume per lane (plan B1), listed in the deletion checklist.
WEIGHTS_VOLUME = "mva-zoo-{key}-weights"

#: The user's hard cap for the whole of step 8 (2026-09-23), and each lane's share of it.
#: The rest is reserve. A lane that would exceed its share stops and says so.
CAP_USD = 50.0
LANE_BUDGET_USD: dict[str, float] = {
    "ntv2": 6.0,
    "esmc": 4.0,
    "evo2": 18.0,
    "boltz2": 6.0,
    "api": 1.0,
    "esm2": 5.0,  # iteration-6 model-generation check (protocol ceiling, 2026-10-22)
}

#: Measured GPU seconds exclude cold start and the idle window before scale-down; the guard
#: pads every estimate by this factor. The billing report is what settles it.
OVERHEAD_FACTOR = 1.3

#: USD per GPU-second, modal.com/pricing, read 2026-09-23.
GPU_USD_PER_SECOND: dict[str, float] = {
    "B200": 0.001736,
    "H200": 0.001261,
    "H100": 0.001097,
    "A100-80GB": 0.000694,
    "A100": 0.000583,
    "A100-40GB": 0.000583,
    "L40S": 0.000542,
    "A10": 0.000306,
    "A10G": 0.000306,
    "L4": 0.000222,
    "T4": 0.000164,
}


class Item(TypedDict):
    """One allele on the wire. ``center`` is the 0-based offset of the change in both windows."""

    allele_id: str
    ref: str
    alt: str
    center: int


class ScoredItem(TypedDict):
    """One lane's verdict on one item. ``score`` is the model's *published* number; the
    card's ``score_sign`` turns it into the zoo's "higher = more damaging" on the laptop."""

    allele_id: str
    score: float
    aux: dict[str, Any]


class Reply(TypedDict):
    """What one ``score_batch`` call returns."""

    scores: list[ScoredItem]
    version: str
    digest: str
    gpu: str
    seconds: float
    skipped: int


def app_name(key: str) -> str:
    return f"{APP_PREFIX}{key}"


def price(gpu: str, seconds: float) -> float:
    """USD for ``seconds`` of ``gpu``; an unknown GPU is priced as an H100 (the dearest
    common one), so a typo can only over-count."""
    name, _, many = gpu.partition(":")
    rate = GPU_USD_PER_SECOND.get(name, GPU_USD_PER_SECOND["H100"])
    count = int(many) if many else 1
    return rate * count * seconds


def reply(
    scores: list[ScoredItem], *, version: str, digest: str, gpu: str, seconds: float, sent: int
) -> Reply:
    """The container's side of the contract, in one call, so every lane replies alike."""
    return Reply(
        scores=scores,
        version=version,
        digest=digest,
        gpu=gpu,
        seconds=round(seconds, 3),
        skipped=sent - len(scores),
    )
