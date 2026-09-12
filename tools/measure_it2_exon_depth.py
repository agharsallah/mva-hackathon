#!/usr/bin/env python3
"""Measure read depth **per coding exon**, not per baited interval.

``results.it2_exon_depth`` is named for exons but holds the *merged baited intervals* the
coverage stage was run over — 126 of the 128 core and mechanism-term genes are a single
interval there, so it can answer "is this gene deep enough" and cannot answer "is this
*exon* deep enough". The second question is the one an absence inside a gene has to be read
against, and the exon-coverage exhibit needs it as a grid.

So this re-runs mosdepth over the exons themselves, from the same BAM the calling stage
produced, and writes a table that carries **no coordinate**: a gene, an exon's ordinal
within that gene, its length, and its mean depth.

Assumptions and limits, stated beside the result:

* exon intervals come from ``warehouse.coding_regions``, which is a union over transcripts,
  so "exon 7" is the 7th coding interval of the gene and not a transcript's 7th exon;
* ``--mapq 20`` matches the calling stage, so these depths are comparable with the ones in
  ``results.it2_exon_depth`` and not with a raw pileup;
* genes outside the target set are not measured — the decoys' null is a per-gene rate, and
  nothing in the report reads a decoy at exon resolution.

Usage::

    uv run python tools/measure_it2_exon_depth.py
    uv run python tools/measure_it2_exon_depth.py --tiers core,mechanism-term
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mva.calling.coverage import per_region, summarise, write_bed
from mva.warehouse.postgres import ALIAS, attached
from mva.warehouse.settings import Postgres

DEFAULT_BAM = Path("build/it2/step-2/calls/baited.bam")
DEFAULT_OUT = Path("build/it2/step-2/exon-depth.tsv")
DEFAULT_WORK = Path("build/it2/step-2/exon-depth")

#: The tiers the exhibit reads. Decoys are excluded on purpose: see the module docstring.
DEFAULT_TIERS = ("core", "mechanism-term", "net")

EXONS_SQL = f"""
    SELECT r.gene, r.chrom, r.start, r."end", d.tier
    FROM {ALIAS}.warehouse.coding_regions r
    JOIN {ALIAS}.results.it2_bait_density d ON d.symbol = r.gene
    WHERE d.tier IN ({{tiers}})
    ORDER BY r.gene, r.chrom, r.start
"""


def exon_rows(settings: Postgres, tiers: tuple[str, ...]) -> list[tuple]:
    placeholders = ", ".join(f"'{tier}'" for tier in tiers)
    with attached(settings, read_only=True) as connection:
        return connection.execute(EXONS_SQL.format(tiers=placeholders)).fetchall()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--bam", type=Path, default=DEFAULT_BAM)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--work", type=Path, default=DEFAULT_WORK)
    parser.add_argument("--tiers", default=",".join(DEFAULT_TIERS))
    args = parser.parse_args(argv)

    if not args.bam.is_file():
        print(f"no BAM at {args.bam} — run the calling stage first")
        return 1
    settings = Postgres.from_env()
    if settings.missing:
        print("missing settings: " + ", ".join(settings.missing))
        return 1

    rows = exon_rows(settings, tuple(t.strip() for t in args.tiers.split(",") if t.strip()))
    if not rows:
        print("no exons for those tiers")
        return 1

    # The BED name carries the gene and the exon's ordinal, so the depth table can be
    # written without ever reading a coordinate back out of mosdepth's output.
    ordinal: dict[str, int] = {}
    tier_of: dict[str, str] = {}
    intervals = []
    for gene, chrom, start, end, tier in rows:
        ordinal[gene] = ordinal.get(gene, 0) + 1
        tier_of[gene] = tier
        intervals.append((str(chrom), int(start), int(end), f"{gene}|{ordinal[gene]}"))

    bed = write_bed(intervals, args.work / "target-exons.bed")
    coverage = per_region(args.bam, bed, args.work, stem="exons")
    print(summarise(coverage))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["symbol", "tier", "exon_index", "exon_bases", "mean_depth"])
        for region in coverage.regions:
            gene, index = region.name.rsplit("|", 1)
            writer.writerow(
                [gene, tier_of.get(gene, ""), index, region.bases, f"{region.mean_depth:.2f}"]
            )
    print(f"exon depth -> {args.out}  ({len(coverage.regions):,} exons)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
