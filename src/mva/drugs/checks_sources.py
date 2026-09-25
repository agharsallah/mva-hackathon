"""Read the annotation and screen files the checks need, keyed on the join key.

* :func:`load_moa_index` - the Drug Repurposing Hub MOA and target annotation, as PRISM ships
  it (``*_Compound_List.csv``: ``Drug.Name``, ``MOA``, ``repurposing_target``;
  ``*_treatment_info.csv``: ``name``, ``moa``, ``target``). The first file listed wins for
  a drug; later files only fill drugs it lacks. PRISM writes some names with hyphens for
  spaces (``VALPROIC-ACID``), so each name is indexed both as written and with hyphens read
  as spaces - a lookup convenience for K1 only, never the convergence join key.
* :func:`load_sweep` - per-drug screen contrasts for K3, from any TSV whose column names are
  passed in (the screen-wide sweep's schema is its own generator's to fix).
"""

from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .checks import Measurement
from .names import base_name

__all__ = [
    "Annotation",
    "SweepColumns",
    "annotation_for",
    "load_moa_index",
    "load_sweep",
    "lookup_keys",
]


@dataclass(frozen=True)
class Annotation:
    moa: str
    targets: tuple[str, ...]
    source: str


def lookup_keys(name: str) -> list[str]:
    """The join key, and the join key with hyphens read as spaces when that differs."""
    keys = [base_name(name)]
    spaced = base_name(name.replace("-", " "))
    if spaced not in keys:
        keys.append(spaced)
    return keys


_COLUMNS = (("Drug.Name", "MOA", "repurposing_target"), ("name", "moa", "target"))


def load_moa_index(paths: Sequence[Path]) -> dict[str, Annotation]:
    """``{join key: Annotation}`` from one or more Hub annotation CSVs, first file first."""
    out: dict[str, Annotation] = {}
    for path in paths:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = reader.fieldnames or []
            name_col, moa_col, target_col = next(c for c in _COLUMNS if c[0] in fields)
            local: dict[str, Annotation] = {}
            for row in reader:
                name = (row.get(name_col) or "").strip()
                if not name or name == "NA":
                    continue
                moa = (row.get(moa_col) or "").strip()
                moa = "" if moa == "NA" else moa
                targets = tuple(
                    t.strip()
                    for t in (row.get(target_col) or "").split(",")
                    if t.strip() and t.strip() != "NA"
                )
                for key in lookup_keys(name):
                    held = local.get(key)
                    if held is None or (not held.moa and moa):
                        local[key] = Annotation(moa, targets, path.name)
        for key, value in local.items():
            if key not in out or (not out[key].moa and value.moa):
                out[key] = value
    return out


@dataclass(frozen=True)
class SweepColumns:
    """Where a sweep TSV keeps each field. ``p_opposite`` may be absent; then ``1 - p``."""

    drug: str = "drug"
    contrast: str = "contrast"
    delta: str = "cliffs_delta"
    p: str = "p_raw"
    p_opposite: str | None = None
    #: Keep only rows whose ``only_column`` equals ``only_value`` (e.g. one representative
    #: copy per compound); ``None`` keeps every row.
    only_column: str | None = None
    only_value: str = "true"


def load_sweep(path: Path, cols: SweepColumns) -> dict[str, list[Measurement]]:
    """``{join key: [Measurement]}``; ``1 - p`` stands in for the opposite one-sided p when
    the file has no such column (exact for a continuous statistic, conservative with ties)."""
    out: dict[str, list[Measurement]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if cols.only_column and row.get(cols.only_column, "").lower() != cols.only_value:
                continue
            try:
                delta = float(row[cols.delta])
                p = float(row[cols.p])
            except (TypeError, ValueError):
                continue  # an untestable row (too few lines) carries no number: not measured
            raw_opp = row.get(cols.p_opposite) if cols.p_opposite else None
            p_opp = float(raw_opp) if raw_opp not in (None, "") else 1.0 - p
            note = "p_opposite = 1 - p" if cols.p_opposite is None else ""
            measurement = Measurement(row[cols.contrast], delta, p_opp, note)
            for key in lookup_keys(row[cols.drug]):
                out.setdefault(key, []).append(measurement)
    return out


def annotation_for(
    index: Mapping[str, Annotation], drug: str, label: str = ""
) -> Annotation | None:
    """The annotation for a join key, trying the label's spellings when the key misses."""
    for key in [drug, *lookup_keys(label)] if label else [drug]:
        if key in index:
            return index[key]
    return None
