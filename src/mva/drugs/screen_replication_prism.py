"""Readers that turn the public DepMap / PRISM downloads into the shapes the contrast wants.

Everything PRISM- or DepMap-specific lives here so :mod:`mva.drugs.screen_replication`
stays a generic rank-contrast engine. Swapping in GDSC, CTRP or a lab's own plate reader
means writing another module of this shape, not touching the statistics.

The four public files this reads, all CC BY 4.0, all from the figshare mirrors recorded in
``docs/iteration4/step-9/research/data-sources.md`` §1 (the depmap.org API itself now
answers scripts with a Cloudflare challenge):

===================================== ==================================================
file                                  what it carries
===================================== ==================================================
``Extended_Primary_Data_Matrix.csv``  PRISM Repurposing 24Q2 primary: **log fold change**
                                      of barcode abundance after 5 days at 2.5 uM, rows =
                                      compounds (``BRD:BRD-...``), columns = DepMap model
                                      ids. More negative = the drug killed that line more.
``Extended_Primary_Compound_List.csv``compound annotation: name, MOA, targets, screen
``Model.csv`` (24Q4)                  one row per cell line: Oncotree lineage/code, age
``OmicsSignatures.csv`` (24Q4)        per-line ``Aneuploidy`` (arm-level events, 0-39),
                                      ``CIN``, ``Ploidy``, ``WGD``, ``LoHFraction``
``secondary-screen-dose-response``    PRISM 20Q2 secondary: **AUC** of a fitted 8-point
                                      dose-response curve — a different release and a
                                      different metric, for the sensitivity check
===================================== ==================================================

Both metrics are *lower = more sensitive*, so both are passed with
``lower_is_sensitive=True``.

No patient data is read anywhere in this module, and no genomic position can appear in its
outputs: the identifiers are drug names, BRD ids, DepMap model ids and gene symbols.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import polars as pl

from mva.drugs.screen_replication import Group

__all__ = [
    "RMS_ONCOTREE_CODES",
    "CompoundIndex",
    "ResponseMatrix",
    "core_broad_id",
    "lineage_group",
    "load_compound_list",
    "load_model_table",
    "load_primary_matrix",
    "load_secondary_auc",
    "load_secondary_compound_list",
    "load_signatures",
    "normalise_name",
]

#: Oncotree codes DepMap uses for rhabdomyosarcoma, the child's tumour context. ``RMS`` is
#: the unspecified parent, ``ERMS``/``ARMS``/``PLRMS``/``SCRMS``/``SRMS`` its subtypes.
RMS_ONCOTREE_CODES = ("RMS", "ERMS", "ARMS", "PLRMS", "SCRMS", "SRMS")

_PUNCT = re.compile(r"[^A-Z0-9]+")
_BROAD_CORE = re.compile(r"(BRD-[A-Z]\d+)")


def core_broad_id(broad_id: str) -> str:
    """``BRD:BRD-K09416995-001-39-9`` -> ``BRD-K09416995``.

    The trailing segments are the compound *batch*, and a drug carries different batches in
    different PRISM releases. Cross-release joins therefore go through this core id; within
    one release the full id stays the key.
    """
    match = _BROAD_CORE.search(broad_id.upper())
    return match.group(1) if match else broad_id.upper()


def normalise_name(name: str) -> str:
    """``"Valproic acid"``, ``"VALPROIC-ACID"`` and ``"valproic_acid"`` all become one key.

    PRISM writes ``VALPROIC-ACID`` where the repository's tables write ``VALPROIC ACID``,
    so a raw string join silently drops candidates. Matching is done on this key **and**
    cross-checked against the stable ``broad_id``, never on the raw name alone.
    """
    return _PUNCT.sub("", name.strip().upper())


@dataclass(frozen=True)
class CompoundIndex:
    """The PRISM compound annotation, indexed by normalised name and by BRD id."""

    table: pl.DataFrame

    def by_name(self, name: str) -> pl.DataFrame:
        """Every PRISM row whose name or synonym normalises to ``name``."""
        key = normalise_name(name)
        return self.table.filter(pl.col("name_key") == key)

    def by_broad_id(self, broad_id: str) -> pl.DataFrame:
        """Every row matching ``broad_id`` exactly or on its release-independent core."""
        core = core_broad_id(broad_id)
        return self.table.filter((pl.col("broad_id") == broad_id) | (pl.col("broad_core") == core))

    def by_moa(self, moa: str) -> pl.DataFrame:
        """Every row whose comma-separated ``MOA`` field contains ``moa`` (case-blind)."""
        return self.table.filter(
            pl.col("moa").fill_null("").str.to_uppercase().str.contains(moa.upper(), literal=True)
        )

    def names(self) -> dict[str, str]:
        """``{item_id: display name}`` for every compound in the annotation."""
        return dict(zip(self.table["item_id"], self.table["name"], strict=True))

    def moa(self) -> dict[str, str]:
        return dict(zip(self.table["item_id"], self.table["moa"].fill_null(""), strict=True))


def load_compound_list(path: Path) -> CompoundIndex:
    """Read ``Extended_Primary_Compound_List.csv`` into a :class:`CompoundIndex`."""
    raw = pl.read_csv(path, infer_schema_length=20000)
    table = raw.select(
        item_id=pl.col("IDs"),
        broad_id=pl.col("IDs").str.replace("^BRD:", ""),
        name=pl.col("Drug.Name"),
        synonyms=pl.col("Synonyms").fill_null(""),
        screen=pl.col("screen"),
        dose=pl.col("dose"),
        moa=pl.col("MOA"),
        target=pl.col("repurposing_target"),
    )
    return CompoundIndex(_key(table))


def load_secondary_compound_list(path: Path) -> CompoundIndex:
    """The 20Q2 secondary ``treatment-info`` file, in the same shape as the 24Q2 list.

    It is the one release that carries a ``phase`` column, which is how "approved" is
    decided for the negative-control universe (``phase == "Launched"``).
    """
    raw = pl.read_csv(path, infer_schema_length=20000)
    table = (
        raw.select(
            item_id=pl.col("broad_id"),
            broad_id=pl.col("broad_id"),
            name=pl.col("name"),
            synonyms=pl.lit(""),
            screen=pl.lit("20Q2-secondary"),
            dose=pl.col("dose").cast(pl.Float64, strict=False),
            moa=pl.col("moa"),
            target=pl.col("target"),
            phase=pl.col("phase"),
        )
        .filter(pl.col("name").is_not_null() & (pl.col("name") != "NA"))
        .unique(subset=["broad_id"], keep="first")
    )
    return CompoundIndex(_key(table))


def _key(table: pl.DataFrame) -> pl.DataFrame:
    """Add the two join keys every candidate match uses: normalised name and core BRD id."""
    return table.with_columns(
        name_key=pl.col("name").map_elements(normalise_name, return_dtype=pl.String),
        broad_core=pl.col("broad_id").map_elements(core_broad_id, return_dtype=pl.String),
    )


class _Row(Mapping[str, float]):
    """One compound's responses as a read-only mapping, materialised on demand.

    The full 24Q2 matrix is 6,790 x 919; holding every row as a Python dict at once costs
    hundreds of megabytes, so the sweep over all compounds walks rows lazily instead.
    """

    __slots__ = ("_lines", "_values")

    def __init__(self, lines: Sequence[str], values: np.ndarray) -> None:
        self._lines = lines
        self._values = values

    def __getitem__(self, key: str) -> float:
        return float(self._values[self._lines.index(key)])

    def __iter__(self) -> Iterator[str]:
        return iter(self._lines)

    def __len__(self) -> int:
        return len(self._lines)

    def items(self) -> Iterator[tuple[str, float]]:  # type: ignore[override]
        return zip(self._lines, (float(v) for v in self._values), strict=True)


@dataclass(frozen=True)
class ResponseMatrix(Mapping[str, Mapping[str, float]]):
    """A screen as ``{compound id: {line id: response}}``, backed by one dense array."""

    item_ids: list[str]
    lines: list[str]
    matrix: np.ndarray
    metric: str
    release: str

    def __getitem__(self, key: str) -> Mapping[str, float]:
        return _Row(self.lines, self.matrix[self.item_ids.index(key)])

    def __iter__(self) -> Iterator[str]:
        return iter(self.item_ids)

    def __len__(self) -> int:
        return len(self.item_ids)

    def subset(self, item_ids: Sequence[str]) -> ResponseMatrix:
        """The same matrix restricted to ``item_ids``, in the order given."""
        keep = [self.item_ids.index(i) for i in item_ids if i in set(self.item_ids)]
        return ResponseMatrix(
            item_ids=[self.item_ids[i] for i in keep],
            lines=self.lines,
            matrix=self.matrix[keep, :],
            metric=self.metric,
            release=self.release,
        )

    def rank_normalised(self) -> ResponseMatrix:
        """Replace each line's responses by their percentile **within that line**.

        A line that is simply easy to kill scores low against every compound, which a
        between-line comparison would read as drug selectivity. Ranking inside each column
        removes that line-level offset: after it, a contrast can only see *which* drugs a
        line is unusually sensitive to, not how sensitive it is overall.
        """
        ranked = np.full(self.matrix.shape, np.nan, dtype=float)
        for col in range(self.matrix.shape[1]):
            column = self.matrix[:, col]
            seen = np.isfinite(column)
            count = int(seen.sum())
            if count == 0:
                continue
            order = np.argsort(np.argsort(column[seen]))
            ranked[seen, col] = (order + 0.5) / count
        return ResponseMatrix(
            item_ids=list(self.item_ids),
            lines=list(self.lines),
            matrix=ranked,
            metric=f"within-line percentile of {self.metric}",
            release=self.release,
        )

    def line_medians(self) -> dict[str, float]:
        """Each line's median response over every compound — the generic-sensitivity proxy."""
        with np.errstate(invalid="ignore"):
            med = np.nanmedian(self.matrix, axis=0)
        return dict(zip(self.lines, (float(v) for v in med), strict=True))


def load_primary_matrix(path: Path, *, release: str = "PRISM Repurposing 24Q2") -> ResponseMatrix:
    """Read the extended primary matrix (rows = compounds, columns = DepMap model ids)."""
    frame = pl.read_csv(path, infer_schema_length=0)
    id_col = frame.columns[0]
    items = frame[id_col].to_list()
    lines = frame.columns[1:]
    values = (
        frame.drop(id_col)
        .with_columns(pl.all().cast(pl.Float64, strict=False))
        .to_numpy()
        .astype(float)
    )
    return ResponseMatrix(
        item_ids=items,
        lines=list(lines),
        matrix=values,
        metric="log fold change, 5 days at 2.5 uM (lower = more sensitive)",
        release=release,
    )


def load_secondary_auc(
    path: Path, *, release: str = "PRISM Repurposing 20Q2 secondary"
) -> ResponseMatrix:
    """Collapse the 20Q2 secondary dose-response parameters to one AUC per drug x line.

    A compound can appear on several ``screen_id`` plates; the median over them is taken,
    and only rows the release marks ``passed_str_profiling`` are used (the lines whose
    identity was confirmed by STR profiling).
    """
    raw = pl.read_csv(
        path,
        infer_schema_length=0,
        columns=["broad_id", "depmap_id", "auc", "passed_str_profiling", "name"],
    )
    clean = (
        raw.filter(pl.col("passed_str_profiling").str.to_uppercase() == "TRUE")
        .with_columns(auc=pl.col("auc").cast(pl.Float64, strict=False))
        .drop_nulls(["auc", "depmap_id", "broad_id"])
        .group_by("broad_id", "depmap_id")
        .agg(auc=pl.col("auc").median())
    )
    wide = clean.pivot(on="depmap_id", index="broad_id", values="auc")
    items = wide["broad_id"].to_list()
    lines = wide.columns[1:]
    values = wide.drop("broad_id").to_numpy().astype(float)
    return ResponseMatrix(
        item_ids=items,
        lines=list(lines),
        matrix=values,
        metric="dose-response AUC, 8 doses (lower = more sensitive)",
        release=release,
    )


def load_model_table(path: Path) -> pl.DataFrame:
    """``Model.csv`` with the columns the contrasts and the confounder checks need."""
    return pl.read_csv(path, infer_schema_length=20000).select(
        "ModelID",
        "StrippedCellLineName",
        "OncotreeCode",
        "OncotreeLineage",
        "OncotreePrimaryDisease",
        "Age",
        "AgeCategory",
        "GrowthPattern",
    )


def load_signatures(path: Path) -> pl.DataFrame:
    """``OmicsSignatures.csv``; the unnamed first column is the model id."""
    frame = pl.read_csv(path, infer_schema_length=20000)
    return frame.rename({frame.columns[0]: "ModelID"})


def lineage_group(
    models: pl.DataFrame,
    *,
    codes: Sequence[str],
    screened: Sequence[str],
    name: str,
    in_label: str,
    out_label: str,
    restrict_lineage: str | None = None,
) -> Group:
    """Lines whose Oncotree code is in ``codes`` versus the rest of the screen.

    ``restrict_lineage`` narrows the comparison arm to one Oncotree lineage — the
    lineage-matched control that asks whether an apparent lineage effect is really a
    tissue-of-origin effect shared by every sarcoma in the screen.
    """
    present = models.filter(pl.col("ModelID").is_in(list(screened)))
    inside = set(present.filter(pl.col("OncotreeCode").is_in(list(codes)))["ModelID"].to_list())
    rest = present.filter(~pl.col("OncotreeCode").is_in(list(codes)))
    if restrict_lineage is not None:
        rest = rest.filter(pl.col("OncotreeLineage") == restrict_lineage)
    outside = set(rest["ModelID"].to_list())
    scope = (
        f"every other screened line ({len(outside)})"
        if restrict_lineage is None
        else f"other screened {restrict_lineage} lines ({len(outside)})"
    )
    return Group(
        name=name,
        inside=frozenset(inside),
        outside=frozenset(outside),
        in_label=in_label,
        out_label=out_label,
        definition=(
            f"DepMap 24Q4 Model.csv OncotreeCode in {tuple(codes)} "
            f"({len(inside)} screened lines) versus {scope}"
        ),
    )
