"""Per-region depth — the evidence behind every "there is nothing here".

**Depth** is how many reads cover a given base. It is the quantity that decides whether an
absence means anything: a gene with no second allele at 40x is a finding, the same gene at
3x is a gap in the data wearing a finding's clothes. So every claim step 2 makes about a
gene not carrying something is reported beside the depth of the exons that claim covers.

**mosdepth rather than `samtools depth`**, because the question is per region and not per
base: mosdepth walks the BAM's index once and accumulates into the supplied intervals,
where a per-base dump of 42 Mb would be written and re-aggregated for nothing.

**Baited coverage is not genome coverage, and the difference is the point.** Inside a
baited region depth should approach the delivery's genome-wide 44x, because the recovery
kept the reads that belong there. Where it does not, exactly one of three things is true —
the bait could not reach that sequence (measured separately, per gene), the aligner could
not place reads there uniquely, or the sample really has less DNA there. The third is a
copy-number finding and the first two are artefacts, which is why the per-gene bait density
from the uniqueness pass is carried alongside this table rather than left in another file.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .tools import Provenance, run, started_now


@dataclass(frozen=True)
class RegionDepth:
    """Mean depth over one named interval."""

    contig: str
    start: int
    end: int
    name: str
    mean_depth: float

    @property
    def bases(self) -> int:
        return self.end - self.start


@dataclass(frozen=True)
class Coverage:
    """What mosdepth produced, plus the global distribution it also reports."""

    regions: tuple[RegionDepth, ...]
    manifest: Path
    prefix: Path

    def below(self, depth: float) -> tuple[RegionDepth, ...]:
        """Regions under a threshold — the gate's own query, not a caller's loop."""
        return tuple(region for region in self.regions if region.mean_depth < depth)


def write_bed(rows: list[tuple[str, int, int, str]], path: Path, *, sort: bool = True) -> Path:
    """A BED of the intervals to measure. Half-open and 0-based, as BED has always been.

    Sorted by default because mosdepth walks the BAM in coordinate order and an unsorted
    BED makes it re-seek; the flag exists only so a caller with an already-sorted list can
    say so.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(rows, key=lambda row: (row[0], row[1], row[2])) if sort else rows
    with path.open("w", encoding="ascii", newline="\n") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerows(ordered)
    return path


def per_region(
    bam: Path,
    bed: Path,
    out_dir: Path,
    *,
    stem: str = "baited",
    threads: int = 4,
    min_mapq: int = 20,
) -> Coverage:
    """Mean depth over every interval in ``bed``.

    ``min_mapq`` is a decision, stated: reads the aligner could not place confidently are
    excluded, because counting them as depth would credit a region with evidence that is
    really evidence for "this sequence occurs in more than one place". 20 is the usual
    cut (a 1-in-100 chance the placement is wrong) and is recorded in the manifest.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = out_dir / stem
    provenance = started_now("coverage")
    provenance.inputs = {"bam": str(bam), "regions": str(bed)}
    provenance.parameters = {
        "tool": "mosdepth",
        "min_mapq": min_mapq,
        "threads": threads,
        "flags": "--no-per-base --use-median false (means reported)",
    }
    provenance.invocations.append(
        run(
            [
                "mosdepth",
                "--no-per-base",
                "--by",
                str(bed),
                "--mapq",
                str(min_mapq),
                "--threads",
                str(threads),
                str(prefix),
                str(bam),
            ]
        )
    )
    regions = read_regions(Path(f"{prefix}.regions.bed.gz"))
    provenance.outputs = {
        "regions": f"{prefix}.regions.bed.gz",
        "summary": f"{prefix}.mosdepth.summary.txt",
        "regions_measured": str(len(regions)),
    }
    manifest = provenance.write(out_dir / f"{stem}.coverage.provenance.json")
    return Coverage(regions=regions, manifest=manifest, prefix=prefix)


def read_regions(path: Path) -> tuple[RegionDepth, ...]:
    """mosdepth's ``.regions.bed.gz``: contig, start, end, name, mean depth."""
    import gzip

    found: list[RegionDepth] = []
    with gzip.open(path, "rt", encoding="ascii") as handle:
        for line in handle:
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 5:
                continue
            found.append(
                RegionDepth(
                    contig=fields[0],
                    start=int(fields[1]),
                    end=int(fields[2]),
                    name=fields[3],
                    mean_depth=float(fields[4]),
                )
            )
    return tuple(found)


def summarise(coverage: Coverage, floor: float = 10.0) -> dict[str, object]:
    """The gate's numbers: how many regions, how deep, and which fall under the floor."""
    depths = sorted(region.mean_depth for region in coverage.regions)
    if not depths:
        return {"regions": 0, "below_floor": 0, "floor": floor}
    middle = depths[len(depths) // 2]
    thin = coverage.below(floor)
    return {
        "regions": len(depths),
        "median_depth": round(middle, 2),
        "min_depth": round(depths[0], 2),
        "max_depth": round(depths[-1], 2),
        "floor": floor,
        "below_floor": len(thin),
        "below_floor_names": [region.name for region in thin[:50]],
    }


__all__ = ["Coverage", "Provenance", "RegionDepth", "per_region", "summarise", "write_bed"]
