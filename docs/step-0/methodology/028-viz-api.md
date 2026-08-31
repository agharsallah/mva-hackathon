# 028 — One JSON origin for the browser: `mva-viz-api`

**A step-0 platform entry, so it carries no hypothesis.** It records what was built, what
was measured, and the two facts that changed a design decision mid-build.

## Question

The report needs charts, and a React app cannot speak to PostgreSQL, to an S3-compatible
object store, and to a job API — three protocols, two credentials, one of which must never
reach a browser. Can one HTTP service serve all three, with **no endpoint able to trigger a
whole-genome scan**, and answer every chart in under a second on a warm cache?

## Inputs

| Input | Version / shape |
|---|---|
| `pg.warehouse.variants_raw` | 5,012,204 rows, every column TEXT, no index |
| `pg.warehouse.stats_summary` | 200 raw `bcftools stats` lines (`line_no`, `line`) |
| `pg.warehouse.filter_gt_counts`, `contig_counts`, `profile_scalars`, `source_objects`, `probe_ledger`, `data_lineage`, `mva_panel_grch38`, `panel_variant_counts` | as ingested |
| `pg.results.*` | the five pre-existing derivations |
| `s3://mva/reads/runs.parquet` | 8 rows |
| `s3://mva/reads/manifest.parquet` | 272 rows |
| `s3://mva/reads/lane=<1-4>/read=<1-2>/part-*.parquet` | 272 shards, 1,071,835,104 reads |
| `ressources/data-profile/mva_panel_grch38.bed` | 8 genes, 6 columns |
| Contract | `viz-api-contract.md`, shared with the React app |

## Commands run

Six new derivations were added to `src/mva/warehouse/analysis.py` and executed:

```bash
uv run mva-warehouse pg-derive --only stats_sn stats_tstv stats_dp stats_st stats_idd
#   results.stats_sn        9 rows
#   results.stats_tstv      1 rows
#   results.stats_dp       55 rows
#   results.stats_st       12 rows
#   results.stats_idd     120 rows

time uv run mva-warehouse pg-derive --only variant_density_bins
#   results.variant_density_bins  2,961 rows
#   real 1m44.92s
```

Verification of the big one:

```bash
uv run mva-warehouse pg-query "SELECT count(DISTINCT chrom) AS chroms, count(*) AS rows,
                               sum(n) AS total FROM pg.results.variant_density_bins"
# chroms=25  rows=2961  total=4895719
```

Then the service, from the repository root:

```bash
uv run mva-viz-api --port 8900
curl -s http://127.0.0.1:8900/health
curl -s "http://127.0.0.1:8900/api/overview?refresh=true"
# … every endpoint in the contract; outputs below
uv run pytest    # 599 passed
```

## Observed output

### The derivations

`variant_density_bins` covers **25 canonical contigs in 2,961 bins**, holding 4,895,719 of
the 5,012,204 records. The 116,485 difference is real and expected: it is every record on
the 1,665 non-canonical contigs (alts, decoys, unplaced), which `length(chrom) <= 2`
excludes — the same predicate the other derivations use.

### Endpoint timings, measured

| Endpoint | Cold | Warm | Rows |
|---|---|---|---|
| `/health` | instant | — | — |
| `/api/overview` | 1.3 s | cached | 1 object |
| `/api/genome/allele-balance` | < 1 s | live | 24 |
| `/api/genome/contig-density` | < 1 s | live | 25 |
| `/api/genome/density-bins` | < 1 s | live | 2,961 (85 for `chrom=15`) |
| `/api/callset/depth-distribution` | < 1 s | live | 55 |
| `/api/callset/substitutions` | < 1 s | live | 12 |
| `/api/callset/indel-lengths` | < 1 s | live | 120 |
| `/api/callset/filters` | < 1 s | live | 35 |
| `/api/callset/genotypes` | < 1 s | live | 3 |
| `/api/panel/genes` | < 1 s | live | 8 |
| `/api/panel/locus?gene=BUB1B` | **8.4 s** | **0.09 s** | 80 |
| `/api/reads/runs` | < 1 s | live | 8 |
| `/api/reads/partitions` | < 1 s | live | 8 |
| `/api/reads/flowcell?lane=1&read=1` | **2.4 s** | **0.035 s** | 31,487 |
| `/api/reads/quality-levels` | **41 s** | cached | 32 |
| `/api/reads/cycle-quality` | **36 s** | **0.013 s** | 1,192 |
| `/api/probe/*`, `/api/jobs/*` | 503 in 7 ms | — | upstream down |

### The overview object, live

```json
{"total_variants": 5012204, "pass_variants": 4740790, "snps": 4086641,
 "indels": 930181, "multiallelic_sites": 66860, "tstv": 1.94, "samples": 1,
 "total_reads": 1071835104, "read_length": 149, "est_coverage_x": 51.9,
 "mean_depth_x": 44.3, "canonical_contigs": 25, "all_contigs": 1690,
 "delivery_objects": 12, "delivery_bytes": 84985953378,
 "all_hashes_verified": true, "probe_budget_total": 18, "probe_budget_spent": 0}
```

### Three findings worth keeping

**1. The NovaSeq quantisation is visible in the data, and it is exactly four levels.**
`/api/reads/quality-levels`, sampling 100k reads from each of the 8 partitions, returns 32
rows — 4 per partition, at Phred **2, 11, 25 and 37**, with no value in between:

```
lane 1 read 1:  phred 2 → 42      phred 11 → 407,562
                phred 25 → 658,133  phred 37 → 13,834,263
```

That settles the chart form: a four-bar histogram is honest, a smooth density curve is a
fabrication. Read 2 is measurably worse than read 1 at every level (632,510 vs 407,562
bases at Phred 11), which is the normal second-read penalty.

**2. Quality decays along the read, mildly.** `/api/reads/cycle-quality` returns 149 cycles
× 8 partitions. Lane 1 read 1 runs 36.24 at cycle 1 → **34.60 at cycle 149**: a 1.6-point
fall, no cliff. Nothing here argues for trimming.

**3. The multiallelic defence fires on the very first gene asked.** `BUB1B` holds 80
variants, of which **one** is a `1/2` site with a comma-packed ALT and a three-value `AD`.
The decoder reports `ad_alt: null, vaf: null` there rather than attributing reads to an
arbitrary one of the two alternates — 79 rows carry a VAF, 1 does not, and the blank is the
correct answer.

### One environment fact, recorded because it cost time

On this machine a VS Code helper process is listening on `127.0.0.1:8765` — the reads API's
default port — and it **accepts the TCP connection without ever answering**. A proxy
request therefore hangs for the full client timeout instead of failing fast, which looks
exactly like a bug in the proxy and is not one. Against a genuinely closed port every proxy
route returns `503 {"detail": "reads API unreachable at <url>"}` in under 10 ms.

Consequence: set `MVA_READS_API_URL` explicitly rather than relying on the default port.

## Conclusions

1. **Precompute, then serve.** No endpoint scans the callset. The one that must read it
   (`/api/panel/locus`) constrains `chrom` first and is cached, so it costs 8.4 s once and
   0.09 s thereafter. Everything else reads a derived table of at most 2,961 rows.
2. **Parse provenance-bearing data in a derivation, not in a request.** The `bcftools
   stats` sections are now five typed tables with lineage edges, so a chart's numbers can
   be traced to a `pg-derive` run. A regex inside an HTTP handler cannot be.
3. **The cache is a correctness feature, not only a speed one.** Every response carries
   `cached_at`, so a stale number is visible as stale in the UI. The cache directory sits
   under gitignored `build/` because the locus entries hold **real patient positions** —
   verified with `git check-ignore`.
4. **`//` not `/`.** DuckDB's `/` is float division; `pos / 1000000` would produce one
   group per position instead of one per megabase. Recorded because the bug is silent — it
   yields a plausible table with 5 million rows.
5. **Two directions of the chr-prefix bridge now exist in the one owner module.** The panel
   is `chr15`, the callset is `15`; a region query built from the panel without stripping
   matches nothing, which looks identical to a gene with no variants.
   `to_vcf_contig()` joins `to_submission_contig()` in `src/mva/pipeline/variant.py`, and
   `tests/test_variant.py` covers both.

## Deviation from the contract, stated for the record

The contract's header says **all** `/api/*` endpoints use the `{data, cached_at, source}`
envelope; its proxy section writes `→ upstream JobOut`. Those cannot both be literal. The
global rule was followed: proxy responses are `{data: <JobOut>, cached_at: null, source:
"<upstream url>"}`. Error bodies are untouched FastAPI `{detail: …}`, as the contract
specifies. `mean_depth_x` is **44.3**, not the contract's illustrative 44.0 — it is the
het-weighted autosomal mean of `results.allele_balance_flags.mean_dp`, computed, not quoted.
