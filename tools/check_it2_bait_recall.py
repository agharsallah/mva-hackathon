#!/usr/bin/env python3
"""H021: does the bait keep the reads that carry a known allele? Ask the old instrument.

Step 2 reasons about absences — an exon with no coverage, a gene with no second allele —
and those only mean something if the survivor set really is a superset of the region's
variant-carrying reads. Asserting that would be a claim with no test, so the tool the bait
replaces is used to check it.

``mva.reads.scan`` finds every read containing an exact 31-mer, on either strand, with a
matcher measured three independent ways (step-0 entries 024-027) and capped at 500 probes.
``tools/build_it2_witness.py`` drew 120 heterozygous alleles the delivered callset already
reports inside the baited region and built the 31-mer centred on each alternate base. Every
read the strike returns for those probes came from inside the bait **by construction**, so
every one of them must appear among the bait sweep's survivors. The share that does is the
bait's measured recall at the stride that was used.

The join key is the flowcell coordinate ``(lane, tile, x, y)`` — the same key R1 and R2 of
a fragment share, and the only identity the read store keeps.

A recall below 0.90 refutes H021, and the pre-registered response is to lower the stride
and repeat the pass **before** interpreting any allele the bait produced.

Usage::

    uv run python tools/check_it2_bait_recall.py
    uv run python tools/check_it2_bait_recall.py --reads build/it2/step-2/baited-reads.parquet
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import httpx
import polars as pl

from mva.warehouse.settings import setting

DEFAULT_OUT = Path("build/it2/step-2")
#: Reads reported per probe. A true single-copy 31-mer is expected in ~35 reads at 44x
#: (mva.reads.triage), so 1000 is far above any honest count and the cap never binds.
SCAN_LIMIT = 1000
#: How long to let the strike run. It is one pass over 1.07 billion reads.
WAIT_SECONDS = 280
POLL_ROUNDS = 12


def submit_scan(probes: list[tuple[str, str]], base: str, token: str) -> dict:
    """Run the 500-probe strike as a job and wait for it, long-polling."""
    headers = {"X-API-Key": token}
    body = {
        "probes": [{"name": name, "sequence": sequence} for name, sequence in probes],
        "limit": SCAN_LIMIT,
    }
    with httpx.Client(base_url=base, timeout=60.0, headers=headers) as client:
        started = client.post("/scan", json=body)
        started.raise_for_status()
        job_id = started.json()["id"]
        print(f"strike job {job_id}: {len(probes)} probes, one pass over the store")
        for _ in range(POLL_ROUNDS):
            reply = client.get(
                f"/jobs/{job_id}/wait", params={"timeout": WAIT_SECONDS}, timeout=None
            )
            reply.raise_for_status()
            job = reply.json()
            if job["state"] in {"done", "failed", "cancelled", "lost"}:
                if job["state"] != "done":
                    raise SystemExit(f"strike {job['state']}: {job.get('error')}")
                return job["result"]
            print(f"  … still running ({int(job.get('elapsed_seconds') or 0)}s)")
    raise SystemExit("strike did not finish within the polling budget")


def read_probes(path: Path) -> list[tuple[str, str]]:
    with path.open(encoding="ascii") as handle:
        return [
            (fields[0], fields[1])
            for fields in (line.rstrip("\n").split("\t") for line in handle)
            if len(fields) == 2
        ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--reads", type=Path, default=None, help="the recovered-reads Parquet")
    parser.add_argument("--api", default=None, help="reads API base URL")
    parser.add_argument("--threshold", type=float, default=0.90, help="H021's refutation line")
    parser.add_argument("--skip-scan", action="store_true", help="reuse a saved strike result")
    args = parser.parse_args(argv)

    probes = read_probes(args.out / "witness-probes.tsv")
    reads_path = args.reads or (args.out / "baited-reads.parquet")
    if not reads_path.exists():
        print(f"missing {reads_path} — the bait pass has not been downloaded yet")
        return 1

    hits_path = args.out / "witness-hits.json"
    if args.skip_scan and hits_path.exists():
        result = json.loads(hits_path.read_text(encoding="utf-8"))
    else:
        base = args.api or setting("MVA_READS_API_URL") or "http://127.0.0.1:8765"
        token = setting("MVA_API_TOKEN") or ""
        started = time.perf_counter()
        result = submit_scan(probes, base.rstrip("/"), token)
        print(f"strike returned in {time.perf_counter() - started:.0f}s")
        hits_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    hits = pl.DataFrame(result["hits"]) if result.get("hits") else pl.DataFrame()
    if hits.height == 0:
        print("the strike found no reads for any witness probe — nothing to test against")
        return 1

    witness = hits.select(
        pl.col("lane").cast(pl.Int64),
        pl.col("read_num").cast(pl.Int64).alias("read"),
        pl.col("tile").cast(pl.Int64),
        pl.col("x").cast(pl.Int64),
        pl.col("y").cast(pl.Int64),
        pl.col("probe"),
    ).unique()

    recovered = (
        pl.scan_parquet(reads_path)
        .select(
            pl.col("lane").cast(pl.Int64),
            pl.col("read").cast(pl.Int64),
            pl.col("tile").cast(pl.Int64),
            pl.col("x").cast(pl.Int64),
            pl.col("y").cast(pl.Int64),
        )
        .unique()
        .collect(engine="streaming")
    )

    keys = ["lane", "read", "tile", "x", "y"]
    kept = witness.join(recovered, on=keys, how="semi")
    recall = kept.height / witness.height

    per_probe = (
        witness.join(kept.with_columns(pl.lit(True).alias("kept")), on=[*keys, "probe"], how="left")
        .group_by("probe")
        .agg(
            pl.len().alias("reads"),
            pl.col("kept").fill_null(False).sum().alias("kept"),
        )
    )
    missed = per_probe.filter(pl.col("kept") < pl.col("reads"))

    print(f"\nwitness reads found by the strike: {witness.height:,}")
    print(f"  also present in the bait survivors: {kept.height:,}")
    print(f"  recall: {recall:.4f}")
    print(f"  probes with at least one read lost: {missed.height} of {per_probe.height}")
    verdict = "supported" if recall >= args.threshold else "refuted"
    print(f"\nH021 (recall >= {args.threshold:.2f}): {verdict.upper()}")
    if verdict == "refuted":
        print("  pre-registered response: lower the stride and repeat the pass before")
        print("  interpreting any allele the bait produced.")

    payload = {
        "hypothesis": "H021",
        "threshold": args.threshold,
        "witness_probes": len(probes),
        "witness_reads": witness.height,
        "kept": kept.height,
        "recall": round(recall, 6),
        "probes_with_a_lost_read": missed.height,
        "verdict": verdict,
        "method": (
            "reads found by mva.reads.scan for 31-mers centred on heterozygous alleles the "
            "delivered callset reports inside the baited region, joined to the bait sweep's "
            "survivors on the flowcell coordinate (lane, tile, x, y)"
        ),
        "per_probe": per_probe.sort("probe").to_dicts(),
    }
    path = args.out / "bait-recall.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nwrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
