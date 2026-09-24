"""A variant atlas: every single-residue substitution of one protein, with its predicted effect.

One row per ``(position, alt)`` — 19 × length rows — joining a structure-based stability
prediction (ThermoMPNN ΔΔG, kcal/mol, positive = destabilising), an optional sequence-only
score (ESM1b log-likelihood ratio), and the residue's context (pLDDT, RSA, annotated
features). Gene-agnostic: a UniProt accession and the per-swap ΔΔG table are the only inputs.

Then two uses, both pure functions over the atlas:

* :func:`evaluate` — do published alleles with a known class (e.g. abundance-lowering vs
  stable) separate on the atlas's scores? AUROC with a bootstrap interval, LOO ridge logistic.
* :func:`place` — where does one substitution fall: its ΔΔG percentile among all
  substitutions, the fitted model's probability, the features covering its residue.

Sources and helpers: :mod:`mva.drugs.variant_atlas_sources` (fetch, parse, RSA),
:mod:`mva.drugs.variant_atlas_model` (the statistics).
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl

from .variant_atlas_model import (
    auroc,
    bootstrap_auroc,
    fit_logistic,
    loo_probabilities,
    percentile_rank,
    roc_points,
)
from .variant_atlas_sources import Feature, Residue

__all__ = [
    "ATLAS_COLUMNS",
    "MODELS",
    "Change",
    "build_atlas",
    "evaluate",
    "labelled_rows",
    "parse_change",
    "place",
    "read_ddg_tsv",
]

ATLAS_COLUMNS = (
    "uniprot", "position", "wt", "alt", "change", "ddg", "ddg_percentile", "esm1b_llr",
    "plddt", "rsa", "region", "features",
)  # fmt: skip

#: The two pre-set models of E1: ΔΔG alone, then ΔΔG with the residue's context.
MODELS: dict[str, tuple[str, ...]] = {
    "ddg": ("ddg",),
    "ddg+rsa+plddt": ("ddg", "rsa", "plddt"),
}
#: Priority when one residue sits under several features: the first match names its region.
REGION_ORDER = ("UniProt Domain", "UniProt Region", "UniProt Motif", "literature", "InterPro")

_THREE = {
    "Ala": "A", "Arg": "R", "Asn": "N", "Asp": "D", "Cys": "C", "Gln": "Q", "Glu": "E",
    "Gly": "G", "His": "H", "Ile": "I", "Leu": "L", "Lys": "K", "Met": "M", "Phe": "F",
    "Pro": "P", "Ser": "S", "Thr": "T", "Trp": "W", "Tyr": "Y", "Val": "V",
}  # fmt: skip


@dataclass(frozen=True)
class Change:
    wt: str
    position: int
    alt: str


def parse_change(text: str) -> Change | None:
    """``R727C``, ``p.R727C``, ``p.Arg727Cys`` or ``ENSP…:p.Arg727Cys`` → Change."""
    body = text.rsplit(":", maxsplit=1)[-1].removeprefix("p.")
    short = re.fullmatch(r"([A-Z])(\d+)([A-Z])", body)
    if short:
        return Change(short[1], int(short[2]), short[3])
    long = re.fullmatch(r"([A-Z][a-z]{2})(\d+)([A-Z][a-z]{2})", body)
    if long and long[1] in _THREE and long[3] in _THREE:
        return Change(_THREE[long[1]], int(long[2]), _THREE[long[3]])
    return None


def read_ddg_tsv(path: Path) -> list[tuple[int, str, str, float]]:
    """ThermoMPNN lane output (``position wt alt ddg``) → rows, self-swaps dropped."""
    with path.open() as handle:
        return [
            (int(r["position"]), r["wt"], r["alt"], float(r["ddg"]))
            for r in csv.DictReader(handle, delimiter="\t")
            if r["wt"] != r["alt"]
        ]


def _region(features: Sequence[Feature], position: int) -> tuple[str, str]:
    """``(primary region name, every covering feature joined by '; ')``."""
    covering = [f for f in features if f.covers(position)]
    names = "; ".join(dict.fromkeys(f.name for f in covering))
    for prefix in REGION_ORDER:
        for feature in covering:
            if feature.source.startswith(prefix):
                return feature.name, names
    return ("none annotated", names)


def build_atlas(
    accession: str,
    ddg: Iterable[tuple[int, str, str, float]],
    residues: Sequence[Residue],
    features: Sequence[Feature],
    esm1b: dict[tuple[int, str], float] | None = None,
) -> pl.DataFrame:
    """The atlas table. Raises if the ΔΔG table and the structure disagree on a residue."""
    by_pos = {r.position: r for r in residues}
    context = {p: _region(features, p) for p in by_pos}
    rows: list[dict[str, Any]] = []
    for position, wt, alt, value in ddg:
        residue = by_pos[position]
        if residue.aa != wt:
            raise ValueError(f"residue {position}: structure has {residue.aa}, ΔΔG table {wt}")
        region, names = context[position]
        rows.append(
            {
                "uniprot": accession,
                "position": position,
                "wt": wt,
                "alt": alt,
                "change": f"{wt}{position}{alt}",
                "ddg": value,
                "esm1b_llr": (esm1b or {}).get((position, alt)),
                "plddt": residue.plddt,
                "rsa": residue.rsa,
                "region": region,
                "features": names,
            }
        )
    frame = pl.DataFrame(rows, schema_overrides={"esm1b_llr": pl.Float64})
    frame = frame.with_columns(
        (100 * (pl.col("ddg").rank("average") - 0.5) / pl.len()).alias("ddg_percentile")
    )
    return frame.select(ATLAS_COLUMNS).sort(["position", "alt"])


def labelled_rows(
    atlas: pl.DataFrame, labels_tsv: Path, positive: str, negative: str, primary_only: bool
) -> pl.DataFrame:
    """Published alleles joined to the atlas; ``y`` = 1 for ``positive``, 0 for ``negative``.

    An allele whose reference residue disagrees with the atlas is a numbering error and
    raises rather than joining silently.
    """
    with labels_tsv.open() as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    keep = []
    for row in rows:
        if row["class"] not in (positive, negative):
            continue
        if primary_only and row["primary"] != "yes":
            continue
        change = parse_change(row["protein_change"])
        if change is None:
            raise ValueError(f"unparseable protein change {row['protein_change']!r}")
        keep.append(
            {"change": f"{change.wt}{change.position}{change.alt}", "label": row["class"],
             "pmid": row["pmid"], "y": int(row["class"] == positive)}
        )  # fmt: skip
    joined = pl.DataFrame(keep).join(atlas, on="change", how="left")
    missing = joined.filter(pl.col("ddg").is_null())["change"].to_list()
    if missing:
        raise ValueError(f"labelled alleles absent from the atlas (numbering?): {missing}")
    return joined


def evaluate(labelled: pl.DataFrame, bootstrap: int = 2000, seed: int = 0) -> dict[str, Any]:
    """Per pre-set model: LOO probabilities, AUROC and its interval; raw-score AUROCs too."""
    y = labelled["y"].to_list()
    out: dict[str, Any] = {
        "n_positive": int(sum(y)),
        "n_negative": len(y) - int(sum(y)),
        "raw": {},
        "models": {},
    }
    raw = {"ddg": labelled["ddg"].to_list()}
    if labelled["esm1b_llr"].null_count() == 0:
        raw["esm1b_llr_negated"] = [-v for v in labelled["esm1b_llr"].to_list()]
    for name, scores in raw.items():
        out["raw"][name] = {
            "auroc": auroc(scores, y),
            "ci95": bootstrap_auroc(scores, y, bootstrap, seed),
            "roc": roc_points(scores, y),
        }
    for name, features in MODELS.items():
        rows = labelled.select(features).rows()
        loo = loo_probabilities(rows, y, features)
        fit = fit_logistic(rows, y, features)
        out["models"][name] = {
            "features": list(features),
            "loo_probability": dict(zip(labelled["change"].to_list(), loo, strict=True)),
            "auroc_loo": auroc(loo, y),
            "ci95_loo": bootstrap_auroc(loo, y, bootstrap, seed),
            "roc_loo": roc_points(loo, y),
            "coef_standardised": fit.coef.tolist(),
            "mean": fit.mean.tolist(),
            "scale": fit.scale.tolist(),
        }
    return out


def place(atlas: pl.DataFrame, labelled: pl.DataFrame, change: Change) -> dict[str, Any]:
    """One substitution on the atlas: ΔΔG percentile, both models' calls, its region."""
    key = f"{change.wt}{change.position}{change.alt}"
    hit = atlas.filter(pl.col("change") == key)
    if hit.height != 1:
        raise ValueError(f"{key}: not a single atlas row (reference residue mismatch?)")
    row = hit.row(0, named=True)
    y = labelled["y"].to_list()
    calls = {}
    for name, features in MODELS.items():
        fit = fit_logistic(labelled.select(features).rows(), y, features)
        p = fit.probability([row[f] for f in features])
        calls[name] = {"probability": p, "call": "abundance-lowering" if p >= 0.5 else "stable"}
    return {
        "change": key,
        "ddg": row["ddg"],
        "ddg_percentile": percentile_rank(atlas["ddg"].to_list(), row["ddg"]),
        "esm1b_llr": row["esm1b_llr"],
        "plddt": row["plddt"],
        "rsa": row["rsa"],
        "region": row["region"],
        "features": row["features"],
        "in_labelled_set": key in set(labelled["change"].to_list()),
        "calls": calls,
    }
