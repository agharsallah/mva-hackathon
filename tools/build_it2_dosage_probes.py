#!/usr/bin/env python3
"""Cut step 8's dosage probes from the reference, and say what the pass will cost.

Allele balance cannot see a chromosome with no heterozygous sites — the male X, or a gain
present in every cell. Dosage can, and dosage needs a fixed set of k-mers that name each
chromosome unambiguously. This cuts them.

Three numbers are printed **before** the pass is licensed, because a pass over 1.07 billion
reads that turns out to have been asking the wrong question is an hour of a shared machine:

``probes kept``      how many survived the uniqueness filter, per contig
``expected count``   probes x depth / 2, the mean occurrences each should be seen at
``projected time``   shards x the measured per-shard cost

**The probes are reference sequence.** They carry no patient information and the array is
published to the object store so the job service can fetch it by key — the same shape the
step-2 bait used, and for the same reason: a quarter of a million k-mers do not belong in a
request body. The *counts* that come back are about the child and stay under ``build/``.

Writes, under ``--out`` (gitignored — reference sequence, but large):

``dosage-probes.npy``   sorted unique canonical k-mers that survived the filter
``dosage-owner.npy``    which contig each surviving probe came from
``summary.json``        per-contig counts, the arithmetic above, and what was dropped
``provenance.json``     inputs with their sha256, the parameters, and the code version

Usage::

    uv run python tools/build_it2_dosage_probes.py
    uv run python tools/build_it2_dosage_probes.py --per-chromosome 5000 --skip-uniqueness
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mva.kmer import chromosome, fasta, uniqueness
from mva.kmer.membership import Bait

REPO = Path(__file__).resolve().parent.parent
DEFAULT_REFERENCE = REPO / "build" / "reference" / "GRCh38.fa"
DEFAULT_OUT = REPO / "build" / "it2" / "step-8" / "probes"

#: The delivered callset's mapped depth. Used only to print what the pass should see.
DEFAULT_DEPTH = 44.0

#: Measured 2026-09-11 on the job service, beside the data: seconds per shard for a full
#: pass. Printed as a projection, never as a promise.
SECONDS_PER_SHARD = 11.0
SHARDS = 272

#: The contigs a dosage is reported for, in karyogram order, in the **bare** spelling
#: ``mva.kmer.fasta`` renames to on the way in — the same spelling the callset and the
#: warehouse use, so no name ever crosses a boundary. Alternates and unplaced contigs have
#: no dosage worth reporting and would only dilute the calibration set.
WANTED = (*(str(n) for n in range(1, 23)), "X", "Y")


def code_version() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            sha.update(chunk)
    return sha.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--per-chromosome", type=int, default=chromosome.DEFAULT_PER_CHROMOSOME)
    parser.add_argument("--calibration", type=int, default=chromosome.DEFAULT_PER_CHROMOSOME)
    parser.add_argument("--k", type=int, default=31)
    parser.add_argument("--depth", type=float, default=DEFAULT_DEPTH)
    parser.add_argument(
        "--skip-uniqueness",
        action="store_true",
        help="cut the probes without the genome-wide filter — a dry run, never a real set",
    )
    args = parser.parse_args(argv)

    if not args.reference.is_file():
        raise SystemExit(f"reference not found: {args.reference}")
    args.out.mkdir(parents=True, exist_ok=True)

    print(f"cutting from {args.reference} ({args.per_chromosome:,} per contig)")
    design = chromosome.design(
        fasta.contigs(args.reference, wanted=set(WANTED)),
        per_chromosome=args.per_chromosome,
        calibration=args.calibration,
        k=args.k,
    )
    print(f"  cut      {len(design):,} probes over {len(design.contigs)} contigs")

    report: dict[str, object] = {}
    kept = design
    if not args.skip_uniqueness:
        bait = Bait(np.sort(np.unique(design.kmers)), k=args.k)
        occurrence = uniqueness.count_in_genome(args.reference, bait)
        unique, report = uniqueness.drop_repeats(bait, occurrence)
        survivors = set(unique.kmers.tolist())
        mask = np.array([int(value) in survivors for value in design.kmers])
        kept = chromosome.ChromosomeProbes(
            kmers=design.kmers[mask],
            contigs=design.contigs,
            owner=design.owner[mask],
            considered=design.considered,
            k=args.k,
        )
        print(f"  unique   {len(kept):,} probes survive the genome-wide filter")

    np.save(args.out / "dosage-probes.npy", np.sort(np.unique(kept.kmers)))
    np.save(args.out / "dosage-owner.npy", kept.owner)

    per_contig = kept.per_contig()
    expected = args.depth / 2.0
    summary = {
        **kept.as_dict(),
        "uniqueness": report,
        "expected_count_per_probe": round(expected, 2),
        "expected_observations": {
            name: round(count * expected) for name, count in per_contig.items()
        },
        "projected_pass_minutes": round(SHARDS * SECONDS_PER_SHARD / 60.0, 1),
        "projected_note": (
            f"{SHARDS} shards at {SECONDS_PER_SHARD} s each, measured beside the data on "
            "2026-09-11. From a laptop the same pass is ~4.2 h, because the object-store "
            "link saturates and parallelism buys nothing."
        ),
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (args.out / "provenance.json").write_text(
        json.dumps(
            {
                "name": "it2_step8_dosage_probes",
                "built_by": "tools/build_it2_dosage_probes.py",
                "code_version": code_version(),
                "inputs": [
                    {
                        "name": args.reference.name,
                        "sha256": digest(args.reference),
                        "bytes": args.reference.stat().st_size,
                        "role": "the reference the probes are cut from; no patient sequence",
                    }
                ],
                "parameters": {
                    "k": args.k,
                    "per_chromosome": args.per_chromosome,
                    "calibration": args.calibration,
                    "uniqueness_filtered": not args.skip_uniqueness,
                },
                "outputs": [
                    {"path": "dosage-probes.npy", "probes": len(kept)},
                    {"path": "dosage-owner.npy", "probes": int(kept.owner.size)},
                ],
                "patient_data": "none: every probe is GRCh38 sequence",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\n  probes per contig: {per_contig}")
    print(f"  each should be seen ~{expected:.1f}x at {args.depth:.0f}x depth")
    print(f"  projected pass: {summary['projected_pass_minutes']} min beside the data")
    print(f"\nwrote {args.out}/dosage-probes.npy and its manifest")
    return 0


if __name__ == "__main__":
    sys.exit(main())
