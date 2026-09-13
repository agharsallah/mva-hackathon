#!/usr/bin/env python3
"""Stage 1 of step 3 — spell every allele both ways, and keep the windows that discriminate.

Four sources of alleles, and each is here for a reason:

``reads``
    every distinct allele step 2's two callers found (75,733 of them). H024 is written about
    the heterozygous ones, and H027 about the 1,199 the delivered callset never reported —
    which are inside this set, tagged, not fetched separately.
``clinvar``
    every ClinVar pathogenic or likely-pathogenic allele of a target or decoy gene. H025 asks
    which published alleles are *present at all*, and that is a discovery question the reads
    can answer for alleles no caller nominated. The catalogue is public and says nothing
    about this child, so the blind protocol allows it; it is fetched fresh over step 2's own
    baited intervals rather than reusing ``warehouse.clinvar_panel``, which holds iteration
    1's eighteen-gene panel and would import that gene list into a blind step.
``calibration``
    10,000 PASS heterozygous and 10,000 PASS homozygous-alternate SNVs from the delivered
    callset, **drawn from inside the baited intervals**. The bait recovered 0.905 of the
    reads carrying a known allele (entry 087); drawing calibration and probe counts from the
    same recovery makes that factor common to both sides of the ratio the genotype model
    fits, so it cancels. A genome-wide calibration set would read every allele as ~10%
    under-covered.

Two reference passes, both unavoidable and both streamed:

1. **design** — slice the bases around each allele and cut the two windows.
2. **uniqueness** — count every probe k-mer in GRCh38, so the alternate side can be required
   to occur *zero* times and the reference side exactly once. Step 2 filtered the reference
   side while its strike searched for the alternate, and lost reads because of it (087).

Everything written lands under ``build/`` and stays there: an alternate k-mer spells a base
this child carries, and is patient data.

Usage::

    uv run python tools/build_it2_probes.py
    uv run python tools/build_it2_probes.py --calibration 2000 --probes 3
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mva.calling.tools import sha256
from mva.kmer import uniqueness
from mva.kmer.encode import K
from mva.kmer.membership import Bait
from mva.kmer.probes import Allele, design, occurrence_map, unique_only
from mva.warehouse.postgres import ALIAS, attached
from mva.warehouse.settings import Postgres

DEFAULT_OUT = Path("build/it2/step-3")
DEFAULT_REFERENCE = Path("build/reference/GRCh38.fa")
DEFAULT_REGIONS = Path("build/it2/step-2/baited-regions.bed")
DEFAULT_CLINVAR = Path("build/it2/step-3/clinvar-baited.tsv")

#: Calibration markers per class. FastGT fits on 100,000; 10,000 is what the baited
#: intervals hold comfortably and is far past what four parameters need.
DEFAULT_CALIBRATION = 10_000

#: Drawn once, recorded, never edited — the same discipline as step 1's decoy set.
SEED = 20260913

HET = ("0/1", "1/0", "0|1", "1|0")
HOM_ALT = ("1/1", "1|1")

READ_ALLELES_SQL = f"""
    SELECT DISTINCT a.chrom, a.pos, a.ref, a.alt,
           coalesce(n.gene, c.gene, '') AS gene,
           (n.chrom IS NOT NULL) AS novel
    FROM {ALIAS}.results.it2_read_alleles a
    LEFT JOIN {ALIAS}.warehouse.it2_read_annotations n
      ON a.chrom = n.chrom AND a.pos = n.pos AND a.ref = n.ref AND a.alt = n.alt
    LEFT JOIN {ALIAS}.warehouse.coding_annotations c
      ON a.chrom = c.chrom AND a.pos = c.pos AND a.ref = c.ref AND a.alt = c.alt
"""

#: Pulled one contig at a time. The whole predicate matches 3.8 million rows, and asking
#: for them in a single statement closed the Postgres connection mid-COPY; a contig is a
#: natural chunk the table is already clustered by, and the loop is cheaper than a retry.
CALIBRATION_SQL = f"""
    SELECT chrom, CAST(pos AS BIGINT) AS pos, ref, alt,
           split_part(sample_call, ':', 1) AS gt
    FROM {ALIAS}.warehouse.variants_raw
    WHERE chrom = ?
      AND filter = 'PASS' AND length(ref) = 1 AND length(alt) = 1
      AND split_part(sample_call, ':', 1) IN {HET + HOM_ALT}
      AND CAST(pos AS BIGINT) BETWEEN ? AND ?
"""


@dataclass(frozen=True)
class Sourced:
    """One allele and where it came from — several sources may name the same allele."""

    allele: Allele
    origin: str


def baited(regions: Path) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Per-contig sorted interval bounds, for asking whether a position was baited."""
    rows: dict[str, list[tuple[int, int]]] = {}
    with regions.open(encoding="utf-8") as handle:
        for line in handle:
            fields = line.rstrip("\n").split("\t")
            if len(fields) >= 3:
                rows.setdefault(fields[0], []).append((int(fields[1]), int(fields[2])))
    packed: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for contig, spans in rows.items():
        spans.sort()
        starts = np.array([start for start, _ in spans], dtype=np.int64)
        # Running maximum, so a nested interval cannot hide a position inside an earlier one.
        ends = np.maximum.accumulate(np.array([end for _, end in spans], dtype=np.int64))
        packed[contig] = (starts, ends)
    return packed


def inside(
    intervals: dict[str, tuple[np.ndarray, np.ndarray]], contig: str, positions: np.ndarray
) -> np.ndarray:
    """Which of ``positions`` on one contig fall inside a baited interval.

    Vectorised on purpose: the calibration source is 3.8 million PASS SNVs, and asking this
    one row at a time costs minutes of interpreter time for an answer numpy gives in one
    ``searchsorted``.
    """
    found = intervals.get(contig)
    if found is None:
        return np.zeros(positions.size, dtype=bool)
    starts, ends = found
    index = np.searchsorted(starts, positions, side="right") - 1
    inside_one = np.zeros(positions.size, dtype=bool)
    ok = index >= 0
    inside_one[ok] = positions[ok] <= ends[index[ok]]
    return inside_one


def gene_symbols(regions: Path) -> set[str]:
    return {
        line.split("\t")[3].strip()
        for line in regions.read_text(encoding="utf-8").splitlines()
        if len(line.split("\t")) >= 4
    }


def from_reads(settings: Postgres) -> list[Sourced]:
    with attached(settings, read_only=True) as connection:
        rows = connection.execute(READ_ALLELES_SQL).fetchall()
    return [
        Sourced(
            allele=Allele(str(chrom), int(pos), str(ref), str(alt), str(gene)),
            origin="reads-novel" if novel else "reads",
        )
        for chrom, pos, ref, alt, gene, novel in rows
    ]


def from_clinvar(path: Path, genes: set[str]) -> list[Sourced]:
    """Pathogenic and likely-pathogenic alleles of the 792 genes.

    ``Conflicting`` assertions are excluded because they are not a claim, and anything whose
    significance string also says benign is excluded for the same reason.
    """
    frame = pl.read_csv(path, separator="\t", infer_schema_length=0)
    lowered = pl.col("clnsig").str.to_lowercase()
    kept = frame.filter(
        lowered.str.contains("pathogenic")
        & ~lowered.str.contains("conflicting")
        & ~lowered.str.contains("benign")
        & pl.col("gene").is_in(list(genes))
    )
    return [
        Sourced(
            allele=Allele(str(row["chrom"]), int(row["pos"]), row["ref"], row["alt"], row["gene"]),
            origin="clinvar",
        )
        for row in kept.iter_rows(named=True)
    ]


def from_calibration(
    settings: Postgres,
    intervals: dict[str, tuple[np.ndarray, np.ndarray]],
    per_class: int,
    seed: int,
) -> list[Sourced]:
    parts: list[pl.DataFrame] = []
    with attached(settings, read_only=True) as connection:
        for contig, (starts, ends) in sorted(intervals.items()):
            # The contig's own span bounds the pull; the exact interval test is the numpy
            # one below. Postgres does the coarse cut, numpy the fine one.
            frame = connection.execute(
                CALIBRATION_SQL, [contig, int(starts[0]), int(ends[-1])]
            ).pl()
            if frame.height == 0:
                continue
            keep = inside(intervals, contig, frame["pos"].to_numpy())
            if keep.any():
                parts.append(frame.filter(pl.Series(keep)))
    if not parts:
        return []
    frame = pl.concat(parts)
    drawn: list[Sourced] = []
    for label, genotypes in (("calibration-het", HET), ("calibration-hom-alt", HOM_ALT)):
        part = frame.filter(pl.col("gt").is_in(list(genotypes)))
        if part.height > per_class:
            part = part.sample(per_class, seed=seed, shuffle=True)
        drawn.extend(
            Sourced(
                allele=Allele(str(row["chrom"]), int(row["pos"]), row["ref"], row["alt"], label),
                origin=label,
            )
            for row in part.iter_rows(named=True)
        )
    return drawn


def merge(groups: list[list[Sourced]]) -> tuple[list[Allele], list[str]]:
    """One row per distinct allele, carrying every source that named it.

    The same allele can be a read call, a ClinVar entry and a calibration marker at once, and
    counting its probes three times would weight it three times in the fit.
    """
    order: dict[tuple[str, int, str, str], int] = {}
    alleles: list[Allele] = []
    origins: list[set[str]] = []
    for group in groups:
        for item in group:
            key = (item.allele.contig, item.allele.position, item.allele.ref, item.allele.alt)
            if key not in order:
                order[key] = len(alleles)
                alleles.append(item.allele)
                origins.append(set())
            origins[order[key]].add(item.origin)
    return alleles, ["+".join(sorted(names)) for names in origins]


def write_tables(out: Path, alleles, origins, built, counts_per_allele) -> dict[str, str]:
    """The allele table and the packed probes. Both stay under ``build/``."""
    allele_path = out / "alleles.tsv"
    with allele_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(
            ["allele_index", "chrom", "pos", "ref", "alt", "symbol", "origin", "probes"]
        )
        for index, (allele, origin) in enumerate(zip(alleles, origins, strict=True)):
            writer.writerow(
                [
                    index,
                    allele.contig,
                    allele.position,
                    allele.ref,
                    allele.alt,
                    allele.label,
                    origin,
                    int(counts_per_allele[index]),
                ]
            )
    probes_path = out / "probes.npz"
    np.savez_compressed(
        probes_path,
        allele=np.array([pair.allele for pair in built.pairs], dtype=np.int64),
        offset=np.array([pair.offset for pair in built.pairs], dtype=np.int32),
        ref_kmer=np.array([pair.ref_kmer for pair in built.pairs], dtype=np.uint64),
        alt_kmer=np.array([pair.alt_kmer for pair in built.pairs], dtype=np.uint64),
    )
    return {"alleles": str(allele_path), "probes": str(probes_path)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--regions", type=Path, default=DEFAULT_REGIONS)
    parser.add_argument("--clinvar", type=Path, default=DEFAULT_CLINVAR)
    parser.add_argument("--calibration", type=int, default=DEFAULT_CALIBRATION)
    parser.add_argument("--probes", type=int, default=3)
    parser.add_argument("--k", type=int, default=K)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--skip-uniqueness", action="store_true")
    args = parser.parse_args(argv)

    for path in (args.reference, args.regions, args.clinvar):
        if not path.is_file():
            print(f"missing {path}")
            return 1
    settings = Postgres.from_env()
    if settings.missing:
        print("missing settings: " + ", ".join(settings.missing))
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    intervals = baited(args.regions)
    genes = gene_symbols(args.regions)

    reads = from_reads(settings)
    clinvar = from_clinvar(args.clinvar, genes)
    calibration = from_calibration(settings, intervals, args.calibration, args.seed)
    alleles, origins = merge([reads, clinvar, calibration])
    print(
        f"alleles: {len(reads):,} from the reads, {len(clinvar):,} from ClinVar, "
        f"{len(calibration):,} calibration -> {len(alleles):,} distinct"
    )

    built = design(args.reference, alleles, k=args.k, probes=args.probes)
    print(f"designed {len(built.pairs):,} probe pairs; skipped {built.skipped}")

    report = dict(built.skipped)
    if not args.skip_uniqueness:
        values = built.kmers()
        bait = Bait.of(values, k=args.k)
        print(f"uniqueness pass over {len(bait):,} distinct probe k-mers ...")
        occurrence = uniqueness.count_in_genome(args.reference, bait)
        built, report = unique_only(built, occurrence_map(built, occurrence.counts))
        print(f"kept {len(built.pairs):,} probe pairs; dropped {report}")

    counts = built.counts_per_allele()
    written = write_tables(args.out, alleles, origins, built, counts)
    summary = {
        "alleles_distinct": len(alleles),
        "alleles_from_reads": len(reads),
        "alleles_from_clinvar": len(clinvar),
        "alleles_calibration": len(calibration),
        "probe_pairs": len(built.pairs),
        "probe_kmers": int(built.kmers().size),
        "alleles_with_three_probes": int((counts >= args.probes).sum()),
        "alleles_with_no_probe": int((counts == 0).sum()),
        "skipped": report,
        "k": args.k,
        "probes_requested": args.probes,
        "seed": args.seed,
        "calibration_per_class": args.calibration,
        "uniqueness_pass": not args.skip_uniqueness,
        "reference_sha256": sha256(args.reference, limit=1 << 24),
        "outputs": written,
    }
    (args.out / "probes-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(
        json.dumps({k: v for k, v in summary.items() if k != "outputs"}, indent=2, sort_keys=True)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
