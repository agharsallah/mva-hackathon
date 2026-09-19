"""Tier-1 lane: a score table published **per protein**, joined through the gene symbol.

A precomputed missense table comes in one of two shapes. The easy one is keyed by the
genomic change itself and joins on ``allele_id``; :mod:`.duckdb_lookup` serves it. The
other — ESM1b (Brandes 2023), EVE, and most things built by protein people — is keyed by a
**UniProt accession** (the protein's stable id in the UniProt database, e.g. ``P04637``,
with an isoform suffix like ``-2`` where a protein has several forms) and a **protein
change written in one-letter code** (``R550Q``: arginine at residue 550 replaced by
glutamine). The allele record has neither.

What it has is ``gene`` and ``hgvs_p`` — VEP's protein spelling, which is Ensembl-flavoured
and three-letter (``ENSP00000287667.1:p.Arg550Gln``). This lane is the translation between
the two, and it is deliberately the *only* place that translation lives:

1. ``hgvs_p`` → ``R550Q``, by reading the wild-type residue, the position and the mutant
   residue out of the HGVS string and mapping three-letter codes to one
   (:data:`ONE_LETTER`). Anything that is not a plain substitution — a frameshift, a stop,
   a deletion — yields no key and is simply not scored, which is correct: these tables hold
   single-residue substitutions only.
2. ``gene`` → the accessions that gene has in the table, through a **side map** the table's
   own publisher ships (``map_parquet`` / ``map_csv``: two columns, an accession and a gene
   symbol). Several accessions per gene is normal — one per isoform — and all of them are
   tried.

**Why joining through a gene symbol is safe here, and where it is not.** A symbol is a
weaker key than an accession: symbols drift, and UniProt's own gene names are not always
the HGNC symbol (the ESM1b map spells some immunoglobulin genes ``KV37``). Two guards make
the *scores* trustworthy anyway, while leaving the *coverage* honestly lower than an
accession join would give:

* the change key carries the **wild-type residue**, so an isoform whose residue 550 is not
  an arginine simply has no ``R550Q`` row and cannot match. A wrong-isoform hit is not
  merely unlikely, it is unrepresentable.
* where a gene's symbol is missing from the publisher's map, the lane scores nothing for
  it rather than guessing — the loss shows up as coverage, never as a wrong number.

Several matching rows (several isoforms) collapse to the **largest** oriented score, like
every other lookup lane, so ``ScoreRow.score`` always means "higher = more damaging".
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..types import Adapter, AlleleRecord, Coverage, RemoteJob, ScoreRow, Tier
from . import DEFAULT_RECORDS, coverage_from_ids

__all__ = ["ONE_LETTER", "ProteinTableAdapter", "build", "short_change"]

#: Where the fetch step leaves a downloaded score table once it is converted to Parquet.
TABLES = Path("build/it4/tables")

#: Records staged per statement.
CHUNK = 20_000

_KEYS = "zoo_protein_keys"

#: The 20 standard amino acids, three-letter code to one. ``Ter`` (a stop) is deliberately
#: absent: a table of single-residue substitutions has no row for one, and mapping it to
#: ``*`` would invent a key that never matches.
ONE_LETTER = {
    "Ala": "A", "Arg": "R", "Asn": "N", "Asp": "D", "Cys": "C",
    "Gln": "Q", "Glu": "E", "Gly": "G", "His": "H", "Ile": "I",
    "Leu": "L", "Lys": "K", "Met": "M", "Phe": "F", "Pro": "P",
    "Ser": "S", "Thr": "T", "Trp": "W", "Tyr": "Y", "Val": "V",
}  # fmt: skip

#: ``…:p.Arg550Gln`` — wild-type residue, position, mutant residue. Nothing else matches,
#: so frameshifts (``p.Arg550fs``), stops (``p.Arg550Ter``) and synonymous changes
#: (``p.Arg550=``) fall through and are not scored.
_SUBSTITUTION = re.compile(r"p\.([A-Z][a-z]{2})(\d+)([A-Z][a-z]{2})$")


def short_change(hgvs_p: str | None) -> str | None:
    """``ENSP…:p.Arg550Gln`` → ``R550Q``; anything that is not a substitution → ``None``."""
    if not hgvs_p:
        return None
    found = _SUBSTITUTION.search(hgvs_p)
    if not found:
        return None
    wild, position, mutant = found.groups()
    if wild not in ONE_LETTER or mutant not in ONE_LETTER:
        return None
    return f"{ONE_LETTER[wild]}{position}{ONE_LETTER[mutant]}"


@dataclass
class ProteinTableAdapter:
    """A per-protein score table, reached from ``gene`` + ``hgvs_p``."""

    name: str
    version: str
    parquet: Path
    gene_map: Path
    accession_column: str = "uniprot"
    change_column: str = "hgvs_p"
    map_accession_column: str = "id"
    map_gene_column: str = "gene"
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
        keys = [
            (record.allele_id, record.gene, short_change(record.hgvs_p))
            for record in records
            if record.gene and short_change(record.hgvs_p)
        ]
        if not keys:
            return {}
        self._require(self.parquet, "score table")
        self._require(self.gene_map, "gene map")
        from mva.warehouse.postgres import safe_identifier

        connection = self._connection()
        accession = safe_identifier(self.accession_column)
        change = safe_identifier(self.change_column)
        map_accession = safe_identifier(self.map_accession_column)
        map_gene = safe_identifier(self.map_gene_column)
        score = safe_identifier(self.score_column)
        aux = [safe_identifier(name) for name in self.aux]

        connection.execute(
            f"CREATE OR REPLACE TEMP TABLE {_KEYS} "
            "(allele_id_key VARCHAR, gene VARCHAR, change VARCHAR)"
        )
        connection.executemany(f"INSERT INTO {_KEYS} VALUES (?, ?, ?)", keys)
        oriented = f"s.{score}" if self.score_sign >= 0 else f"(-1 * s.{score})"
        picks = [f"max({oriented})", *(f"arg_max(s.{name}, {oriented})" for name in aux)]
        reader = "read_parquet" if self.gene_map.suffix == ".parquet" else "read_csv"
        rows = connection.execute(
            f"SELECT k.allele_id_key, {', '.join(picks)} "
            f"FROM {_KEYS} k "
            f"JOIN {reader}(?, header=true) m ON m.{map_gene} = k.gene "
            f"JOIN read_parquet(?) s "
            f"  ON CAST(s.{accession} AS VARCHAR) = CAST(m.{map_accession} AS VARCHAR) "
            f" AND CAST(s.{change} AS VARCHAR) = k.change "
            f"WHERE s.{score} IS NOT NULL "
            "GROUP BY k.allele_id_key",
            [str(self.gene_map), str(self.parquet)],
        ).fetchall()
        connection.execute(f"DROP TABLE IF EXISTS {_KEYS}")
        return {
            str(row[0]): (
                None if row[1] is None else float(row[1]),
                {name: row[index + 2] for index, name in enumerate(aux)},
            )
            for row in rows
        }

    def _require(self, path: Path, what: str) -> None:
        if not path.exists():
            raise FileNotFoundError(
                f"{self.name}: no {what} at {path} — run the lane's fetch script"
            )


def build(card: Any, *, connection: Any = None, records_parquet: Path = DEFAULT_RECORDS) -> Adapter:
    """Build the lane one model card describes."""
    params = dict(getattr(card, "params", {}) or {})
    key = params.get("key", ("uniprot", "hgvs_p"))
    return ProteinTableAdapter(
        name=str(card.key),
        version=str(card.version),
        parquet=Path(str(params.get("parquet") or TABLES / f"{card.key}.parquet")),
        gene_map=Path(str(params.get("gene_map") or TABLES / f"{card.key}.genes.csv")),
        accession_column=str(key[0]),
        change_column=str(key[1]),
        map_accession_column=str(params.get("map_accession", "id")),
        map_gene_column=str(params.get("map_gene", "gene")),
        score_column=str(params.get("score_column", "score")),
        aux=tuple(params.get("aux", ()) or ()),
        score_sign=int(params.get("score_sign", 1) or 1),
        licence=str(getattr(card, "licence", "") or ""),
        digest=str(params.get("digest", "") or ""),
        connection=connection,
        catalogue_adjacent=bool(getattr(card, "catalogue_adjacent", False)),
    )
