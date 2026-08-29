# 008 — Shipping the derived profile tables into a DuckDB warehouse

## Question

Can the profile tables be made queryable in SQL on a shared machine, and what does
"install DuckDB on a server" actually mean given DuckDB has no server?

## Finding first

**DuckDB cannot be "exposed on a server" in the sense the question assumes.** It is an
embedded database: a library in the calling process plus one file on disk, like SQLite.
There is no daemon, no port, no accounts. The deployment therefore reduces to (a) a
`duckdb` binary on the box, (b) the Parquet on the box, (c) a `.duckdb` file built from it
— with the box's existing SSH access as the only access control. No network service is
opened at any point.

## Inputs

- Source tables: `ressources/data-profile/` — 17 files, of which 12 are stageable
  (`.tsv`, `.bed`, `.txt`).
- `duckdb` 1.5.5 (Python package `duckdb==1.5.5`, added via `uv add duckdb`; CLI
  `duckdb_cli-linux-amd64` v1.5.5 `d8cdaa33fd` for the remote-side rehearsal).
- Code: `src/mva/warehouse/{catalog,stage,remote,cli}.py`, entry point `mva-warehouse`.

## Commands run and observed output

### 1. Stage the profile into typed Parquet

```
$ uv run mva-warehouse stage
staged 14 tables from ressources/data-profile into build/warehouse
  contig_counts               1,690 rows   3 cols    10,016 B
  fastq_profile                   8 rows   5 cols     1,257 B
  fastq_qc_l001                   9 rows   2 cols       589 B
  fastq_read_headers              8 rows   2 cols       940 B
  filter_gt_counts               38 rows   3 cols       993 B
  manifest                       12 rows   3 cols     1,537 B
  mva_panel_grch38                8 rows   4 cols       789 B
  panel_variant_counts            8 rows   6 cols     1,109 B
  stats_summary                 200 rows   2 cols     2,341 B
  vcf_chrom_allele_balance       24 rows   5 cols     1,292 B
  vcf_fields                     31 rows   3 cols     1,595 B
  vcf_header_lines            2,621 rows   2 cols    22,256 B
  profile_scalars                 4 rows   3 cols       714 B
  warehouse_catalog              13 rows   5 cols     2,001 B
  total                       4,674 rows              47,429 B
```

14 tables, 4,674 rows, **47 KB total**. Two of the tables are synthesised rather than
copied: `profile_scalars` collects the rollup lines that appear under several source files,
and `warehouse_catalog` describes every other table so the database is self-documenting.

### 2. Confirm types were inferred, not left as text

```
$ uv run python -c "...DESCRIBE..."
vcf_chrom_allele_balance: chrom:VARCHAR, n_het:BIGINT, mean_vaf:DOUBLE, mean_dp:DOUBLE,
                          pct_in_0_40_0_60:DOUBLE
panel_variant_counts:     gene:VARCHAR, chrom:VARCHAR, start:BIGINT, end:BIGINT,
                          n_all:BIGINT, n_pass:BIGINT
fastq_profile:            file:VARCHAR, bytes:BIGINT, read_len:BIGINT, est_reads:BIGINT,
                          est_gbases:DOUBLE
```

Numeric columns are numeric, so `WHERE mean_dp > 45` compares numbers. A join across two
independently staged tables also works:

```
$ ... SELECT p.gene, p.n_all, p.n_pass, b.end - b.start AS span_bp
      FROM panel_variant_counts p JOIN mva_panel_grch38 b ON p.gene = b.name
      ORDER BY span_bp DESC
CEP192  255 251 173771
SMC5    125 124 136605
CENPE   169 166 133115
DICER1   87  87 111783
BUB1B    80  76 100154
CEP57    13  13  87106
TRIP13   12   6  66509
TP53    120 118  65768
```

These reproduce the counts recorded in [003](003-panel-gene-variant-counts.md), now
joinable against the interval table rather than eyeballed side by side.

The rollup scalars that a naive CSV read would have discarded survive:

```
fastq_profile.tsv         est_total_gbases         160.9
fastq_profile.tsv         est_raw_coverage_x        51.9
vcf_filter_gt_counts.tsv  records_in_phase_group  770458.0
vcf_filter_gt_counts.tsv  total_records          5012204.0
```

`total_records` 5,012,204 matches [001](001-vcf-provenance-and-structure.md) and
`records_in_phase_group` 770,458 matches [006](006-phasing-power-on-bub1b.md), confirming
the normalisation did not alter any value.

### 3. Rehearse the *remote* script locally against the real CLI

The generated SSH payload was run through `bash` against a simulated remote root, using the
actual downloaded `duckdb` 1.5.5 CLI rather than the Python package, so the CLI flags and
the heredoc quoting are exercised for real:

```
$ ... load_command(...) executed via bash ...
┌──────────────────────────┬──────┐
│        table_name        │ rows │
├──────────────────────────┼──────┤
│ contig_counts            │ 1690 │
│ ...                      │  ... │
│ warehouse_catalog        │   13 │
└──────────────────────────┴──────┘
```

All 14 tables rebuilt. The read-only `query` path was exercised the same way and returned
`warehouse_catalog` correctly.

### 4. Tests

```
$ uv run pytest tests/ -q
150 passed in 4.36s
```

23 of those are new (`tests/test_warehouse.py`). The remote half is tested by *building*
commands and asserting on their text — never by contacting a machine — which is why
`remote.py` separates command construction from execution.

## Bugs this run caught

Both were found by rehearsing rather than by reasoning, and both would have failed only on
the real box:

1. **`COPY … TO ?` rejects a bound parameter for its destination.** The first staging
   attempt raised `IO Error: No files found that match the pattern
   "build/warehouse/contig_counts.parquet"` — the two placeholders had been bound in a way
   that fed the output path to the reader. Fixed by using DuckDB's relation API
   (`read_csv(...).write_parquet(...)`), which takes both paths as *values*, so neither is
   ever parsed and there is no interpolation to get wrong.

2. **`~` is not expanded inside a SQL string literal.** `read_parquet('~/warehouse/x.parquet')`
   fails on a box where the file plainly exists: the remote shell never sees the tilde
   (it is inside SQL quotes) and DuckDB reads it as a directory literally named `~`. Fixed
   by having the load script `cd` to the warehouse root and use paths relative to it.

## Conclusion

The profile is queryable in SQL, typed, and reproducible from the committed repository in
under a second. The remote deployment is four idempotent, independently runnable steps over
SSH that open no network service. Confirmed working end-to-end against the real DuckDB CLI;
**not yet run against an actual remote host**, because no host has been provisioned — the
`preflight` verb exists to be the first thing run when one is.

Scope: derived tables only (counts, summaries, intervals, checksums). No reads, no
genotypes, no patient variant records. `build/` and `*.duckdb` are gitignored.

See [`docs/warehouse.md`](../warehouse.md) for the pipeline diagram and usage.
