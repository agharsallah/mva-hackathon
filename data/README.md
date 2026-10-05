# `data/` — the challenge inputs and everything derived from them

**Standing:** 2026-10-05 — the layout is declared; **nothing is downloaded yet.**

```
data/
  raw/        the organisers' files, byte-for-byte as published   [gitignored]
  parquet/    derived tables                                      [gitignored]
  manifests/  one JSON per derived table, saying how it was made  [COMMITTED]
```

## Why only the manifests are committed

The raw files are 625 MB and re-downloadable from the organisers; the Parquet is
reproducible from them. Committing either would put bytes in git that git cannot help
with. What is *not* reproducible from the inputs alone is **how** a table was built — the
parameters, the tool version, the decisions. That is what a manifest holds, and that is
what is committed.

A derived table without a manifest is not a result. It is a file.

## What goes in `raw/`

From the organisers' AVIDa-hHER2 release — see [`../docs/challenge.md`](../docs/challenge.md)
for the schema and the reading of each column:

| File | Size |
|---|---|
| `AVIDa-hHER2.csv` | 499 MB |
| `NGS_read_count_table.csv` | 126 MB |
| `prediction_template_ONU11.csv` | 8.76 kB |
| `prediction_template_ONU13.csv` | 8.76 kB |
| `prediction_template_ONU23.csv` | 8.85 kB |
| `README.md` | 17.3 kB — **the organisers' own data documentation; read it first** |

Nothing rewrites a file in `raw/`. A correction is a new derived table with a manifest
saying what it corrected, never an edit to the input.

## Querying

In-process, with Polars or DuckDB. There is no database server — 625 MB does not need
one. See the **Data** section of [`../CLAUDE.md`](../CLAUDE.md).
