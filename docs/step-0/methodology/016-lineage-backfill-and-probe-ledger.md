# 016 — Closing the lineage gap and building the probe ledger

## Question

Two of the five gaps recorded in [`015`](015-step-1-consolidation.md) were the last step-1
items:

1. `warehouse.data_lineage` held **one** row, naming a *local* path with an empty
   `source_version` and empty `source_sha256`, and there were **no edges** for the five
   derivations logged in `results.derivation_runs`. "Which bytes produced this result?"
   was not answerable from the database.
2. Nothing recorded which of the team's **18** oracle submissions had been spent, by whom,
   with what content, and what came back.

## Finding first

`data_lineage` now holds **7 rows**: the original local-path edge, a **superseding** edge
naming `s3://mva/source/WGS_EX2312012_HGWCNDSX7.vcf.gz` with the publisher-verified
`sha256` and the MinIO `version_id`, and **one edge per derivation**. `pg-derive` records
its own edge from now on, so the backfill verb is only for runs that predate it.
`warehouse.probe_ledger` exists with **0 rows — no probe has been spent**; `probe-budget`
answers `0/18 spent, 18 remaining`.

## Inputs

- Repository working tree, `main`, on top of commit `80fcc41` (HEAD advanced to `fa71b00`
  during the session from parallel work; nothing here depends on that change).
- PostgreSQL 18.4 on the remote VPS, database `mva`, schemas `warehouse` + `results`.
  Connection from `.env` via `mva.warehouse.settings`; DuckDB `postgres` extension.
- MinIO bucket `mva`, versioning Enabled; the verified truth read out of
  `warehouse.source_objects` (12 rows, populated by `source-check` in
  [`014`](014-source-of-truth-and-lineage.md)).
- Oracle budget of 18 from [`ideation/hackathon-intel.md`](../../../ideation/hackathon-intel.md)
  §9; submission column set from `ressources/hackathon-rules/track1_submission_template.csv`
  and `src/mva/pipeline/submission.py`.

## Design decisions, and why

**The lineage table is append-only by design, so the correction is a new row.** Its module
docstring states the rule outright — "lineage that can be edited is not evidence". An
`UPDATE` would have made the earlier, wrong claim disappear, which is exactly the failure
mode append-only exists to prevent. `lineage-repair` therefore *appends* a superseding edge
whose `notes` name the `produced_at` of the row it replaces, and `lineage-list` computes
`is_current` with a window function rather than storing a flag that would have to be
updated.

**The repair is matched by file name, not by the delivery.** `lineage-repair` selects every
edge whose `source_ref` is not an `s3://` URL, takes the basename, and looks it up in
`source_objects`. Nothing about this case's callset is hardcoded, so the verb transfers to
any other N-of-1 dataset. It is a no-op once the target already has an object edge.

**The forward path is automatic.** `postgres.derive()` now calls
`lineage.derivation_edge()` inside the same connection as the derivation itself. A result
whose lineage depends on somebody remembering a second command is a result that will lack
lineage. `derive()` also now stamps one timestamp for the whole run — previously each
`INSERT` called `now()` separately — so the provenance row and the lineage edge that
references it name the same instant.

**Derivation inputs come from `depends_on`, not from parsing the SQL.** A test already
asserts every declared dependency is actually selected from, so the edge and the statement
cannot drift.

**The probe ledger lives in `warehouse`, not `results`.** It is hand-written operational
state — a record of irreversible actions taken in the outside world — like the upload
ledger and the lineage list beside it. The `results` schema is reserved for tables that are
a pure function of their inputs and get rebuilt by `pg-derive`; a submission cannot be
recomputed.

## Exact commands run

```bash
uv run mva-warehouse pg-check
uv run mva-warehouse pg-query "SELECT * FROM pg.warehouse.data_lineage"
uv run mva-warehouse lineage-repair
uv run mva-warehouse lineage-backfill
uv run mva-warehouse lineage-repair     # re-run, to check idempotency
uv run mva-warehouse lineage-backfill   # re-run, to check idempotency
uv run mva-warehouse pg-query "SELECT target_schema, target_table, target_rows, source_kind, \
  source_ref, left(source_sha256,16) AS sha256_head, source_version \
  FROM pg.warehouse.data_lineage ORDER BY produced_at"
uv run mva-warehouse probe-budget
uv run mva-warehouse probe-list
uv run mva-warehouse pg-query "SELECT column_name, data_type FROM pg.information_schema.columns \
  WHERE table_schema='warehouse' AND table_name='probe_ledger' ORDER BY ordinal_position"
uv run pytest -q
```

Tables are addressed `pg.<schema>.<table>` because `pg-query` runs in DuckDB with the
hosted PostgreSQL attached under the alias `pg`.

## Observed output

### Before — the gap, as it stood

```
┌───────────────┬──────────────┬─────────────┬─────────────┬───────────────────────────────────────────────────────┬────────────────┬───────────────┐
│ target_schema │ target_table │ target_rows │ source_kind │ source_ref                                            │ source_version │ source_sha256 │
├───────────────┼──────────────┼─────────────┼─────────────┼───────────────────────────────────────────────────────┼────────────────┼───────────────┤
│ warehouse     │ variants_raw │ 5012204     │ file        │ /home/abdu/ubuntu/data/WGS_EX2312012_HGWCNDSX7.vcf.gz │                │               │
└───────────────┴──────────────┴─────────────┴─────────────┴───────────────────────────────────────────────────────┴────────────────┴───────────────┘
(1 row)
```

### `lineage-repair`

```
  warehouse.variants_raw
    was      /home/abdu/ubuntu/data/WGS_EX2312012_HGWCNDSX7.vcf.gz
    now      s3://mva/source/WGS_EX2312012_HGWCNDSX7.vcf.gz
    sha256   bec64c68d3ad10d05b8071d07cdf87d217013d66d3ba02e24b505035c9d42175
    version  3a79ea8b-6221-4b8c-b217-94d4344db81f

1 superseding edge(s) appended to warehouse.data_lineage
```

The hash and version were **not typed in** — they were read out of `source_objects`, where
`source-check` had verified them against the publisher (`hash_verified = true`).

### `lineage-backfill`

```
  results.panel_gene_density       8 rows  <- panel_variant_counts, mva_panel_grch38   (run 2026-08-29 12:49:49.377449)
  results.filter_impact           35 rows  <- filter_gt_counts   (run 2026-08-29 12:49:49.943372)
  results.sequencing_yield         4 rows  <- fastq_profile   (run 2026-08-29 12:49:50.072284)
  results.contig_density          25 rows  <- contig_counts   (run 2026-08-29 12:49:49.679121)
  results.allele_balance_flags    24 rows  <- vcf_chrom_allele_balance   (run 2026-08-29 12:49:49.801881)

5 derivation edge(s) appended to warehouse.data_lineage
```

### Idempotency — both verbs re-run immediately

```
nothing to repair — every lineage edge already names an object in the store
nothing to backfill — every logged derivation run already has an edge
```

### After — the edge list

```
┌───────────────┬──────────────────────┬─────────────┬─────────────┬────────────────────────────────────────────────────────────┬──────────────────┬──────────────────────────────────────┐
│ target_schema │ target_table         │ target_rows │ source_kind │ source_ref                                                 │ sha256_head      │ source_version                       │
├───────────────┼──────────────────────┼─────────────┼─────────────┼────────────────────────────────────────────────────────────┼──────────────────┼──────────────────────────────────────┤
│ warehouse     │ variants_raw         │ 5012204     │ file        │ /home/abdu/ubuntu/data/WGS_EX2312012_HGWCNDSX7.vcf.gz      │                  │                                      │
│ warehouse     │ variants_raw         │ 5012204     │ object      │ s3://mva/source/WGS_EX2312012_HGWCNDSX7.vcf.gz             │ bec64c68d3ad10d0 │ 3a79ea8b-6221-4b8c-b217-94d4344db81f │
│ results       │ panel_gene_density   │ 8           │ table       │ warehouse.panel_variant_counts, warehouse.mva_panel_grch38 │                  │                                      │
│ results       │ filter_impact        │ 35          │ table       │ warehouse.filter_gt_counts                                 │                  │                                      │
│ results       │ sequencing_yield     │ 4           │ table       │ warehouse.fastq_profile                                    │                  │                                      │
│ results       │ contig_density       │ 25          │ table       │ warehouse.contig_counts                                    │                  │                                      │
│ results       │ allele_balance_flags │ 24          │ table       │ warehouse.vcf_chrom_allele_balance                         │                  │                                      │
└───────────────┴──────────────────────┴─────────────┴─────────────┴────────────────────────────────────────────────────────────┴──────────────────┴──────────────────────────────────────┘
(7 rows)
```

The superseded row is still there — that is the point. Its replacement says so in `notes`:

```
supersedes the edge produced at 2026-08-29 16:37:29; the same bytes, now named by their
object-store location, publisher-verified hash and version. hash_verified=True.
columns: line_no + chrom, pos, id, ref, alt, qual, filter, info, format, sample_call
```

### The probe ledger

```
$ uv run mva-warehouse probe-budget
all tracks: 0/18 spent, 18 remaining

$ uv run mva-warehouse probe-list
┌──────────┬───────────┬───────┬──────┬──────────────┬────────────────┬────────┬───────┬──────────┬──────────────┐
│ probe_id │ logged_at │ track │ type │ submitted_by │ submission_ref │ n_rows │ score │ response │ payload_head │
├──────────┼───────────┼───────┼──────┼──────────────┼────────────────┼────────┼───────┼──────────┼──────────────┤
└──────────┴───────────┴───────┴──────┴──────────────┴────────────────┴────────┴───────┴──────────┴──────────────┘
(0 rows)

budget: 0/18 spent, 18 remaining
```

Zero rows is the honest state: **no probe has been spent.** No test data was inserted into
the live table; `probe-log` is exercised only by the hermetic fake in
`tests/test_warehouse_ledgers.py`.

Schema, read back from `information_schema`:

```
┌────────────────┬─────────────────────────────┐
│ column_name    │ data_type                   │
├────────────────┼─────────────────────────────┤
│ probe_id       │ bigint                      │
│ score          │ double precision            │
│ rationale      │ character varying           │
│ logged_at      │ timestamp without time zone │
│ track          │ character varying           │
│ probe_type     │ character varying           │
│ submitted_by   │ character varying           │
│ submission_ref │ character varying           │
│ payload        │ character varying           │
│ n_rows         │ integer                     │
│ response       │ character varying           │
└────────────────┴─────────────────────────────┘
(11 rows)
```

### Tests

```
$ uv run pytest -q
305 passed in 4.02s
```

Baseline was 268. The 37 new tests are `tests/test_warehouse_ledgers.py` (29) plus 8 picked
up automatically by `tests/test_cli_parsers.py`, which parametrizes over every registered
verb (6 new) and every source file (2 new modules). One of the 29 asserts the property the
whole design rests on: neither ledger's SQL ever contains `UPDATE`, `DELETE` or `DROP`.

## What is now one query

```sql
-- which bytes produced this table, currently
SELECT * FROM warehouse.data_lineage
WHERE (target_schema, target_table, produced_at) IN (
  SELECT target_schema, target_table, max(produced_at)
  FROM warehouse.data_lineage GROUP BY 1, 2);

-- how many oracle submissions are left
SELECT 18 - count(*) AS remaining FROM warehouse.probe_ledger;
```

Or as verbs: `mva-warehouse lineage-list --current`, `mva-warehouse probe-budget`.

## Conclusion

Both step-1 gaps are closed against the live database. Lineage is now a query rather than
an argument: every table in `warehouse` and `results` has an edge, the raw callset's edge
names the exact object, hash and version the bytes came from, and `pg-derive` maintains the
edges from here on without anyone remembering to. The probe ledger exists and is empty,
which is the correct state — the budget is intact at 18.

**Deliberately not done:** no view or extra column was added to `data_lineage`
(`is_current` is computed on read, and adding columns to an evidence table would have been
a schema change beyond the correction this entry is about); nothing was written to
`variants_raw`, `source_*` or `results.*`; and no row was inserted into the live probe
ledger to "test" it.
