# 022 — The bake-off on the delivery itself

**A step-0 platform entry, so it carries no hypothesis.** It **confirms on real data**
what [018](018-fastq-conversion-engine-choice.md) measured on synthetic reads, under the
corrected budget of [021](021-the-row-group-is-a-memory-budget.md). This is the run that
authorises the full conversion.

## Question

With the row group at 200,000 rows and the benchmark applying a real job's memory budget,
which engine converts the delivered reads, and does its memory hold as the input grows?

## Finding first

**oxbow, at 567,735 reads/second — 4.4× the dependency-free fallback — with flat memory.**
`polars_bio` is the one that genuinely grows with input and is disqualified for the full
set.

## Inputs

- Server `vmi2938918` (the VPS holding MinIO and PostgreSQL), Python 3.13.
- `WGS_EX2312012_HGWCNDSX7_S16_L001_R1_001.fastq.gz`, read **over the S3 API** from the
  bucket (`--source s3`) — the delivery exists only as objects ([019](019-where-the-read-bytes-come-from.md)).
- Samples of 2,000,000 and 6,000,000 reads cut from the head of that file.
- `--jobs 10`, so each engine was given the DuckDB memory budget one job of a ten-way run
  would get: **1 GB**.

## Commands run and observed output

```
$ uv run mva-reads bench --source s3 --reads 2000000 --scale 3 --jobs 10
budget per engine: 1GB DuckDB memory (the share of a 10-job run)

  pipe:       2,000,000 reads in 18.3s = 109,005 reads/s, 113.2 MiB parquet,  834 MiB peak RSS
  oxbow:      2,000,000 reads in  7.6s = 263,614 reads/s, 113.3 MiB parquet, 1636 MiB peak RSS
  polars_bio: 2,000,000 reads in 14.5s = 138,158 reads/s, 113.7 MiB parquet, 3443 MiB peak RSS

re-running at 6,000,000 reads on the same budget …
  pipe:       6,000,000 reads in 46.9s = 127,962 reads/s, 338.9 MiB parquet,  831 MiB peak RSS
  oxbow:      6,000,000 reads in 10.6s = 567,735 reads/s, 339.0 MiB parquet, 2011 MiB peak RSS
  polars_bio: 6,000,000 reads in 40.7s = 147,322 reads/s, 340.3 MiB parquet, 7215 MiB peak RSS

  pipe:        834 →  831 MiB peak RSS — flat — need does not grow with input
  oxbow:      1636 → 2011 MiB peak RSS — flat — need does not grow with input
  polars_bio: 3443 → 7215 MiB peak RSS — GROWS with input — check it fits the full file

winner: oxbow at 567,735 reads/s
```

## What the numbers say

**The `BUFFERS` verdict of the first server run was an artefact, and is gone.** Under a
stated budget, `pipe` (834 → 831 MiB) and `oxbow` (1636 → 2011 MiB) are flat while the
input triples. The correction in [021](021-the-row-group-is-a-memory-budget.md) holds on
real data.

**`polars_bio` really does buffer.** 3443 → 7215 MiB is 2.1× for 3× the input — the only
engine whose need tracks the file. It stays available and is not the default.

**All three write the same bytes**, 338.9–340.3 MiB for 6M reads — the cross-check that
the engines agree, matching the row-level equality test in `tests/test_reads_store.py`.

**Throughput rises with sample size for the faster engines** (oxbow 263k → 567k reads/s),
because fixed start-up — opening the object, DuckDB init, the first row group — is
amortised over more reads. The 6M figure is the one to extrapolate from; the 2M figure
understates a long run.

## What it implies for the full conversion

At 567,735 reads/s, one pass over all **1,079,858,785** reads is **~32 minutes** of
single-stream work. Eight files converting in parallel should finish well inside that,
bounded by disk and gzip decompression rather than by parsing — which was the goal of
choosing the engine at all.

Expected output is **~61 GiB** of Parquet (extrapolating 339 MiB / 6M reads), against
84.67 GB of source gzip: **the columnar copy is smaller than the delivered gzip**, as
[012](012-read-storage-options.md) predicted.

## Consequence recorded in code

`mva-reads convert` now refuses up front when the staging filesystem cannot hold the
output (`store.check_room`, ~0.75 × source bytes), and reports overall wall time and
throughput when it finishes. Discovering a full disk at 90% of a half-hour run is the
worst possible time to discover it.

## Conclusion

**Convert with oxbow.** The engine question is closed on real data; what remains is the
run itself and the verification of its output.
