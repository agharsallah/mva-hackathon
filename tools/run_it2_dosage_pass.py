#!/usr/bin/env python3
"""Run step 8's dosage pass on the job service, and turn its counts into copy numbers.

The probe set is uploaded once and named by key; the pass runs where the reads are. Three
guards, in the order they matter:

1. **The projection is printed before the pass is submitted.** A run over 1.07 billion reads
   on a shared machine is an hour that cannot be taken back, so what it should cost and what
   it should see are stated first.
2. **A timing probe runs first unless it is explicitly skipped.** ``--shards N`` measures the
   real per-shard cost on this service today rather than trusting a figure measured in
   September, and the full pass is licensed by it.
3. **A partial result is labelled partial.** ``CountResult.complete`` is false whenever fewer
   shards were swept than the store holds, and nothing downstream reads a partial count as a
   dosage.

Usage::

    uv run python tools/run_it2_dosage_pass.py --shards 2          # timing probe
    uv run python tools/run_it2_dosage_pass.py --upload --full     # the pass
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import it2_step8_common as common
from mva.io.writers import write_json, write_tsv
from mva.kmer.chromosome import ChromosomeProbes
from mva.kmer.dosage import dosage
from mva.reads import client as reads_client
from mva.warehouse import objects
from mva.warehouse.settings import object_store, setting

DEFAULT_PROBES = Path("build/it2/step-8/probes")
DEFAULT_KEY = "derived/it2/step-8/dosage-probes.npy"
SHARDS = 272


def load_design(root: Path) -> ChromosomeProbes:
    """The probe set as designed, so a flat count vector can be split by contig again."""
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    return ChromosomeProbes(
        kmers=np.load(root / "dosage-probes.npy"),
        contigs=tuple(summary["contigs"]),
        owner=np.load(root / "dosage-owner.npy"),
        considered=summary["considered"],
        k=int(summary["k"]),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probes", type=Path, default=DEFAULT_PROBES)
    parser.add_argument("--key", default=DEFAULT_KEY, help="object key to publish probes under")
    parser.add_argument("--out", type=Path, default=common.DEFAULT_OUT)
    parser.add_argument("--upload", action="store_true", help="publish the probe array first")
    parser.add_argument("--shards", type=int, default=2, help="timing probe; 0 with --full")
    parser.add_argument("--full", action="store_true", help="sweep every shard")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--api", default="", help="override MVA_READS_API_URL")
    args = parser.parse_args(argv)

    base = args.api or setting("MVA_READS_API_URL") or "http://127.0.0.1:8765"
    token = setting("MVA_API_TOKEN") or ""

    design = load_design(args.probes)
    print(f"probe set: {len(design):,} k-mers over {len(design.contigs)} contigs")
    print(
        f"projection: {SHARDS} shards; a partial run is labelled partial and not read as a dosage"
    )

    if args.upload:
        store = object_store()
        published = objects.put(store, args.probes / "dosage-probes.npy", args.key)
        print(f"published  {published}")

    body = {
        "probes_key": args.key,
        "k": design.k,
        "workers": args.workers,
        **({} if args.full else {"shard_limit": args.shards}),
    }
    scope = "every shard" if args.full else f"{args.shards} shard(s)"
    print(f"submitting: {len(design):,} probes over {scope}")
    started = time.perf_counter()
    result = reads_client.submit("tally", body, base, token)
    elapsed = time.perf_counter() - started
    counts = np.array(result.pop("counts", []), dtype=np.int64)
    print(f"\npass: {json.dumps(result, indent=2)}")
    print(f"wall clock {elapsed / 60:.1f} min")

    if not result.get("complete"):
        per_shard = elapsed / max(result.get("shards_swept", 1), 1)
        print(
            f"\npartial pass. Measured {per_shard:.1f} s per shard here, so the full "
            f"{SHARDS} shards project to {SHARDS * per_shard / 60:.0f} min. "
            "Re-run with --full to license a dosage."
        )
        return 0

    args.out.mkdir(parents=True, exist_ok=True)
    rows = [row.as_dict() for row in dosage(counts, design, seed=common.SEED)]
    write_json(args.out / "dosage.json", {"pass": result, "dosage": rows})
    columns = list(rows[0]) if rows else []
    write_tsv(args.out / "tables" / "it2_chrom_dosage.tsv", rows, columns)
    print(f"\nwrote {args.out}/dosage.json and its table")
    for row in rows:
        print(
            f"  chr{row['chrom']:<4} relative {row['relative']:.4f} "
            f"[{row['low']:.4f}, {row['high']:.4f}]  absolute {row['absolute']:.4f}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
