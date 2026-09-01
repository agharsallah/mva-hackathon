# 045 — The orphan tables: what the warehouse held that nothing served

**A step-0 platform entry, so it carries no hypothesis.** It records a census, three new
surfaces, and — the core of the entry — the list of things that were *not* built, with the
measurement that ruled each one out.

## Question

Three tables existed in the warehouse with nothing reading them, and one column of a
fourth had never been parsed at all:

- `results.sequencing_yield` — derived, four rows, no route.
- `warehouse.vcf_fields` — 31 rows, the callset's own header schema, no route.
- `warehouse.stats_summary` — 200 raw `bcftools stats` lines, of which five section codes
  were parsed into typed tables and the rest were not.

Can each be served with a derivation where parsing is needed, a route, and an exhibit —
and, for the ones that should *not* be served, can the reason be measured rather than
asserted?

## Inputs

| Input | Shape as read |
|---|---|
| `pg.warehouse.stats_summary` | 200 rows, `line_no` + `line` |
| `pg.warehouse.vcf_fields` | 31 rows, `kind` / `id` / `description` |
| `pg.results.sequencing_yield` | 4 rows, one per lane |
| `pg.warehouse.filter_gt_counts` | genotype counts, used as an independent check |
| `/api/reads/runs` (parquet store) | 8 rows, the counted read census |
| `ressources/data-profile/vcf_stats_summary.txt` | the delivered stats file itself |
| Code | `src/mva/warehouse/analysis_stats.py` (new), `queries.py`, `routes_warehouse.py` |

## Commands run

```bash
uv run python -c "…"   # section census, see below
awk '{print $1}' ressources/data-profile/vcf_stats_summary.txt | sort | uniq -c
uv run mva-warehouse pg-derive --only stats_af
uv run mva-warehouse pg-derive --only sequencing_yield
uv run mva-viz-api --port 8954
curl -s -w '%{time_total}s %{size_download}B' http://127.0.0.1:8954/api/callset/zygosity-split
curl -s -w '%{time_total}s %{size_download}B' http://127.0.0.1:8954/api/callset/fields
curl -s -w '%{time_total}s %{size_download}B' http://127.0.0.1:8954/api/reads/yield
uv run pytest -q                     # 1078 passed, 11 pre-existing test_reads_api failures
cd app && npm run typecheck && npm run build
```

## Observed output

### 1. The section census — measured, and shorter than a full `bcftools stats` run

```sql
SELECT split_part(line, chr(9), 1) AS code, count(*) AS n
FROM pg.warehouse.stats_summary GROUP BY code ORDER BY n DESC
```

| Code | Lines | What it is | Status |
|---|---:|---|---|
| `IDD` | 120 | indel length spectrum | already derived → `results.stats_idd` |
| `DP` | 55 | per-site read-depth histogram | already derived → `results.stats_dp` |
| `ST` | 12 | substitution spectrum | already derived → `results.stats_st` |
| `SN` | 9 | headline counters | already derived → `results.stats_sn` |
| `AF` | 2 | stats by non-reference allele frequency | **derived here → `results.stats_af`** |
| `SiS` | 1 | singleton stats | **skipped — duplicate, see §3** |
| `TSTV` | 1 | transition/transversion | already derived → `results.stats_tstv` |
| | **200** | | |

The seven codes account for all 200 lines. `awk` over the committed source file returns the
same seven counts, so the census is a property of the **delivery**, not of the ingest: the
publisher shipped a reduced stats file with the `#` header comments stripped and most
sections omitted.

### 2. Sections that do not exist, and were therefore not derived

| Section | What a full run would give | Why nothing was built |
|---|---|---|
| `QUAL` | call-quality histogram | **absent from the delivered file.** The mission expected it; it is not there. Per-record QUAL is still available from `variants_raw` via `variant_density_bins` (`mean_qual`, `low_qual_n` per megabase), which is where the Genome page already reads it. |
| `HWE` | Hardy–Weinberg equilibrium | absent; and degenerate on one sample regardless. |
| `PSC` / `PSI` | per-sample counters, per-sample indels | absent; one sample means these restate `SN`. |
| `ID` | per-ID counters | absent. |
| `FS`, `ICS`, `GCsAF` | strand bias, indel context, GC-vs-AF | absent. |

Nothing was invented to fill any of these. `tests/test_warehouse_stats.py` asserts no
derivation parses any of the absent codes, so a future entry cannot quietly add one
against a section the file does not have.

### 3. `SiS` gets no table, because it is the same row twice — measured

`bcftools` prints the singleton counters once keyed by allele count (`SiS`) and again as
the first `AF` bin keyed by frequency. On the delivery the two lines carry identical
counters:

```
SiS  0  1         2536505  1665690  870815  644292  0  0  644292
AF   0  0.000000  2536505  1665690  870815  644292  0  0  644292
AF   0  0.990000  1552121  1032666  519455  346146  0  0  346146
```

A `stats_sis` table would therefore be one duplicated row. What `SiS` contributes is its
*key* — the bin is `AC = 1` — which is what licenses the reading in §4. That fact is
recorded in the derivation's docstring instead of in a second table.

Columns 8–10 (repeat-consistent / repeat-inconsistent / not-applicable) are indel-repeat
annotation, which needs `bcftools stats -f <fasta>`. The flag was not used: both rows show
`0 / 0 / <every indel>`. None of the three is derived, and a test pins that degeneracy.

### 4. The `AF` section is a zygosity split, and the identity is exact

`AF` is computed from each record's own `AC`/`AN`. **This callset has one sample**, so
`AN = 2` everywhere and `AC` can only be 1 or 2 — hence exactly two bins, and they mean
*heterozygous* and *homozygous alternate*, not "rare" and "common". Reading them as
population frequency is precisely the error
[`data-findings` §2.5](../../../ideation/data-findings.md) warns about for `INFO/AF`.

The reading was **checked against an independent counter**, not assumed. `bcftools`
computed `AF` from `AC`/`AN`; `filter_gt_counts` counted `GT` strings. They agree exactly:

| Bin | Alleles in `stats_af` | Genotype counter | Equal |
|---|---:|---|---|
| `0.00` | 3,180,797 | 3,047,077 (`0/1`) + 2 × 66,860 (`1/2`) = 3,180,797 | yes |
| `0.99` | 1,898,267 | 1,898,267 (`1/1`) | yes |

A `1/2` record carries **two** different alternate alleles, so it contributes two — which
is also why the allele total (5,079,064) exceeds the 5,012,204 record count.

The label is still emitted **conditionally**: the derivation reads the `SN` sample count
and writes `zygosity = NULL` on anything but a single-sample callset, so the reading cannot
outlive the assumption that produces it. Two tests cover that (two samples, and no `SN`
line at all).

`results.stats_af`, as derived:

| `af_bin` | `zygosity` | `n_snps` | `n_ts` | `n_tv` | `n_indels` | `n_alleles` | `ts_tv` | `pct_of_alleles` |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 0.00 | heterozygous | 2,536,505 | 1,665,690 | 870,815 | 644,292 | 3,180,797 | **1.913** | 62.63 |
| 0.99 | homozygous alternate | 1,552,121 | 1,032,666 | 519,455 | 346,146 | 1,898,267 | **1.988** | 37.37 |

**The finding the table buys.** Ts/Tv per bin is what the callset-wide 1.94 hides. A random
error process gives ~0.5; real biology ~2.0. Heterozygous calls sit at 1.913 and
homozygous-alternate calls at 1.988 — the het half is the noisier half, which is where
false positives are expected to concentrate, because one copy's worth of evidence is half
the evidence. This is a reading of a 0.075 gap between two ratios, not a measured false
positive rate; it says where to look, not how much is wrong.

### 5. The yield estimate's error, now measurable

`results.sequencing_yield` is derived from `warehouse.fastq_profile`: reads and bases are
**extrapolated** from each gzipped FASTQ's byte size and its first read's length, because
counting means decompressing 79 GB. The parquet store did decompress it once, so
`/api/reads/runs` holds the count — and the pair makes the estimate's error measurable
rather than assumed.

| Lane | Counted (parquet) | Estimated (bytes) | Error |
|---|---:|---:|---:|
| L001 | 273,173,284 | 276,180,373 | **+1.10 %** |
| L002 | 269,769,824 | 272,700,071 | **+1.09 %** |
| L003 | 262,785,380 | 263,619,859 | **+0.32 %** |
| L004 | 266,106,616 | 267,358,482 | **+0.47 %** |
| **all** | **1,071,835,104** | **1,079,858,785** | **+0.75 %** |

High on all four lanes: a one-sided bias from gzip's compression ratio, not noise. Good
enough to size a disk; not good enough to quote as a read count, which is why every read
figure elsewhere in the app comes from the counted store.

### 6. Endpoint timings and sizes, measured on port 8954

| Endpoint | Warm | Rows | Payload |
|---|---|---:|---:|
| `/api/callset/zygosity-split` | 0.28–0.44 s | 2 | 391 B |
| `/api/callset/fields` | 0.28–0.33 s | 31 | 3,145 B |
| `/api/reads/yield` | 0.28–0.36 s | 4 | 421 B |

All three are one-line entries in the `TABLES` map in `routes_warehouse.py`, so none is
cached: the cost is the `ATTACH` (~0.3 s, [measured in 034](034-data-catalog-endpoints.md)),
not the read. `/reads/yield` lives in the warehouse router because it reads a PostgreSQL
result table; it is tagged `reads` so `/docs` groups it with the read-store routes.

Derivation costs: `pg-derive --only stats_af` **2.2 s** wall, 2 rows;
`--only sequencing_yield` **1.7 s** wall, 4 rows. Both are parses of tables in the tens of
rows — the wall time is the connection, not the work.

### 7. What was deliberately *not* given a surface

**`warehouse.warehouse_catalog` needs none: it is already the description column of
`/api/catalog/tables`.** `src/mva/viz/catalog.py:188` reads
`SELECT table_name, description FROM pg.warehouse.warehouse_catalog` and joins it onto
every staged table's row, so a dedicated endpoint would serve the same 17 rows a second
time under a different name. Verified live: all 42 tables in both schemas come back from
`/api/catalog/tables` with a non-null `description` and `why`.

`source_files` likewise: it is already joined into `/api/catalog/objects` as
`first_uploaded_at` ([entry 034](034-data-catalog-endpoints.md)).

The remaining unserved tables, and a recommendation each — **recommended, not built**:

| Table | Rows | Recommendation |
|---|---:|---|
| `warehouse.fastq_profile` | 8 | The per-*file* grain under `sequencing_yield`'s per-*lane* grain. Worth a row-expansion inside the new yield exhibit, not an endpoint. |
| `warehouse.fastq_qc_l001` | 9 | fastp metrics from **one lane only**. Serving it as if it characterised the run would be a scope error; it belongs in the Compare page's observed-vs-expected table, where the "applies to" column can say `L001`. |
| `warehouse.manifest` | 12 | Superseded in practice by `source_objects` + `source_files`, which `/api/catalog/objects` already serves with digests and upload times. Keep for provenance; no surface. |
| `warehouse.vcf_header_lines` | 2,621 | The raw header. `vcf_fields` is its parsed, useful subset and is now served; the raw 2,621 lines are provenance, not a page. |
| `warehouse.fastq_read_headers` | 8 | One read name per file, barcode redacted. Already summarised on the Reads page as instrument/run/flowcell. No surface. |
| `warehouse.stats_summary` | 200 | The raw source of six derived tables. Provenance; nothing should chart raw lines. |
| `warehouse.qc_norms`, `gnomad_constraint`, `clinvar_panel`, `vcf_chrom_allele_balance` | 20 / 18,314 / 17,832 / 24 | Not orphans — each is an *input* to a derivation whose output is already served (`qc_observed_expected`, `panel_gene_constraint`, `allele_balance_flags`). |

## What was built

| Surface | Reads | Exhibit |
|---|---|---|
| `GET /api/callset/zygosity-split` | `pg.results.stats_af` (new derivation) | Callset → `ZygositySplit` — stacked SNP/indel bars per bin, Ts/Tv per bin against a random-error line, and the table with the explicit "not a population frequency" reading |
| `GET /api/callset/fields` | `pg.warehouse.vcf_fields` | Callset → `HeaderFields` — sortable, filterable `DataTable` grouped by namespace, with a column naming where each field is actually read |
| `GET /api/reads/yield` | `pg.results.sequencing_yield` | Reads → `DeliveredYield` — estimated against counted reads per lane, with the per-lane error |

New module `src/mva/warehouse/analysis_stats.py` holds the one new derivation and plugs
into `analysis.py` the way `analysis_reference.py` does: one import, one tuple addition.

New tests: `tests/test_warehouse_stats.py` (15, hermetic DuckDB over the delivered stats
lines) and `tests/test_viz_orphans.py` (11, mocked below `queries.fetch`).

## Conclusion

Three orphan surfaces built, two sections deliberately not derived with a measured reason
each, and one table (`warehouse_catalog`) confirmed to need no surface because it already
*is* one.

The entry's real content is §2 and §3. The mission that produced it expected a `QUAL`
histogram and a `SiS` table; the file has no `QUAL` section at all, and `SiS` is a
duplicate of a row that was already going to be derived. Both are recorded as absences
with the measurement behind them rather than filled in.

The one new number worth carrying forward is the **Ts/Tv gap between heterozygous (1.913)
and homozygous-alternate (1.988) calls** — a triage signal about where false positives sit
in this callset, and a reason the non-PASS heterozygous search space on the Panel page
needs its evidence read carefully rather than counted.
