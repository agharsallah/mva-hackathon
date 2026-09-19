"""Tier-1 lane: a score table keyed on the **genomic coordinate**, joined inside ``build/``.

:mod:`.duckdb_lookup` joins a published table on something the allele record carries in the
clear — a protein change, an accession. Some publishers key on the change itself instead:
``chrom, pos, ref, alt``. GPN-MSA is the case this lane was built for; PrimateAI-3D and CADD's
whole-genome file are the same shape.

That is a problem the other lanes do not have, because **the record set that leaves this
machine is coordinate-free by design**: :class:`~mva.zoo.types.AlleleRecord` has no position
field, and `allele_id` — 16 hex characters of SHA-256 over ``chrom:pos:ref:alt`` — is the only
key allowed in a tracked file. Joining on a coordinate would mean putting one in Python
memory and, sooner or later, in a log line or a test fixture.

The fix is to never leave the database. The lane reads the downloaded score table (a Parquet
under ``build/<prefix>/tables/``), computes ``allele_id`` **in SQL** over its coordinate
columns with :func:`~mva.zoo.adapters.allele_id_sql` — the same expression, character for
character, that the Python helper computes — and joins on that id. The coordinate is read by
DuckDB from a gitignored file and is consumed inside the same statement that hashes it;
nothing but ``(allele_id, score)`` crosses back into Python.

Parameters, all from the model card:

``parquet``
    the converted table; defaults to ``build/it4/tables/<key>.parquet``, where
    ``tools/fetch_zoo_tables.py --subset-from`` leaves it.
``columns``
    the four coordinate column names in that table, in order. The default matches the
    ``chrom pos ref alt score`` layout the GPN-MSA dataset card documents.
``score_column`` / ``aux`` / ``score_sign``
    as in :mod:`.duckdb_lookup`. GPN-MSA publishes a log-likelihood-ratio-like number that
    is **more negative for a worse change**, so its card sets ``score_sign = -1`` and every
    ``ScoreRow.score`` still points the zoo's one way: higher = more damaging.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..types import Adapter, AlleleRecord, Coverage, RemoteJob, ScoreRow, Tier
from . import DEFAULT_RECORDS, allele_id_sql, coverage_from_ids

__all__ = ["CoordinateTableAdapter", "build"]

#: Where the fetch step leaves a converted score table.
TABLES = Path("build/it4/tables")

#: The four coordinate columns, in the order a published SNV table spells them.
DEFAULT_COLUMNS: tuple[str, str, str, str] = ("chrom", "pos", "ref", "alt")

#: Allele ids staged per statement.
CHUNK = 20_000

_IDS = "zoo_coord_ids"
_INDEX = "zoo_coord_index"


@dataclass
class CoordinateTableAdapter:
    """A published table keyed on the genomic change, re-keyed to ``allele_id`` in SQL."""

    name: str
    version: str
    parquet: Path
    columns: tuple[str, str, str, str] = DEFAULT_COLUMNS
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
    _indexed: bool = False

    def __post_init__(self) -> None:
        if len(self.columns) != 4:
            raise ValueError(
                f"{self.name}: `columns` must name exactly chrom, pos, ref and alt "
                f"(got {self.columns!r})"
            )

    @property
    def source_ref(self) -> str:
        return str(self.parquet)

    def table_digest(self) -> str:
        """SHA-256 of the Parquet — what the lineage edge records as the source bytes."""
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
        """The fraction of the record set the published table has a row for.

        For an all-possible-SNV table the shortfall is the indels: there is no row for a
        change that is not one base for one base, and that is a fact about the model's
        input class, not a failure of the fetch.
        """
        return coverage_from_ids(self.name, records, set(self._lookup(records)))

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

    def _ensure_index(self) -> None:
        """Re-key the whole score table to ``allele_id`` once, into a temp table.

        Hashing 7 million rows costs a few seconds; doing it inside every 20,000-row chunk
        would cost that per chunk. The temp table lives in the connection, so it dies with
        the process and never touches disk outside DuckDB's own spill directory.
        """
        if self._indexed:
            return
        if not self.parquet.exists():
            raise FileNotFoundError(
                f"{self.name}: no score table at {self.parquet} — run "
                f"`tools/fetch_zoo_tables.py --fetch {self.name} --subset-from <records>`"
            )
        from mva.warehouse.postgres import safe_identifier

        chrom, pos, ref, alt = (safe_identifier(name) for name in self.columns)
        score = safe_identifier(self.score_column)
        aux = [safe_identifier(name) for name in self.aux]
        oriented = f"{score}" if self.score_sign >= 0 else f"(-1 * {score})"
        carried = "".join(f", {name}" for name in aux)
        connection = self._connection()
        connection.execute(
            f"CREATE OR REPLACE TEMP TABLE {_INDEX} AS SELECT "
            f"{allele_id_sql(chrom, pos, ref, alt)} AS allele_id, "
            f"{oriented} AS oriented{carried} "
            f"FROM read_parquet('{str(self.parquet).replace(chr(39), chr(39) * 2)}') "
            f"WHERE {score} IS NOT NULL"
        )
        self._indexed = True

    def _lookup(
        self, records: Sequence[AlleleRecord]
    ) -> dict[str, tuple[float | None, dict[str, Any]]]:
        pending = [record for record in records if record.allele_id not in self._asked]
        for start in range(0, len(pending), CHUNK):
            chunk = pending[start : start + CHUNK]
            self._cache.update(self._fetch([record.allele_id for record in chunk]))
            self._asked.update(record.allele_id for record in chunk)
        return {
            record.allele_id: self._cache[record.allele_id]
            for record in records
            if record.allele_id in self._cache
        }

    def _fetch(self, ids: Sequence[str]) -> dict[str, tuple[float | None, dict[str, Any]]]:
        if not ids:
            return {}
        self._ensure_index()
        from mva.warehouse.postgres import safe_identifier

        aux = [safe_identifier(name) for name in self.aux]
        connection = self._connection()
        connection.execute(f"CREATE OR REPLACE TEMP TABLE {_IDS} (allele_id VARCHAR)")
        connection.executemany(f"INSERT INTO {_IDS} VALUES (?)", [[key] for key in ids])
        picks = ["max(s.oriented)", *(f"arg_max(s.{name}, s.oriented)" for name in aux)]
        rows = connection.execute(
            f"SELECT k.allele_id, {', '.join(picks)} FROM {_IDS} k "
            f"JOIN {_INDEX} s ON s.allele_id = k.allele_id GROUP BY k.allele_id"
        ).fetchall()
        connection.execute(f"DROP TABLE IF EXISTS {_IDS}")
        return {
            str(row[0]): (
                None if row[1] is None else float(row[1]),
                {name: row[index + 2] for index, name in enumerate(aux)},
            )
            for row in rows
        }


def build(card: Any, *, connection: Any = None, records_parquet: Path = DEFAULT_RECORDS) -> Adapter:
    """Build the lane one model card describes.

    ``records_parquet`` is accepted and ignored: this lane needs no coordinate from the
    record set, because it derives every id from the *published* table's own coordinates.
    That is the whole point — one side of the join is public data, the other is 39,286
    opaque ids.
    """
    params = dict(getattr(card, "params", {}) or {})
    columns = tuple(params.get("columns") or DEFAULT_COLUMNS)
    return CoordinateTableAdapter(
        name=str(card.key),
        version=str(card.version),
        parquet=Path(str(params.get("parquet") or TABLES / f"{card.key}.parquet")),
        columns=(str(columns[0]), str(columns[1]), str(columns[2]), str(columns[3])),
        score_column=str(params.get("score_column", "score")),
        aux=tuple(params.get("aux", ()) or ()),
        score_sign=int(params.get("score_sign", 1) or 1),
        licence=str(getattr(card, "licence", "") or ""),
        digest=str(params.get("digest", "") or ""),
        connection=connection,
        catalogue_adjacent=bool(getattr(card, "catalogue_adjacent", False)),
    )
