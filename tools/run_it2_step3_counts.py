#!/usr/bin/env python3
"""Stage 2 of step 3 — count every probe in the recovered reads, once per molecule.

The reads are already here. Step 2's pass over 1.07 billion of them kept the 15,773,226
that touch a baited region (7,886,613 complete pairs), and step 3 counts its probes in
*those* — no job service, no second full pass. The plan's "single read pass for steps 2-3-8"
did not happen: that pass asked only whether a read touched the bait and returned reads, not
counts (entry 087).

**Counted per fragment, not per read.** R1 and R2 are two reads of one piece of DNA. At a
~266 bp fragment against 2 x 150 bp of read they overlap, so a probe sitting in the overlap
is seen twice for a single molecule — and the genotype model's coverage parameter is per
molecule. Both numbers are reported: the collapsed count is what the model is fitted on, and
the raw-to-collapsed ratio is a QC number rather than an assumption.

**How the collapse stays cheap.** Deduplicating ``(fragment, probe)`` pairs exactly would
mean holding tens of millions of two-column rows. Instead each pair is packed into one
``uint64``: the flowcell coordinate is hashed to 40 bits and the probe index occupies 21.
Two *different* fragments collide with probability about 2^-40 each, so across 7.9 million
fragments the expected number of collided pairs is ~28 — each of which under-counts one
probe by one molecule out of tens. That is three orders of magnitude below the dispersion
the genotype model fits, and it is recorded here rather than presented as exact.

Usage::

    uv run python tools/run_it2_step3_counts.py
    uv run python tools/run_it2_step3_counts.py --reads build/it2/step-3/smoke/reads.parquet
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mva.kmer.count import hits_per_read, tally
from mva.kmer.encode import K
from mva.kmer.membership import Bait
from mva.reads.bait import code_matrix

DEFAULT_OUT = Path("build/it2/step-3")
DEFAULT_READS = Path("build/it2/step-2/baited-reads.parquet")

#: Reads per batch. Each holds a ``rows x 119`` uint64 window matrix twice over, so 400,000
#: reads is ~760 MB of working set — comfortable inside 16 GiB beside the probe set.
BATCH = 400_000

#: Bits the probe index occupies in a packed pair. 2^21 = 2,097,152 distinct probe k-mers,
#: checked rather than assumed.
SLOT_BITS = 21
SLOT_MASK = (1 << SLOT_BITS) - 1

#: Bits left for the hashed fragment identity. See the module docstring for the collision
#: arithmetic this number is chosen by.
FRAGMENT_BITS = 64 - SLOT_BITS

_U64 = np.uint64


@dataclass(frozen=True)
class Counted:
    """Two tallies of the same pass: raw occurrences, and one observation per molecule."""

    raw: np.ndarray
    per_fragment: np.ndarray
    reads_scanned: int
    windows_scanned: int
    hit_pairs: int
    distinct_pairs: int
    seconds: float


def _mix(values: np.ndarray) -> np.ndarray:
    """SplitMix64's finaliser — the same one :mod:`mva.kmer.membership` uses."""
    with np.errstate(over="ignore"):
        mixed = values ^ (values >> _U64(30))
        mixed = (mixed * _U64(0xBF58476D1CE4E5B9)) & _U64(0xFFFFFFFFFFFFFFFF)
        mixed = mixed ^ (mixed >> _U64(27))
        mixed = (mixed * _U64(0x94D049BB133111EB)) & _U64(0xFFFFFFFFFFFFFFFF)
        return np.asarray(mixed ^ (mixed >> _U64(31)), dtype=np.uint64)


def fragment_ids(frame: pl.DataFrame) -> np.ndarray:
    """One hashed identity per read, equal for the two reads of a pair.

    The flowcell coordinate ``(lane, tile, x, y)`` is what names a cluster, and both mates
    of a fragment carry the same one — which is why ``mva.reads.bait`` uses it as the pair
    key and why it can stand in for the molecule here.
    """
    packed = (
        (frame["lane"].to_numpy().astype(np.uint64) << _U64(44))
        | (frame["tile"].to_numpy().astype(np.uint64) << _U64(32))
        | (frame["x"].to_numpy().astype(np.uint64) << _U64(16))
        | frame["y"].to_numpy().astype(np.uint64)
    )
    return _mix(packed) >> _U64(SLOT_BITS)


def count_reads(reads: Path, probes: Bait, *, batch: int, limit: int | None) -> Counted:
    """Stream the recovered reads, tallying raw occurrences and per-fragment presence."""
    if len(probes) > (SLOT_MASK + 1):
        raise ValueError(
            f"{len(probes):,} probe k-mers exceeds the {SLOT_MASK + 1:,} a packed pair holds"
        )

    scan = pl.scan_parquet(reads)
    total = int(scan.select(pl.len()).collect().item())
    if limit is not None:
        total = min(total, limit)

    raw = np.zeros(len(probes), dtype=np.uint64)
    packed_pairs: list[np.ndarray] = []
    scanned = windows = 0
    started = time.perf_counter()
    for offset in range(0, total, batch):
        rows = min(batch, total - offset)
        frame = scan.slice(offset, rows).collect()
        codes = code_matrix(frame["sequence"])
        counted = tally(codes, probes)
        raw += counted.counts.astype(np.uint64)
        scanned += counted.reads_scanned
        windows += counted.windows_scanned

        read_rows, slots = hits_per_read(codes, probes)
        if read_rows.size:
            identity = fragment_ids(frame)[read_rows].astype(np.uint64)
            packed_pairs.append((identity << _U64(SLOT_BITS)) | slots.astype(np.uint64))
        print(
            f"  {offset + rows:,}/{total:,} reads  {time.perf_counter() - started:,.0f}s",
            flush=True,
        )

    joined = np.concatenate(packed_pairs) if packed_pairs else np.empty(0, dtype=np.uint64)
    unique = np.unique(joined)
    per_fragment = np.bincount(
        (unique & _U64(SLOT_MASK)).astype(np.int64), minlength=len(probes)
    ).astype(np.uint64)
    return Counted(
        raw=raw,
        per_fragment=per_fragment,
        reads_scanned=scanned,
        windows_scanned=windows,
        hit_pairs=int(joined.size),
        distinct_pairs=int(unique.size),
        seconds=round(time.perf_counter() - started, 1),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--reads", type=Path, default=DEFAULT_READS)
    parser.add_argument("--batch", type=int, default=BATCH)
    parser.add_argument("--limit", type=int, default=None, help="stop after this many reads")
    parser.add_argument("--k", type=int, default=K)
    args = parser.parse_args(argv)

    probes_file = args.out / "probes.npz"
    for path in (args.reads, probes_file):
        if not path.is_file():
            print(f"missing {path} — run tools/build_it2_probes.py first")
            return 1

    stored = np.load(probes_file)
    values = np.concatenate([stored["ref_kmer"], stored["alt_kmer"]])
    probes = Bait.of(values, k=args.k)
    print(f"{stored['allele'].size:,} probe pairs -> {len(probes):,} distinct k-mers")

    result = count_reads(args.reads, probes, batch=args.batch, limit=args.limit)

    # Back from the deduplicated k-mer set to the two sides of each pair. A k-mer that is one
    # allele's reference and another's alternate was counted once and is read twice, which is
    # correct: it is one quantity, observed once.
    ref_slot = probes.positions(stored["ref_kmer"])
    alt_slot = probes.positions(stored["alt_kmer"])
    counts_path = args.out / "probe-counts.npz"
    np.savez_compressed(
        counts_path,
        allele=stored["allele"],
        offset=stored["offset"],
        ref_fragments=result.per_fragment[ref_slot],
        alt_fragments=result.per_fragment[alt_slot],
        ref_raw=result.raw[ref_slot],
        alt_raw=result.raw[alt_slot],
    )

    raw_total = int(result.raw.sum())
    collapsed = int(result.per_fragment.sum())
    summary = {
        "probe_pairs": int(stored["allele"].size),
        "probe_kmers": len(probes),
        "reads_scanned": result.reads_scanned,
        "windows_scanned": result.windows_scanned,
        "hit_pairs": result.hit_pairs,
        "distinct_pairs": result.distinct_pairs,
        "raw_occurrences": raw_total,
        "fragment_observations": collapsed,
        "raw_to_fragment_ratio": round(raw_total / collapsed, 4) if collapsed else None,
        "probes_with_no_observation": int((result.per_fragment == 0).sum()),
        "seconds": result.seconds,
        "batch": args.batch,
        "outputs": {"counts": str(counts_path)},
    }
    (args.out / "counts-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
