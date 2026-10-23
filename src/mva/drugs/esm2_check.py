"""The ESM-2 model-generation check: windows to scan, the score table, and its evaluation.

Frozen protocol: ``ressources/track2/it6/esm2_check/protocol.md``. In plain words:

* **Windows.** ESM-2 was trained on crops of at most 1,022 residues; BubR1 has 1,050. Each
  site is scored in a 1,022-residue window centred on it and clamped at the ends (the
  *primary* window). Two fixed windows — N (residues 1–1022) and C (29–1050) — score every
  site they contain again, so the effect of the context choice is measured, not assumed.
* **Score.** Mask the site, read the model's log-probabilities there, and take
  ``log P(alt) − log P(wt)``. One forward pass per (window, site) gives all 19 substitutions.
  The damage score is its negation — higher = more damaging — fixed before any number existed.
* **Evaluation.** Raw AUROC on the eight primary alleles, the exact one-sided permutation tail
  over all C(8,5) = 56 label assignments, a stratified bootstrap interval, and the paired AUROC
  difference against the two comparators already in the atlas (ThermoMPNN ΔΔG, −ESM1b LLR).

Pure: numpy and polars only. The Modal side is :mod:`mva.zoo.modal_apps.esm2`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from itertools import combinations
from typing import Any

import numpy as np
import polars as pl

from mva.drugs.variant_atlas_model import auroc, bootstrap_auroc, percentile_rank

__all__ = [
    "AMINO",
    "CONTEXT",
    "DOMAIN",
    "HIGH_DAMAGE_PERCENTILE",
    "evaluate",
    "exact_tail",
    "jobs",
    "paired_difference",
    "primary_start",
    "score_table",
    "window_shift",
]

AMINO = "ACDEFGHIKLMNPQRSTVWY"
#: Residues per window: 1,024 training tokens minus ``<cls>`` and ``<eos>``.
CONTEXT = 1022
#: UniProt "Protein kinase" (the BubR1 pseudokinase), 1-based inclusive.
DOMAIN = (766, 1050)
#: Descriptive "high damage" line for the patient's placement (protocol: top 20 %).
HIGH_DAMAGE_PERCENTILE = 80.0


def primary_start(site: int, length: int, context: int = CONTEXT) -> int:
    """0-based start of the site-centred, terminal-clamped window for 1-based ``site``."""
    if not 1 <= site <= length:
        raise ValueError(f"site {site} outside 1..{length}")
    return min(max(site - 1 - context // 2, 0), max(length - context, 0))


def jobs(length: int, context: int = CONTEXT) -> list[tuple[int, int]]:
    """Every distinct ``(window_start, site)`` to run: primary, N and C windows, de-duplicated."""
    n_start, c_start = 0, max(length - context, 0)
    wanted: set[tuple[int, int]] = set()
    for site in range(1, length + 1):
        wanted.add((primary_start(site, length, context), site))
        for start in (n_start, c_start):
            if start < site <= start + context:
                wanted.add((start, site))
    return sorted(wanted)


def score_table(
    sequence: str,
    log_probs: Mapping[tuple[int, int], Sequence[float]],
    context: int = CONTEXT,
) -> pl.DataFrame:
    """One row per substitution: masked-marginal ``llr`` and ``damage`` in each window.

    ``log_probs[(start, site)]`` is the 20-vector over :data:`AMINO` at the masked site.
    Columns ``damage`` (primary window), ``damage_n``, ``damage_c`` (null where the fixed
    window does not contain the site). Raises on a missing primary pass or a non-finite value.
    """
    length = len(sequence)
    c_start = max(length - context, 0)
    rows: list[dict[str, Any]] = []
    for site in range(1, length + 1):
        wt = sequence[site - 1]
        start = primary_start(site, length, context)
        if (start, site) not in log_probs:
            raise ValueError(f"no primary pass for site {site}")
        windows = {"": start, "_n": 0, "_c": c_start}
        vectors = {
            tag: np.asarray(log_probs[(s, site)], dtype=float)
            for tag, s in windows.items()
            if (s, site) in log_probs and s < site <= s + context
        }
        for tag, vec in vectors.items():
            if vec.shape != (len(AMINO),) or not np.isfinite(vec).all():
                raise ValueError(f"site {site} window{tag or ' primary'}: bad log-prob vector")
        for alt in AMINO:
            if alt == wt:
                continue
            row: dict[str, Any] = {
                "position": site, "wt": wt, "alt": alt,
                "change": f"{wt}{site}{alt}", "window_start": start + 1,
            }  # fmt: skip
            for tag in ("", "_n", "_c"):
                got = vectors.get(tag)
                llr = None if got is None else float(got[AMINO.index(alt)] - got[AMINO.index(wt)])
                row[f"llr{tag}"] = llr
                row[f"damage{tag}"] = None if llr is None else -llr
            rows.append(row)
    schema: dict[str, Any] = {"position": pl.Int64, "wt": pl.Utf8, "alt": pl.Utf8,
                              "change": pl.Utf8, "window_start": pl.Int64}  # fmt: skip
    schema |= {f"{k}{t}": pl.Float64 for t in ("", "_n", "_c") for k in ("llr", "damage")}
    return pl.DataFrame(rows, schema=schema)


def exact_tail(scores: Sequence[float], labels: Sequence[int]) -> tuple[float, int, int]:
    """One-sided label-permutation tail: share of class assignments with AUROC ≥ observed.

    Enumerates every way to pick ``sum(labels)`` positives from the scored alleles (56 for
    5 of 8) with the actual scores, ties included. Returns ``(tail, hits, total)``.
    """
    observed = auroc(scores, labels)
    n, k = len(labels), int(sum(labels))
    total = hits = 0
    for chosen in combinations(range(n), k):
        perm = [int(i in chosen) for i in range(n)]
        total += 1
        hits += auroc(scores, perm) >= observed - 1e-12
    return hits / total, hits, total


def paired_difference(
    a: Sequence[float], b: Sequence[float], labels: Sequence[int], n: int = 2000, seed: int = 0
) -> dict[str, Any]:
    """AUROC(a) − AUROC(b) on the same alleles, with a paired stratified bootstrap interval."""
    rng = np.random.default_rng(seed)
    sa, sb, y = np.asarray(a, float), np.asarray(b, float), np.asarray(labels, int)
    pos, neg = np.flatnonzero(y == 1), np.flatnonzero(y == 0)
    draws = []
    for _ in range(n):
        idx = np.concatenate([rng.choice(pos, pos.size), rng.choice(neg, neg.size)])
        yy = y[idx].tolist()
        draws.append(auroc(sa[idx].tolist(), yy) - auroc(sb[idx].tolist(), yy))
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return {"difference": auroc(a, labels) - auroc(b, labels),
            "ci95": (float(lo), float(hi))}  # fmt: skip


def window_shift(table: pl.DataFrame, changes: Sequence[str] | None = None) -> dict[str, Any]:
    """How much the N-versus-C context moves damage scores and ranks where both apply."""
    both = table.filter(pl.col("damage_n").is_not_null() & pl.col("damage_c").is_not_null())
    if changes is not None:
        both = both.filter(pl.col("change").is_in(list(changes)))
    if both.height == 0:
        return {"n": 0}
    diff = (both["damage_n"] - both["damage_c"]).abs()
    rho = None
    if both.height > 2:
        ranks = (both["damage_n"].rank().to_numpy(), both["damage_c"].rank().to_numpy())
        rho = float(np.corrcoef(*ranks)[0, 1])
    return {"n": both.height, "max_abs": float(diff.max()),  # type: ignore[arg-type]
            "median_abs": float(diff.median()),  # type: ignore[arg-type]
            "spearman": rho}  # fmt: skip


def evaluate(
    labelled: pl.DataFrame, table: pl.DataFrame, bootstrap: int = 2000, seed: int = 0
) -> dict[str, Any]:
    """The primary endpoint and its comparators on one labelled set (``change``, ``y`` …).

    ``labelled`` is :func:`mva.drugs.variant_atlas.labelled_rows` output (it carries ``ddg``
    and ``esm1b_llr``); ESM-2 damage is joined from ``table``.
    """
    joined = labelled.join(
        table.select("change", "damage", "damage_n", "damage_c"), on="change", how="left"
    )
    if joined["damage"].null_count():
        raise ValueError("a labelled allele has no ESM-2 score (numbering mismatch?)")
    y = joined["y"].to_list()
    predictors = {
        "esm2_damage": joined["damage"].to_list(),
        "thermompnn_ddg": joined["ddg"].to_list(),
        "esm1b_llr_negated": [-v for v in joined["esm1b_llr"].to_list()],
    }
    out: dict[str, Any] = {"n_positive": int(sum(y)), "n_negative": len(y) - int(sum(y)),
                           "predictors": {}, "paired": {}}  # fmt: skip
    for name, scores in predictors.items():
        tail, hits, total = exact_tail(scores, y)
        out["predictors"][name] = {
            "auroc": auroc(scores, y),
            "ci95": bootstrap_auroc(scores, y, bootstrap, seed),
            "exact_tail": tail,
            "exact_hits": hits,
            "exact_total": total,
        }
    for other in ("thermompnn_ddg", "esm1b_llr_negated"):
        out["paired"][f"esm2_minus_{other}"] = paired_difference(
            predictors["esm2_damage"], predictors[other], y, bootstrap, seed
        )
    window_scores = {}
    for tag in ("damage_n", "damage_c"):
        if joined[tag].null_count() == 0:
            window_scores[tag] = auroc(joined[tag].to_list(), y)
    out["window_auroc"] = window_scores
    out["alleles"] = joined.select(
        "change", "label", "y", "damage", "damage_n", "damage_c", "ddg", "esm1b_llr"
    ).to_dicts()
    out["allele_percentile"] = {
        c: percentile_rank(table["damage"].to_list(), d)
        for c, d in zip(joined["change"], joined["damage"], strict=True)
    }
    return out
