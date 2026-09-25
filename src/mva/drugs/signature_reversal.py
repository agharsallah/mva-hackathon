"""Signature reversal, the pure part: pick a signature, draw decoys, rank what reverses it.

A **signature** here is a pair of gene sets: the genes a perturbation raised (``up``) and
the genes it lowered (``down``). A **connectivity engine** (SigCom LINCS, iLINCS) scores
every library signature against it; a compound whose own signature points the other way is
a **reverser** — the classic "find the drug that undoes the disease's expression change"
idea (Lamb 2006, the Connectivity Map).

This module holds no I/O and no network. It answers four questions with plain data:

1. :func:`read_consensus_row` — which coefficients does a consensus matrix hold for one
   perturbation? (one row of a genes-as-columns TSV, streamed)
2. :func:`pick_signature` — which genes are the fixed query? (the top ``n`` raised and
   lowered genes within a declared gene space)
3. :func:`decoy_signatures` — which size-matched random queries calibrate "specifically"?
4. :func:`rank_by_label` — per compound (or per perturbed gene), where is its best
   signature? One compound has many signatures (cell lines, doses, times); it is ranked by
   the best of them, and the aggregation is stated in every output.

Nothing here knows BUB1B, LINCS or a disease: every name comes from the caller.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Collection, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass

__all__ = [
    "Hit",
    "Ranked",
    "Signature",
    "decoy_signatures",
    "ilincs_reverser_hits",
    "percentile",
    "pick_signature",
    "rank_by_label",
    "read_consensus_row",
    "sigcom_hits",
    "top_keys",
]


@dataclass(frozen=True)
class Signature:
    """One up/down query and where it came from."""

    name: str
    up: tuple[str, ...]
    down: tuple[str, ...]
    source: str

    def genes(self) -> frozenset[str]:
        return frozenset(self.up) | frozenset(self.down)


@dataclass(frozen=True)
class Hit:
    """One library signature in one direction's ordering (1 = strongest)."""

    signature_id: str
    position: int
    score: float
    label: str
    context: str = ""


@dataclass(frozen=True)
class Ranked:
    """One label (a compound, or a perturbed gene) at its best signature."""

    key: str
    label: str
    rank: int
    best_position: int
    best_score: float
    signature_id: str
    context: str
    signatures: int


def read_consensus_row(lines: Iterable[str], perturbation: str) -> dict[str, float]:
    """Coefficients of one row of a ``perturbations × genes`` TSV (header = genes).

    The first line is the header (a blank corner cell, then gene symbols); each later line
    is ``<perturbation>\\t<value>…``. Stops at the first match; raises when absent.
    """
    stream: Iterator[str] = iter(lines)
    try:
        header = next(stream).rstrip("\n").split("\t")[1:]
    except StopIteration as error:
        raise ValueError("consensus matrix is empty") from error
    for line in stream:
        name, _, rest = line.partition("\t")
        if name != perturbation:
            continue
        values = rest.rstrip("\n").split("\t")
        if len(values) != len(header):
            raise ValueError(f"row {perturbation}: {len(values)} values, {len(header)} genes")
        return {gene: float(value) for gene, value in zip(header, values, strict=True)}
    raise ValueError(f"perturbation {perturbation!r} is not a row of the consensus matrix")


def pick_signature(
    coefficients: Mapping[str, float],
    *,
    space: Collection[str],
    size: int,
    exclude: Collection[str] = (),
    name: str,
    source: str,
) -> Signature:
    """The ``size`` most raised and ``size`` most lowered genes of ``space``.

    Ties are broken by gene symbol so the pick is deterministic. Every up gene must have a
    positive coefficient and every down gene a negative one, or the signature is refused:
    a "raised" gene that went down would be a mislabelled query.
    """
    kept = [(gene, value) for gene, value in coefficients.items() if gene in space]
    kept = [(gene, value) for gene, value in kept if gene not in set(exclude)]
    if len(kept) < 2 * size:
        raise ValueError(f"{len(kept)} genes in the space, {2 * size} needed")
    ordered = sorted(kept, key=lambda item: (-item[1], item[0]))
    up = ordered[:size]
    down = sorted(kept, key=lambda item: (item[1], item[0]))[:size]
    if up[-1][1] <= 0 or down[-1][1] >= 0:
        raise ValueError("the space has too few raised or lowered genes for this size")
    return Signature(
        name=name,
        up=tuple(gene for gene, _ in up),
        down=tuple(gene for gene, _ in down),
        source=source,
    )


def decoy_signatures(
    space: Collection[str],
    *,
    n_up: int,
    n_down: int,
    count: int,
    seed: int,
    exclude: Collection[str] = (),
) -> list[Signature]:
    """``count`` random up/down queries of the real query's sizes, from the same space.

    One seeded generator draws them in order, so decoy ``k`` is the same on every run.
    Up and down never share a gene within one decoy; decoys may share genes with the real
    signature, as random draws from the same space would.
    """
    pool = sorted(set(space) - set(exclude))
    if len(pool) < n_up + n_down:
        raise ValueError(f"{len(pool)} genes in the space, {n_up + n_down} needed")
    rng = random.Random(seed)
    out: list[Signature] = []
    for k in range(1, count + 1):
        drawn = rng.sample(pool, n_up + n_down)
        out.append(
            Signature(
                name=f"decoy-{k:02d}",
                up=tuple(sorted(drawn[:n_up])),
                down=tuple(sorted(drawn[n_up:])),
                source=f"random draw {k} of {count}, seed {seed}",
            )
        )
    return out


def sigcom_hits(
    reply: Mapping[str, object],
    labels: Mapping[str, str],
    *,
    direction: str,
    contexts: Mapping[str, str] | None = None,
) -> list[Hit]:
    """One direction (``"reversers"`` or ``"mimickers"``) of a SigCom reply, 1-based.

    A signature whose id is missing from ``labels`` is dropped — it cannot be named — and
    the caller counts those drops from the difference in lengths.
    """
    max_rank = int(str(reply["maxRank"]))
    results = reply["results"]
    if not isinstance(results, list):
        raise TypeError("SigCom reply: results is not a list")
    out: list[Hit] = []
    for row in results:
        if row.get("type") != direction:
            continue
        uuid = str(row["uuid"])
        if uuid not in labels:
            continue
        rank = int(row["rank"])
        position = max_rank - rank if direction == "reversers" else rank + 1
        out.append(
            Hit(
                signature_id=uuid,
                position=position,
                score=float(row["z-sum"]),
                label=labels[uuid],
                context=(contexts or {}).get(uuid, ""),
            )
        )
    return sorted(out, key=lambda hit: (hit.position, hit.signature_id))


def ilincs_reverser_hits(rows: Sequence[Mapping[str, object]]) -> list[Hit]:
    """iLINCS concordance rows with negative similarity, most negative first (1-based).

    Ties on similarity break on p-value, then signature id.
    """
    reversing = [row for row in rows if float(str(row["similarity"])) < 0]
    ordered = sorted(
        reversing,
        key=lambda row: (
            float(str(row["similarity"])),
            float(str(row["pValue"])),
            str(row["signatureID"]),
        ),
    )
    return [
        Hit(
            signature_id=str(row["signatureID"]),
            position=index,
            score=float(str(row["similarity"])),
            label=str(row["compound"]),
            context=f"{row.get('cellLine', '')} {row.get('concentration', '')} "
            f"{row.get('time', '')}".strip(),
        )
        for index, row in enumerate(ordered, start=1)
    ]


def rank_by_label(
    hits: Iterable[Hit],
    *,
    key: Callable[[str], str],
    exclude: Collection[str] = (),
) -> list[Ranked]:
    """Aggregate hits per ``key(label)`` by best position; rank 1 = best label.

    ``exclude`` holds keys (not labels) left out before ranking, e.g. the perturbed gene
    itself in a positive control.
    """
    best: dict[str, Hit] = {}
    counts: dict[str, int] = {}
    for hit in hits:
        k = key(hit.label)
        if not k or k in exclude:
            continue
        counts[k] = counts.get(k, 0) + 1
        held = best.get(k)
        if held is None or (hit.position, hit.signature_id) < (held.position, held.signature_id):
            best[k] = hit
    ordered = sorted(best.items(), key=lambda item: (item[1].position, item[0]))
    return [
        Ranked(
            key=k,
            label=hit.label,
            rank=index,
            best_position=hit.position,
            best_score=hit.score,
            signature_id=hit.signature_id,
            context=hit.context,
            signatures=counts[k],
        )
        for index, (k, hit) in enumerate(ordered, start=1)
    ]


def top_keys(ranked: Sequence[Ranked], n: int) -> frozenset[str]:
    """Keys of the ``n`` best-ranked labels."""
    return frozenset(item.key for item in ranked if item.rank <= n)


def percentile(rank: int, universe: int) -> float:
    """``rank / universe``: 0.01 = the top 1 % of the universe."""
    if universe <= 0:
        raise ValueError("empty universe")
    return rank / universe
