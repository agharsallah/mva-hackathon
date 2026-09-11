"""Read a gene model and a tiered gene list into padded intervals.

The seam between "a list of genes someone chose" and "the stretches of reference to cut
k-mers from". Both halves are plain tables — a gene model with one row per coding interval,
and one or more gene lists with a tier per gene — so this module takes column names rather
than assuming a schema, and no caller has to re-derive the padding rule.

**Padding is per tier because the question is per tier.** A gene under structural suspicion
needs reference reach far beyond its exons, because a deletion that removes one has its
breakpoints deep in the introns around it; a gene being screened for coding and splice
alleles needs a couple of kilobases. Which tiers get which is the caller's decision,
declared once here rather than implied by an `if` somewhere downstream.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path

from .bait import Interval


def read_rows(path: Path) -> list[dict[str, str]]:
    """A tab-separated table as dicts — every reader here takes the same shape."""
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def read_gene_model(
    path: Path,
    *,
    contig: str = "chrom",
    start: str = "start",
    end: str = "end",
    gene: str = "gene",
) -> dict[str, list[Interval]]:
    """Intervals per gene symbol, from a gene-model table."""
    by_gene: dict[str, list[Interval]] = defaultdict(list)
    for row in read_rows(path):
        by_gene[row[gene]].append(Interval(row[contig], int(row[start]), int(row[end])))
    return dict(by_gene)


def read_tiers(
    sources: Sequence[tuple[Path, str | None]],
    *,
    symbol: str = "symbol",
    tier: str = "tier",
) -> dict[str, str]:
    """Gene symbol -> tier, merging several lists.

    Each source is ``(path, default_tier)``: a list that carries its own ``tier`` column
    passes ``None``, a list that is entirely one tier names it. The first source to claim
    a symbol keeps it, so a gene appearing in both a target list and a decoy list is a
    target — which is the only sane resolution, and one a caller should not have to
    remember.
    """
    tiers: dict[str, str] = {}
    for path, default in sources:
        for row in read_rows(path):
            tiers.setdefault(row[symbol], default or row[tier])
    return tiers


def pad_by_tier(
    tier_of: dict[str, str],
    by_gene: dict[str, list[Interval]],
    *,
    wide_tiers: Iterable[str],
    wide_pad: int,
    narrow_pad: int,
) -> tuple[list[Interval], dict[str, dict[str, int]], list[str]]:
    """Padded intervals for every gene, per-tier counts, and the genes with no model entry.

    The third return value is not an error list to swallow: a gene absent from the model
    is a gene this bait cannot reach, and naming it is how that becomes a stated blind spot
    rather than a silent omission.
    """
    from .bait import plan

    wide = set(wide_tiers)
    padded: list[Interval] = []
    per_tier: dict[str, dict[str, int]] = defaultdict(lambda: {"genes": 0, "bases": 0})
    missing: list[str] = []
    for gene, tier in sorted(tier_of.items()):
        intervals = by_gene.get(gene)
        if not intervals:
            missing.append(gene)
            continue
        widened = [
            interval.padded(wide_pad if tier in wide else narrow_pad) for interval in intervals
        ]
        per_tier[tier]["genes"] += 1
        per_tier[tier]["bases"] += plan(widened).bases
        padded.extend(widened)
    return padded, dict(per_tier), missing


def padded_by_gene(
    tier_of: dict[str, str],
    by_gene: dict[str, list[Interval]],
    *,
    wide_tiers: Iterable[str],
    wide_pad: int,
    narrow_pad: int,
) -> dict[str, list[Interval]]:
    """The same padding, kept labelled per gene — the input :func:`mva.kmer.bait.profile` takes."""
    wide = set(wide_tiers)
    labelled: dict[str, list[Interval]] = {}
    for gene, tier in tier_of.items():
        intervals = by_gene.get(gene)
        if intervals:
            pad = wide_pad if tier in wide else narrow_pad
            labelled[gene] = [interval.padded(pad) for interval in intervals]
    return labelled
