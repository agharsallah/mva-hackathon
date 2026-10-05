"""Writing a stage's rows out as a TSV a loader can read, and its numbers as JSON.

Every analysis stage in this project ends the same way: a handful of tables written to
``build/<step>/tables/*.tsv`` for the loader, and one JSON sidecar holding the counts and
intervals no table has a column for. That ending was copied into four tool scripts before it
was written down once; this module is the one copy.

Two conventions are load-bearing rather than cosmetic:

* **Booleans go out as ``true`` / ``false``**, because the loaders read every column as text
  and then ``CAST`` it, and DuckDB's cast accepts those two spellings. Python's ``True``
  would arrive as a string and cast to nothing.
* **A tab, carriage return or newline inside a value becomes a space.** Free text in these
  tables is display text — a paper title, a note, a reason — and a literal tab in it would
  move every column to its right, silently, in a file nobody re-reads by eye.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

__all__ = ["cell", "write_json", "write_tsv"]


def cell(value: Any) -> str:
    """One TSV cell: ``None`` is empty, a boolean is ``true``/``false``, text loses its tabs."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).replace("\t", " ").replace("\r", " ").replace("\n", " ")


def write_tsv(path: Path, rows: Iterable[Mapping[str, Any]], columns: Sequence[str]) -> int:
    """Write ``rows`` under ``columns`` and return how many were written.

    ``columns`` is the promise: a key missing from a row becomes an empty cell rather than an
    error, and a key present in the row but absent from ``columns`` is not written. That is
    deliberate — the column list is the table's schema, and a stage that starts emitting an
    extra key should have to change the schema to make it arrive.

    Quoting is stated rather than sniffed, for the same reason the tab replacement exists.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(list(columns))
        for row in rows:
            writer.writerow([cell(row.get(name)) for name in columns])
            written += 1
    return written


def write_json(path: Path, payload: Mapping[str, Any]) -> Path:
    """The numbers no table holds — counts, intervals, hashes — beside the tables.

    Keys are sorted and the indent is fixed so that re-running a stage whose results did not
    change produces a byte-identical file, and ``git diff`` shows only what actually moved.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return path
