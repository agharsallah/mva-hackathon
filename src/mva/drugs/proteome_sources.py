"""Readers for public drug-perturbation and baseline proteomics tables.

Each reader turns one published supplementary file into a :class:`~.proteome.ProteomeMatrix`
(genes x perturbations, log2 fold change vs vehicle) or a plain mapping. The file layouts
were read by eye on 2026-09-25 and are stated per reader; a layout change raises rather than
silently misreading a column.

* :func:`read_wide_log2fc` - a CSV, one row per protein, one column per perturbation, values
  already log2 fold change (Mitchell et al. 2023, *Nat Biotechnol* 41:845, Supplementary
  Data 3: HCT116, 875 compounds, 24 h, log2 FC vs DMSO median-normalised per plex).
* :func:`read_ratio_workbook` - an xlsx whose values are fold changes (ratios, not logs)
  with replicate columns ``<drug>_<n>`` (Saei et al. 2019, *Nat Commun* 10:5715,
  Supplementary Data 4-6: ProTargetMiner deep sets, 9 drugs x 3 replicates per cell line).
* :func:`read_ccle_protein` - the CCLE normalised protein table (Nusinow et al. 2020,
  *Cell* 180:387): relative abundance per cell line, used for a baseline correlation only.
* :func:`read_half_lives` - Mathieson et al. 2018 (*Nat Commun* 9:689) protein half-lives
  (hours) per cell type and replicate.

A protein listed under several rows (isoforms, protein groups naming several genes) is
kept once, as the row with the most quantified values (ties: the first row). That choice is
stated here because it decides which isoform of a gene a result speaks for.
"""

from __future__ import annotations

import csv
import gzip
import math
import re
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from .proteome import ProteomeMatrix

__all__ = [
    "collapse",
    "compound_of",
    "drug_means",
    "read_ccle_protein",
    "read_half_lives",
    "read_ratio_workbook",
    "read_wide_log2fc",
]

_MISSING = {"", "NA", "NaN", "nan", "#N/A", "None", "Inf", "-Inf"}


def _num(value: Any) -> float:
    if value is None:
        return math.nan
    if isinstance(value, int | float):
        return float(value)
    text = str(value).strip()
    if text in _MISSING:
        return math.nan
    try:
        return float(text)
    except ValueError:
        return math.nan


def collapse(rows: Iterable[tuple[str, list[float]]]) -> tuple[list[str], np.ndarray]:
    """One row per gene symbol: the row with the most finite values wins (first on ties)."""
    best: dict[str, list[float]] = {}
    order: list[str] = []
    for gene, values in rows:
        if not gene:
            continue
        if gene not in best:
            order.append(gene)
            best[gene] = values
            continue
        if sum(map(math.isfinite, values)) > sum(map(math.isfinite, best[gene])):
            best[gene] = values
    return order, np.array([best[g] for g in order], dtype=float)


def compound_of(label: str) -> str:
    """``"Sildenafil_PDE5A"`` → ``"Sildenafil"``: Mitchell labels are ``<compound>_<target>``."""
    head, sep, _ = label.rpartition("_")
    return head if sep else label


def read_wide_log2fc(
    path: Path,
    *,
    gene_column: str = "Gene Name",
    skip: Sequence[str] = ("UniprotID",),
    encoding: str = "cp1252",
) -> ProteomeMatrix:
    """Read a proteins x perturbations CSV of log2 fold changes.

    The Mitchell file is Windows-1252 (it holds non-breaking spaces in compound names);
    labels are returned with those folded to plain spaces.
    """
    with path.open(newline="", encoding=encoding) as handle:
        reader = csv.reader(handle)
        header = [h.replace("\xa0", " ").strip() for h in next(reader)]
        if gene_column not in header:
            raise ValueError(f"{path}: no {gene_column!r} column")
        gene_at = header.index(gene_column)
        keep = [i for i, h in enumerate(header) if i != gene_at and h not in skip]
        rows = ((line[gene_at].strip(), [_num(line[i]) for i in keep]) for line in reader)
        genes, values = collapse(rows)
    return ProteomeMatrix(tuple(genes), tuple(header[i] for i in keep), values, path.as_posix())


def _sheet_rows(path: Path) -> Iterator[tuple[Any, ...]]:
    import openpyxl  # optional at import time: only the proteome route reads xlsx

    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        yield from book.worksheets[0].iter_rows(values_only=True)
    finally:
        book.close()


def _genes_of(field: Any) -> list[str]:
    return [g.strip() for g in str(field or "").split(";") if g.strip() and g.strip() != "None"]


def read_ratio_workbook(
    path: Path, *, header_row: int = 2, gene_column: str = "Gene names", first_value: int = 5
) -> ProteomeMatrix:
    """Read a ProTargetMiner-style xlsx of fold-change ratios; values become log2.

    A protein group naming several genes (``HSPA1B;HSPA1A``) is indexed under each of them
    unless that gene also has a row of its own; :func:`collapse` then keeps one row per gene.
    """
    rows = list(_sheet_rows(path))
    header = [str(h) if h is not None else "" for h in rows[header_row]]
    if gene_column not in header:
        raise ValueError(f"{path}: no {gene_column!r} column in row {header_row}")
    gene_at = header.index(gene_column)
    labels = header[first_value:]
    single: set[str] = set()
    parsed: list[tuple[list[str], list[float]]] = []
    for row in rows[header_row + 1 :]:
        genes = _genes_of(row[gene_at])
        with np.errstate(divide="ignore", invalid="ignore"):
            values = [
                math.log2(v) if math.isfinite(v) and v > 0 else math.nan
                for v in (_num(x) for x in row[first_value : first_value + len(labels)])
            ]
        if len(genes) == 1:
            single.add(genes[0])
        parsed.append((genes, values))
    exploded = (
        (gene, values)
        for genes, values in parsed
        for gene in genes
        if len(genes) == 1 or gene not in single
    )
    names, matrix = collapse(exploded)
    return ProteomeMatrix(tuple(names), tuple(labels), matrix, path.as_posix())


def drug_means(matrix: ProteomeMatrix, *, pattern: str = r"_(\d+)$") -> ProteomeMatrix:
    """Average replicate columns ``<drug>_<n>`` into one column per drug (NaN-aware)."""
    groups: dict[str, list[int]] = {}
    for j, label in enumerate(matrix.perturbations):
        groups.setdefault(re.sub(pattern, "", label), []).append(j)
    drugs = tuple(groups)
    with np.errstate(all="ignore"):
        values = np.column_stack([np.nanmean(matrix.values[:, groups[d]], axis=1) for d in drugs])
    return ProteomeMatrix(matrix.genes, drugs, values, matrix.source)


def read_ccle_protein(path: Path, *, marker: str = "_TenPx") -> ProteomeMatrix:
    """CCLE normalised protein table: value columns are ``<line>_<tissue>_TenPxNN``."""
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        gene_at = header.index("Gene_Symbol")
        keep = [i for i, h in enumerate(header) if marker in h and not h.endswith("_Peptides")]
        rows = ((line[gene_at].strip(), [_num(line[i]) for i in keep]) for line in reader)
        genes, values = collapse(rows)
    return ProteomeMatrix(tuple(genes), tuple(header[i] for i in keep), values, path.as_posix())


def read_half_lives(path: Path, *, sheet_row: int = 0) -> dict[str, dict[str, float]]:
    """``gene → {"<cell type> replicate <n>": half-life hours}`` from Mathieson 2018.

    Only the ``... half life`` columns are read; ``Inf`` and ``#N/A`` are dropped.
    """
    rows = _sheet_rows(path)
    header = [str(h or "") for h in next(rows)]
    cols = [
        (i, h.replace(" half_life", "").strip()) for i, h in enumerate(header) if "half_life" in h
    ]
    out: dict[str, dict[str, float]] = {}
    for row in rows:
        gene = str(row[0] or "").strip()
        if not gene:
            continue
        values = {name: _num(row[i]) for i, name in cols}
        kept = {k: v for k, v in values.items() if math.isfinite(v)}
        if kept:
            out.setdefault(gene, kept)
    return out
