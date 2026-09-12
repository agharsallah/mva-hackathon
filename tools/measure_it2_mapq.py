#!/usr/bin/env python3
"""Stage 0 of step 3 — where the aligner was unsure, and which genes may be reported on.

Step 2 dropped 8.79 % of its bait k-mers as repeated and could not reach the pre-registered
5 % at any available parameter (entry 086). That number says how much *bait* was lost. It
does not say what happened to the reads that survived: a gene whose sequence occurs in
several places collects reads from all of them, the aligner marks them ``MAPQ 0`` ("I could
not choose"), and a k-mer counter — which has no notion of where a read came from — would
count them as evidence for this gene.

So before step 3 fits any model, one pass over the alignment step 2 already produced says,
per gene, what share of its reads the aligner declined to place. That is the measurement
that replaces the retired off-target gate with the per-gene reachability rule of
`plan.md` §11.7.

**The rule, fixed before the run.** A gene is `unreachable` when either

* its bait density is below **half the median** surviving-k-mer density
  (`results.it2_bait_density`, plan §11.7), or
* more than **50 %** of its reads carry ``MAPQ 0`` — a majority the aligner refused to
  place.

An unreachable gene is **flagged, never dropped**: step 3 still counts its probes, and the
flag is what stops an absence there being read as a finding.

Decoys are measured identically. H020 is refuted, so nothing in step 3 may assume a target
gene's result is worth more than a decoy's before the filter.

Usage::

    uv run python tools/measure_it2_mapq.py
    uv run python tools/measure_it2_mapq.py --mapq0-ceiling 0.3
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mva.calling.mapq import per_region, summarise
from mva.warehouse.postgres import ALIAS, attached
from mva.warehouse.settings import Postgres

DEFAULT_BAM = Path("build/it2/step-2/calls/baited.bam")
DEFAULT_REGIONS = Path("build/it2/step-2/baited-regions.bed")
DEFAULT_OUT = Path("build/it2/step-3")

#: Pre-registered, before the run: more than half a gene's reads at MAPQ 0 means the
#: aligner refused to place the majority of the evidence, and no count from it is read as
#: a genotype without the flag beside it.
MAPQ0_CEILING = 0.5

#: plan.md 11.7 — the per-gene bait-density gate that replaced `off-target < 5 %`.
DENSITY_FRACTION = 0.5

DENSITY_SQL = f"SELECT symbol, tier, density FROM {ALIAS}.results.it2_bait_density"


def read_intervals(path: Path) -> list[tuple[str, int, int, str]]:
    """The baited intervals, labelled by gene — the BED step 2's coverage stage used."""
    rows: list[tuple[str, int, int, str]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 4:
                continue
            rows.append((fields[0], int(fields[1]), int(fields[2]), fields[3]))
    return rows


def density_rows(settings: Postgres) -> dict[str, tuple[str, float]]:
    with attached(settings, read_only=True) as connection:
        return {
            str(symbol): (str(tier), float(density))
            for symbol, tier, density in connection.execute(DENSITY_SQL).fetchall()
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--bam", type=Path, default=DEFAULT_BAM)
    parser.add_argument("--regions", type=Path, default=DEFAULT_REGIONS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--mapq0-ceiling", type=float, default=MAPQ0_CEILING)
    parser.add_argument("--density-fraction", type=float, default=DENSITY_FRACTION)
    args = parser.parse_args(argv)

    for path in (args.bam, args.regions):
        if not path.is_file():
            print(f"missing {path} — run step 2's calling stage first")
            return 1
    settings = Postgres.from_env()
    if settings.missing:
        print("missing settings: " + ", ".join(settings.missing))
        return 1

    intervals = read_intervals(args.regions)
    density = density_rows(settings)
    if not density:
        print("results.it2_bait_density is empty — load step 2's tables first")
        return 1

    profile = per_region(args.bam, intervals, args.out / "mapq", stem="mapq")
    report = summarise(profile, ceiling=args.mapq0_ceiling)

    median_density = statistics.median(value for _, value in density.values())
    floor = median_density * args.density_fraction

    out = args.out / "mapq.tsv"
    out.parent.mkdir(parents=True, exist_ok=True)
    sparse = thin = both = 0
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(
            [
                "symbol",
                "tier",
                "reads",
                "mapq0",
                "mapq0_fraction",
                "median_mapq",
                "mean_mapq",
                "bait_density",
                "sparse_bait",
                "mapq_refused",
                "reachable",
            ]
        )
        for row in sorted(profile.regions, key=lambda item: item.name):
            tier, value = density.get(row.name, ("", 0.0))
            is_sparse = value < floor
            is_refused = row.mapq0_fraction > args.mapq0_ceiling
            sparse += int(is_sparse)
            thin += int(is_refused)
            both += int(is_sparse and is_refused)
            writer.writerow(
                [
                    row.name,
                    tier,
                    row.reads,
                    row.mapq0,
                    f"{row.mapq0_fraction:.6f}",
                    f"{row.median_mapq:.1f}",
                    f"{row.mean_mapq:.2f}",
                    f"{value:.6f}",
                    is_sparse,
                    is_refused,
                    not (is_sparse or is_refused),
                ]
            )

    report |= {
        "genes": len(profile.regions),
        "median_bait_density": round(median_density, 6),
        "density_floor": round(floor, 6),
        "sparse_bait": sparse,
        "mapq_refused": thin,
        "both": both,
        "unreachable": sparse + thin - both,
        "mapq0_ceiling": args.mapq0_ceiling,
    }
    (args.out / "mapq-summary.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    print(f"mapq profile -> {out}  ({len(profile.regions):,} genes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
