#!/usr/bin/env python3
"""Stage 2's gate — does the new counting kernel count what it claims?

`mva.kmer.count` is a new instrument, and step 3's every number rests on it. So before any
of those numbers are believed it is checked against the engine step 0 already validated:
the multi-literal string matcher behind `mva.reads.scan` (Polars ``contains_any``, an
Aho-Corasick/Teddy automaton). The two share no code and no representation — one searches
64-bit integers in a sorted array, the other searches text — so agreeing is evidence and
disagreeing is a defect in exactly one of them.

**The comparison is "how many reads carry this probe".** That is what the strike answers;
the kernel's occurrence tally is a different quantity (a probe twice in one read is two
occurrences and one read), so ``hits_per_read`` is the side compared.

**Both strands, explicitly.** A fragment is sequenced from whichever strand it came off. The
kernel handles this by storing one canonical k-mer; the strike handles it by searching for
the sequence and its reverse complement. Reading the same answer out of two different
solutions to the same problem is most of the value of the check.

**Twenty probes, on a read subset.** The strike was validated at twenty literals
(``docs/step-0/methodology/027``) and is not the thing being tested here — the kernel is. A
subset keeps the check to seconds so it can run as a gate rather than as an occasion.

Usage::

    uv run python tools/check_it2_kernel.py
    uv run python tools/check_it2_kernel.py --probes 20 --reads 2000000
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mva.kmer.count import hits_per_read
from mva.kmer.encode import K, decode
from mva.kmer.membership import Bait
from mva.reads.bait import code_matrix
from mva.reads.scan import reverse_complement

DEFAULT_OUT = Path("build/it2/step-3")
DEFAULT_READS = Path("build/it2/step-2/baited-reads.parquet")

#: Drawn once, recorded, never edited.
SEED = 20260913


def strike_counts(frame: pl.DataFrame, sequences: list[str]) -> list[int]:
    """Reads carrying each probe, by the text matcher — one column expression per probe.

    ``contains_any`` over the probe and its reverse complement is exactly what
    ``mva.reads.scan.survivors`` builds, evaluated over the same reads.
    """
    return [
        int(
            frame.select(
                pl.col("sequence").str.contains_any([sequence, reverse_complement(sequence)]).sum()
            ).item()
        )
        for sequence in sequences
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--reads", type=Path, default=DEFAULT_READS)
    parser.add_argument("--probes", type=int, default=20)
    parser.add_argument("--rows", type=int, default=2_000_000)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--k", type=int, default=K)
    args = parser.parse_args(argv)

    probes_file = args.out / "probes.npz"
    for path in (args.reads, probes_file):
        if not path.is_file():
            print(f"missing {path} — run tools/build_it2_probes.py first")
            return 1

    stored = np.load(probes_file)
    pool = np.unique(np.concatenate([stored["ref_kmer"], stored["alt_kmer"]]))
    rng = np.random.default_rng(args.seed)
    drawn = pool[rng.choice(pool.size, size=min(args.probes, pool.size), replace=False)]
    bait = Bait.of(drawn, k=args.k)
    sequences = [decode(int(value), k=args.k) for value in bait.kmers]

    frame = pl.scan_parquet(args.reads).head(args.rows).collect()
    _rows, slots = hits_per_read(code_matrix(frame["sequence"]), bait)
    kernel = np.bincount(slots, minlength=len(bait)).tolist()
    strike = strike_counts(frame, sequences)

    disagreements = [
        {"probe": index, "kernel": int(a), "strike": int(b)}
        for index, (a, b) in enumerate(zip(kernel, strike, strict=True))
        if int(a) != int(b)
    ]
    report = {
        "probes": len(bait),
        "reads": frame.height,
        "kernel_total": int(sum(kernel)),
        "strike_total": int(sum(strike)),
        "probes_with_no_hit": int(sum(1 for value in kernel if value == 0)),
        "disagreements": disagreements,
        "agree": not disagreements,
        "seed": args.seed,
    }
    (args.out / "kernel-check.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    if disagreements:
        print(f"\nGATE FAILED: {len(disagreements)} probe(s) disagree")
        return 1
    print("\ngate passed: the kernel and the strike agree on every probe")
    return 0


if __name__ == "__main__":
    sys.exit(main())
