# 034 — The data catalogue: two endpoints that describe the data instead of reading it

**A step-0 platform entry, so it carries no hypothesis.** It records what was built, the
one measurement that decided a design choice, and the nulls the contract has to carry.

## Question

Every existing `/api/*` endpoint answers "what does the data *say*". Nothing answers the
question a reviewer asks first: **what raw data exists, what is in each file, when did it
arrive, where does it live, and what is in the database that was built from it?**

Four tables already hold the answer and none of them was served:
`warehouse.source_objects` (the store inventory), `warehouse.source_files` (the upload
ledger), `warehouse.warehouse_catalog` (the self-describing table catalogue) and
`warehouse.data_lineage` (the edge list). Can one pair of endpoints assemble them without
inventing a single number?

## Inputs

| Input | Shape as read |
|---|---|
| `pg.warehouse.source_objects` | 12 rows, one per object under `source/` |
| `pg.warehouse.source_files` | 14 rows (the VCF and its index were uploaded twice), 12 distinct `object_key` |
| `pg.warehouse.warehouse_catalog` | 17 rows, `table_name → description` |
| `pg.warehouse.data_lineage` | 20 rows, 19 distinct `(target_schema, target_table)` |
| `pg.results.derivation_runs` | 14 derivations, latest `question` per name |
| `pg.information_schema.tables` | 38 tables across `warehouse` + `results` |
| Code | `src/mva/viz/catalog.py`, routes in `src/mva/viz/routes_warehouse.py` |

## Commands run

```bash
uv run mva-warehouse pg-check                       # PostgreSQL 18.4, 1338 MB
uv run mva-warehouse pg-query "SELECT file_name, object_key, min(uploaded_at) …
                               FROM pg.warehouse.source_files GROUP BY 1,2"
uv run mva-viz-api --port 8931
curl -s -w '%{time_total}' http://127.0.0.1:8931/api/catalog/objects
curl -s -w '%{time_total}' 'http://127.0.0.1:8931/api/catalog/tables?refresh=true'
uv run pytest -q                                    # 726 passed, 11 pre-existing failures
```

## Observed output

### The measurement that decided the design: how to count rows

Three ways to put a row count next to 38 table names, timed with `time.perf_counter()`
inside **one** `mva.warehouse.postgres.attached(read_only=True)` session against the live
hosted database, so the attach cost is paid once and excluded from all three:

```python
# 1. estimate
"""SELECT * FROM postgres_query('pg', $$
     SELECT n.nspname, c.relname, c.reltuples::bigint FROM pg_class c
     JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname IN ('warehouse','results') AND c.relkind = 'r' $$)"""
# 2. one round trip per table
[f"SELECT count(*) FROM pg.{schema}.{table}" for schema, table in listed]
# 3. one pushed-down statement — what mva.viz.catalog._counts builds
f"SELECT s, t, n FROM postgres_query('pg', $${union}$$)"   # union = one count(*) per
#                                                            table, joined by UNION ALL
```

| Method | Cost | Usable? |
|---|---|---|
| `pg_class.reltuples` via `postgres_query` | **0.23 s** | **No** |
| one `count(*)` round trip per table | 25.70 s | yes, but 10× the cost |
| one `UNION ALL` of `count(*)` pushed down through `postgres_query` | **2.71 s** | **yes** |

`reltuples` fails on correctness, not on speed: **22 of the 38 tables have never been
`ANALYZE`d and report `-1`**, and the one table large enough for the estimate to matter is
wrong — `variants_raw` estimates 5,014,376 against an actual 5,012,204, an error of 2,172
rows. A catalogue whose row counts are silently wrong is worse than one with no counts.

So: exact counts, one pushed-down statement, and the endpoint is cached.

Attach cost is worth recording separately, because it dominates the cheap endpoint:
**0.33 s** per `ATTACH`, and listing the 38 tables from `information_schema` is 0.58 s.

### Endpoint timings and sizes, measured

| Endpoint | Cold | Warm | Rows | Payload |
|---|---|---|---|---|
| `/api/catalog/objects` | 0.50–0.60 s | live, not cached | 12 | 9,877 B |
| `/api/catalog/tables?refresh=true` | **4.02 s** first, **1.57–1.64 s** once PostgreSQL's buffer cache holds `variants_raw` | **0.008 s** | 38 | 11,861 B |

`objects` is left live: it is one join over a 12-row table that `mva-warehouse
source-check` replaces wholesale, and caching it would only hide a fresh survey.
`tables` is cached under the existing mechanism, with `?refresh=true`.

### One object row, as served

```json
{"file_name": "WGS_EX2312012_HGWCNDSX7_S16_L001_R1_001.fastq.gz",
 "object_key": "source/WGS_EX2312012_HGWCNDSX7_S16_L001_R1_001.fastq.gz",
 "location": "s3://mva/source/WGS_EX2312012_HGWCNDSX7_S16_L001_R1_001.fastq.gz",
 "kind": "fastq", "role": "reads",
 "description": "Raw sequencing reads as the instrument delivered them — gzipped FASTQ, four lines per read: name, bases, separator, per-base quality. Lane 1, mate R1, sample WGS_EX2312012, flowcell HGWCNDSX7.",
 "size_bytes": 10467073561, "content_type": "binary/octet-stream",
 "sha256": "5ec244c0…4939f", "sha256_source": "publisher", "hash_verified": true,
 "version_id": "998e30c9-1bfe-4a38-ad0f-a277fa3f5c22",
 "last_modified": "2026-08-29T13:50:24.232000",
 "first_uploaded_at": "2026-08-29T15:50:24.333630",
 "sample": "WGS_EX2312012", "flowcell": "HGWCNDSX7", "lane": 1, "read_num": 1}
```

### One table row, as served

```json
{"schema": "warehouse", "table": "variants_raw",
 "description": "The callset as delivered, one row per VCF record with every column kept as text — the lossless raw layer every derivation reads.",
 "rows": 5012204, "produced_at": "2026-08-29T21:02:49.217464",
 "source_kind": "object",
 "source_ref": "s3://mva/source/WGS_EX2312012_HGWCNDSX7.vcf.gz",
 "tool": "mva-warehouse"}
```

### Four findings worth keeping

**1. The upload ledger matches every object today, and the join must still be a LEFT
JOIN.** All 12 `object_key`s in `source_objects` have at least one `source_files` row, so
no `first_uploaded_at` is currently null. That is a fact about today, not a guarantee: the
`source-fetch` path streams from the publisher straight into the bucket, and an object that
arrives that way never passes through the ledger. The join is a LEFT JOIN and the field is
nullable; the tests cover the null case even though the live data does not exercise it.

**2. Fourteen ledger rows, twelve objects.** The VCF and its index each have two upload
rows — the same bytes, uploaded twice. `MIN(uploaded_at)` is the honest answer for "when
did this first arrive", and the append-only history stays visible in
`/api/provenance/sources` and the ledger itself.

**3. Nineteen of 38 tables have no lineage edge, and every one of the 38 has a
description.** The tables with no edge are the ledgers, the catalogue table and the staged
profile tables — nothing derived them, and saying so is the correct answer. Descriptions
resolve in three steps: the staged catalogue (16 tables), the latest
`derivation_runs.question` (14 tables), then an in-code one-liner in
`catalog.UNCATALOGUED` (8 tables: the raw layer, the four ledgers, `panel_annotations`,
`warehouse_catalog`, `derivation_runs`). No table falls through to null today.

**4. A catalogue row can outlive its table.** `warehouse_catalog` still names
`hf_lfs_sha256`, which was staged but never ingested. Enumerating from
`information_schema` rather than from the catalogue means the endpoint lists what the
database actually holds; the stale catalogue row is simply never reached.

## Conclusions

1. **Exact beats cheap when the number is the product.** The catalogue *is* the row
   counts; a `reltuples` estimate that reads `-1` for 22 tables would make the page a
   liar for 0.2 s of saving. 2.7 s pushed down, once, behind a cache.
2. **Push the aggregation into PostgreSQL.** One `UNION ALL` inside `postgres_query` is
   9.5× faster than one round trip per table, for the same exact answer. The round trips,
   not the counting, were the cost.
3. **Descriptions of *contents* are the one thing that has to be written.** Sizes, hashes,
   versions, lane numbers and row counts all exist in the database. What a FASTQ *is* does
   not, so `catalog.ROLES` and `catalog.DOCUMENTS` map role and extension to one sentence
   — keyed on the parsed role, not on this delivery's file names, so another case gets the
   right sentence or the honest "nothing is claimed about its contents".
4. **Two nulls are part of the contract, not gaps.** `first_uploaded_at` for an object the
   ledger never saw, and the four lineage fields for a table nothing derived. Both are
   asserted in `tests/test_viz_catalog.py`.

## Tests

`tests/test_viz_catalog.py`, 23 tests, hermetic: `catalog.attached` is replaced by a fake
connection answering on a SQL fragment, in the style of `tests/test_viz_units.py`. Covered:
the `location` build, the field order of the contract, the description mapping for each
role and each document extension, the trailing lane/mate/sample/flowcell clause, the
upload match and its null, the exact-count pushdown being one statement, the three
description sources and the null fallback, description not leaking across schemas, the
latest lineage edge and its four nulls, one attach per catalogue, and both HTTP surfaces
(objects live, tables cached with `?refresh=`).

`uv run pytest -q` → **726 passed**, 11 failures, all pre-existing in
`tests/test_reads_api.py` and unrelated to this change.
