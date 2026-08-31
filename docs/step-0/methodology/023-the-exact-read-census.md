# 023 — The read store is built, and the read count was wrong

**A step-0 platform entry, so it carries no hypothesis.** It **supersedes the read count**
of [005](005-fastq-structure-and-quality.md), which was explicitly an estimate.

## Question

Convert all eight delivered FASTQ into the sharded Parquet store, and check the result
against the delivery. Does it hold?

## Finding first

**The store is built and verified: 272 shards, 63.03 GiB, in `s3://mva/reads/`.** Every
check passes except one, and that one is the *reference number* being wrong, not the data.

**The delivery holds 1,071,835,104 reads, not 1,079,858,785.** The recorded figure was
**0.74% high (8,023,681 reads)**. This is now an exact census — every record counted on
the way through — where the old number was an extrapolation.

## Inputs

- Server `vmi2938918`, 8 cores, Python 3.13, oxbow engine, `--jobs 8`.
- All 8 FASTQ read over the S3 API (`--source s3`), 78.9 GiB of source gzip.
- Staging `/root/mva-staging` (185.6 GiB free, 59.1 GiB predicted by the preflight).

## Commands run and observed output

```
$ uv run mva-reads convert --source s3 --engine oxbow --jobs 8
  disk: 59.1 GiB needed, 185.6 GiB free on /root/mva-staging
  each job: 1 threads, 1GB DuckDB memory limit
  …_L001_R1_001.fastq.gz: 136,586,642 reads in 3,666s (37,261/s), 35 shards, 7.69 GiB
  …_L001_R2_001.fastq.gz: 136,586,642 reads in 3,668s (37,232/s), 35 shards, 8.27 GiB
  …_L002_R1_001.fastq.gz: 134,884,912 reads in 3,662s (36,834/s), 34 shards, 7.66 GiB
  …_L002_R2_001.fastq.gz: 134,884,912 reads in 3,663s (36,825/s), 34 shards, 8.21 GiB
  …_L003_R1_001.fastq.gz: 131,392,690 reads in 3,592s (36,583/s), 33 shards, 7.54 GiB
  …_L003_R2_001.fastq.gz: 131,392,690 reads in 3,615s (36,344/s), 33 shards, 7.98 GiB
  …_L004_R1_001.fastq.gz: 133,053,308 reads in 3,625s (36,704/s), 34 shards, 7.61 GiB
  …_L004_R2_001.fastq.gz: 133,053,308 reads in 3,636s (36,589/s), 34 shards, 8.07 GiB
total: 1,071,835,104 reads in 61.2 min (291,941 reads/s overall), 63.03 GiB parquet
uploaded 274 objects to s3://mva/reads
```

```
$ uv run mva-reads verify --source s3 --expected-total 1079858785
ok: 272 shards, 1,071,835,104 rows counted
ok: lane 1: R1 136,586,642 == R2 136,586,642
ok: lane 2: R1 134,884,912 == R2 134,884,912
ok: lane 3: R1 131,392,690 == R2 131,392,690
ok: lane 4: R1 133,053,308 == R2 133,053,308
ok: <all 8 files>: first record round-trips byte-identically
ok: <all 8 files>: last record round-trips byte-identically
FAIL: grand total 1,071,835,104 == expected 1,079,858,785
```

## Why the store is right and the old number is wrong

Three independent arguments, any one of which is sufficient:

1. **The old total is odd.** 1,079,858,785 cannot be a paired-end read count: R1 must
   equal R2 in every lane, so the total is twice the sum of the lanes and is necessarily
   **even**. No true count of this delivery can be an odd number.

2. **It was never counted.** [005](005-fastq-structure-and-quality.md) says so plainly —
   "estimated by decompressing a fixed 200 MB compressed slice and scaling by file size —
   a full `wc -l` over 80 GB would take roughly half an hour for no extra precision". The
   half hour would in fact have bought 0.74%. Its per-file range, 131,443,212–138,245,967,
   brackets the true 131,392,690–136,586,642 but runs high at the top end, as scaling from
   the head of a gzip does when compression varies along the file.

3. **Four independent pairs match exactly.** R1 and R2 counts agree to the read in all
   four lanes. A conversion that dropped or truncated records would have to drop precisely
   the same number from eight independently-converted files to preserve that.

And the completeness check that matters most: **the last record of every source file
round-trips byte-identically**. That record is only reachable by decompressing the whole
object, so each conversion demonstrably ran to the true end of its stream.

## The exact census

| Lane | R1 = R2 reads | Lane total |
|---|---|---|
| 1 | 136,586,642 | 273,173,284 |
| 2 | 134,884,912 | 269,769,824 |
| 3 | 133,053,308 | 266,106,616 |
| 4 | 131,392,690 | 262,785,380 |
| **All** | | **1,071,835,104** |

At 2 × 149 bp: **159,703,430,496 bases — 159.7 Gb, 51.5× raw** against a 3.1 Gb genome
(was 160.9 Gb / 51.9×). `ideation/data-findings.md` is updated; it owns these numbers.

**63.03 GiB of Parquet from 78.9 GiB of source gzip** — the columnar copy is smaller than
the delivered compressed FASTQ *and* is queryable, which is what [012](012-read-storage-options.md)
predicted (it estimated 64 GB).

## The one disappointment: parallelism did not pay

`--jobs 8` on 8 cores gave each job **1 thread**, and each converted at ~36,700 reads/s
for **291,941 reads/s overall**. The single-job bench in
[022](022-engine-bakeoff-on-the-delivery.md) reached **567,735 reads/s** on its own.
Eight one-thread jobs were therefore about **half the speed of one eight-thread job**, and
the run took 61.2 minutes where ~32 was predicted.

The two runs are not perfectly comparable — the bench converted a local sample, this read
from the object store — but the gap is large and one-directional. The likely cause is that
`machine_share` splits cores by job count, so `--jobs 8` starves each DuckDB of the
threads its Parquet writer and projection need, while the gzip decompression that
parallelism was meant to overlap is not the bottleneck the engine faces. **Not yet
tested:** `--jobs 2` or `--jobs 4` with correspondingly more threads each. Worth measuring
before any re-conversion, and not worth re-running the store for on its own.

## Conclusion

The read store exists, is verified, and is queryable at `s3://mva/reads/`. The delivery
holds **1,071,835,104 reads / 159.7 Gb**, counted rather than estimated.

`verify --expected-total` should be given the counted number from now on; passing the old
estimate is what produced the single `FAIL` above, and that failure did its job.
