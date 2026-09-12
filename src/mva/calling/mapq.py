"""Where the aligner was unsure — the gate that decides which genes may be reported on.

**Mapping quality (MAPQ)** is the aligner's own phred-scaled statement of how likely it is
that a read belongs where it was put. ``MAPQ 0`` is the special value every short-read
aligner uses for "this sequence occurs in more than one place and I picked one at random".
It is not a low score; it is a refusal to answer.

**Why this runs before any model is fitted.** A baited region that is repetitive collects
reads from its paralogues, and neither the bait's uniqueness filter nor a k-mer count can
see that: the bait filter dropped the k-mers it *knew* were repeated (8.79 % of them), and
a k-mer counter has no notion of where a read came from at all. The aligner does, and it
already wrote its opinion into a BAM that exists. So one pass over that BAM says, per gene,
what fraction of its reads the aligner declined to place — and a gene whose reads pile at
MAPQ 0 is a gene whose counts mean something other than what they appear to mean, *before*
a negative binomial is fitted to them.

**Counted per interval, not per read.** Reads are tallied by binary-searching each
interval's bounds into the contig's sorted alignment starts. That makes a read overlapping
two genes count for both, which is the honest answer for a per-gene profile, and it avoids
having to decide an ownership rule that does not exist in the data. The cost is the usual
edge effect of tallying by alignment start: a read whose start lies just before an interval
is not counted for it, so an interval's tally is short by at most one read length at its
left edge. Stated here rather than corrected, because the quantity of interest is a
*fraction* and both numerator and denominator lose the same reads.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import polars as pl

from .tools import Provenance, pipe, started_now

#: SAM flags excluded from the tally: unmapped (0x4), secondary (0x100), supplementary
#: (0x800). A secondary alignment is the same read placed a second time, and counting it
#: would inflate exactly the repetitive regions this measurement exists to find.
EXCLUDE_FLAGS = "0x904"

#: Columns 3, 4 and 5 of a SAM record: reference name, leftmost position, MAPQ.
SAM_COLUMNS = "3,4,5"


@dataclass(frozen=True)
class RegionMapq:
    """The aligner's confidence over one named interval."""

    name: str
    reads: int
    mapq0: int
    median_mapq: float
    mean_mapq: float

    @property
    def mapq0_fraction(self) -> float:
        """Share of this interval's reads the aligner refused to place uniquely."""
        return self.mapq0 / self.reads if self.reads else 0.0


@dataclass(frozen=True)
class MapqProfile:
    """Per-interval confidence, plus the reads that fell outside every interval."""

    regions: tuple[RegionMapq, ...]
    off_target: RegionMapq
    reads_total: int
    manifest: Path
    table: Path

    def unreachable(self, ceiling: float) -> tuple[RegionMapq, ...]:
        """Intervals whose MAPQ-0 fraction exceeds a threshold — the gate's own query."""
        return tuple(row for row in self.regions if row.mapq0_fraction > ceiling)


def _read_sam_columns(path: Path) -> pl.DataFrame:
    """The three-column dump, sorted by contig and position so a search can index it."""
    frame = pl.read_csv(
        path,
        separator="\t",
        has_header=False,
        new_columns=["contig", "pos", "mapq"],
        schema_overrides={"contig": pl.Utf8, "pos": pl.Int64, "mapq": pl.Int32},
    )
    return frame.sort(["contig", "pos"])


def _stats(name: str, mapq: np.ndarray) -> RegionMapq:
    if mapq.size == 0:
        return RegionMapq(name=name, reads=0, mapq0=0, median_mapq=0.0, mean_mapq=0.0)
    return RegionMapq(
        name=name,
        reads=int(mapq.size),
        mapq0=int((mapq == 0).sum()),
        median_mapq=float(np.median(mapq)),
        mean_mapq=round(float(mapq.mean()), 2),
    )


def _tally(
    frame: pl.DataFrame, intervals: list[tuple[str, int, int, str]]
) -> tuple[list[RegionMapq], np.ndarray, dict[str, np.ndarray]]:
    """Per-interval statistics, and a mask of which reads any interval claimed."""
    by_contig: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    claimed: dict[str, np.ndarray] = {}
    offset = 0
    for contig, part in frame.group_by("contig", maintain_order=True):
        name = str(contig[0])
        pos = part["pos"].to_numpy()
        mapq = part["mapq"].to_numpy()
        by_contig[name] = (pos, mapq, np.arange(offset, offset + pos.size))
        claimed[name] = np.zeros(pos.size, dtype=bool)
        offset += pos.size

    # Intervals sharing a label are one region: a gene is several baited intervals, and a
    # median over its reads is not recoverable from per-interval medians, so the slices are
    # gathered first and the statistics computed once per label.
    slices: dict[str, list[np.ndarray]] = {}
    for contig, start, end, label in intervals:
        slices.setdefault(label, [])
        found = by_contig.get(contig)
        if found is None:
            continue
        pos, mapq, _ = found
        # BED is half-open and 0-based; SAM's POS is 1-based, so the interval [start, end)
        # is the SAM range [start + 1, end].
        lo = int(np.searchsorted(pos, start + 1, side="left"))
        hi = int(np.searchsorted(pos, end, side="right"))
        claimed[contig][lo:hi] = True
        slices[label].append(mapq[lo:hi])

    rows = [
        _stats(label, np.concatenate(parts) if parts else np.empty(0, dtype=np.int32))
        for label, parts in slices.items()
    ]

    loose = [by_contig[name][1][~mask] for name, mask in claimed.items() if name in by_contig]
    off = np.concatenate(loose) if loose else np.empty(0, dtype=np.int32)
    return rows, off, claimed


def per_region(
    bam: Path,
    intervals: list[tuple[str, int, int, str]],
    out_dir: Path,
    *,
    stem: str = "mapq",
) -> MapqProfile:
    """One `samtools view` pass, tallied into the supplied named intervals.

    ``intervals`` are BED-style ``(contig, start, end, name)`` tuples; they may overlap,
    and a read inside two of them counts for both. The intermediate three-column dump is
    kept beside the manifest: it is the only artifact that would let someone re-derive a
    different statistic from the same pass without re-reading the BAM.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    dump = out_dir / f"{stem}.sam-columns.tsv"
    provenance: Provenance = started_now("mapq")
    provenance.inputs = {"bam": str(bam)}
    provenance.parameters = {
        "tool": "samtools view",
        "exclude_flags": EXCLUDE_FLAGS,
        "columns": SAM_COLUMNS,
        "intervals": len(intervals),
        "assignment": "alignment start, binary-searched per interval; overlaps counted twice",
    }
    provenance.invocations.extend(
        pipe(
            [
                ["samtools", "view", "-F", EXCLUDE_FLAGS, str(bam)],
                ["cut", "-f", SAM_COLUMNS],
            ],
            stdout=dump,
        )
    )

    frame = _read_sam_columns(dump)
    rows, off, _ = _tally(frame, intervals)
    table = write_table(rows, out_dir / f"{stem}.tsv")
    provenance.outputs = {
        "dump": str(dump),
        "table": str(table),
        "reads": str(frame.height),
        "off_target_reads": str(int(off.size)),
    }
    manifest = provenance.write(out_dir / f"{stem}.provenance.json")
    return MapqProfile(
        regions=tuple(rows),
        off_target=_stats("__off_target__", off),
        reads_total=int(frame.height),
        manifest=manifest,
        table=table,
    )


def write_table(rows: list[RegionMapq], path: Path) -> Path:
    """The profile as a TSV carrying a name and four counts — never a coordinate."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["name", "reads", "mapq0", "mapq0_fraction", "median_mapq", "mean_mapq"])
        for row in rows:
            writer.writerow(
                [
                    row.name,
                    row.reads,
                    row.mapq0,
                    f"{row.mapq0_fraction:.6f}",
                    f"{row.median_mapq:.1f}",
                    f"{row.mean_mapq:.2f}",
                ]
            )
    return path


def summarise(profile: MapqProfile, ceiling: float = 0.5) -> dict[str, object]:
    """The gate's numbers: how confident the aligner was, and where it was not."""
    measured = [row for row in profile.regions if row.reads]
    fractions = sorted(row.mapq0_fraction for row in measured)
    worst = sorted(measured, key=lambda row: row.mapq0_fraction, reverse=True)[:10]
    return {
        "reads_total": profile.reads_total,
        "regions": len(profile.regions),
        "regions_with_reads": len(measured),
        "off_target_reads": profile.off_target.reads,
        "off_target_mapq0_fraction": round(profile.off_target.mapq0_fraction, 6),
        "off_target_median_mapq": profile.off_target.median_mapq,
        "median_region_mapq0_fraction": round(fractions[len(fractions) // 2], 6)
        if fractions
        else 0.0,
        "ceiling": ceiling,
        "above_ceiling": len(profile.unreachable(ceiling)),
        "worst": [(row.name, round(row.mapq0_fraction, 4), row.reads) for row in worst],
    }


__all__ = ["MapqProfile", "RegionMapq", "per_region", "summarise", "write_table"]
