"""How many copies of this exon are there — counted, with no alignment and no caller.

A region present twice puts its k-mers into roughly twice as many reads as a region present
once. So copy number is a **ratio**, and the whole difficulty is the denominator: reads are
not spread evenly over the genome, and dividing by a genome-wide average would read every
GC-rich exon as a deletion.

**The local flank is the denominator, and the genome is the cross-check.** GeneToCN's
finding (Pajuste 2023) is that k-mers from the sequence immediately either side of a region
share its coverage bias, so dividing by them cancels it. This module computes both — local
flank and genome-wide — and reports the **disagreement between them** as a column rather
than picking one, because a region where the two denominators differ is a region where the
local sequence is unusual, and that is worth seeing.

.. code::

    copy number  =  2 x median(region k-mer counts) / median(flank k-mer counts)

Two is the convention: a diploid region reads as 2.0, a heterozygous deletion as 1.0.

**Exon scale is not free, and is not assumed.** GeneToCN's smallest validated unit is
5.5 kb, and it judged 268 gene-specific k-mers unreliable against 3,095 reliable. A coding
exon is often a few hundred bases. So an exon is estimated **only where it retains at least
300 surviving unique k-mers**, and below that it is pooled into its gene and *labelled as
pooled* — the plan's conditional, not a deferral. Every estimate carries the k-mer count it
was computed from, so a reader never has to take the resolution on trust.

**The deletion threshold is measured on this sample, not imported.** A "low" copy number
means low *compared to what*. The comparison is a null band: the same arithmetic run over a
thousand exons that have no reason to be deleted, whose spread is what normal looks like
here, at this depth, with this bait. An exon below that band's 2.5th percentile is a
candidate; an exon inside it is not, however low the number sounds.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import numpy as np

#: Surviving unique k-mers an exon needs before it is estimated on its own. Below this it is
#: pooled to its gene. GeneToCN called 268 unreliable and 3,095 reliable; 300 is the plan's
#: pre-registered line between them, chosen before any exon was measured.
MIN_EXON_KMERS = 300

#: Flanking k-mers a gene needs for a local denominator, split between its two sides
#: (GeneToCN, Methods p. 7). Below this the local denominator is not computed and the
#: genome-wide one carries the estimate alone — which is recorded, not hidden.
MIN_FLANK_KMERS = 2_000

#: The null band's lower tail. An exon below it is a deletion candidate.
DELETION_PERCENTILE = 2.5

#: Copies a normal autosomal region has. The scale, stated once.
DIPLOID = 2.0


@dataclass(frozen=True)
class Region:
    """One unit being measured — an exon, or a whole gene when its exons were too thin."""

    gene: str
    label: str
    counts: np.ndarray
    pooled: bool = False

    @property
    def kmers(self) -> int:
        return int(self.counts.size)

    @property
    def median(self) -> float:
        return float(np.median(self.counts)) if self.counts.size else 0.0


@dataclass(frozen=True)
class Estimate:
    """A copy number, both denominators, and the resolution it was computed at."""

    gene: str
    label: str
    kmers: int
    pooled: bool
    median_count: float
    local: float | None
    genome_wide: float

    @property
    def disagreement(self) -> float | None:
        """How far the two denominators differ, as a fraction of the local estimate.

        Not an error term. A region whose local flank says 2.0 and whose genome-wide
        denominator says 1.4 is a region whose neighbourhood is deeper than the genome, and
        that is a property of the sequence worth reporting next to the number."""
        if self.local is None or self.local == 0:
            return None
        return abs(self.genome_wide - self.local) / self.local

    @property
    def best(self) -> float:
        """The estimate to read: local where it exists, genome-wide where it does not."""
        return self.genome_wide if self.local is None else self.local


@dataclass(frozen=True)
class NullBand:
    """What a normal copy number looks like on this sample, at this depth, with this bait."""

    low: float
    high: float
    median: float
    regions: int
    percentile: float

    def contains(self, value: float) -> bool:
        return self.low <= value <= self.high


def pool_thin_exons(
    regions: Iterable[Region], *, minimum: int = MIN_EXON_KMERS
) -> tuple[list[Region], dict[str, int]]:
    """Keep exons that carry enough k-mers; pool the rest into their gene.

    Returns the regions to estimate and a count of what happened, because "this gene was
    measured at gene resolution" is a fact about the answer, not an implementation detail.
    """
    kept: list[Region] = []
    thin: dict[str, list[np.ndarray]] = {}
    report = {"exon_scale": 0, "pooled_exons": 0, "pooled_genes": 0}
    for region in regions:
        if region.kmers >= minimum:
            kept.append(region)
            report["exon_scale"] += 1
        else:
            thin.setdefault(region.gene, []).append(region.counts)
            report["pooled_exons"] += 1
    for gene, parts in thin.items():
        joined = np.concatenate(parts) if parts else np.empty(0)
        kept.append(Region(gene=gene, label=gene, counts=joined, pooled=True))
        report["pooled_genes"] += 1
    return kept, report


def estimate(
    regions: Sequence[Region],
    flank_median: dict[str, float],
    genome_median: float,
) -> list[Estimate]:
    """Copy number per region against both denominators.

    ``flank_median`` is the median count of a gene's flanking k-mers; a gene absent from it
    had too few flanking k-mers to qualify, and its estimate carries ``local = None`` rather
    than a denominator built from too little.
    """
    found: list[Estimate] = []
    for region in regions:
        local_denominator = flank_median.get(region.gene)
        found.append(
            Estimate(
                gene=region.gene,
                label=region.label,
                kmers=region.kmers,
                pooled=region.pooled,
                median_count=region.median,
                local=(DIPLOID * region.median / local_denominator if local_denominator else None),
                genome_wide=(DIPLOID * region.median / genome_median if genome_median else 0.0),
            )
        )
    return found


def null_band(values: Sequence[float], *, percentile: float = DELETION_PERCENTILE) -> NullBand:
    """The spread of copy number over regions with no reason to be anything but diploid.

    The threshold every deletion claim is read against. Computed here rather than imported,
    because "low" depends on this sample's depth, this bait's density and this run's
    dispersion — none of which a published cut-off knows about.
    """
    array = np.asarray([value for value in values if np.isfinite(value)], dtype=float)
    if array.size == 0:
        return NullBand(low=0.0, high=0.0, median=0.0, regions=0, percentile=percentile)
    return NullBand(
        low=float(np.percentile(array, percentile)),
        high=float(np.percentile(array, 100.0 - percentile)),
        median=float(np.median(array)),
        regions=int(array.size),
        percentile=percentile,
    )


def below_band(estimates: Iterable[Estimate], band: NullBand) -> list[Estimate]:
    """Regions under the null band's lower tail — the deletion candidates, and nothing else.

    An estimate whose value merely *sounds* low is not here. That is the point of the band.
    """
    return [row for row in estimates if row.best < band.low]


def summarise(estimates: Sequence[Estimate], band: NullBand) -> dict[str, object]:
    """The gate's numbers: resolution, both denominators, and what fell out of the band."""
    values = np.asarray([row.best for row in estimates], dtype=float)
    gaps = [row.disagreement for row in estimates if row.disagreement is not None]
    low = below_band(estimates, band)
    return {
        "regions": len(estimates),
        "exon_scale": sum(1 for row in estimates if not row.pooled),
        "pooled": sum(1 for row in estimates if row.pooled),
        "without_local_denominator": sum(1 for row in estimates if row.local is None),
        "median_copy_number": round(float(np.median(values)), 4) if values.size else 0.0,
        "null_band_low": round(band.low, 4),
        "null_band_high": round(band.high, 4),
        "null_band_regions": band.regions,
        "median_denominator_disagreement": round(float(np.median(gaps)), 4) if gaps else None,
        "below_band": len(low),
        "below_band_labels": [row.label for row in low[:50]],
    }


__all__ = [
    "DELETION_PERCENTILE",
    "DIPLOID",
    "MIN_EXON_KMERS",
    "MIN_FLANK_KMERS",
    "Estimate",
    "NullBand",
    "Region",
    "below_band",
    "estimate",
    "null_band",
    "pool_thin_exons",
    "summarise",
]
