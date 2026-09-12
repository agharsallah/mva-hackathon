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
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import httpx
import polars as pl

from mva.warehouse.settings import setting

DEFAULT_OUT = Path("build/it2/step-2")
#: Reads a single-copy heterozygous 31-mer is expected in: depth x (L - k + 1)/L / 2.
#: A probe found in many times this many reads is matching more than one place in the
#: genome, which is a statement about the probe, not about the bait.
EXPECTED_READS = 44 * (150 - 31 + 1) / 150 / 2

#: Above this multiple of :data:`EXPECTED_READS`, a probe is reported separately.
MULTI_LOCUS_MULTIPLE = 2.0

#: Reads reported per probe. A true single-copy 31-mer is expected in ~35 reads at 44x
#: (mva.reads.triage), so 1000 is far above any honest count and the cap never binds.
SCAN_LIMIT = 1000
#: Seconds per long-poll. Deliberately short: a 280 s held connection to the job service
#: is long enough for an idle timeout somewhere between here and the server to close it,
#: and the job keeps running while the client believes it failed. Many short polls cost
#: nothing and cannot be cut.
WAIT_SECONDS = 25
#: Total polling budget — the strike is one pass over 1.07 billion reads.
POLL_ROUNDS = 160


def submit_all(probes: list[tuple[str, str]], base: str, token: str, *, chunk: int) -> dict:
    """Run the strike in batches of ``chunk`` probes and merge the hits.

    One pass over 1.07 billion reads costs the same for 1 probe or 500 — that is the
    strike's whole design — so batching is normally wrong. It is right here for a reason
    that has nothing to do with speed: at ~200 probes the survivor scan repeatedly took
    the shared job service down mid-pass, three times, while the batch size step-0 entry
    027 measured and proved (20) has never failed. Correctness is identical either way;
    what changes is whether the run finishes.

    The cost is real and is stated: N/chunk full passes instead of one.
    """
    merged: list[dict] = []
    batches = [probes[start : start + chunk] for start in range(0, len(probes), chunk)]
    print(f"{len(probes)} probes in {len(batches)} batches of up to {chunk}")
    for index, batch in enumerate(batches, start=1):
        print(f"batch {index}/{len(batches)} …")
        result = submit_scan(batch, base, token)
        merged.extend(result.get("hits", []))
        print(f"  {len(result.get('hits', [])):,} hits ({result.get('seconds')}s)")
    return {"hits": merged, "batches": len(batches)}


def submit_scan(probes: list[tuple[str, str]], base: str, token: str, job_id: str = "") -> dict:
    """Run the 500-probe strike as a job and wait for it.

    ``job_id`` attaches to a strike that is already running instead of starting another —
    a full pass over the store is an hour of someone's machine, and a dropped connection
    on this side is no reason to spend it twice.
    """
    headers = {"X-API-Key": token}
    body = {
        "probes": [{"name": name, "sequence": sequence} for name, sequence in probes],
        "limit": SCAN_LIMIT,
    }
    with httpx.Client(base_url=base, timeout=60.0, headers=headers) as client:
        if not job_id:
            started = client.post("/scan", json=body)
            started.raise_for_status()
            job_id = started.json()["id"]
            print(f"strike job {job_id}: {len(probes)} probes, one pass over the store")
        else:
            print(f"attaching to strike job {job_id}")
        for round_number in range(POLL_ROUNDS):
            try:
                reply = client.get(
                    f"/jobs/{job_id}/wait", params={"timeout": WAIT_SECONDS}, timeout=60.0
                )
                reply.raise_for_status()
                job = reply.json()
            except (httpx.HTTPError, httpx.RemoteProtocolError) as dropped:
                # The job does not care that our connection did. Say so and poll again.
                print(f"  … poll {round_number} dropped ({type(dropped).__name__}); retrying")
                time.sleep(5)
                continue
            if job["state"] in {"done", "failed", "cancelled", "lost"}:
                if job["state"] != "done":
                    raise SystemExit(f"strike {job['state']}: {job.get('error')}")
                return job["result"]
            if round_number % 4 == 0:
                print(f"  … still running ({int(job.get('elapsed_seconds') or 0)}s)")
    raise SystemExit(f"strike {job_id} did not finish within the polling budget")


def _recall(rows: list[dict]) -> float:
    total = sum(row["reads"] for row in rows)
    return sum(row["kept"] for row in rows) / total if total else 0.0


def reachable(witness: dict, bait_path: Path, k: int = 31) -> tuple[list[dict], list[dict]]:
    """Split the witness alleles by whether the bait ever claimed to reach them.

    A witness allele is only a fair test of the **stride** if the bait contains the
    sequence around it. Where the reference k-mer at that position was dropped by the
    uniqueness filter as occurring elsewhere in the genome (entry 085), the bait
    deliberately does not cover that allele, and including it would test a design decision
    rather than the engine.

    It is also what makes the strike survivable. A k-mer that occurs in many places matches
    an enormous number of reads, and `scan.kmers` joins every survivor against every probe
    before applying its per-probe limit — which is what restarted the job service twice
    before this split existed. Both numbers are reported: the honest denominator for H021
    is the reachable set, and the excluded count is stated beside it.
    """
    import numpy as np

    from mva.kmer.encode import codes_of, window_kmers
    from mva.kmer.membership import Bait

    bait = Bait.load(bait_path, k=k)
    alleles = witness["alleles"]
    packed = np.array(
        [window_kmers(codes_of(allele["reference_kmer"]), k)[0][0] for allele in alleles],
        dtype=np.uint64,
    )
    covered = bait.contains(packed)
    inside = [allele for allele, keep in zip(alleles, covered, strict=True) if keep]
    outside = [allele for allele, keep in zip(alleles, covered, strict=True) if not keep]
    return inside, outside


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--reads", type=Path, default=None, help="the recovered-reads Parquet")
    parser.add_argument("--api", default=None, help="reads API base URL")
    parser.add_argument("--threshold", type=float, default=0.90, help="H021's refutation line")
    parser.add_argument("--bootstrap", type=int, default=2000, help="per-probe replicates")
    parser.add_argument("--seed", type=int, default=20260912)
    parser.add_argument("--skip-scan", action="store_true", help="reuse a saved strike result")
    parser.add_argument("--job", default="", help="attach to a strike already running")
    parser.add_argument(
        "--chunk",
        type=int,
        default=20,
        help="probes per strike. 20 is the size step-0 entry 027 measured; larger batches "
        "took the job service down three times.",
    )
    return parser.parse_args(argv)


@dataclass(frozen=True)
class Diagnostics:
    """What the headline recall is made of — computed after it, never able to move it."""

    low: float
    high: float
    above: float
    cut: float
    single: int
    single_recall: float
    many: int
    many_recall: float


def diagnose(rows: list[dict], args: argparse.Namespace) -> Diagnostics:
    """A per-probe interval and a split by read count.

    Both are **post-hoc** and reported beside the pre-registered number, never in place of
    it: a threshold reinterpreted after seeing which side of it the data fell is not a
    threshold.

    The unit of correlation is the probe, not the read — reads of one allele share its
    locus, its depth and its k-mer's uniqueness — so the interval is bootstrapped over
    probes. Resampling reads would give a far tighter interval that means nothing.
    """
    rng = random.Random(args.seed)
    replicates = []
    for _ in range(args.bootstrap):
        drawn = [rows[rng.randrange(len(rows))] for _ in rows]
        replicates.append(_recall(drawn))
    replicates.sort()
    cut = EXPECTED_READS * MULTI_LOCUS_MULTIPLE
    single = [row for row in rows if row["reads"] <= cut]
    many = [row for row in rows if row["reads"] > cut]
    return Diagnostics(
        low=replicates[int(0.025 * len(replicates))],
        high=replicates[int(0.975 * len(replicates)) - 1],
        above=sum(value >= args.threshold for value in replicates) / len(replicates),
        cut=cut,
        single=len(single),
        single_recall=_recall(single),
        many=len(many),
        many_recall=_recall(many),
    )


def report(found: Diagnostics, threshold: float) -> None:
    print(f"\nper-probe bootstrap 95% interval: [{found.low:.4f}, {found.high:.4f}]")
    print(f"  replicates at or above {threshold:.2f}: {found.above:.1%}")
    print(
        f"\nprobes at a single-copy read count (<= {found.cut:.0f}, expected "
        f"{EXPECTED_READS:.1f}): {found.single} — recall {found.single_recall:.4f}"
    )
    print(
        f"probes found in more reads than one locus can supply: {found.many} — "
        f"recall {found.many_recall:.4f}"
    )


def summarise(
    args: argparse.Namespace,
    witness_json: dict,
    probes: list,
    outside: list,
    witness_height: int,
    kept_height: int,
    recall: float,
    missed_height: int,
    diagnostics: Diagnostics,
    verdict: str,
    per_probe_rows: list[dict],
) -> dict:
    """The result as JSON — one place, so the entry and the figure read the same numbers."""
    return {
        "hypothesis": "H021",
        "threshold": args.threshold,
        "witness_alleles_drawn": len(witness_json["alleles"]),
        "witness_probes_used": len(probes),
        "excluded_not_covered_by_bait": len(outside),
        "witness_reads": witness_height,
        "kept": kept_height,
        "recall": round(recall, 6),
        "probes_with_a_lost_read": missed_height,
        "verdict": verdict,
        "method": (
            "reads found by mva.reads.scan for 31-mers centred on heterozygous alleles the "
            "delivered callset reports inside the baited region, joined to the bait sweep's "
            "survivors on the flowcell coordinate (lane, tile, x, y). Alleles whose "
            "reference k-mer the uniqueness filter dropped as repeated are excluded and "
            "counted: the bait does not cover them, so they would test a design decision "
            "rather than the stride."
        ),
        "bootstrap": {
            "unit": "probe — reads of one allele share its locus, depth and k-mer uniqueness",
            "replicates": args.bootstrap,
            "interval_95": [round(diagnostics.low, 6), round(diagnostics.high, 6)],
            "share_at_or_above_threshold": round(diagnostics.above, 4),
        },
        "by_read_count": {
            "expected_reads_single_copy": round(EXPECTED_READS, 2),
            "cut": round(diagnostics.cut, 1),
            "single_copy_probes": diagnostics.single,
            "single_copy_recall": round(diagnostics.single_recall, 6),
            "multi_locus_probes": diagnostics.many,
            "multi_locus_recall": round(diagnostics.many_recall, 6),
            "note": (
                "post-hoc stratification, reported beside the pre-registered number and "
                "never in place of it. A probe found in many times the reads one locus can "
                "supply is matching several places; the strike has no positions and counts "
                "those reads, while the bait correctly did not recover them."
            ),
        },
        "per_probe": per_probe_rows,
    }


#: The flowcell coordinate: the only identity the read store keeps, and the key R1 and R2
#: of one fragment share.
JOIN_KEYS = ["lane", "read", "tile", "x", "y"]


def join_to_survivors(result: dict, reads_path: Path):
    """Which of the strike's reads the bait also kept, overall and per probe."""
    hits = pl.DataFrame(result["hits"]) if result.get("hits") else pl.DataFrame()
    if hits.height == 0:
        return None, None, None
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
        .select([pl.col(name).cast(pl.Int64) for name in JOIN_KEYS])
        .unique()
        .collect(engine="streaming")
    )
    kept = witness.join(recovered, on=JOIN_KEYS, how="semi")
    per_probe = (
        witness.join(
            kept.with_columns(pl.lit(True).alias("kept")),
            on=[*JOIN_KEYS, "probe"],
            how="left",
        )
        .group_by("probe")
        .agg(pl.len().alias("reads"), pl.col("kept").fill_null(False).sum().alias("kept"))
    )
    return witness, kept, per_probe


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    witness_json = json.loads((args.out / "witness.json").read_text(encoding="utf-8"))
    inside, outside = reachable(witness_json, args.out / "bait.npy")
    probes = [(allele["probe"], allele["alternate_kmer"]) for allele in inside]
    print(f"witness alleles drawn: {len(witness_json['alleles'])}")
    print(f"  inside the bait (reference k-mer survived the uniqueness filter): {len(inside)}")
    print(f"  excluded, the bait never covered them: {len(outside)}")
    if len(probes) > 500:
        print(f"  capping at the API's 500-probe limit (from {len(probes)})")
        probes = probes[:500]
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
        if args.job:
            result = submit_scan(probes, base.rstrip("/"), token, job_id=args.job)
        else:
            result = submit_all(probes, base.rstrip("/"), token, chunk=args.chunk)
        print(f"strike returned in {time.perf_counter() - started:.0f}s")
        hits_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    witness, kept, per_probe_frame = join_to_survivors(result, reads_path)
    if witness is None:
        print("the strike found no reads for any witness probe — nothing to test against")
        return 1
    recall = kept.height / witness.height
    per_probe_rows = per_probe_frame.sort("probe").to_dicts()
    missed = per_probe_frame.filter(pl.col("kept") < pl.col("reads"))

    print(f"\nwitness reads found by the strike: {witness.height:,}")
    print(f"  also present in the bait survivors: {kept.height:,}")
    print(f"  recall: {recall:.4f}")
    print(f"  probes with at least one read lost: {missed.height} of {per_probe_frame.height}")
    diagnostics = diagnose(per_probe_rows, args)
    report(diagnostics, args.threshold)

    verdict = "supported" if recall >= args.threshold else "refuted"
    print(f"\nH021 (recall >= {args.threshold:.2f}): {verdict.upper()}")
    if verdict == "refuted":
        print("  pre-registered response: lower the stride and repeat the pass before")
        print("  interpreting any allele the bait produced.")

    payload = summarise(
        args,
        witness_json,
        probes,
        outside,
        witness.height,
        kept.height,
        recall,
        missed.height,
        diagnostics,
        verdict,
        per_probe_rows,
    )
    path = args.out / "bait-recall.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nwrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
