#!/usr/bin/env python3
"""Turn step 2's tool outputs into the TSVs the warehouse loads.

The calling stages leave VCFs, a BED of depths and a pile of JSON manifests — formats
built for the tools that wrote them, not for SQL. This is the seam: read each one with the
parser that understands it, write flat rows, and let
:mod:`mva.warehouse.it2_step2_tables` put them where the pair SQL and the dashboard can
reach them.

**Nothing is filtered here and nothing is judged here.** Every call each caller emitted
becomes a row, including the ones that failed the caller's own filters, because a row that
was never written cannot be reconsidered and H022's concordance is a statement about what
the callers said — not about what we kept.

Usage::

    uv run python tools/export_it2_step2_tables.py
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mva.calling import sv as sv_module
from mva.kmer import regions as regions_module
from mva.kmer.bait import merge
from mva.pipeline import vcf as vcf_module
from mva.pipeline.variant import to_vcf_contig

DEFAULT_OUT = Path("build/it2/step-2")
DEFAULT_STEP1 = Path("build/it2/step-1")
DEFAULT_CODING = Path("ressources/reference/coding_regions.tsv")
WIDE_TIERS = ("core", "mechanism-term")


def write_tsv(path: Path, header: list[str], rows: list[list[Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
    return len(rows)


def _metrics(stage: str, payload: dict[str, Any], names: tuple[str, ...]) -> list[list[Any]]:
    """The named numbers of one JSON payload as (stage, metric, value, note) rows."""
    return [
        [stage, name, float(payload[name]), ""] for name in names if payload.get(name) is not None
    ]


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def bait_qc(out: Path, tables: Path) -> int:
    """The pass's funnel as one long table — stage, metric, value — so a new measurement is
    a row rather than a schema change, and a stage that did not run is simply absent."""
    summary = _read(out / "summary.json")
    unique = summary.get("uniqueness") or {}
    result = _read(out / "bait-pass.json")
    recovery = _read(out / "recovery.json")
    report = _read(out / "calling-report.json")

    rows: list[list[Any]] = []
    rows += _metrics(
        "bait", summary, ("bait_bases", "kmers_cut", "kmers_kept", "expected_reads", "genes")
    )
    rows += _metrics("uniqueness", unique, ("repeated", "unseen", "windows_scanned"))
    if unique.get("bait_kmers"):
        rows.append(
            [
                "uniqueness",
                "off_target_fraction",
                unique["repeated"] / unique["bait_kmers"],
                "gate was < 0.05; it failed and was re-measured per gene (entry 085)",
            ]
        )
    rows += _metrics(
        "pass",
        result,
        (
            "reads_scanned",
            "reads_matched",
            "matched_fraction",
            "fragments",
            "orphans",
            "orphans_filled",
            "shards",
            "seconds",
            "stride",
            "workers",
        ),
    )
    rows += _metrics("recover", recovery, ("fragments", "dropped"))
    rows += _metrics(
        "align",
        report.get("alignment") or {},
        ("reads", "mapped", "mapped_fraction", "properly_paired", "duplicates"),
    )
    rows += _metrics(
        "coverage",
        report.get("coverage") or {},
        ("regions", "median_depth", "min_depth", "below_floor"),
    )
    rows += [
        ["stage", stage["name"], float(stage.get("seconds", 0)), stage["status"]]
        for stage in report.get("stages", [])
    ]
    return write_tsv(tables / "it2_bait_qc.tsv", ["stage", "metric", "value", "note"], rows)


def bait_density(out: Path, tables: Path) -> int:
    source = out / "bait-profile.tsv"
    if not source.exists():
        return 0
    with source.open(encoding="utf-8") as handle:
        rows = [
            [
                r["symbol"],
                r["tier"],
                r["bases"],
                r["windows"],
                r["surviving"],
                r["density"],
                r["lost"],
            ]
            for r in csv.DictReader(handle, delimiter="\t")
        ]
    return write_tsv(
        tables / "it2_bait_density.tsv",
        ["symbol", "tier", "bases", "windows", "surviving", "density", "lost"],
        rows,
    )


def exon_depth(out: Path, tables: Path) -> int:
    source = out / "calls" / "baited.regions.bed.gz"
    if not source.exists():
        return 0
    with gzip.open(source, "rt", encoding="ascii") as handle:
        rows = [
            fields[:5]
            for fields in (line.rstrip("\n").split("\t") for line in handle)
            if len(fields) >= 5
        ]
    return write_tsv(
        tables / "it2_exon_depth.tsv", ["chrom", "start", "end", "symbol", "mean_depth"], rows
    )


def read_alleles(out: Path, tables: Path) -> int:
    rows: list[list[Any]] = []
    for caller in ("freebayes", "bcftools"):
        # The normalised file's exact name depends on what the chain did to it on the way
        # (freebayes' output is sorted first, which renames it), so it is found by pattern.
        # Normalised wins over raw: two callers can only be compared after norm.
        calls = sorted((out / "calls").glob(f"baited.{caller}*.vcf.gz"))
        preferred = [path for path in calls if ".norm." in path.name] or calls
        for source in preferred[:1]:
            # `mva.pipeline.vcf` returns variants in the **submission** representation,
            # which is chr-prefixed. Every other table in this step — the depths, the SV
            # calls, the gene model, the bait — is in the callset's bare spelling, and a
            # join across the two silently returns nothing. `mva.pipeline.variant` owns
            # both directions for exactly this reason
            # (docs/step-0/notes/chr-prefix-bridge.md); this is the way back.
            rows.extend(
                [
                    caller,
                    to_vcf_contig(call.variant.chrom),
                    call.variant.pos,
                    call.variant.ref,
                    call.variant.alt,
                    call.genotype,
                    ",".join(call.filters),
                    call.depth,
                    call.ref_depth,
                    call.alt_depth,
                    call.is_het,
                    call.is_hom_alt,
                    call.vaf,
                    call.phase_set,
                ]
                for call in vcf_module.iter_calls(source)
            )
            break
    return write_tsv(
        tables / "it2_read_alleles.tsv",
        [
            "caller",
            "chrom",
            "pos",
            "ref",
            "alt",
            "genotype",
            "filters",
            "depth",
            "ref_depth",
            "alt_depth",
            "is_het",
            "is_hom_alt",
            "vaf",
            "phase_set",
        ],
        rows,
    )


def bait_edges(
    step1: Path, coding: Path, wide_pad: int, narrow_pad: int
) -> dict[str, list[tuple[int, int]]]:
    """The merged baited intervals per contig — what a bait-edge flag is measured against."""
    tier_of = regions_module.read_tiers(
        [(step1 / "targets.tsv", None), (step1 / "decoys.tsv", "decoy")]
    )
    by_gene = regions_module.read_gene_model(coding)
    labelled = regions_module.padded_by_gene(
        tier_of, by_gene, wide_tiers=WIDE_TIERS, wide_pad=wide_pad, narrow_pad=narrow_pad
    )
    edges: dict[str, list[tuple[int, int]]] = {}
    everything = [interval for intervals in labelled.values() for interval in intervals]
    for interval in merge(everything):
        edges.setdefault(interval.contig, []).append((interval.start, interval.end))
    return edges


def sv_calls(out: Path, tables: Path, edges: dict[str, list[tuple[int, int]]]) -> int:
    rows: list[list[Any]] = []
    sources = {
        "delly": out / "calls" / "baited.delly.bcf",
        "dysgu": out / "calls" / "baited.dysgu.vcf",
    }
    for caller, source in sources.items():
        if not source.exists():
            continue
        method = sv_module.METHOD_CLASS[caller]
        rows.extend(
            [
                call.caller,
                call.method_class,
                call.contig,
                call.position,
                call.end,
                call.sv_type,
                call.length,
                call.filters,
                call.genotype,
                sv_module.near_bait_edge(call.contig, call.position, edges),
                call.precision_prior,
            ]
            for call in sv_module.read_calls(source, caller=caller, method_class=method)
        )
    return write_tsv(
        tables / "it2_sv_calls.tsv",
        [
            "caller",
            "method_class",
            "chrom",
            "pos",
            "end_pos",
            "sv_type",
            "sv_len",
            "filters",
            "genotype",
            "bait_edge",
            "precision_prior",
        ],
        rows,
    )


def phase_blocks(out: Path, tables: Path) -> int:
    from mva.calling.phase import read_blocks

    source = out / "calls" / "baited.phased.vcf"
    if not source.exists():
        return 0
    rows = [[block.contig, block.start, block.end, block.variants] for block in read_blocks(source)]
    return write_tsv(tables / "it2_phase_blocks.tsv", ["chrom", "start", "end", "variants"], rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--step1", type=Path, default=DEFAULT_STEP1)
    parser.add_argument("--coding", type=Path, default=DEFAULT_CODING)
    parser.add_argument("--wide-pad", type=int, default=50_000)
    parser.add_argument("--narrow-pad", type=int, default=2_000)
    args = parser.parse_args(argv)

    tables = args.out / "tables"
    edges = bait_edges(args.step1, args.coding, args.wide_pad, args.narrow_pad)
    written = {
        "it2_bait_qc": bait_qc(args.out, tables),
        "it2_bait_density": bait_density(args.out, tables),
        "it2_exon_depth": exon_depth(args.out, tables),
        "it2_read_alleles": read_alleles(args.out, tables),
        "it2_sv_calls": sv_calls(args.out, tables, edges),
        "it2_phase_blocks": phase_blocks(args.out, tables),
    }
    print(f"{'table':>20} {'rows':>10}")
    for table, rows in written.items():
        print(f"{table:>20} {rows:>10,}" + ("   (source absent — not written)" if not rows else ""))
    print(f"\nwrote {tables}")
    print("next: uv run mva-warehouse pg-load-it2-step2")
    return 0


if __name__ == "__main__":
    sys.exit(main())
