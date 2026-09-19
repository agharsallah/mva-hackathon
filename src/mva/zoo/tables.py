"""Turning a published score *archive* into the one long table a lookup lane joins.

Some model authors publish one file per protein, and the file is a **matrix**: one column
per residue position (headed by the wild-type amino acid and the position, ``"A 1"``), one
row per substituted amino acid, and the score in the cell. ESM1b (Brandes 2023) ships
42,286 such files. A lane cannot join a matrix; it needs one row per change, keyed by the
protein and the change — ``(uniprot, "A1K", score)``.

This module is that reshaping, and it is a **leaf**: it imports nothing from the zoo, reads
only files it is handed, and writes one Parquet. :mod:`tools.fetch_zoo_tables` calls it
after a download; a test calls it on three invented members.

**Why it is written in Python rather than in SQL.** The obvious implementation is one
DuckDB ``UNPIVOT`` over a glob. It does not work: every member's *column names are its own
protein's positions*, so no two members share a schema and ``union_by_name`` over tens of
thousands of them never finishes. One statement per member does work, but the per-statement
overhead dominates — 12,183 members measured at ~1,000 per 10 minutes, so two hours for one
lane. Reading the files with :mod:`csv` and writing the rows with :mod:`pyarrow` does the
same 12,183 in minutes, because a 200 KB CSV costs a parse, not a query plan.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Sequence
from pathlib import Path

__all__ = ["MatrixRow", "accession_of", "unpivot_matrix_members"]

#: Rows buffered before a Parquet row group is written.
BATCH = 500_000

#: ``(accession, change, score)`` — the shape a per-protein lookup lane joins on.
MatrixRow = tuple[str, str, float]


def accession_of(member: Path) -> str:
    """``P04637-2_LLR.csv`` → ``P04637-2``. The name up to the publisher's suffix."""
    return member.name.split("_")[0]


def _rows_of(member: Path, score_sign: int) -> Iterator[MatrixRow]:
    """One member's cells as ``(accession, "A1K", score)``.

    The header's first cell is empty (the row-label column); every other cell is
    ``"<wild-type residue> <position>"``. Each data row starts with the substituted
    residue. A blank cell means the author published no score for that change and is
    skipped rather than written as a null — a lane's coverage should count rows that exist.
    """
    import csv

    accession = accession_of(member)
    with member.open(newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            return
        # "A 1" -> "A1"; the empty first cell keeps its index so the columns line up.
        labels = [cell.replace(" ", "") for cell in header]
        for row in reader:
            if not row:
                continue
            mutant = row[0].strip()
            if not mutant:
                continue
            for index in range(1, min(len(row), len(labels))):
                cell = row[index]
                if not cell:
                    continue
                try:
                    value = float(cell)
                except ValueError:
                    continue
                yield accession, f"{labels[index]}{mutant}", score_sign * value


def unpivot_matrix_members(
    members: Sequence[Path],
    target: Path,
    *,
    score_sign: int = 1,
    progress: Callable[[str], None] | None = None,
) -> int:
    """Every member unpivoted into one Parquet at ``target``. Returns the row count.

    ``score_sign`` is ``-1`` where the published number points the other way (ESM1b's
    log-likelihood ratio is *more negative* for a worse change), so that every score this
    writes means "higher = more damaging" — the one orientation the cache promises.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    say = progress or (lambda _line: None)
    schema = pa.schema([("uniprot", pa.string()), ("hgvs_p", pa.string()), ("score", pa.float64())])
    target.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with pq.ParquetWriter(target, schema) as writer:
        for done, batch in enumerate(_batched(members, score_sign, say), start=1):
            writer.write_table(pa.Table.from_arrays(_columns(batch, pa), schema=schema))
            written += len(batch)
            say(f"    row group {done}: {written:,} rows")
    return written


def _columns(batch: list[MatrixRow], pa: object) -> list[object]:
    array = getattr(pa, "array")  # noqa: B009 — pyarrow is imported by the caller
    return [
        array([row[0] for row in batch]),
        array([row[1] for row in batch]),
        array([row[2] for row in batch]),
    ]


def _batched(
    members: Sequence[Path], score_sign: int, say: Callable[[str], None]
) -> Iterable[list[MatrixRow]]:
    """Members read in order, handed out in row batches so memory stays flat."""
    batch: list[MatrixRow] = []
    for index, member in enumerate(members, start=1):
        batch.extend(_rows_of(member, score_sign))
        if index % 2_000 == 0:
            say(f"    {index:,}/{len(members):,} members")
        if len(batch) >= BATCH:
            yield batch
            batch = []
    if batch:
        yield batch
