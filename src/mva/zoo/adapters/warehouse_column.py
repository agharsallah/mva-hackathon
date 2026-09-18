"""Tier-1 lane: a score that is *already* a column of a warehouse table.

Two of the MVP models were annotated into the warehouse long before the zoo existed —
AlphaMissense as ``am_pathogenicity`` and SpliceAI as ``spliceai_ds_max`` in
``warehouse.it2_insilico_annotations``. Re-downloading their tables to score the same
alleles again would be a waste; this lane reads the column instead.

The one design rule here is **the join happens in the database**. Those tables are keyed by
coordinate (``chrom, pos, ref, alt``); the record set is keyed by ``allele_id``. Pulling
coordinates into Python to match them would carry patient positions out of the warehouse,
so the id is computed *in SQL* (:func:`~mva.zoo.adapters.allele_id_sql`) and only ids and
numbers cross back. Nothing this module returns contains a coordinate.

Parameters, from the model card's ``params``:

``table``
    the warehouse table to read (``it2_insilico_annotations``).
``column``
    the column holding the score (``am_pathogenicity``).
``aux``
    further columns to carry along as context (``["am_class"]``).
``score_transform``
    how to collapse several rows for the same allele — these tables carry one row per
    transcript. ``identity`` (the default) takes any one row; ``max`` takes the row with
    the largest score, which is the convention SpliceAI's own delta-max already uses.
``score_sign``
    ``1`` (the default) where the column is already "higher = more damaging", ``-1`` where
    it is the other way round. Every cached score points the same way.
``schema``
    which schema the table lives in; ``warehouse`` unless the card says otherwise.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..types import Adapter, AlleleRecord, Coverage, RemoteJob, ScoreRow, Tier
from . import DEFAULT_RECORDS, allele_id_sql, coverage_from_ids

__all__ = ["TRANSFORMS", "WarehouseColumnAdapter", "build"]

#: How a repeated allele is collapsed, and what that choice does to the ``aux`` columns.
TRANSFORMS: tuple[str, ...] = ("identity", "max")

#: Ids per statement. One temporary table per chunk, joined against the warehouse table.
CHUNK = 5_000

_WANTED = "zoo_wanted"


@dataclass
class WarehouseColumnAdapter:
    """A model whose scores are a column of a table the warehouse already holds."""

    name: str
    version: str
    connection: Any
    table: str
    column: str
    aux: tuple[str, ...] = ()
    score_transform: str = "identity"
    score_sign: int = 1
    schema: str = "warehouse"
    licence: str = ""
    digest: str = ""
    tier: Tier = 1
    catalogue_adjacent: bool = False
    venue: str = "laptop"
    _cache: dict[str, tuple[float | None, dict[str, Any]]] = field(default_factory=dict)
    _asked: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if self.score_transform not in TRANSFORMS:
            raise ValueError(
                f"{self.name}: score_transform must be one of {TRANSFORMS}; "
                f"got {self.score_transform!r}"
            )

    @property
    def source_ref(self) -> str:
        """What the lineage edge names as the source: the column, fully qualified."""
        return f"{self.schema}.{self.table}.{self.column}"

    # ── the Adapter protocol ─────────────────────────────────────────────────────────

    def coverage(self, records: Sequence[AlleleRecord]) -> Coverage:
        """How many of these alleles the column has a **non-null** number for."""
        found = self._lookup(records)
        return coverage_from_ids(self.name, records, {key for key, _ in found.items()})

    def score(self, records: Sequence[AlleleRecord]) -> Iterator[ScoreRow]:
        """One row per allele the column answers for; silent about the ones it does not."""
        found = self._lookup(records)
        for record in records:
            hit = found.get(record.allele_id)
            if hit is None:
                continue
            value, aux = hit
            yield ScoreRow(
                allele_id=record.allele_id,
                model=self.name,
                version=self.version,
                score=value,
                aux=aux,
                digest=self.digest,
                venue=self.venue,
                licence=self.licence,
            )

    def submit(self, records: Sequence[AlleleRecord]) -> RemoteJob:
        """Tier 1 runs here; there is nothing to submit."""
        raise NotImplementedError(f"{self.name} is a tier-1 lookup — call score()")

    # ── the one query ────────────────────────────────────────────────────────────────

    def _lookup(
        self, records: Sequence[AlleleRecord]
    ) -> dict[str, tuple[float | None, dict[str, Any]]]:
        """Fetch every requested allele's score, caching so coverage+score cost one pass.

        Misses are remembered too (``_asked``): an allele the table has no row for must not
        be looked up again on the next call, or every pass would re-query the whole gap.
        """
        wanted = [record.allele_id for record in records if record.allele_id not in self._asked]
        for start in range(0, len(wanted), CHUNK):
            chunk = wanted[start : start + CHUNK]
            self._cache.update(self._fetch(chunk))
            self._asked.update(chunk)
        return {
            record.allele_id: self._cache[record.allele_id]
            for record in records
            if record.allele_id in self._cache
        }

    def _fetch(self, ids: Sequence[str]) -> dict[str, tuple[float | None, dict[str, Any]]]:
        """One SQL statement: stage the ids, join, aggregate, return ids and numbers only."""
        if not ids:
            return {}
        from mva.warehouse.postgres import ALIAS, safe_identifier

        connection = self.connection
        connection.execute(f"CREATE OR REPLACE TEMP TABLE {_WANTED} (allele_id VARCHAR)")
        connection.executemany(f"INSERT INTO {_WANTED} VALUES (?)", [[allele] for allele in ids])
        table = f"{ALIAS}.{safe_identifier(self.schema)}.{safe_identifier(self.table)}"
        column = safe_identifier(self.column)
        aux = [safe_identifier(name) for name in self.aux]
        oriented = f"t.{column}" if self.score_sign >= 0 else f"(-1 * t.{column})"
        picks = [
            self._collapse(oriented, oriented),
            *(self._collapse(f"t.{name}", oriented) for name in aux),
        ]
        rows = connection.execute(
            f"SELECT w.allele_id, {', '.join(picks)} "
            f"FROM {table} t JOIN {_WANTED} w "
            f"ON w.allele_id = {allele_id_sql('t.chrom', 't.pos', 't.ref', 't.alt')} "
            f"WHERE t.{column} IS NOT NULL "
            "GROUP BY w.allele_id"
        ).fetchall()
        connection.execute(f"DROP TABLE IF EXISTS {_WANTED}")
        return {
            str(row[0]): (
                None if row[1] is None else float(row[1]),
                {name: row[index + 2] for index, name in enumerate(aux)},
            )
            for row in rows
        }

    def _collapse(self, expression: str, score: str) -> str:
        """The aggregate that picks one value per allele, per ``score_transform``."""
        if self.score_transform == "max":
            if expression == score:
                return f"max({expression})"
            return f"arg_max({expression}, {score})"
        return f"any_value({expression})"


def build(card: Any, *, connection: Any = None, records_parquet: Path = DEFAULT_RECORDS) -> Adapter:
    """Build the lane one model card describes. ``records_parquet`` is unused here —
    this lane never needs a coordinate on this side of the join."""
    if connection is None:
        raise ValueError(
            f"{getattr(card, 'key', 'this lane')} reads the warehouse — pass a connection"
        )
    params = dict(getattr(card, "params", {}) or {})
    return WarehouseColumnAdapter(
        name=str(card.key),
        version=str(card.version),
        connection=connection,
        table=str(params["table"]),
        column=str(params["column"]),
        aux=tuple(params.get("aux", ()) or ()),
        score_transform=str(params.get("score_transform", "identity")),
        score_sign=int(params.get("score_sign", 1) or 1),
        schema=str(params.get("schema", "warehouse")),
        licence=str(getattr(card, "licence", "") or ""),
        digest=str(params.get("digest", "") or ""),
        catalogue_adjacent=bool(getattr(card, "catalogue_adjacent", False)),
    )
