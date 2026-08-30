# 018 — Which library should parse 1.08 billion reads into Parquet?

**A step-0 platform entry, so it carries no hypothesis.** Step 0 is machinery, and its
goal — "does this work" — is answered by building it ([`../../method.md`](../../method.md),
[`src/mva/science/steps.py`](../../../src/mva/science/steps.py)). The entries that bind a
test to a hypothesis start at step 1.

## Question

`mva-reads` converts the delivered `.fastq.gz` into sharded Parquet. Every engine must
hand DuckDB the same three columns (`header`, `sequence`, `quality`), so the choice is
purely about throughput, memory behaviour, and whether the dependency is alive. Which
library, and is it fast enough that the conversion is decompression-bound rather than
parser-bound?

## Finding first

**`oxbow` 0.8.1**, at **752,652 reads/second** on synthetic data — **15× the
dependency-free shell fallback** (49,102 reads/s) and 1.6× `polars-bio` (472,379
reads/s). All three stream: memory grows sub-linearly with input.

**`biobear` was dropped, on maintenance grounds, not performance.** It worked (374,839
reads/s in a first local run) but its last commit is **2025-03-10** and its last release
**2025-01-19** — 18 months stale — and it has no wheel for Python 3.13+, which forced this
project's interpreter down to 3.12.

| Library | Last release | Last commit | Verdict |
|---|---|---|---|
| **oxbow** 0.8.1 | 2026-06-29 | 2026-07-27 | **chosen** — Rust/`noodles`, PyArrow dataset, 169★ |
| polars-bio 0.35.1 | 2026-08-28 | 2026-08-28 | kept as second engine — Rust/DataFusion, 195★ |
| biobear 0.23.7 | 2025-01-19 | 2025-03-10 | **removed** — stale, no cp313/cp314 wheels |

## Inputs

- Laptop: macOS 25.5.0 (darwin), Apple silicon, DuckDB 1.5.5, Python 3.12 then 3.13.
- **Synthetic reads, not the delivery.** 5,000,000 reads (149 bp, 4-level quality
  alphabet `F,:#`, NovaSeq-shaped headers), built by concatenating ten copies of a
  500,000-read generated file — gzip streams concatenate natively. Read payloads are
  patient data; benchmarking on them happens on the server, and the sample never enters
  the repository.
- `src/mva/reads/{engines,convert,bench}.py` at the commit adding this entry.

## Commands run and observed output

```
$ mva-reads bench --source . --reads 1200000 --scale 4

cutting 1,200,000-read sample from BIG_SYN_S1_L001_R1_001.fastq.gz …
  pipe:       1,200,000 reads in 24.0s =  49,929 reads/s,  54.7 MiB parquet, 1139 MiB peak RSS
  oxbow:      1,200,000 reads in  2.0s = 608,130 reads/s,  54.8 MiB parquet, 1362 MiB peak RSS
  polars_bio: 1,200,000 reads in  2.6s = 467,771 reads/s,  54.8 MiB parquet, 1953 MiB peak RSS

re-running at 4,800,000 reads to test memory growth …
  pipe:       4,800,000 reads in 97.8s =  49,102 reads/s, 218.5 MiB parquet, 1536 MiB peak RSS
  oxbow:      4,800,000 reads in  6.4s = 752,652 reads/s, 218.8 MiB parquet, 2714 MiB peak RSS
  polars_bio: 4,800,000 reads in 10.2s = 472,379 reads/s, 218.5 MiB parquet, 2954 MiB peak RSS

  pipe:       1139 → 1536 MiB peak RSS — streams
  oxbow:      1362 → 2714 MiB peak RSS — streams
  polars_bio: 1953 → 2954 MiB peak RSS — streams

winner: oxbow at 752,652 reads/s
```

Repeated after moving the interpreter to **Python 3.13** (which biobear had blocked), same
sample, same machine — the ordering is unchanged and oxbow is if anything faster:

```
  pipe:       4,800,000 reads in 96.4s =  49,818 reads/s, 2197 MiB peak RSS
  oxbow:      4,800,000 reads in  5.6s = 854,068 reads/s, 3263 MiB peak RSS
  polars_bio: 4,800,000 reads in 10.2s = 468,348 reads/s, 3948 MiB peak RSS
```

Output size is identical to 0.3 MiB across engines (218.5–218.8 MiB), which is the
cross-check that they really do produce the same rows. The equality is also asserted
directly: `tests/test_reads_store.py::test_engines_agree_with_pipe` full-joins each
engine's output against the `pipe` engine's on `(tile, x, y)` and requires zero differing
sequences, qualities, filter flags or barcodes.

### Two measurement mistakes made and corrected

Both are recorded because either one alone would have produced a wrong recommendation.

1. **Peak memory measured in one process is meaningless.** `ru_maxrss` is a high-water
   mark that never falls, so the second engine measured inherited the first one's peak —
   oxbow appeared to use `+0 MiB`. Each engine now runs in its own spawned process.
2. **Memory must be compared above one Parquet row group.** DuckDB accumulates a full
   row group (1,000,000 rows) before flushing it, so below that size *every* engine's
   memory grows with the sample, and the growth is the writer's buffer filling, not the
   reader hoarding. An earlier 100k-vs-500k run therefore flagged `pipe` and `oxbow` as
   buffering. The comparison above uses 1.2M vs 4.8M reads; `bench.race` now warns when
   the sample is under one row group.

### Where the `pipe` engine's time actually goes

```
$ time (gzip -dc SYN.fastq.gz > /dev/null)                    0.15s
$ time (gzip -dc SYN.fastq.gz | paste - - - - > /dev/null)    9.04s
$ time (gzip -dc SYN.fastq.gz | awk 'ORS=NR%4?"\t":"\n"')     4.75s
```

Decompression is 0.15s of a 10s run: macOS's BSD `paste` is the bottleneck, not gzip and
not DuckDB. GNU `paste` on the Linux server should be substantially faster, so the
fallback's ~49k reads/s is a macOS floor, not a Linux one. It does not change the choice.

## Consequences recorded in code

- Default engine is `oxbow`; `pipe` needs no dependency at all and stays as the fallback
  when a wheel will not build; `polars_bio` is the third contender.
- **Python raised 3.12 → 3.13.** biobear had no cp313 wheel and its pyo3 build refused to
  compile against a newer interpreter, which is what pinned the project down; both
  replacements ship current wheels. `requires-python` is now `>=3.11,<3.15`, the range
  polars-bio supports.
- Both optional engines live in the `bench` dependency group, so a plain `uv sync` does not
  need them: `uv sync --group bench`.
- Parallel conversion now sets a **per-job DuckDB memory limit** (`store.machine_share`):
  each DuckDB instance otherwise claims ~80% of RAM for its buffer pool, and eight
  concurrent jobs doing that is an out-of-memory kill rather than a speed-up.

## Conclusion

Take `oxbow`. At 752k reads/s a single-stream pass over all 1,079,858,785 reads is
**~24 minutes of parsing**, which means the full conversion is bounded by gzip
decompression and disk, not by the parser — the parser has stopped being the interesting
variable, which is the point of choosing it.

**Not yet measured on the delivery.** Every number here is synthetic and from a laptop.
The server bake-off on a real `.fastq.gz` (`mva-reads bench --reads 2000000`) is the run
that authorises the full conversion, and it gets its own entry.
