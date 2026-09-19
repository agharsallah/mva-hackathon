#!/usr/bin/env python3
"""Turn a saved dosage pass into a copy-number statement, after removing composition.

The pass produces a count per probe. Dividing by a denominator gives a ratio, and the ratio
comes with a bootstrap interval -- but that interval resamples *probes*, so it measures
counting noise and is blind to any bias every probe on a chromosome shares. GC bias is
exactly such a bias: library preparation and amplification favour some compositions by a few
per cent across a whole chromosome, which is the same size as the low-fraction mosaic gain
this step is looking for.

So the ratio is regressed on each chromosome's GC content, measured from the reference, and
what survives is the number a copy-number claim may be made from. The residual spread across
autosomes is the honest precision floor -- not the bootstrap width.

**The regressor is the chromosome's GC, not the probes'.** Both were computed and the
chromosome's was chosen on two grounds settled before any residual was read: GC bias acts on
fragments of a few hundred bases, so a 31-mer's own GC is the wrong scale; and the surviving
probes are what the uniqueness filter left, which is not composed like the chromosome around
it. This tool reports both fits so the choice is checkable rather than asserted.

Usage::

    uv run python tools/analyse_it2_dosage.py
    uv run python tools/analyse_it2_dosage.py --counts build/it2/step-8/counts.npy
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import it2_step8_common as common
from mva.io.writers import write_json, write_tsv
from mva.kmer import fasta
from mva.kmer.chromosome import ChromosomeProbes, gc_content
from mva.kmer.dosage import Composition, Dosage, composition, dosage

REPO = Path(__file__).resolve().parent.parent
DEFAULT_REFERENCE = REPO / "build" / "reference" / "GRCh38.fa"
DEFAULT_PROBES = Path("build/it2/step-8/probes")

#: Contigs kept out of every fit: one copy in this male proband, so their ratio is a half
#: and a regression through them would be fitting sex, not composition.
HEMIZYGOUS = frozenset({"X", "Y"})

#: Reported beside the raw z. With 22 autosomes tested at once, an uncorrected 0.05 is a
#: coin flip -- roughly one autosome in the set will clear it on a genome with no event.
AUTOSOMES = 22


def reference_gc(path: Path, wanted: frozenset[str]) -> dict[str, float]:
    """GC per contig, straight from the reference. One pass; there is no index to seek with."""
    return {contig.name: gc_content(contig) for contig in fasta.contigs(path, wanted=set(wanted))}


def load_design(root: Path) -> tuple[ChromosomeProbes, np.ndarray]:
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    design = ChromosomeProbes(
        kmers=np.load(root / "dosage-design.npy"),
        contigs=tuple(summary["contigs"]),
        owner=np.load(root / "dosage-owner.npy"),
        considered=summary["considered"],
        k=int(summary["k"]),
    )
    return design, np.load(root / "dosage-probes.npy")


def report(rows: tuple[Dosage, ...], fit: Composition) -> list[dict[str, float | str]]:
    """One row per autosome: the ratio, what composition predicted, and what is left."""
    out: list[dict[str, float | str]] = []
    for row in rows:
        residual = fit.residual.get(row.chrom)
        if residual is None:
            continue
        z = (residual - 1.0) / fit.residual_spread if fit.residual_spread else 0.0
        out.append(
            {
                "chrom": row.chrom,
                "gc": round(fit.gc[row.chrom], 5),
                "relative": round(row.relative, 5),
                "residual": round(residual, 5),
                "z": round(z, 3),
                # A gain in a share f of cells raises a chromosome's sequence by f/2. The
                # inverse is signed: a loss comes out negative and is left that way.
                "implied_fraction": round(2 * (residual - 1.0), 5),
            }
        )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--counts", type=Path, default=Path("build/it2/step-8/counts.npy"))
    parser.add_argument("--probes", type=Path, default=DEFAULT_PROBES)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--out", type=Path, default=common.DEFAULT_OUT)
    args = parser.parse_args(argv)

    design, counted = load_design(args.probes)
    counts = np.load(args.counts)
    rows = dosage(counts, design, kmers=counted, seed=common.SEED)

    wanted = frozenset(name for name in design.contigs if name != "calibration")
    gc = reference_gc(args.reference, wanted)

    # Both fits, always. The chromosome-GC fit is the one reported; the probe-GC fit is kept
    # beside it because "we chose the better regressor" is a claim, and a reader should be
    # able to see what the other one said rather than take it on trust.
    by_chromosome = composition(rows, design, exclude=HEMIZYGOUS, gc=gc)
    by_probe = composition(rows, design, exclude=HEMIZYGOUS)

    for fit in (by_chromosome, by_probe):
        print(
            f"{fit.source:<26} pearson {fit.correlation:+.4f}  "
            f"R2 {fit.correlation**2 * 100:5.1f}%  "
            f"spread {fit.spread * 100:.3f}% -> {fit.residual_spread * 100:.3f}%"
        )

    table = report(rows, by_chromosome)
    worst = max(table, key=lambda row: abs(float(row["z"])))
    print()
    print(f"{'contig':<8}{'GC':>8}{'dosage':>9}{'residual':>10}{'z':>7}{'implied f':>11}")
    for row in table:
        implied = float(row["implied_fraction"]) * 100
        print(
            f"chr{row['chrom']:<5}{row['gc']:>8.4f}{row['relative']:>9.4f}"
            f"{row['residual']:>10.4f}{row['z']:>7.2f}{implied:>10.2f}%"
        )
    print()
    print(
        f"largest residual: chr{worst['chrom']} at z {worst['z']}, implied fraction "
        f"{float(worst['implied_fraction']) * 100:.2f}%. The precision floor is the residual "
        f"spread, {by_chromosome.residual_spread * 100:.2f}%, which is "
        f"{by_chromosome.residual_spread * 200:.2f}% of cells -- not the bootstrap width."
    )

    args.out.mkdir(parents=True, exist_ok=True)
    write_json(
        args.out / "composition.json",
        {
            "reported": by_chromosome.as_dict(),
            "alternative": by_probe.as_dict(),
            "autosomes_tested": AUTOSOMES,
            "note": (
                "the residual spread is the precision floor for a copy-number claim; the "
                "bootstrap interval on `relative` resamples probes and cannot see a bias "
                "every probe on a chromosome shares"
            ),
            "rows": table,
        },
    )
    write_tsv(
        args.out / "tables" / "it2_dosage_composition.tsv",
        table,
        ["chrom", "gc", "relative", "residual", "z", "implied_fraction"],
    )
    print(f"\nwrote {args.out}/composition.json and its table")
    return 0


if __name__ == "__main__":
    sys.exit(main())
