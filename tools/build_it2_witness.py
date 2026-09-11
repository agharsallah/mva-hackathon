#!/usr/bin/env python3
"""Build the witness probe set that tests the bait against the instrument it replaces.

**The problem this solves.** Step 2 recovers reads with a new engine (:mod:`mva.kmer`) at a
scale nothing in this repository has run before, and then reasons about what it *did not*
find — an exon with no coverage, a gene with no second allele. Those absences only mean
anything if the survivor set really is a superset of the region's variant-carrying reads.
Asserting that would be a claim with no test behind it.

**The test (H021).** The old instrument validates the new one. `mva.reads.scan` finds the
reads carrying a given 31-mer exactly, on either strand, with a matcher that has been
measured three independent ways (step-0 entries 024-027). So: draw heterozygous alleles
the delivered callset already reports inside the baited region, build the 31-mer centred
on each alternate base, and ask the old strike which reads carry it. Every one of those
reads came from the baited region by construction, so every one of them **must** appear in
the bait sweep's survivors. The fraction that does is the bait's measured recall, and the
stride's cost stops being an assumption.

**Why this is allowed under the blind protocol.** The delivered callset is an allowed
input (`docs/iteration2/plan.md` §1); only iteration-1 *candidate* tables are not. Nothing
here reads one: the query is over `warehouse.variants_raw`, the unfiltered layer-1 table,
and the alleles are drawn by a seeded random sample, never chosen.

**Nothing this writes may be committed.** A probe is 31 bases of this child's sequence
centred on one of their alleles. Outputs go under ``build/``, which is gitignored, and
`tools/check_coordinates.py` refuses long DNA literals in tracked files.

Usage::

    uv run python tools/build_it2_witness.py --sample 120 --seed 20260912
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mva.kmer.encode import K
from mva.warehouse import postgres
from mva.warehouse.settings import Postgres

DEFAULT_OUT = Path("build/it2/step-2")
DEFAULT_STEP1 = Path("build/it2/step-1")
DEFAULT_CODING = Path("ressources/reference/coding_regions.tsv")
DEFAULT_REFERENCE = Path("build/reference/GRCh38.fa")
DEFAULT_SEED = 20260912

#: Genotype spellings the delivery uses for "one copy of the alternate allele".
HET_CALLS = ("0/1", "1/0", "0|1", "1|0")


@dataclass(frozen=True)
class Allele:
    """One heterozygous substitution the delivered callset reports."""

    chrom: str
    pos: int
    ref: str
    alt: str
    genotype: str


@dataclass(frozen=True)
class Probe:
    """An allele plus the two k-mers that distinguish a carrier read from a non-carrier."""

    probe: str
    chrom: str
    pos: int
    ref: str
    alt: str
    genotype: str
    reference_kmer: str
    alternate_kmer: str


def target_regions(step1: Path, coding: Path, padding: int) -> list[tuple[str, int, int]]:
    """Coding intervals of the target genes only — decoys are not a witness set.

    The witness must lie where the bait is *densest* and where the step's conclusions are
    drawn. Padding is the narrow one: an allele in a deep intron of a core gene would test
    the wide padding, which is not what H021 is about.
    """
    symbols = {
        row["symbol"] for row in csv.DictReader((step1 / "targets.tsv").open(), delimiter="\t")
    }
    with coding.open(encoding="utf-8") as handle:
        return [
            (row["chrom"], max(0, int(row["start"]) - padding), int(row["end"]) + padding)
            for row in csv.DictReader(handle, delimiter="\t")
            if row["gene"] in symbols
        ]


def sample_alleles(
    regions: list[tuple[str, int, int]], sample: int, seed: int, settings: Postgres
) -> list[Allele]:
    """Heterozygous PASS single-base substitutions inside the regions, seeded random draw.

    The SQL selects; the draw happens here so the seed is ours and the sample is
    reproducible from the manifest rather than from whatever order Postgres returned.
    """
    values = ", ".join(f"('{chrom}', {start}, {end})" for chrom, start, end in regions)
    query = f"""
        WITH region(chrom, start, stop) AS (VALUES {values})
        SELECT v.chrom, CAST(v.pos AS BIGINT) AS pos, v.ref, v.alt,
               split_part(v.sample_call, ':', 1) AS genotype
        FROM pg.warehouse.variants_raw v
        JOIN region r
          ON v.chrom = r.chrom
         AND CAST(v.pos AS BIGINT) BETWEEN r.start AND r.stop
        WHERE v.filter = 'PASS'
          AND length(v.ref) = 1 AND length(v.alt) = 1
          AND v.alt IN ('A', 'C', 'G', 'T')
          AND split_part(v.sample_call, ':', 1) IN {HET_CALLS}
    """
    with postgres.attached(settings, read_only=True) as connection:
        rows = connection.execute(query).fetchall()
    drawn = random.Random(seed).sample(rows, min(sample, len(rows)))
    return [
        Allele(chrom=chrom, pos=int(pos), ref=ref, alt=alt, genotype=genotype)
        for chrom, pos, ref, alt, genotype in drawn
    ]


def faidx(reference: Path, chrom: str, start: int, end: int) -> str:
    """One reference slice, 1-based inclusive, as samtools spells it."""
    result = subprocess.run(
        ["samtools", "faidx", str(reference), f"{chrom}:{start}-{end}"],
        capture_output=True,
        text=True,
        check=True,
    )
    return "".join(result.stdout.splitlines()[1:]).upper()


def probes(alleles: list[Allele], reference: Path, k: int) -> list[Probe]:
    """A reference and an alternate k-mer centred on each allele.

    The alternate k-mer is the read sequence a carrier must contain; the reference k-mer
    is its control, and a probe whose reference k-mer does not match the callset's REF
    base is dropped rather than guessed at — that mismatch means the reference build and
    the callset disagree, which is the one thing this whole stage assumes they do not.
    """
    flank = k // 2
    built: list[Probe] = []
    for allele in alleles:
        window = faidx(reference, allele.chrom, allele.pos - flank, allele.pos + flank)
        if len(window) != k or window[flank] != allele.ref:
            continue
        alternate = window[:flank] + allele.alt + window[flank + 1 :]
        if set(alternate) - set("ACGT"):
            continue
        built.append(
            Probe(
                probe=f"alt{len(built) + 1}",
                **asdict(allele),
                reference_kmer=window,
                alternate_kmer=alternate,
            )
        )
    return built


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step1", type=Path, default=DEFAULT_STEP1)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--coding", type=Path, default=DEFAULT_CODING)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--k", type=int, default=K)
    parser.add_argument("--padding", type=int, default=2_000)
    parser.add_argument("--sample", type=int, default=120, help="probes to draw (API cap: 500)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    regions = target_regions(args.step1, args.coding, args.padding)
    print(f"{len(regions):,} target coding intervals (+/- {args.padding:,} bp)")
    alleles = sample_alleles(regions, args.sample, args.seed, Postgres.from_env())
    print(f"drew {len(alleles)} heterozygous PASS substitutions from seed {args.seed}")
    built = probes(alleles, args.reference, args.k)
    dropped = len(alleles) - len(built)
    print(f"built {len(built)} probe pairs ({dropped} dropped: reference/callset mismatch or N)")

    table = args.out / "witness-probes.tsv"
    with table.open("w", encoding="ascii", newline="\n") as handle:
        for probe in built:
            handle.write(f"{probe.probe}\t{probe.alternate_kmer}\n")
    detail = args.out / "witness.json"
    detail.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "tool": "tools/build_it2_witness.py",
                "seed": args.seed,
                "k": args.k,
                "padding": args.padding,
                "regions": len(regions),
                "drawn": len(alleles),
                "probes": len(built),
                "dropped": dropped,
                "source": "pg.warehouse.variants_raw (layer 1, unfiltered delivered callset)",
                "filters": "FILTER = PASS, single-base REF and ALT, heterozygous genotype",
                "alleles": [asdict(probe) for probe in built],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {table} ({len(built)} probes) and {detail}")
    print("next: POST /scan with these probes, then join the hits to the bait survivors")
    return 0


if __name__ == "__main__":
    sys.exit(main())
