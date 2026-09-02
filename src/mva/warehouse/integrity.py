"""Evidence that an ingest kept everything it was given.

"The row counts match" is not proof. A column can be silently retyped, a sentinel can
become a NULL, an empty string can vanish, and every count still agrees. This module
produces a **fingerprint** — a compact summary that changes if any of those happen — and
compares fingerprints taken at either end of a transfer.

Three properties make a fingerprint useful rather than decorative:

* **Order-independent.** A Parquet file may hand rows back in a different order than the
  source did. The checksum is a sum over per-value hashes, so it cannot depend on order,
  and unlike an XOR it does not cancel when a value appears twice.
* **NULL and empty string are distinguished.** This is the one place DuckDB's CSV reader
  genuinely loses information — an empty cell in a typed column arrives as NULL — so the
  fingerprint counts them separately and a conflation shows up as a mismatch rather than
  passing silently.
* **Type-independent.** Every value is hashed through its ``VARCHAR`` rendering, so a
  column that arrives as ``BIGINT`` at one end and ``VARCHAR`` at the other still compares
  equal on content. Types are reported alongside, as information rather than as a verdict,
  because a deliberate retyping is not data loss.

The counterpart to this is :func:`~mva.warehouse.vcfstage.verify_roundtrip`, which proves
retention a second and stronger way for VCF specifically: reconstruct the original lines
from what was stored and compare digests.
"""

from dataclasses import dataclass, field

#: Stands in for SQL NULL when hashing, so a real NULL cannot collide with the four-letter
#: string "NULL" that VCF and TSV files genuinely contain.
NULL_SENTINEL = "\\x00<NULL>\\x00"


@dataclass(frozen=True)
class ColumnFingerprint:
    """Content evidence for one column."""

    name: str
    type_name: str
    non_null: int
    nulls: int
    empties: int
    distinct: int
    checksum: int

    def content_equals(self, other: "ColumnFingerprint") -> bool:
        """True when the *values* match, whatever the two columns' declared types are."""
        return (
            self.non_null == other.non_null
            and self.nulls == other.nulls
            and self.empties == other.empties
            and self.distinct == other.distinct
            and self.checksum == other.checksum
        )


@dataclass(frozen=True)
class TableFingerprint:
    """Content evidence for a whole table."""

    label: str
    rows: int
    columns: list[ColumnFingerprint] = field(default_factory=list)

    @property
    def by_name(self) -> dict[str, ColumnFingerprint]:
        return {column.name: column for column in self.columns}


@dataclass(frozen=True)
class Discrepancy:
    """One way in which two fingerprints disagree."""

    scope: str
    detail: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.scope}: {self.detail}"


def fingerprint(connection, source: str, label: str, distinct: bool = True) -> TableFingerprint:
    """Fingerprint whatever ``source`` names — a table, or a ``read_parquet(...)`` call.

    Every column's statistics are gathered in **one** scan. The obvious implementation —
    a query per column — costs N passes over the data, which is unnoticeable on a profile
    table and ruinous on a five-million-row callset, where it turned a check into a
    multi-minute job.

    ``distinct`` computes exact distinct counts. It is the expensive part on wide text
    columns (a VCF's ``INFO`` is long and almost entirely unique), and it adds little on
    top of the checksum, which already detects any content change. Turn it off for large
    inputs.

    ``source`` is interpolated into the FROM clause, so it must come from the caller's own
    code and never from user input. It is a SQL fragment by necessity: the whole point is
    to fingerprint sources that are not tables.
    """
    described = connection.execute(f"DESCRIBE SELECT * FROM {source}").fetchall()
    names = [row[0] for row in described]
    types = [str(row[1]) for row in described]

    selects = ["count(*)"]
    for name in names:
        quoted = f'"{name}"'
        text = f"{quoted}::VARCHAR"
        selects += [
            f"count({quoted})",
            f"coalesce(sum(CASE WHEN {text} = '' THEN 1 ELSE 0 END), 0)",
            f"count(DISTINCT {quoted})" if distinct else "0",
            f"coalesce(sum(hash(coalesce({text}, '{NULL_SENTINEL}'))::HUGEINT), 0)",
        ]
    row = connection.execute(f"SELECT {', '.join(selects)} FROM {source}").fetchone()

    rows = int(row[0])
    columns = []
    for index, (name, type_name) in enumerate(zip(names, types, strict=True)):
        base = 1 + index * 4
        non_null, empties, distinct_n, checksum = (int(v) for v in row[base : base + 4])
        columns.append(
            ColumnFingerprint(
                name, type_name, non_null, rows - non_null, empties, distinct_n, checksum
            )
        )
    return TableFingerprint(label, rows, columns)


def compare(before: TableFingerprint, after: TableFingerprint) -> list[Discrepancy]:
    """Every way ``after`` fails to carry the same content as ``before``."""
    found: list[Discrepancy] = []

    if before.rows != after.rows:
        # Signed from the destination's point of view, so a loss reads as negative.
        delta = after.rows - before.rows
        found.append(
            Discrepancy("row count", f"{before.rows:,} -> {after.rows:,} ({delta:+,} rows)")
        )

    missing = [c.name for c in before.columns if c.name not in after.by_name]
    added = [c.name for c in after.columns if c.name not in before.by_name]
    if missing:
        found.append(Discrepancy("columns", f"absent downstream: {', '.join(missing)}"))
    if added:
        found.append(Discrepancy("columns", f"appeared downstream: {', '.join(added)}"))

    for column in before.columns:
        other = after.by_name.get(column.name)
        if other is None or column.content_equals(other):
            continue
        parts = []
        if column.checksum != other.checksum:
            parts.append("content checksum differs")
        if column.nulls != other.nulls:
            parts.append(f"nulls {column.nulls:,} -> {other.nulls:,}")
        if column.empties != other.empties:
            parts.append(f"empty strings {column.empties:,} -> {other.empties:,}")
        if column.distinct != other.distinct:
            parts.append(f"distinct {column.distinct:,} -> {other.distinct:,}")
        if column.non_null != other.non_null:
            parts.append(f"non-null {column.non_null:,} -> {other.non_null:,}")
        found.append(Discrepancy(column.name, "; ".join(parts)))
    return found


def retyped(before: TableFingerprint, after: TableFingerprint) -> list[tuple[str, str, str]]:
    """Columns whose declared type changed but whose content did not.

    Reported separately from :func:`compare` because a retype is usually intentional —
    staging deliberately turns text into numbers — and is only a problem when it is a
    surprise. Content equality is what makes it safe.
    """
    changes = []
    for column in before.columns:
        other = after.by_name.get(column.name)
        if other and column.type_name != other.type_name and column.content_equals(other):
            changes.append((column.name, column.type_name, other.type_name))
    return changes


def render(
    before: TableFingerprint, after: TableFingerprint, discrepancies: list[Discrepancy]
) -> str:
    """A human-readable verdict, for a terminal or a methodology note."""
    lines = [
        f"{'':<24}{before.label:>18}{after.label:>18}",
        f"{'rows':<24}{before.rows:>18,}{after.rows:>18,}",
        "",
    ]
    header = f"{'column':<24}{'type before':>18}{'type after':>18}   content"
    lines.append(header)
    lines.append("-" * len(header))
    for column in before.columns:
        other = after.by_name.get(column.name)
        if other is None:
            lines.append(f"{column.name:<24}{column.type_name:>18}{'ABSENT':>18}   LOST")
            continue
        verdict = "identical" if column.content_equals(other) else "DIFFERS"
        lines.append(f"{column.name:<24}{column.type_name:>18}{other.type_name:>18}   {verdict}")
    lines.append("-" * len(header))
    if discrepancies:
        lines.append(f"{len(discrepancies)} discrepancy(ies):")
        lines += [f"  {item}" for item in discrepancies]
    else:
        lines.append("No discrepancies: every column's content is byte-identical.")
    return "\n".join(lines)
