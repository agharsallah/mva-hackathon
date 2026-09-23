"""The adapter lane — one module per model, one factory, one shared vocabulary.

An **adapter** is the thin layer that makes one model look like every other model to the
workflow: give it :class:`~mva.zoo.types.AlleleRecord` rows, get
:class:`~mva.zoo.types.ScoreRow` rows back. It is the same idea as a database driver — the
caller writes one piece of code and swaps the driver underneath.

Three lanes ship in the MVP, one file each:

===========================  =====  ==========================================================
module                       tier   what it reads
===========================  =====  ==========================================================
:mod:`.warehouse_column`     1      a score column already sitting in the warehouse
:mod:`.duckdb_lookup`        1      a downloaded score table converted to Parquet once
:mod:`.vep_rest`             1      Ensembl VEP REST with a plugin switched on (remote)
===========================  =====  ==========================================================

*Tier* is where the model runs, not how good it is: **tier 1** = look the answer up (no
model executes), **tier 2** = a local CPU process, **tier 3** = a remote GPU job. Tier 3 is
still unbuilt.

This module holds what every lane shares: the factory (:func:`build`), the coordinate-free
key expressed as SQL (:func:`allele_id_sql`, which must agree with
:func:`~mva.zoo.types.allele_id` exactly), the record loader, and the coverage helpers.
"""

from __future__ import annotations

import importlib
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

from ..types import Adapter, AlleleRecord, Coverage

__all__ = [
    "ADAPTER_MODULES",
    "DEFAULT_RECORDS",
    "UnknownAdapterError",
    "allele_id_sql",
    "build",
    "coverage_from_ids",
    "coverage_of",
    "records_from_parquet",
]

#: Where step 1 leaves the record set. The coordinate columns live *only* in this file,
#: under ``build/``; nothing that leaves the machine carries them.
DEFAULT_RECORDS = Path("build/it4/records.parquet")

#: ``card.adapter`` → the module that knows how to build it. A new lane is a new entry and
#: a new file, never an edit to an existing lane.
ADAPTER_MODULES: dict[str, str] = {
    "warehouse_column": "mva.zoo.adapters.warehouse_column",
    "duckdb_lookup": "mva.zoo.adapters.duckdb_lookup",
    "protein_table": "mva.zoo.adapters.protein_table",
    "coordinate_table": "mva.zoo.adapters.coordinate_table",
    "local_process": "mva.zoo.adapters.local_process",
    "vep_rest": "mva.zoo.adapters.vep_rest",
    "modal": "mva.zoo.adapters.modal_gpu",
}


class UnknownAdapterError(ValueError):
    """``card.adapter`` names a lane that has no module. Listing the known ones is the fix."""


class _Card(Protocol):
    """The slice of a registry model card an adapter needs. The registry owns the rest."""

    key: str
    version: str
    adapter: str
    params: dict[str, Any]
    licence: str


class _Lane(Protocol):
    """What every adapter module exposes: one builder with this exact signature."""

    def build(
        self, card: Any, *, connection: Any = None, records_parquet: Path = DEFAULT_RECORDS
    ) -> Adapter: ...


def build(
    card: Any,
    *,
    connection: Any = None,
    records_parquet: Path = DEFAULT_RECORDS,
) -> Adapter:
    """Return the adapter one model card describes.

    Dispatch is by name, not by subclassing: ``card.adapter`` is a key of
    :data:`ADAPTER_MODULES`, and the module it names supplies its own ``build``. The full
    dotted path is accepted too, so a card may spell the lane either way.
    """
    name = str(getattr(card, "adapter", "") or "")
    target = ADAPTER_MODULES.get(name) or (name if name in ADAPTER_MODULES.values() else "")
    if not target:
        known = ", ".join(sorted(ADAPTER_MODULES))
        raise UnknownAdapterError(f"no adapter module for {name!r}; known lanes: {known}")
    module = importlib.import_module(target)
    return module.build(card, connection=connection, records_parquet=records_parquet)


def coverage_of(adapter: Adapter, records: Sequence[AlleleRecord]) -> Coverage:
    """How much of ``records`` this adapter can score — the lane's own answer.

    A one-line indirection on purpose: callers (the CLI, the workflow) ask *this* function
    so they never need to know which lane they hold.
    """
    return adapter.coverage(records)


def coverage_from_ids(
    model: str, records: Sequence[AlleleRecord], scored: set[str] | frozenset[str]
) -> Coverage:
    """Build a :class:`~mva.zoo.types.Coverage` from the set of ids a lane can answer.

    Every lane computes coverage the same way once it knows which alleles it has a row
    for, so the counting — overall and per consequence class — lives here rather than
    three times over. A record with no consequence is counted under ``unknown``: dropping
    it would make the per-class totals disagree with the overall one.
    """
    by_consequence: dict[str, tuple[int, int]] = {}
    for record in records:
        label = record.consequence or "unknown"
        hit, total = by_consequence.get(label, (0, 0))
        by_consequence[label] = (hit + (1 if record.allele_id in scored else 0), total + 1)
    return Coverage(
        model=model,
        scored=sum(1 for record in records if record.allele_id in scored),
        total=len(records),
        by_consequence=dict(sorted(by_consequence.items())),
    )


def _strip_chr(expression: str) -> str:
    """SQL that removes one leading ``chr``/``CHR`` from a contig name, and nothing else."""
    return (
        f"CASE WHEN starts_with({expression}, 'chr') THEN substr({expression}, 4) "
        f"WHEN starts_with({expression}, 'CHR') THEN substr({expression}, 4) "
        f"ELSE {expression} END"
    )


def allele_id_sql(
    chrom: str = "chrom", pos: str = "pos", ref: str = "ref", alt: str = "alt"
) -> str:
    """The SQL expression that computes :func:`~mva.zoo.types.allele_id` in the database.

    Why it exists: the warehouse tables are keyed by coordinate, and joining 40k alleles by
    pulling the coordinates into Python would mean shipping them out of ``build/``.
    Computing the id inside DuckDB keeps the coordinate on the server side of the join.

    The two implementations must agree exactly — ``tests/test_zoo_adapters.py`` asserts it
    over every fixture row, because a silent disagreement would show up as a lane with 0 %
    coverage and no error.
    """
    name = f"CAST({chrom} AS VARCHAR)"
    contig = f"upper({_strip_chr(_strip_chr(name))})"
    text = (
        f"concat({contig}, ':', CAST({pos} AS BIGINT), "
        f"':', upper(CAST({ref} AS VARCHAR)), ':', upper(CAST({alt} AS VARCHAR)))"
    )
    return f"substr(sha256({text}), 1, 16)"


#: The record columns :func:`records_from_parquet` reads. The coordinate columns are read
#: only by :mod:`.vep_rest`, which needs them to ask a remote server about a position.
RECORD_FIELDS: tuple[str, ...] = (
    "allele_id",
    "gene",
    "transcript",
    "consequence",
    "hgvs_c",
    "hgvs_p",
    "uniprot",
    "is_read_only",
    "af_gnomad",
    "clin_sig",
)


def records_from_parquet(
    path: Path | str = DEFAULT_RECORDS,
    *,
    limit: int | None = None,
    allele_ids: Sequence[str] | None = None,
    connection: Any = None,
) -> list[AlleleRecord]:
    """Load step 1's record set as :class:`~mva.zoo.types.AlleleRecord` objects.

    The sequence-window and coordinate columns are deliberately *not* read: an adapter that
    needs them says so and reads them itself. Missing columns are tolerated — the record
    shape is nullable by design, and a fixture file that carries only half of it is still a
    valid input.
    """
    import duckdb

    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"no record set at {source}; run `mva-zoo records` first")
    con = connection or duckdb.connect()
    present = {
        str(row[0])
        for row in con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(source)]).fetchall()
    }
    columns = [name if name in present else f"NULL AS {name}" for name in RECORD_FIELDS]
    sql = f"SELECT {', '.join(columns)} FROM read_parquet(?)"
    params: list[Any] = [str(source)]
    if allele_ids is not None:
        marks = ", ".join("?" for _ in allele_ids)
        sql += f" WHERE allele_id IN ({marks})" if allele_ids else " WHERE false"
        params.extend(allele_ids)
    if limit is not None:
        sql += f" LIMIT {int(limit)}"
    rows = con.execute(sql, params).fetchall()
    return [_record(row) for row in rows]


def _record(row: Sequence[Any]) -> AlleleRecord:
    return AlleleRecord(
        allele_id=str(row[0]),
        gene=_text(row[1]),
        transcript=_text(row[2]),
        consequence=_text(row[3]),
        hgvs_c=_text(row[4]),
        hgvs_p=_text(row[5]),
        uniprot=_text(row[6]),
        is_read_only=bool(row[7]),
        af_gnomad=None if row[8] is None else float(row[8]),
        clin_sig=_text(row[9]),
    )


def _text(value: Any) -> str | None:
    """Empty strings and SQL NULL both mean "not known" in these tables."""
    if value is None:
        return None
    text = str(value)
    return text or None
