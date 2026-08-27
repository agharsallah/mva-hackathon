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
"""

import csv
from dataclasses import dataclass
from typing import TextIO

from .variant import Variant

PROBAND_ID = "PROBAND01"
MAX_ROWS = 10
FINDING_TYPES = ("primary", "secondary")

HEADER = [
    "proband_id", "chrom_1", "pos_1", "ref_1", "alt_1",
    "chrom_2", "pos_2", "ref_2", "alt_2", "epcr", "finding_type", "notes",
]


@dataclass
class Row:
    """One submission row: a single variant, or a compound-heterozygous pair."""

    variant: Variant
    partner: Variant | None = None
    epcr: float = 0.5
    finding_type: str = "primary"
    notes: str = ""

    def as_fields(self) -> list[str]:
        v, p = self.variant, self.partner
        return [
            PROBAND_ID,
            v.chrom, str(v.pos), v.ref, v.alt,
            p.chrom if p else "", str(p.pos) if p else "", p.ref if p else "", p.alt if p else "",
            _format_epcr(self.epcr), self.finding_type, self.notes,
        ]


def write_submission(rows: list[Row], out: TextIO) -> None:
    """Validate ``rows`` and write them to ``out`` in descending-epcr rank order."""
    validate(rows)
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(HEADER)
    for row in sorted(rows, key=lambda r: r.epcr, reverse=True):
        writer.writerow(row.as_fields())


def validate(rows: list[Row]) -> None:
    """Raise ``ValueError`` on anything the scorer would reject or rank ambiguously."""
    if not rows:
        raise ValueError("a submission needs at least one row")
    if len(rows) > MAX_ROWS:
        raise ValueError(f"a submission may hold at most {MAX_ROWS} rows, got {len(rows)}")

    for row in rows:
        if not 0 < row.epcr <= 1:
            raise ValueError(f"epcr must lie in (0, 1], got {row.epcr}")
        if row.finding_type not in FINDING_TYPES:
            raise ValueError(
                f"finding_type must be one of {FINDING_TYPES}, got {row.finding_type!r}"
            )

    epcrs = [_format_epcr(r.epcr) for r in rows]
    if len(set(epcrs)) != len(epcrs):
        raise ValueError(
            "epcr values must be distinct: equal values leave rank order decided by "
            "file position, which makes an oracle probe impossible to decode"
        )


def _format_epcr(value: float) -> str:
    """Render without trailing zeros so 0.95 stays 0.95 rather than 0.9500000000000001."""
    return f"{value:.10g}"
