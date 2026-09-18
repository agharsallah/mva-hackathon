"""What step 1's record set says about itself, and where it lands.

Split from :mod:`mva.zoo.record` because it is a different concern and because the module
limit is 400 lines: :mod:`.record` *reads* the warehouse into records, this module *counts*
them and *writes* them out. The two halves meet only through
:class:`~mva.zoo.types.AlleleRecord`.

Three outputs and one number:

* ``results.it4_allele_records`` — the coordinate-free table, **replaced** on every run. It
  is a projection of the warehouse, not a log, so two runs must not double its rows; the
  audit trail of runs lives in the append-only lineage edge list instead.
* ``build/it4/records.parquet`` — the same rows **plus** the coordinate. Gitignored, and the
  only file in the step that carries a patient position.
* ``build/it4/records.provenance.json`` — inputs, parameters, row counts, the parquet's
  sha256, the tool and the timestamp. A reader holding only ``build/it4/`` can tell which
  tables the rows came from, which flags were set, and whether the parquet has been touched.
* :attr:`RunSummary.p4_1a_fraction` — the MVP claim `P4-1a`. Computed here, judged nowhere
  here (see the class docstring).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..warehouse import lineage
from ..warehouse.postgres import ALIAS, safe_identifier
from .record_hgvs import Coordinate
from .types import RECORD_COLUMNS, RECORDS_TABLE, AlleleRecord

__all__ = [
    "DEFAULT_OUT_DIR",
    "PARQUET_COLUMNS",
    "TOOL",
    "TRANSFORM",
    "RunSummary",
    "Written",
    "ensure_records_table",
    "summarise",
    "write",
]

#: Where the gitignored half of the output goes.
DEFAULT_OUT_DIR = Path("build/it4")

#: Written into the lineage edge and the provenance manifest.
TRANSFORM = "it4-allele-records"
TOOL = "mva-zoo records"

#: The parquet's columns: every :class:`~mva.zoo.types.AlleleRecord` field, then the
#: coordinate the table may not carry, then the run stamp. The two sequence-window pairs
#: are already here and stay null in the MVP, so adding them (plan §5, opt-A/opt-B) is a
#: fill rather than a migration.
PARQUET_COLUMNS: tuple[tuple[str, str], ...] = (
    ("allele_id", "VARCHAR"),
    ("gene", "VARCHAR"),
    ("transcript", "VARCHAR"),
    ("consequence", "VARCHAR"),
    ("hgvs_c", "VARCHAR"),
    ("hgvs_p", "VARCHAR"),
    ("uniprot", "VARCHAR"),
    ("protein_window_ref", "VARCHAR"),
    ("protein_window_alt", "VARCHAR"),
    ("dna_window_ref", "VARCHAR"),
    ("dna_window_alt", "VARCHAR"),
    ("is_read_only", "BOOLEAN"),
    ("af_gnomad", "DOUBLE"),
    ("clin_sig", "VARCHAR"),
    ("chrom", "VARCHAR"),
    ("pos", "BIGINT"),
    ("ref", "VARCHAR"),
    ("alt", "VARCHAR"),
    ("built_at", "TIMESTAMP"),
    ("source", "VARCHAR"),
    ("run_id", "VARCHAR"),
)


@dataclass(frozen=True)
class Written:
    """Where the two halves of the output landed, and the parquet's digest."""

    run_id: str
    rows: int
    parquet: Path
    provenance: Path
    sha256: str


@dataclass(frozen=True)
class RunSummary:
    """The day-1 numbers step 1 exists to produce. Counts only — never a position.

    ``p4_1a_fraction`` is the claim `P4-1a` of plan §5: the share of **coding** alleles
    (the read-only ones are excluded — they have no VCF row and no transcript to spell
    against) carrying a non-null ``hgvs_p`` *or* ``hgvs_c``. The plan's threshold is 0.99,
    refuted below 0.95. This class computes the number; judging it is the main thread's
    job, in the methodology entry that files the claim.
    """

    run_id: str = ""
    total: int = 0
    coding: int = 0
    read_only: int = 0
    with_hgvs_c: int = 0
    with_hgvs_p: int = 0
    by_consequence: dict[str, int] = field(default_factory=dict)
    p4_1a_fraction: float = 0.0
    masked: bool = False
    rows: int = 0
    parquet: str = ""
    provenance: str = ""
    sha256: str = ""
    source: str = ""
    asked: int = 0
    resumed: int = 0


def summarise(records: Sequence[AlleleRecord], **stamp: Any) -> RunSummary:
    """Count what the pass produced. Every field is a count, a share, or a file name."""
    coding = [record for record in records if not record.is_read_only]
    by_consequence: dict[str, int] = {}
    for record in records:
        name = record.consequence or "unknown"
        by_consequence[name] = by_consequence.get(name, 0) + 1
    spelled = sum(1 for record in coding if record.hgvs_p or record.hgvs_c)
    return RunSummary(
        total=len(records),
        coding=len(coding),
        read_only=len(records) - len(coding),
        with_hgvs_c=sum(1 for record in records if record.hgvs_c),
        with_hgvs_p=sum(1 for record in records if record.hgvs_p),
        by_consequence=dict(sorted(by_consequence.items())),
        p4_1a_fraction=spelled / len(coding) if coding else 0.0,
        **stamp,
    )


def ensure_records_table(connection: Any, schema: str) -> None:
    """Create ``results.it4_allele_records`` if absent, in the pinned column order."""
    columns = ", ".join(f"{name} {kind}" for name, kind in RECORD_COLUMNS)
    safe = safe_identifier(schema)
    connection.execute(f"CREATE TABLE IF NOT EXISTS {ALIAS}.{safe}.{RECORDS_TABLE} ({columns})")


def write(
    connection: Any,
    schema_results: str,
    schema_warehouse: str,
    records: Sequence[AlleleRecord],
    coordinates: Mapping[str, Coordinate],
    out_dir: Path = DEFAULT_OUT_DIR,
    run_id: str = "",
    *,
    source: str = "",
    inputs: Mapping[str, int] | None = None,
    parameters: Mapping[str, Any] | None = None,
    built_at: datetime | None = None,
) -> Written:
    """Land the record set: the coordinate-free table, the parquet, the manifest, the edge.

    The table is **replaced** on every run rather than appended to — it is a projection of
    the warehouse, not a log, and two runs of the same step must not double its rows. The
    audit trail of *runs* lives in the append-only lineage edge list instead.
    """
    run = run_id or datetime.now(UTC).strftime("it4-records-%Y%m%dT%H%M%SZ")
    stamp = built_at or datetime.now(UTC).replace(tzinfo=None)
    ensure_records_table(connection, schema_results)
    safe = safe_identifier(schema_results)
    table = f"{ALIAS}.{safe}.{RECORDS_TABLE}"
    connection.execute(f"DELETE FROM {table}")
    marks = ", ".join(["?"] * len(RECORD_COLUMNS))
    connection.executemany(
        f"INSERT INTO {table} VALUES ({marks})",
        [_table_row(record, stamp, source) for record in records],
    )

    parquet = _parquet(connection, records, coordinates, out_dir, run, stamp, source)
    digest = _sha256(parquet)
    manifest = _provenance(
        out_dir,
        run_id=run,
        rows=len(records),
        records=records,
        inputs=dict(inputs or {}),
        parameters=dict(parameters or {}),
        parquet=parquet,
        sha256=digest,
        source=source,
        built_at=stamp,
    )

    lineage.ensure_tables(connection, schema_warehouse)
    lineage.record(
        connection,
        schema_warehouse,
        target_schema=schema_results,
        target_table=RECORDS_TABLE,
        target_rows=len(records),
        source_kind="table",
        source_ref=", ".join(sorted(inputs or {})) or f"{schema_results}.coding_alleles",
        source_version=source,
        source_sha256=digest,
        transform=(
            f"{TRANSFORM}: distinct coding alleles left-joined to the VEP and in-silico "
            f"annotations, unioned with the read-only alleles; HGVS from a VEP REST pass"
        ),
        tool=TOOL,
        notes=f"run_id={run}; parquet={parquet.name}; manifest={manifest.name}",
    )
    return Written(
        run_id=run, rows=len(records), parquet=parquet, provenance=manifest, sha256=digest
    )


def _table_row(record: AlleleRecord, built_at: datetime, source: str) -> list[Any]:
    """One record in :data:`~mva.zoo.types.RECORD_COLUMNS` order — coordinate-free."""
    values: dict[str, Any] = {**record.__dict__, "built_at": built_at, "source": source}
    return [values[name] for name, _kind in RECORD_COLUMNS]


def _parquet(
    connection: Any,
    records: Sequence[AlleleRecord],
    coordinates: Mapping[str, Coordinate],
    out_dir: Path,
    run_id: str,
    built_at: datetime,
    source: str,
) -> Path:
    """The same rows **plus** the coordinate, written through DuckDB into ``build/``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "records.parquet"
    columns = ", ".join(f"{name} {kind}" for name, kind in PARQUET_COLUMNS)
    connection.execute(f"CREATE OR REPLACE TEMP TABLE it4_records_out ({columns})")
    rows = []
    for record in records:
        place = coordinates.get(record.allele_id)
        values: dict[str, Any] = {
            **record.__dict__,
            "chrom": place.chrom if place else None,
            "pos": place.pos if place else None,
            "ref": place.ref if place else None,
            "alt": place.alt if place else None,
            "built_at": built_at,
            "source": source,
            "run_id": run_id,
        }
        rows.append([values[name] for name, _kind in PARQUET_COLUMNS])
    marks = ", ".join(["?"] * len(PARQUET_COLUMNS))
    connection.executemany(f"INSERT INTO it4_records_out VALUES ({marks})", rows)
    quoted = str(path).replace("'", "''")
    connection.execute(f"COPY it4_records_out TO '{quoted}' (FORMAT PARQUET)")
    connection.execute("DROP TABLE it4_records_out")
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _provenance(out_dir: Path, **facts: Any) -> Path:
    """The manifest beside the parquet: inputs, parameters, counts, digest, tool, time.

    Repo rule: nothing is produced without its source and generation process written down
    next to it. A reader who has only ``build/it4/`` can tell which tables the rows came
    from, which flags were set, and whether the parquet has been touched since.
    """
    records: Sequence[AlleleRecord] = facts["records"]
    path = out_dir / "records.provenance.json"
    summary = summarise(records)
    payload = {
        "artifact": str(facts["parquet"]),
        "sha256": facts["sha256"],
        "run_id": facts["run_id"],
        "built_at": facts["built_at"].isoformat(),
        "tool": TOOL,
        "transform": TRANSFORM,
        "annotation_source": facts["source"],
        "inputs": facts["inputs"],
        "parameters": facts["parameters"],
        "rows": {
            "total": summary.total,
            "coding": summary.coding,
            "read_only": summary.read_only,
            "with_hgvs_c": summary.with_hgvs_c,
            "with_hgvs_p": summary.with_hgvs_p,
            "p4_1a_fraction": round(summary.p4_1a_fraction, 6),
            "by_consequence": summary.by_consequence,
        },
        "columns": [name for name, _kind in PARQUET_COLUMNS],
        "targets": {
            "table": RECORDS_TABLE,
            "parquet": str(facts["parquet"]),
        },
        "caveat": (
            "the parquet carries patient coordinates and never leaves build/; the table "
            "and every number above are coordinate-free"
        ),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
