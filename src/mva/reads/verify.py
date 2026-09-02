"""Prove the read store holds what the delivery held, from independent evidence.

Three checks, each against a different witness so no single component grades itself:

* **Manifest reconciliation** — every shard the manifest names exists and holds exactly
  the rows the manifest recorded (counted from the Parquet footers, not trusted).
* **Pair symmetry** — R1 and R2 of a lane came off the same flowcell positions, so their
  read counts must be identical, per lane.
* **Round-trip** — the first and last record of each *source gzip* must reconstruct
  byte-identically from stored columns plus the ``runs`` constants. First and last
  together mean the stream was converted from its true start to its true end; the last
  record requires decompressing the whole source, which is the price of the proof.

An expected grand total (owned by ``ideation/data-findings.md``) can be passed in; it is
deliberately not hard-coded here, because this module must stay case-agnostic.
"""

import gzip
import shutil
import subprocess
from dataclasses import dataclass, field

from . import engines, schema
from .convert import as_source, peek


@dataclass
class Report:
    """Everything checked, and everything that failed."""

    total_rows: int = 0
    shards: int = 0
    failures: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures

    def expect(self, condition: bool, message: str) -> None:
        (self.notes if condition else self.failures).append(
            ("ok: " if condition else "FAIL: ") + message
        )


def against_manifest(connection, root: str, report: Report) -> None:
    """Shard-by-shard row counts versus what the manifest recorded at build time."""
    rows = connection.execute(f"""
        WITH counted AS (
            SELECT filename, count(*) AS actual
            FROM read_parquet('{root}/lane=*/read=*/part-*.parquet',
                              filename=true, hive_partitioning=false)
            GROUP BY filename)
        SELECT m.key, m.rows, coalesce(c.actual, 0)
        FROM '{root}/manifest.parquet' m
        LEFT JOIN counted c ON c.filename LIKE '%/' || m.key
    """).fetchall()
    report.shards = len(rows)
    for key, recorded, actual in rows:
        if recorded != actual:
            report.failures.append(
                f"FAIL: {key}: manifest says {recorded:,}, parquet holds {actual:,}"
            )
    report.total_rows = sum(actual for _, _, actual in rows)
    report.notes.append(f"ok: {report.shards} shards, {report.total_rows:,} rows counted")


def pair_symmetry(connection, root: str, report: Report) -> None:
    """R1 and R2 must be the same size within every lane."""
    lanes = connection.execute(f"""
        SELECT lane,
               sum(rows) FILTER (read_num = 1) AS r1,
               sum(rows) FILTER (read_num = 2) AS r2
        FROM '{root}/manifest.parquet' GROUP BY lane ORDER BY lane
    """).fetchall()
    for lane, r1, r2 in lanes:
        report.expect(r1 == r2, f"lane {lane}: R1 {r1:,} == R2 {r2:,}")


def round_trip(connection, root: str, fastq, report: Report) -> None:
    """First and last source records must rebuild exactly from stored columns."""
    source = as_source(fastq)
    facts = peek(source)
    partition = f"{root}/{schema.shard_dir(facts.lane, facts.read_num)}/part-*.parquet"

    def stored(tile: int, x: int, y: int) -> tuple | None:
        return connection.execute(
            f"SELECT tile, x, y, is_filtered, index_pair, sequence, quality "
            f"FROM read_parquet('{partition}') WHERE tile=? AND x=? AND y=?",
            [tile, x, y],
        ).fetchone()

    for label, record in (("first", _first_record(source)), ("last", _last_record(source))):
        name, sequence, quality = record
        head = name.split(" ")[0].split(":")
        row = stored(int(head[4]), int(head[5]), int(head[6]))
        if row is None:
            report.failures.append(f"FAIL: {source.name} {label} record not in store")
            continue
        rebuilt = facts.rebuild_name(row[0], row[1], row[2], row[3], row[4])
        report.expect(
            rebuilt == name and row[5] == sequence and row[6] == quality,
            f"{source.name}: {label} record round-trips byte-identically",
        )


def _first_record(source) -> tuple[str, str, str]:
    with source.open_stream() as raw, gzip.open(raw, "rt") as handle:
        name, sequence, _, quality = (handle.readline().rstrip("\n") for _ in range(4))
    return name, sequence, quality


def _last_record(source) -> tuple[str, str, str]:
    """The final record, via a full streaming decompression (the honest way).

    There is no cheap way to do this: gzip has no index, so the last record costs a full
    pass over the source. That cost is the proof — it is what shows the conversion ran to
    the true end of the stream rather than stopping early.
    """
    decompressor = engines.find_decompressor()
    local = "" if source.path is None else f" {engines.shlex_quote(source.path)}"
    command = f"{engines.shlex_quote(decompressor)} -dc{local} | tail -n 4"
    if source.path is not None:
        completed = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        tail = completed.stdout.splitlines()
    else:
        process = subprocess.Popen(
            command, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=False
        )
        with source.open_stream() as stream:
            shutil.copyfileobj(stream, process.stdin, length=8 * 1024 * 1024)
            process.stdin.close()
        tail = process.stdout.read().decode().splitlines()
        process.wait()
    return tail[0], tail[1], tail[3]


def run(
    root: str, sources: list, expected_total: int | None = None, deep: bool = True, connection=None
) -> Report:
    """All checks over one store root (a local staging dir or an ``s3://`` prefix).

    For an ``s3://`` root pass a connection already wired to the object store
    (:func:`mva.warehouse.objects.connect`); a bare one is made otherwise.
    """
    import duckdb

    connection = connection or duckdb.connect()
    report = Report()
    against_manifest(connection, root, report)
    pair_symmetry(connection, root, report)
    if expected_total is not None:
        report.expect(
            report.total_rows == expected_total,
            f"grand total {report.total_rows:,} == expected {expected_total:,}",
        )
    if deep:
        for fastq in sources:
            round_trip(connection, root, fastq, report)
    connection.close()
    return report
