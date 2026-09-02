"""Writing the Track 1 submission CSV.

Every constraint here is enforced by the scorer, and a violation is expensive out of
proportion to its size: a row the scorer rejects does not cost a row, it costs one of
eighteen submissions the team will ever have. So the rules are checked before the file
is written rather than after it is uploaded.

The rules, as the scorer applies them:

* ``proband_id`` must be exactly ``PROBAND01`` (matched after ``strip()``, case-sensitive);
* at most 10 rows, ranked by descending ``epcr``, ties broken by file order;
* ``epcr`` in the half-open interval (0, 1];
* ``finding_type`` exactly ``primary`` or ``secondary``;
* a pair goes in ONE row via the ``*_2`` columns — two variants split across two rows
  score partial credit only, never a full match.

Distinct epcr values are required rather than merely recommended. Equal values leave the
rank order decided by file position, and an oracle probe is decoded from the *rank* the
scorer reports, so an ambiguous rank makes the reply unreadable.

Three surfaces, one rule set. :func:`problems` *enumerates* every violation (what an
interactive builder needs: show them all at once), :func:`validate` raises on the first
(what a pipeline needs: stop), and :func:`read_submission` parses a written file back
**the way the scorer parses it** — verbatim strings, no contig normalization — so a
round trip through the CSV is a real check on the spelling that goes over the wire.
"""

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TextIO

from .variant import Variant

PROBAND_ID = "PROBAND01"
MAX_ROWS = 10
FINDING_TYPES = ("primary", "secondary")

HEADER = [
    "proband_id",
    "chrom_1",
    "pos_1",
    "ref_1",
    "alt_1",
    "chrom_2",
    "pos_2",
    "ref_2",
    "alt_2",
    "epcr",
    "finding_type",
    "notes",
]


@dataclass
class Row:
    """One submission row: a single variant, or a compound-heterozygous pair."""

    variant: Variant
    partner: Variant | None = None
    epcr: float = 0.5
    finding_type: str = "primary"
    notes: str = ""

    def variants(self) -> frozenset[Variant]:
        """The alleles this row claims, as the scorer holds them.

        A ``frozenset``, so order within a pair row is irrelevant and a row whose two
        variants are identical *is* a single-variant row — challenge intel §8.2.
        """
        if self.partner is None:
            return frozenset({self.variant})
        return frozenset({self.variant, self.partner})

    def as_fields(self) -> list[str]:
        """Render as the twelve CSV columns, blanking the pair columns for a single."""
        v, p = self.variant, self.partner
        return [
            PROBAND_ID,
            v.chrom,
            str(v.pos),
            v.ref,
            v.alt,
            p.chrom if p else "",
            str(p.pos) if p else "",
            p.ref if p else "",
            p.alt if p else "",
            _format_epcr(self.epcr),
            self.finding_type,
            self.notes,
        ]


def write_submission(rows: list[Row], out: TextIO) -> None:
    """Validate ``rows`` and write them to ``out`` in descending-epcr rank order."""
    validate(rows)
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(HEADER)
    for row in sorted(rows, key=lambda r: r.epcr, reverse=True):
        writer.writerow(row.as_fields())


def validate(rows: list[Row], require_descending: bool = False) -> None:
    """Raise ``ValueError`` on the first thing the scorer would reject or rank ambiguously."""
    for problem in problems(rows, require_descending):
        raise ValueError(problem)


def problems(rows: list[Row], require_descending: bool = False) -> list[str]:
    """Every rule violation in ``rows``, in file order — the enumerating form of ``validate``.

    Row-scoped messages carry a ``row N:`` prefix, 1-based on **file** position, because
    the caller showing them has a row to point at.

    ``require_descending`` adds the one rule the scorer does not have and a builder does:
    file order must already *be* rank order. The scorer sorts, so a shuffled file scores
    identically — but then the rows a human reads and the ranks a probe is decoded from
    are two different orderings, and every reading of the reply has to re-sort by hand.
    """
    found: list[str] = []
    if not rows:
        return ["a submission needs at least one row"]
    if len(rows) > MAX_ROWS:
        found.append(f"a submission may hold at most {MAX_ROWS} rows, got {len(rows)}")

    for index, row in enumerate(rows, start=1):
        if not 0 < row.epcr <= 1:
            found.append(f"row {index}: epcr must lie in (0, 1], got {row.epcr}")
        if row.finding_type not in FINDING_TYPES:
            found.append(
                f"row {index}: finding_type must be one of {FINDING_TYPES}, "
                f"got {row.finding_type!r}"
            )

    epcrs = [_format_epcr(r.epcr) for r in rows]
    if len(set(epcrs)) != len(epcrs):
        found.append(
            "epcr values must be distinct: equal values leave rank order decided by "
            "file position, which makes an oracle probe impossible to decode"
        )
    if require_descending:
        found.extend(_descending_problems(epcrs))
    return found


def read_submission(source: TextIO) -> list[Row]:
    """Parse a written submission back, **exactly as the scorer parses it**.

    The scorer's key is ``(chrom.strip(), int(pos), ref.upper(), alt.upper())`` and it
    never normalizes the contig, so neither does this: whatever ``chr`` spelling reached
    the file is what comes back. That is the point — reading with
    :meth:`Variant.from_vcf` would re-prefix and hide exactly the bug this is for.

    Raises ``ValueError`` on a header or a ``proband_id`` the scorer would not accept.
    """
    reader = csv.reader(source)
    try:
        header = next(reader)
    except StopIteration:
        raise ValueError("an empty file is not a submission") from None
    if header != HEADER:
        raise ValueError(f"header must be {','.join(HEADER)}, got {','.join(header)}")

    rows: list[Row] = []
    for index, fields in enumerate(reader, start=1):
        if not fields:
            continue
        if len(fields) != len(HEADER):
            raise ValueError(f"row {index}: expected {len(HEADER)} fields, got {len(fields)}")
        proband, notes = fields[0].strip(), fields[11]
        if proband != PROBAND_ID:
            raise ValueError(f"row {index}: proband_id must be {PROBAND_ID}, got {proband!r}")
        variant = _parse_variant(fields[1:5])
        if variant is None:
            raise ValueError(f"row {index}: primary variant columns (chrom/pos) must not be blank")
        rows.append(
            Row(
                variant=variant,
                partner=_parse_variant(fields[5:9]),
                epcr=float(fields[9]),
                finding_type=fields[10],
                notes=notes,
            )
        )
    return rows


def _parse_variant(fields: list[str]) -> Variant | None:
    """One four-column allele, verbatim. Blank ``chrom`` or ``pos`` means no variant."""
    chrom, pos, ref, alt = fields
    if not chrom.strip() or not pos.strip():
        return None
    return Variant(chrom.strip(), int(pos), ref.upper(), alt.upper())


def _descending_problems(epcrs: list[str]) -> Iterable[str]:
    """Name each row that does not sit below the one before it."""
    for index in range(1, len(epcrs)):
        if float(epcrs[index]) >= float(epcrs[index - 1]):
            yield (
                f"row {index + 1}: epcr {epcrs[index]} is not below row {index}'s "
                f"{epcrs[index - 1]} — file order must already be rank order"
            )


def _format_epcr(value: float) -> str:
    """Render without trailing zeros so 0.95 stays 0.95 rather than 0.9500000000000001."""
    return f"{value:.10g}"
