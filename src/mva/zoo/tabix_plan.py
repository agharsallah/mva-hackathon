"""Which slices of a huge published table does *this* case need?

The half of the tabix subset that touches nothing: given the record set, it decides the
**regions** — closed intervals of one contig — that a range-reading client must ask for, and
writes them as BED. Split out of :mod:`mva.zoo.tabix_subset` so the arithmetic can be tested
without a network, a binary, or a 37 GB file anywhere in sight.

The one judgement call is ``merge_gap``. One index seek costs a measured ~0.3 s over HTTPS
whatever it returns, so asking for two positions 40 bases apart separately costs twice what
asking for the span between them does, and returns less. Merging neighbours trades a few
unwanted rows for far fewer seeks.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "DEFAULT_GAP",
    "Region",
    "merge_positions",
    "shard",
    "snv_positions",
    "snv_regions",
    "write_bed",
]

#: Merge two wanted positions into one region when they are this close. 1,000 bases was
#: measured on the real record set: 35,881 positions collapse to 21,722 regions (a 39 % cut
#: in seeks) while the span stays at ~3.1 Mb, which is nothing next to a 3.1 Gb genome.
DEFAULT_GAP = 1_000


@dataclass(frozen=True)
class Region:
    """One closed interval of one contig, in 1-based inclusive coordinates (tabix's own)."""

    contig: str
    start: int
    end: int

    def bed_line(self) -> str:
        """The BED spelling: half-open, 0-based start — the format ``tabix -R`` reads."""
        return f"{self.contig}\t{self.start - 1}\t{self.end}\n"

    @property
    def span(self) -> int:
        return self.end - self.start + 1


def snv_positions(records_parquet: Path | str, *, connection: Any = None) -> list[tuple[str, int]]:
    """Every distinct ``(contig, position)`` carrying an **SNV** allele, sorted.

    Only single-base substitutions: a published all-possible-SNV table has no row for an
    insertion or a deletion, so asking for one would buy seeks and no scores. The caller
    reports that gap as coverage rather than hiding it here.
    """
    import duckdb

    source = Path(records_parquet)
    if not source.exists():
        raise FileNotFoundError(f"no record set at {source}; run `mva-zoo records` first")
    con = connection or duckdb.connect()
    rows = con.execute(
        "SELECT DISTINCT upper(regexp_replace(CAST(chrom AS VARCHAR), '^(chr|CHR)', '')) AS contig,"
        " CAST(pos AS BIGINT) AS pos FROM read_parquet(?)"
        " WHERE length(ref) = 1 AND length(alt) = 1 ORDER BY contig, pos",
        [str(source)],
    ).fetchall()
    return [(str(row[0]), int(row[1])) for row in rows]


def snv_regions(
    records_parquet: Path | str,
    *,
    merge_gap: int = DEFAULT_GAP,
    connection: Any = None,
) -> list[Region]:
    """The merged regions covering every SNV allele in a record set."""
    return merge_positions(
        snv_positions(records_parquet, connection=connection), merge_gap=merge_gap
    )


def merge_positions(
    positions: Iterable[tuple[str, int]], *, merge_gap: int = DEFAULT_GAP
) -> list[Region]:
    """Collapse sorted ``(contig, position)`` pairs into regions, merging near neighbours."""
    regions: list[Region] = []
    for contig, position in positions:
        if regions and regions[-1].contig == contig and position - regions[-1].end <= merge_gap:
            regions[-1] = Region(contig, regions[-1].start, max(regions[-1].end, position))
        else:
            regions.append(Region(contig, position, position))
    return regions


def write_bed(regions: Sequence[Region], path: Path) -> int:
    """Write regions as BED. Returns the line count; the file stays under ``build/``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(region.bed_line() for region in regions))
    return len(regions)


def shard(regions: Sequence[Region], jobs: int) -> list[list[Region]]:
    """Split regions into ``jobs`` contiguous blocks — contiguity keeps each worker's
    seeks moving forward through the file, which is the cheap direction."""
    count = max(1, min(int(jobs), len(regions) or 1))
    size = -(-len(regions) // count)
    return [list(regions[start : start + size]) for start in range(0, len(regions), size)]
