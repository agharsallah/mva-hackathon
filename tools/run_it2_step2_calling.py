#!/usr/bin/env python3
"""Take the bait pass's recovered reads to normalised, phased calls — on this machine.

The one stage of step 2 that must run beside the data is the sweep over 1.07 billion reads
(entry 085). Everything after it is small: ~12 million recovered reads is a few gigabytes,
and every tool it needs has an arm64 build. So this is the local half of step 2, and it
starts where the job service left off.

What it does, in order:

1. pull the recovered reads (one Parquet object the ``/bait`` job published),
2. rebuild them as paired FASTQ, byte-exact read names included,
3. write the BED of baited intervals — the same intervals the bait was cut from,
4. align, measure depth, call twice, normalise both, call structural variants, phase,
5. write one report holding every stage's outcome and every tool's version.

Stages that cannot run (a tool missing, a caller failing) are recorded and skipped rather
than aborting the run: five hours of alignment should not be thrown away because a phaser
is not installed.

Usage::

    uv run python tools/run_it2_step2_calling.py
    uv run python tools/run_it2_step2_calling.py --skip-download --threads 8
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import polars as pl

from mva.calling.workflow import run_all
from mva.kmer import regions as regions_module
from mva.reads import recover
from mva.reads.access import s3_root
from mva.warehouse.settings import object_store
from mva.warehouse.source import client

DEFAULT_STEP1 = Path("build/it2/step-1")
DEFAULT_OUT = Path("build/it2/step-2")
DEFAULT_CODING = Path("ressources/reference/coding_regions.tsv")
DEFAULT_REFERENCE = Path("build/reference/GRCh38.fa")
DEFAULT_KEY = "derived/it2/step-2/baited-reads.parquet"

#: Tiers that carried the wide padding — kept in step with tools/build_it2_bait.py.
WIDE_TIERS = ("core", "mechanism-term")


def download(key: str, target: Path) -> Path:
    """Pull the object the bait job published."""
    store = object_store()
    target.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    client(store).download_file(store.bucket, key, str(target))
    size = target.stat().st_size
    print(
        f"downloaded s3://{store.bucket}/{key} ({size:,} B) in {time.perf_counter() - started:.0f}s"
    )
    return target


def write_regions_bed(
    step1: Path, coding: Path, out: Path, *, wide_pad: int, narrow_pad: int
) -> Path:
    """The baited intervals as BED, named by gene, merged so no base is measured twice.

    These are the same intervals the bait was cut from, built by the same code path, so
    "where the bait was" and "where we called" cannot drift apart.
    """
    from mva.calling.coverage import write_bed
    from mva.kmer.bait import merge

    tier_of = regions_module.read_tiers(
        [(step1 / "targets.tsv", None), (step1 / "decoys.tsv", "decoy")]
    )
    by_gene = regions_module.read_gene_model(coding)
    labelled = regions_module.padded_by_gene(
        tier_of, by_gene, wide_tiers=WIDE_TIERS, wide_pad=wide_pad, narrow_pad=narrow_pad
    )
    rows: list[tuple[str, int, int, str]] = []
    for gene, intervals in labelled.items():
        rows.extend(
            (interval.contig, interval.start, interval.end, gene) for interval in merge(intervals)
        )
    path = write_bed(rows, out)
    print(f"regions -> {path} ({len(rows):,} merged intervals)")
    return path


def _existing_reads(fastq_dir: Path) -> tuple[Path | None, Path | None]:
    """The recovered FASTQ pair already on disk, compressed for preference."""
    for suffix in (".fastq.gz", ".fastq"):
        first, second = (
            fastq_dir / f"baited_R1{suffix}",
            fastq_dir / f"baited_R2{suffix}",
        )
        if first.exists() and second.exists():
            return first, second
    return None, None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--step1", type=Path, default=DEFAULT_STEP1)
    parser.add_argument("--coding", type=Path, default=DEFAULT_CODING)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--key", default=DEFAULT_KEY, help="object key the bait job wrote")
    parser.add_argument("--root", default=None, help="read-store root (for the runs table)")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--wide-pad", type=int, default=50_000)
    parser.add_argument("--narrow-pad", type=int, default=2_000)
    parser.add_argument("--depth-floor", type=float, default=10.0)
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--skip-fastq", action="store_true")
    parser.add_argument("--no-sv", action="store_true")
    parser.add_argument("--no-phase", action="store_true")
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    reads_parquet = args.out / "baited-reads.parquet"
    if not args.skip_download:
        download(args.key, reads_parquet)
    if not reads_parquet.exists():
        print(f"missing {reads_parquet} — run the bait pass first, or drop --skip-download")
        return 1

    fastq_dir = args.out / "reads"
    # bgzip-compressed reads are preferred when present: the store's NovaSeq quality
    # strings are four-level binned and compress ~6x, which on a machine this close to
    # full is the difference between a run and a full disk. minimap2 reads either.
    r1, r2 = _existing_reads(fastq_dir)
    if not (r1 and r2):
        frame = pl.read_parquet(reads_parquet)
        print(f"recovered reads: {frame.height:,} rows")
        facts = recover.runs(args.root or s3_root())
        written = recover.to_fastq(frame, facts, fastq_dir)
        print(
            f"fastq -> {written.fragments:,} complete fragments, "
            f"{written.dropped:,} dropped for want of a mate"
        )
        (args.out / "recovery.json").write_text(
            json.dumps(written.as_dict(), indent=2), encoding="utf-8"
        )
        r1, r2 = written.files[1], written.files[2]
    print(f"reads: {r1}, {r2}")

    bed = write_regions_bed(
        args.step1,
        args.coding,
        args.out / "baited-regions.bed",
        wide_pad=args.wide_pad,
        narrow_pad=args.narrow_pad,
    )

    workflow = run_all(
        args.reference,
        r1,
        r2,
        bed,
        args.out / "calls",
        threads=args.threads,
        depth_floor=args.depth_floor,
        with_sv=not args.no_sv,
        with_phase=not args.no_phase,
    )
    report = workflow.write(args.out / "calling-report.json")

    print(f"\n{'stage':>18} {'status':>8} {'seconds':>9}  detail")
    for stage in workflow.stages:
        detail = ", ".join(f"{k}={v}" for k, v in stage.detail.items()) or stage.note
        print(f"{stage.name:>18} {stage.status:>8} {stage.seconds:>9.1f}  {detail[:60]}")
    print(f"\nreport -> {report}")
    return 0 if any(stage.name == "align" and stage.ok for stage in workflow.stages) else 1


if __name__ == "__main__":
    sys.exit(main())
