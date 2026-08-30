# 021 — The row group is a memory budget, and the first bench measured the wrong thing

**A step-0 platform entry, so it carries no hypothesis.** It **corrects the verdict** of
[018](018-fastq-conversion-engine-choice.md) as applied on the server: 018's throughput
ranking stands and oxbow remains the choice, but the memory column of that entry — and the
`BUFFERS` verdict the benchmark printed on real data — measured an artefact.

## Question

The first bake-off on the delivery, on the server, produced a verdict that contradicted
every local run:

```
$ uv run mva-reads bench --source s3 --reads 2000000 --scale 3
  pipe:       2,000,000 reads in 17.8s = 112,463 reads/s, 1348 MiB peak RSS
  oxbow:      2,000,000 reads in  7.0s = 283,764 reads/s, 1843 MiB peak RSS
  polars_bio: 2,000,000 reads in 15.8s = 126,195 reads/s, 3678 MiB peak RSS

  pipe:       1348 →  2455 MiB peak RSS — streams
  oxbow:      1843 →  5617 MiB peak RSS — BUFFERS — unusable at full scale
  polars_bio: 3678 → 10849 MiB peak RSS — BUFFERS — unusable at full scale

winner: pipe at 122,501 reads/s
```

Is oxbow really unusable at full scale, and is the dependency-free fallback really the
engine to convert 1.08 billion reads with?

## Finding first

**No to both. The memory was ours, not the engine's.** Peak memory is governed by the
Parquet **row group size** — a parameter this pipeline sets — and by whether DuckDB was
given a memory limit at all. With the row group reduced, the conversion that ran *out of
memory* completes comfortably and oxbow is **20× faster** than the fallback.

Measured on a 6,000,000-read sample, DuckDB limited to 1 GB:

| Engine | Row group | Result |
|---|---|---|
| oxbow | 1,000,000 rows | **Out of Memory Error** — failed to allocate 128 MiB |
| oxbow | 200,000 rows | 5.9 s, 2084 MiB peak RSS |
| oxbow | 100,000 rows | 5.6 s, 1489 MiB peak RSS |
| pipe | 1,000,000 rows | 122.0 s, 1377 MiB peak RSS |
| pipe | 200,000 rows | 121.8 s, 1132 MiB peak RSS |

Memory tracks the **row group**, not the input size. **DuckDB's Parquet writer holds a
whole row group in memory before flushing it, once per writer thread.** A read is ~300
uncompressed bytes, so 1,000,000 rows is ~300 MB per group — multiplied by threads, that
is gigabytes of buffer that has nothing to do with which library parsed the FASTQ. The
`pipe` engine looked frugal for an unrelated reason: it feeds DuckDB row by row through a
CSV reader and simply runs 20× slower, so less is in flight at any moment.

## The two measurement faults

1. **The benchmark did not apply the memory limit the real run uses.**
   `store.convert_all` sets a per-job DuckDB `memory_limit`; `bench.race` did not. DuckDB
   left unlimited claims ~80% of RAM for its buffer pool and grows into whatever is
   available, so peak RSS measured *what the machine had*, not what the work needed —
   and the growth that triggered `BUFFERS` was the pool expanding, not a reader hoarding.
   `bench.race` now takes `--jobs` / `--memory-limit` and applies the same share a real
   job would get, reporting the budget in its output.

2. **`BUFFERS — unusable at full scale` was too strong a claim for a proxy.** Growth in
   peak RSS across two sample sizes cannot distinguish a reader that hoards from an
   allocator that expands. The verdict now reads `flat` or `GROWS with input`, and an
   engine that genuinely fails under the budget reports its error instead.

## Consequences recorded in code

- `schema.ROW_GROUP_SIZE`: **1,000,000 → 200,000 rows**, with the reason stated at the
  definition — it is a memory budget as much as a layout choice.
- `schema.ROW_GROUPS_PER_FILE`: **4 → 20**, so the shard stays ~4M reads / ~250 MB. The
  shard size is the product of the two; shrinking the group and raising the count keeps
  the file while cutting the writer's buffer fivefold.
- `store.machine_share` subtracts a measured `READER_OVERHEAD_GIB = 1` per job: a 6M-read
  conversion held ~2 GB resident against a 1 GB DuckDB limit, so the reader, its Arrow
  batches and the interpreter cost about a gigabyte on top of whatever DuckDB is allowed.
- `tests/test_reads_store.py::test_row_group_size_is_a_memory_budget` pins the product so
  the ceiling cannot be raised silently.

## Verification

Same 6,000,000-read sample, same 1 GB DuckDB limit, new defaults (200,000 × 20):

```
  oxbow : 6,000,000 reads   6.3s =  958,838/s  RSS 1998 MiB  2 shards, 276 MiB parquet
  pipe  : 6,000,000 reads 123.0s =   48,796/s  RSS 1129 MiB  2 shards, 276 MiB parquet
```

The case that died now runs, and both engines write byte-equivalent output (276 MiB).

## Conclusion

Keep oxbow. The fallback's apparent win was two artefacts stacked: an unbudgeted DuckDB
inflating every peak, and a row group five times larger than it needed to be.

**The general lesson, worth carrying to any Parquet writer in this repo:** row group size
is not only a query-pruning knob. It is the writer's memory floor, paid per thread, and
the default that makes queries marginally better is the one that makes conversions fail.

**Still to run:** the bake-off on the delivery with these defaults, which is what
authorises the full conversion.
