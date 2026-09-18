"""Tier-1 lane: a downloaded score table, converted to Parquet once and joined in DuckDB.

Most "models" in this zoo never run. Their authors scored every possible single-letter
change in the genome and published the answers as a table — **precomputed scores**, the
genomics equivalent of shipping a CDN cache of every response instead of the server. ESM1b
(Brandes 2023) is the MVP example. Scoring is then a join, and a join over ~40k rows is
milliseconds.

The lane is deliberately dumb and fully parameterised, because *which* column and *which*
key change per model while the mechanics never do:

``parquet``
    the converted table. Optional: a card that only names the download ``url`` (the
    registry's required key) falls back to ``build/it4/tables/<key>.parquet``, which is
    where the fetch step converts it. Fetch scripts and digests are committed; the score
    files themselves never are (licence terms, size).
``key``
    the record fields to join on — ``["allele_id"]`` where the table is keyed by the
    change itself, ``["gene", "hgvs_p"]`` where it is keyed by the protein change.
``score_column``
    the column holding the number.
``aux``
    further columns carried into ``ScoreRow.aux`` as context.
``score_sign``
    ``1`` (the default) where the published number is already "higher = more damaging",
    ``-1`` where it is the other way round. ESM1b publishes a log-likelihood ratio, which
    is *more negative* for a worse change, so its card sets ``-1`` and this lane flips it.
    Every ``ScoreRow.score`` in the cache therefore points the same way.

A key that matches several table rows is collapsed to the **largest** score, and the
``aux`` values reported are the ones from that same row (``arg_max``), so a row's context
always describes the number beside it.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..types import Adapter, AlleleRecord, Coverage, RemoteJob, ScoreRow, Tier
from . import DEFAULT_RECORDS, coverage_from_ids

__all__ = ["DuckdbLookupAdapter", "build"]

#: Where the fetch step leaves a downloaded score table once it is converted to Parquet.
TABLES = Path("build/it4/tables")

#: Records staged per statement.
CHUNK = 20_000

_KEYS = "zoo_keys"


@dataclass
class DuckdbLookupAdapter:
    """A model whose published score table is a Parquet file on this machine."""

    name: str
    version: str
    parquet: Path
    key: tuple[str, ...] = ("allele_id",)
    score_column: str = "score"
    aux: tuple[str, ...] = ()
    score_sign: int = 1
    licence: str = ""
    digest: str = ""
    connection: Any = None
    tier: Tier = 1
    catalogue_adjacent: bool = False
    venue: str = "laptop"
    _cache: dict[str, tuple[float | None, dict[str, Any]]] = field(default_factory=dict)
    _asked: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if not self.key:
            raise ValueError(f"{self.name}: `key` must name at least one record field")
        known = set(AlleleRecord.__dataclass_fields__)
        missing = [name for name in self.key if name not in known]
        if missing:
            raise ValueError(
                f"{self.name}: `key` names fields the allele record does not have: {missing}. "
                "A table keyed on coordinates cannot be joined from the record set, which is "
                "coordinate-free by design; that lane needs its own reader."
            )

    @property
    def source_ref(self) -> str:
        return str(self.parquet)

    def table_digest(self) -> str:
        """SHA-256 of the Parquet file — what the lineage edge records as the source bytes."""
        if self.digest:
            return self.digest
        if not self.parquet.exists():
            return ""
        sha = hashlib.sha256()
        with self.parquet.open("rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                sha.update(block)
        self.digest = sha.hexdigest()
        return self.digest

    # ── the Adapter protocol ─────────────────────────────────────────────────────────

    def coverage(self, records: Sequence[AlleleRecord]) -> Coverage:
        """The fraction of the record set the published table has a row for."""
        found = self._lookup(records)
        return coverage_from_ids(self.name, records, set(found))

    def score(self, records: Sequence[AlleleRecord]) -> Iterator[ScoreRow]:
        found = self._lookup(records)
        digest = self.table_digest()
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
                digest=digest,
                venue=self.venue,
                licence=self.licence,
            )

    def submit(self, records: Sequence[AlleleRecord]) -> RemoteJob:
        raise NotImplementedError(f"{self.name} is a tier-1 lookup — call score()")

    # ── the join ─────────────────────────────────────────────────────────────────────

    def _connection(self) -> Any:
        import duckdb

        if self.connection is None:
            self.connection = duckdb.connect()
        return self.connection

    def _lookup(
        self, records: Sequence[AlleleRecord]
    ) -> dict[str, tuple[float | None, dict[str, Any]]]:
        pending = [record for record in records if record.allele_id not in self._asked]
        for start in range(0, len(pending), CHUNK):
            chunk = pending[start : start + CHUNK]
            self._cache.update(self._fetch(chunk))
            self._asked.update(record.allele_id for record in chunk)
        return {
            record.allele_id: self._cache[record.allele_id]
            for record in records
            if record.allele_id in self._cache
        }

    def _fetch(
        self, records: Sequence[AlleleRecord]
    ) -> dict[str, tuple[float | None, dict[str, Any]]]:
        if not records:
            return {}
        if not self.parquet.exists():
            raise FileNotFoundError(
                f"{self.name}: no score table at {self.parquet} — run the lane's fetch script"
            )
        from mva.warehouse.postgres import safe_identifier

        connection = self._connection()
        key = [safe_identifier(name) for name in self.key]
        score = safe_identifier(self.score_column)
        aux = [safe_identifier(name) for name in self.aux]
        columns = ", ".join(f"{name} VARCHAR" for name in key)
        connection.execute(
            f"CREATE OR REPLACE TEMP TABLE {_KEYS} (allele_id_key VARCHAR, {columns})"
        )
        connection.executemany(
            f"INSERT INTO {_KEYS} VALUES (?{', ?' * len(key)})",
            [
                [record.allele_id, *(_field(record, name) for name in self.key)]
                for record in records
            ],
        )
        on = " AND ".join(f"CAST(s.{name} AS VARCHAR) = k.{name}" for name in key)
        oriented = f"s.{score}" if self.score_sign >= 0 else f"(-1 * s.{score})"
        picks = [f"max({oriented})", *(f"arg_max(s.{name}, {oriented})" for name in aux)]
        rows = connection.execute(
            f"SELECT k.allele_id_key, {', '.join(picks)} "
            f"FROM {_KEYS} k JOIN read_parquet(?) s ON {on} "
            f"WHERE s.{score} IS NOT NULL "
            "GROUP BY k.allele_id_key",
            [str(self.parquet)],
        ).fetchall()
        connection.execute(f"DROP TABLE IF EXISTS {_KEYS}")
        return {
            str(row[0]): (
                None if row[1] is None else float(row[1]),
                {name: row[index + 2] for index, name in enumerate(aux)},
            )
            for row in rows
        }


def _field(record: AlleleRecord, name: str) -> str | None:
    """One record field as join text. A null key never matches, which is the intent."""
    value = getattr(record, name, None)
    return None if value is None else str(value)


def build(card: Any, *, connection: Any = None, records_parquet: Path = DEFAULT_RECORDS) -> Adapter:
    """Build the lane one model card describes."""
    params = dict(getattr(card, "params", {}) or {})
    return DuckdbLookupAdapter(
        name=str(card.key),
        version=str(card.version),
        parquet=Path(str(params.get("parquet") or TABLES / f"{card.key}.parquet")),
        key=tuple(params.get("key", ("allele_id",)) or ("allele_id",)),
        score_column=str(params.get("score_column", "score")),
        aux=tuple(params.get("aux", ()) or ()),
        score_sign=int(params.get("score_sign", 1) or 1),
        licence=str(getattr(card, "licence", "") or ""),
        digest=str(params.get("digest", "") or ""),
        connection=connection,
        catalogue_adjacent=bool(getattr(card, "catalogue_adjacent", False)),
    )
