#!/usr/bin/env python3
"""Stage 5 of step 3 — copy number per exon, with no aligner and no caller.

Every coding exon of every target and decoy gene is cut into 31-mers, filtered to the ones
that occur exactly once in GRCh38, and counted in the recovered reads. An exon present twice
puts its k-mers into twice as many reads as one present once, so copy number is a ratio — and
the difficulty is entirely the denominator.

**Two denominators, neither of them chosen.** The local flank is 2,000 unique k-mers taken
from the sequence immediately either side of the gene, split between the two sides: it shares
the gene's coverage bias, which is what makes it cancel (GeneToCN, Pajuste 2023). The
genome-wide median of every measured exon is the cross-check. Their disagreement is a
reported column, because a gene where the two differ is a gene whose neighbourhood is
unusual, and that is worth seeing rather than averaging away.

**Raw occurrence counts, not per-fragment ones.** Unlike a genotype, a copy number is a ratio
of two counts measured the same way, so the read-pair double-counting factor is common to
numerator and denominator and cancels. Skipping the collapse also keeps the probe set — three
million k-mers here, against 764,000 for the genotypes — clear of the packing the genotype
count needs.

**The null band comes from the decoys.** 396 genes matched to the targets on coding length
and exon count, carrying none of the child's symptoms, drawn once from a recorded seed
(entry 084). They have no reason to be deleted, so the spread of *their* copy numbers is what
normal looks like on this sample, at this depth, with this bait — and an exon below its 2.5th
percentile is a candidate. Imported thresholds know none of those three things.

Usage::

    uv run python tools/measure_it2_copynumber.py
    uv run python tools/measure_it2_copynumber.py --flank 3000
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mva.kmer import fasta, uniqueness
from mva.kmer.bait import Interval
from mva.kmer.copynumber import (
    DELETION_PERCENTILE,
    MIN_EXON_KMERS,
    MIN_FLANK_KMERS,
    Region,
    below_band,
    estimate,
    null_band,
    pool_thin_exons,
    summarise,
)
from mva.kmer.count import tally
from mva.kmer.encode import K, codes_of, window_kmers
from mva.kmer.membership import Bait
from mva.reads.bait import code_matrix
from mva.warehouse.postgres import ALIAS, attached
from mva.warehouse.settings import Postgres

DEFAULT_OUT = Path("build/it2/step-3")
DEFAULT_REFERENCE = Path("build/reference/GRCh38.fa")
DEFAULT_READS = Path("build/it2/step-2/baited-reads.parquet")

#: Bases either side of a gene the flanking k-mers are drawn from, before the uniqueness
#: filter removes the repeated ones. Generous because the filter is lossy in exactly the
#: genes that need a denominator most.
FLANK_BASES = 20_000

EXONS_SQL = f"""
    SELECT r.gene, r.chrom, r.start, r."end", d.tier
    FROM {ALIAS}.warehouse.coding_regions r
    JOIN {ALIAS}.results.it2_bait_density d ON d.symbol = r.gene
    ORDER BY r.gene, r.chrom, r.start
"""


def exon_rows(settings: Postgres) -> list[tuple]:
    with attached(settings, read_only=True) as connection:
        return connection.execute(EXONS_SQL).fetchall()


def grouped_intervals(rows: list[tuple], flank: int) -> tuple[dict[str, list[Interval]], dict]:
    """One k-mer group per exon (``gene|ordinal``) and one per gene's flanks (``gene|flank``).

    The flanks are taken from the gene's whole span rather than each exon's, because the
    denominator is meant to carry the *gene's* regional coverage bias — an intronic stretch
    between two exons shares it and is not a separate neighbourhood.
    """
    groups: dict[str, list[Interval]] = {}
    spans: dict[str, tuple[str, int, int]] = {}
    tier_of: dict[str, str] = {}
    ordinal: dict[str, int] = defaultdict(int)
    for gene, chrom, start, end, tier in rows:
        ordinal[gene] += 1
        tier_of[gene] = tier
        groups[f"{gene}|{ordinal[gene]}"] = [Interval(str(chrom), int(start), int(end))]
        previous = spans.get(gene)
        spans[gene] = (
            (str(chrom), int(start), int(end))
            if previous is None
            else (previous[0], min(previous[1], int(start)), max(previous[2], int(end)))
        )
    for gene, (chrom, low, high) in spans.items():
        groups[f"{gene}|flank"] = [
            Interval(chrom, max(0, low - flank), low),
            Interval(chrom, high, high + flank),
        ]
    return groups, {"tier": tier_of, "spans": spans}


def cut_labelled(
    reference: Path, groups: dict[str, list[Interval]], k: int
) -> tuple[Bait, dict[str, np.ndarray]]:
    """Cut each labelled group into its own k-mer array, in **one** pass over the reference.

    ``mva.kmer.bait.cut`` streams the whole FASTA for the interval list it is given, which is
    right when there is one bait and catastrophic when there are 14,044 labelled groups — it
    would read 3 GB of reference once per exon. So the intervals are inverted: grouped by
    contig, cut as that contig goes past, and never revisited.
    """
    by_contig: dict[str, list[tuple[str, Interval]]] = {}
    for label, spans in groups.items():
        for span in spans:
            by_contig.setdefault(span.contig, []).append((label, span))

    per_label: dict[str, list[np.ndarray]] = {label: [] for label in groups}
    for contig in fasta.contigs(reference, wanted=set(by_contig)):
        codes = codes_of(contig.bases)
        for label, span in by_contig[contig.name]:
            piece = codes[max(0, span.start) : min(span.end, codes.size)]
            if piece.size < k:
                continue
            kmers, valid = window_kmers(piece, k)
            if valid.any():
                per_label[label].append(kmers[valid])

    joined = {
        label: (np.unique(np.concatenate(parts)) if parts else np.empty(0, dtype=np.uint64))
        for label, parts in per_label.items()
    }
    everything = [values for values in joined.values() if values.size]
    pool = np.unique(np.concatenate(everything)) if everything else np.empty(0, dtype=np.uint64)
    return Bait.of(pool, k=k), joined


def counts_over_reads(reads: Path, probes: Bait, batch: int, limit: int | None) -> np.ndarray:
    scan = pl.scan_parquet(reads)
    total = int(scan.select(pl.len()).collect().item())
    if limit is not None:
        total = min(total, limit)
    counts = np.zeros(len(probes), dtype=np.uint64)
    started = time.perf_counter()
    for offset in range(0, total, batch):
        rows = min(batch, total - offset)
        frame = scan.slice(offset, rows).collect()
        counts += tally(code_matrix(frame["sequence"]), probes).counts.astype(np.uint64)
        print(
            f"  {offset + rows:,}/{total:,} reads  {time.perf_counter() - started:,.0f}s",
            flush=True,
        )
    return counts


def write_tables(tables: Path, estimates, band, tier_of: dict[str, str], low: set[str]) -> None:
    """The two tables, carrying a gene, an exon ordinal and numbers — never a coordinate."""
    tables.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(
        [
            {
                "symbol": row.gene,
                "tier": tier_of.get(row.gene, ""),
                "label": row.label,
                "exon_ordinal": 0 if row.pooled else int(row.label.rsplit("|", 1)[1]),
                "surviving_kmers": row.kmers,
                "pooled": row.pooled,
                "median_count": round(row.median_count, 4),
                "cn_local": None if row.local is None else round(row.local, 4),
                "cn_genome_wide": round(row.genome_wide, 4),
                "denominator_disagreement": (
                    None if row.disagreement is None else round(row.disagreement, 4)
                ),
                "below_null_band": row.label in low,
            }
            for row in estimates
        ]
    ).write_csv(tables / "it2_exon_cn.tsv", separator="\t")
    pl.DataFrame(
        [
            {
                "percentile": band.percentile,
                "low": round(band.low, 4),
                "high": round(band.high, 4),
                "median": round(band.median, 4),
                "regions": band.regions,
            }
        ]
    ).write_csv(tables / "it2_cn_null.tsv", separator="\t")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--reads", type=Path, default=DEFAULT_READS)
    parser.add_argument("--flank", type=int, default=FLANK_BASES)
    parser.add_argument("--batch", type=int, default=400_000)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--k", type=int, default=K)
    parser.add_argument("--percentile", type=float, default=DELETION_PERCENTILE)
    args = parser.parse_args(argv)

    settings = Postgres.from_env()
    if settings.missing:
        print("missing settings: " + ", ".join(settings.missing))
        return 1

    rows = exon_rows(settings)
    groups, meta = grouped_intervals(rows, args.flank)
    print(f"{len(rows):,} coding exons over {len(meta['spans']):,} genes", flush=True)

    probes, per_label = cut_labelled(args.reference, groups, args.k)
    print(f"cut {len(probes):,} distinct k-mers; uniqueness pass ...", flush=True)
    occurrence = uniqueness.count_in_genome(args.reference, probes)
    unique_mask = occurrence.unique
    unique_kmers = probes.kmers[unique_mask]
    kept = Bait.of(unique_kmers, k=args.k)
    print(f"{len(kept):,} of {len(probes):,} occur exactly once", flush=True)

    counts = counts_over_reads(args.reads, kept, args.batch, args.limit)
    lookup = dict(zip(kept.kmers.tolist(), counts.tolist(), strict=True))

    regions: list[Region] = []
    flank_median: dict[str, float] = {}
    for label, values in per_label.items():
        surviving = np.array([lookup[int(v)] for v in values if int(v) in lookup], dtype=float)
        gene = label.rsplit("|", 1)[0]
        if label.endswith("|flank"):
            if surviving.size >= MIN_FLANK_KMERS:
                flank_median[gene] = float(np.median(surviving))
            continue
        regions.append(Region(gene=gene, label=label, counts=surviving))

    pooled, resolution = pool_thin_exons(regions, minimum=MIN_EXON_KMERS)
    genome_median = float(
        np.median([region.median for region in pooled if region.kmers and region.median > 0])
    )
    estimates = estimate(pooled, flank_median, genome_median)

    tier_of = meta["tier"]
    decoy_values = [row.best for row in estimates if tier_of.get(row.gene) == "decoy"]
    band = null_band(decoy_values, percentile=args.percentile)
    low = {row.label for row in below_band(estimates, band)}

    write_tables(args.out / "tables", estimates, band, tier_of, low)

    report = summarise(estimates, band) | {
        "resolution": resolution,
        "genome_median_count": round(genome_median, 4),
        "genes_with_local_denominator": len(flank_median),
        "kmers_cut": len(probes),
        "kmers_unique": len(kept),
        "flank_bases": args.flank,
        "null_band_source": "decoy-gene exons",
    }
    (args.out / "copynumber-summary.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
