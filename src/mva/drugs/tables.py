"""The five TSVs the snapshot writes: their columns, and how a row is serialised.

One place owns the column order and the scalar spelling, so the writer, the manifest and
any reader cannot drift. Three conventions, applied uniformly:

* a **list** field is joined with ``|`` — TSV has no nesting and a second delimiter is
  cheaper to split than a quoted JSON blob in a column;
* a **boolean** is ``true``/``false``;
* an **unknown** is the empty string, and it means *unknown*: ``fda_label`` empty is "not
  checked", not "no label". The manifest says so too.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

__all__ = [
    "CANDIDATE_COLUMNS",
    "LITERATURE_COLUMNS",
    "PATHWAY_COLUMNS",
    "TARGET_COLUMNS",
    "TRIAL_COLUMNS",
    "cell",
    "write_tsv",
]

TARGET_COLUMNS = ("symbol", "role", "direction_ids", "pathways", "uniprot")

CANDIDATE_COLUMNS = (
    "drug_name",
    "drug_id",
    "target_symbol",
    "target_role",
    "direction_ids",
    "source",
    "interaction_or_moa",
    "action_type",
    "max_phase",
    "approved",
    "fda_label",
    "pmids",
    "first_approval",
    "atc",
)

#: ``query`` is this repository's addition to the contracted trial row: it names which of
#: the snapshot's queries returned the study, so a reader can tell a disease hit from a
#: per-drug hit without re-running anything.
TRIAL_COLUMNS = (
    "nct_id",
    "title",
    "phase",
    "overall_status",
    "conditions",
    "interventions",
    "start_date",
    "study_type",
    "query",
)

#: ``query`` likewise: which of the three literature query families found this paper.
LITERATURE_COLUMNS = ("pmid", "title", "journal", "year", "doi", "query")

PATHWAY_COLUMNS = ("st_id", "display_name", "matched", "n_participants")


def cell(value: Any) -> str:
    """One field, TSV-safe: lists joined with ``|``, booleans lower-case, ``None`` empty.

    Tabs, newlines and carriage returns inside a value are replaced by a space. A trial
    title carrying a newline would otherwise split one record into two, which no reader
    could detect after the fact.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple, set)):
        text = "|".join(cell(item) for item in value)
    else:
        text = str(value)
    for bad in ("\t", "\r\n", "\n", "\r"):
        text = text.replace(bad, " ")
    return text.strip()


def write_tsv(path: Path, columns: Sequence[str], rows: Iterable[dict[str, Any]]) -> int:
    """Write a header and one line per row. Returns the row count, header excluded."""
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("\t".join(columns) + "\n")
        for row in rows:
            stream.write("\t".join(cell(row.get(name)) for name in columns) + "\n")
            written += 1
    return written
