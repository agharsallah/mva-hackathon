#!/usr/bin/env python3
"""Build `ressources/reference/cytoband_arms.tsv` — where each chromosome's arms end.

Step 8 tests the B-allele fraction per chromosome **and per arm**, because a mosaic event
can take one arm and disappear into a whole-chromosome mean. Nothing in this repository
knew where an arm ends: a chromosome arm is separated from its partner by the
**centromere** (the constricted region a chromosome is pulled from during division), and
its position is a property of the reference genome, not of any sample.

**Why a committed table and not an inference.** The obvious shortcut is to find the
centromere as the widest gap in the karyogram's per-megabase bins, since heterozygous
calls vanish across pericentromeric repeats. It does not survive contact:
`results.baf_bins` emits *no row* for an empty bin rather than a flagged one, so the gap
is a hole in a sequence rather than a value; the five acrocentric chromosomes put their
biggest hole at the start; and the 1q, 9q and 16q heterochromatin blocks produce competing
holes elsewhere. The gap survives as the *validation check* in `mva.mosaic.arms`, never as
the source.

**These are reference coordinates, not the child's.** `tools/check_coordinates.py` exempts
`ressources/` for exactly this reason (`SKIP_PREFIXES`): a public reference table carries
positions in the coordinate system, not positions of a patient's variants.

**Acrocentric chromosomes are detected, not listed.** A chromosome whose short arm is a
stalk of ribosomal repeats (13, 14, 15, 21, 22) has no callable p arm, and step 8 reports
it q-arm-only. The flag is read from the band table's own `stalk` stain rather than from a
hard-coded list of five numbers, so the rule is checkable against the file it came from.

Usage::

    uv run python tools/build_cytobands.py                 # fetch, build, manifest
    uv run python tools/build_cytobands.py --manifest-only # re-describe the committed bytes
"""

from __future__ import annotations

import argparse
import csv
import gzip
import sys
import urllib.request
from pathlib import Path

from mva.viz import manifestbase, referencemanifest

REPO = Path(__file__).resolve().parent.parent
DEFAULT_SCRATCH = REPO / "build" / "reference-scratch"
OUT = REPO / "ressources" / "reference" / "cytoband_arms.tsv"
SCRATCH_NAME = "cytoBand.txt.gz"

#: Only the primary assembly. The band file also carries alternate haplotypes and patch
#: contigs, which have no arms and no place in a per-chromosome table.
CANONICAL = tuple(f"chr{name}" for name in [*(str(n) for n in range(1, 23)), "X", "Y"])

COLUMNS = (
    "chrom",
    "chrom_length",
    "p_start",
    "p_end",
    "cen_start",
    "cen_end",
    "q_start",
    "q_end",
    "acrocentric",
    "bands",
)


def fetch(url: str, dest: Path) -> Path:
    """Download once into gitignored scratch; a present file is not re-fetched."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        print(f"scratch  {dest} (already present, not re-fetched)")
        return dest
    print(f"fetching {url}")
    with urllib.request.urlopen(url) as response, dest.open("wb") as handle:
        # The URL is the module-level constant below, never user input; `noqa` states that
        # rather than leaving the audit rule silently disabled.
        handle.write(response.read())
    print(f"scratch  {dest} ({dest.stat().st_size:,} bytes)")
    return dest


def read_bands(path: Path) -> dict[str, list[tuple[int, int, str, str]]]:
    """`chrom -> [(start, end, band, stain)]`, primary assembly only, in file order."""
    bands: dict[str, list[tuple[int, int, str, str]]] = {}
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for row in csv.reader(handle, delimiter="\t"):
            if len(row) < 5 or row[0] not in CANONICAL:
                continue
            bands.setdefault(row[0], []).append((int(row[1]), int(row[2]), row[3], row[4]))
    return bands


def arms(bands: list[tuple[int, int, str, str]]) -> dict[str, object]:
    """One chromosome's geometry, from its own bands.

    The centromere is the span of the bands stained ``acen`` — there are always two, one
    either side of the constriction. Everything before them is the p arm and everything
    after is the q arm, which is the definition rather than a heuristic.
    """
    acen = [(start, end) for start, end, _, stain in bands if stain == "acen"]
    if not acen:
        raise ValueError("no acen band: this contig has no centromere in the band table")
    cen_start = min(start for start, _ in acen)
    cen_end = max(end for _, end in acen)
    return {
        "chrom_length": max(end for _, end, _, _ in bands),
        "p_start": min(start for start, _, _, _ in bands),
        "p_end": cen_start,
        "cen_start": cen_start,
        "cen_end": cen_end,
        "q_start": cen_end,
        "q_end": max(end for _, end, _, _ in bands),
        # A short arm made of ribosomal stalk carries no unique sequence, so it carries no
        # heterozygous sites either: the arm exists cytogenetically and not in a callset.
        "acrocentric": any(stain == "stalk" and start < cen_start for start, _, _, stain in bands),
        "bands": len(bands),
    }


def build(source: Path, out: Path) -> int:
    bands = read_bands(source)
    missing = [name for name in CANONICAL if name not in bands]
    if missing:
        raise SystemExit(f"band table is missing {len(missing)} canonical contigs: {missing}")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for chrom in CANONICAL:
            geometry = arms(bands[chrom])
            writer.writerow({"chrom": chrom, **geometry})
    print(f"wrote    {out} ({len(CANONICAL)} rows)")
    return len(CANONICAL)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch", type=Path, default=DEFAULT_SCRATCH)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument(
        "--manifest-only",
        action="store_true",
        help="re-describe the committed table without fetching or rebuilding it",
    )
    args = parser.parse_args(argv)

    source = args.scratch / SCRATCH_NAME
    if not args.manifest_only:
        fetch(referencemanifest.CYTOBAND_URL, source)
        build(source, args.out)
    if not args.out.exists():
        raise SystemExit(f"{args.out} does not exist; run without --manifest-only first")
    manifestbase.write(
        referencemanifest.cytobands(args.out, source),
        args.out.with_suffix(".provenance.json"),
    )
    print(f"manifest {args.out.with_suffix('.provenance.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
