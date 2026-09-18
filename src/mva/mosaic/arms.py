"""Which arm a call sits on — and the check that the reference geometry is the right one.

The arm assignment itself happens in SQL, against ``warehouse.cytoband_arms``, because the
positions are already in the database and moving millions of them into Python to compare
each against one number would be the wrong place to do it. What lives here is everything
*about* that assignment that a reader should be able to check:

* :func:`centromere_gap` — where the heterozygous calls actually stop, read from the
  karyogram's per-megabase bins. This is the shortcut the plan considered and rejected as a
  *source* for the boundary, and it is exactly right as a *check* on it: if the committed
  centromere and the observed gap disagree by more than a few megabases, one of them is
  about a different assembly.
* :func:`check` — that comparison over every metacentric autosome, with the acrocentrics
  excluded by name of their own flag rather than by a hard-coded list.

**Why the gap is not the source.** ``results.baf_bins`` emits no row for a megabase with no
heterozygous call, so an empty bin is a hole in a sequence rather than a flagged value; the
five acrocentric chromosomes put their largest hole at the start of the chromosome, not at
the centromere; and the heterochromatic blocks on 1q, 9q and 16q produce competing holes
elsewhere. A rule that survives none of those three is not a source of truth. As a check it
is unaffected by all of them, because a check is allowed to be approximate.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise

__all__ = [
    "TOLERANCE_BP",
    "ArmCheck",
    "centromere_gap",
    "check",
    "disagreements",
]

#: How far the observed gap may sit from the committed centromere before it is a finding.
#: Three megabases: pericentromeric heterochromatin extends past the band boundary, so the
#: gap is legitimately wider than the acen bands, and a tighter tolerance would fail on
#: correct data.
TOLERANCE_BP = 3_000_000

BP_PER_MB = 1_000_000


def centromere_gap(bins: Sequence[int]) -> tuple[int, int] | None:
    """The widest run of megabases with no heterozygous call, as ``(start_bp, end_bp)``.

    ``bins`` is the sorted list of megabase indices that *do* carry calls — the ``mb``
    column of ``results.baf_bins`` for one chromosome. ``None`` when there is no interior
    gap at all.
    """
    widest: tuple[int, int] | None = None
    for left, right in pairwise(bins):
        if widest is None or (right - left) > (widest[1] - widest[0]):
            widest = (left, right)
    if widest is None or widest[1] - widest[0] < 2:
        return None
    return ((widest[0] + 1) * BP_PER_MB, widest[1] * BP_PER_MB)


@dataclass(frozen=True)
class ArmCheck:
    """One chromosome's committed centromere against the gap the calls actually leave."""

    chrom: str
    cen_start: int
    cen_end: int
    gap_start: int | None
    gap_end: int | None
    acrocentric: bool

    @property
    def observed(self) -> bool:
        return self.gap_start is not None and self.gap_end is not None

    @property
    def offset_bp(self) -> int | None:
        """How far the gap's midpoint sits from the centromere's. ``None`` when no gap."""
        if not self.observed:
            return None
        assert self.gap_start is not None and self.gap_end is not None
        return abs((self.gap_start + self.gap_end) // 2 - (self.cen_start + self.cen_end) // 2)

    @property
    def agrees(self) -> bool:
        """Acrocentrics are exempt: their largest gap is the short arm, by construction."""
        if self.acrocentric or not self.observed:
            return True
        offset = self.offset_bp
        return offset is not None and offset <= TOLERANCE_BP

    def as_dict(self) -> dict[str, object]:
        return {
            "chrom": self.chrom,
            "acrocentric": self.acrocentric,
            "observed_gap": self.observed,
            "offset_mb": None if self.offset_bp is None else round(self.offset_bp / BP_PER_MB, 2),
            "agrees": self.agrees,
        }


def check(
    geometry: Mapping[str, Mapping[str, int | bool]],
    bins_by_chrom: Mapping[str, Sequence[int]],
) -> list[ArmCheck]:
    """Compare every chromosome's committed centromere against its observed call gap.

    ``geometry`` is ``warehouse.cytoband_arms`` keyed by contig; ``bins_by_chrom`` is the
    ``mb`` values present in ``results.baf_bins`` for each. A chromosome missing from either
    is skipped rather than assumed, which is why the return is a list and not a verdict.
    """
    checks: list[ArmCheck] = []
    for chrom, row in sorted(geometry.items()):
        bins = bins_by_chrom.get(chrom)
        if bins is None:
            continue
        gap = centromere_gap(sorted(bins))
        checks.append(
            ArmCheck(
                chrom=chrom,
                cen_start=int(row["cen_start"]),
                cen_end=int(row["cen_end"]),
                gap_start=None if gap is None else gap[0],
                gap_end=None if gap is None else gap[1],
                acrocentric=bool(row["acrocentric"]),
            )
        )
    return checks


def disagreements(checks: Iterable[ArmCheck]) -> list[ArmCheck]:
    """The chromosomes whose geometry and data disagree — the only rows worth reporting."""
    return [item for item in checks if not item.agrees]
