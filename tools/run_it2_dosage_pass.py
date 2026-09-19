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
   shards were swept than the store holds, and an accidental partial is never read as a
   dosage.

``--subsample N`` is the one exception, and it is a different thing from an accidental
partial: a *deliberate* thinning with an argument behind it. Shards are flowcell partitions
-- lane and read number -- not genomic ones, so any subset of them is a uniform sample of
the library with respect to the genome. Dosage is a **ratio between chromosomes**, and a
uniform thinning multiplies every chromosome's expected count by the same factor, so the
ratio is unbiased and only its variance rises. The thinning factor is recorded in the
output and in every row's provenance; the full-pass projection is printed beside it so the
cost of the choice is visible.

**This argument does not transfer to genotyping.** :mod:`mva.kmer.count` needs absolute
multiplicity at one site, where a thinned count is simply wrong -- which is why that module
says a sampled count is not a count. The difference is the ratio.

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
from mva.warehouse.settings import object_store, setting
from mva.warehouse.source import client

DEFAULT_PROBES = Path("build/it2/step-8/probes")
DEFAULT_KEY = "derived/it2/step-8/dosage-probes.npy"
SHARDS = 272


def load_design(root: Path) -> tuple[ChromosomeProbes, np.ndarray]:
    """The design and the sorted unique array the pass counts, which are not the same length.

    The calibration set is drawn from the per-chromosome pool, so ~8,000 k-mers belong to two
    groups. The design keeps both memberships; the uploaded array holds each k-mer once,
    because that is what a lookup structure can hold. Both are returned and
    :func:`mva.kmer.dosage.dosage` maps one onto the other.
    """
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    design = ChromosomeProbes(
        kmers=np.load(root / "dosage-design.npy"),
        contigs=tuple(summary["contigs"]),
        owner=np.load(root / "dosage-owner.npy"),
        considered=summary["considered"],
        k=int(summary["k"]),
    )
    return design, np.load(root / "dosage-probes.npy")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probes", type=Path, default=DEFAULT_PROBES)
    parser.add_argument("--key", default=DEFAULT_KEY, help="object key to publish probes under")
    parser.add_argument("--out", type=Path, default=common.DEFAULT_OUT)
    parser.add_argument("--upload", action="store_true", help="publish the probe array first")
    parser.add_argument("--shards", type=int, default=2, help="timing probe; 0 with --full")
    parser.add_argument("--full", action="store_true", help="sweep every shard")
    parser.add_argument(
        "--subsample",
        type=int,
        default=0,
        help="sweep this many shards and license a dosage from them. A deliberate uniform "
        "thinning, not a partial run: shards are flowcell partitions, so the ratio between "
        "chromosomes is unbiased and only its variance rises.",
    )
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--api", default="", help="override MVA_READS_API_URL")
    args = parser.parse_args(argv)

    base = args.api or setting("MVA_READS_API_URL") or "http://127.0.0.1:8765"
    token = setting("MVA_API_TOKEN") or ""

    design, counted = load_design(args.probes)
    print(
        f"probe set: {len(design):,} memberships over {len(design.contigs)} contigs, "
        f"{counted.size:,} distinct k-mers uploaded"
    )
    print(
        f"projection: {SHARDS} shards; a partial run is labelled partial and not read as a dosage"
    )

    if args.upload:
        # Raw bytes, not `objects.put`: that helper round-trips through DuckDB's Parquet
        # writer, which is right for a table and wrong for a NumPy array. The bait upload in
        # mva.reads.baitjob takes the same boto3 path for the same reason.
        store = object_store()
        local = args.probes / "dosage-probes.npy"
        client(store).upload_file(str(local), store.bucket, args.key)
        print(f"published  s3://{store.bucket}/{args.key} ({local.stat().st_size:,} bytes)")

    swept = 0 if args.full else (args.subsample or args.shards)
    body = {
        "probes_key": args.key,
        "k": design.k,
        "workers": args.workers,
        **({} if args.full else {"shard_limit": swept}),
    }
    scope = "every shard" if args.full else f"{swept} shard(s)"
    print(f"submitting: {len(design):,} probes over {scope}")
    started = time.perf_counter()
    result = reads_client.submit("tally", body, base, token)
    elapsed = time.perf_counter() - started
    counts = np.array(result.pop("counts", []), dtype=np.int64)
    print(f"\npass: {json.dumps(result, indent=2)}")
    print(f"wall clock {elapsed / 60:.1f} min")

    per_shard = elapsed / max(result.get("shards_swept", 1), 1)
    if not result.get("complete") and not args.subsample:
        print(
            f"\npartial pass. Measured {per_shard:.1f} s per shard here, so the full "
            f"{SHARDS} shards project to {SHARDS * per_shard / 60:.0f} min. "
            "Re-run with --full, or with --subsample N to license a dosage from a "
            "deliberate uniform thinning."
        )
        return 0

    thinning = (result.get("shards_swept") or SHARDS) / SHARDS
    if args.subsample:
        print(
            f"\ndeliberate subsample: {result['shards_swept']} of {SHARDS} shards "
            f"({thinning:.1%} of the library, {result['reads_scanned']:,} reads). Shards are "
            "flowcell partitions, so this is a uniform thinning and the ratio between "
            f"chromosomes is unbiased. The full pass would have taken "
            f"{SHARDS * per_shard / 60:.0f} min."
        )

    args.out.mkdir(parents=True, exist_ok=True)
    rows = [row.as_dict() for row in dosage(counts, design, kmers=counted, seed=common.SEED)]
    for row in rows:
        row["shards_swept"] = result.get("shards_swept")
        row["thinning"] = round(thinning, 5)
    write_json(
        args.out / "dosage.json",
        {
            "pass": result,
            "thinning": round(thinning, 5),
            "thinning_note": (
                "shards are flowcell partitions, not genomic ones, so a subset of them is a "
                "uniform sample of the library; dosage is a ratio between chromosomes, which "
                "a uniform thinning leaves unbiased while raising its variance"
            ),
            "dosage": rows,
        },
    )
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
