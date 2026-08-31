# 035 — The Catalog page

**A step-0 platform entry, so it carries no hypothesis.** It records what was added to `app/`
after [033](033-compare-page.md), and what could not be verified because the endpoints behind it
do not exist yet.

## Question

The app can read the case but cannot answer the question a reviewer asks first: **what data do we
hold, what is in each piece, when did it arrive, and where does it live?** Can that catalogue be
built fixture-first against two not-yet-implemented endpoints — and can the two *gaps* in the
contract (an object with no ingest-ledger row, a table with no lineage edge) be rendered as stated
gaps rather than as blank cells that read like "nothing to see"?

## Inputs

| Input | Version / shape |
|---|---|
| Endpoint contracts | `/api/catalog/objects` (~12 rows), `/api/catalog/tables` (~25–30 rows, schemas `warehouse` and `results`) — supplied verbatim, not yet implemented |
| Existing app | `app/` at `40eb901`, conventions from [029](029-viz-app.md) and [033](033-compare-page.md) |
| Live viz API | `mva-viz-api` on `127.0.0.1:8900` — **up**, `404` on both new routes before and after the work |
| Node toolchain | vite 8.2.2, typescript 7.0.2 — **no new npm dependency added** |

## What was built

**New page `Catalog` (`/catalog`)** — three exhibits:

| Exhibit | Figure | The rule it encodes |
|---|---|---|
| `DeliveryInventory` | one card per raw object, grouped callset → reads (by lane/read) → metadata | The verified badge names **whom** the hash matched: `publisher` (their signed manifest — our bytes are their bytes) vs `own-upload` (our own round-trip only). A null `first_uploaded_at` falls back to `last_modified` **and says so** in a yellow chip, because an upper bound on arrival is not an arrival time. sha256 truncated to 12 chars, full value on hover. |
| `TableCatalog` | `DataTable` of every warehouse/results table + a client-side free-text filter | A row with no lineage edge draws a yellow `no lineage edge` chip in the `produced at` column, and a row with no description a yellow `undescribed` chip — never a blank. The legend states that `rows` is the catalogue's count as of its cached refresh, not a live count. The filter matches table name, `schema.table`, and description, case-insensitively — the first search box in the app outside the probe console, styled as a `Controls` widget. |
| `ReadStoreCard` | a fact card, not a chart | Reuses the **existing** `/api/reads/partitions` and `/api/reads/runs` hooks rather than introducing a second source of truth for shards/reads/GiB. `runs.parquet` carries the engine and per-file seconds but **no timestamp**, so "converted at" renders a yellow "not carried by the runs table" instead of inventing a date. |

**Plumbing** — 2 interfaces (`api/types/catalog.ts`, behind the existing barrel), 2 one-line hooks,
2 fixture builders registered by exact path. One shared control added: `TextFilter` in
`components/Controls.tsx`, so the next filter box does not re-style itself.

**Two files, not one, for the fixture.** A single `fixtures/catalog.ts` reached 456 lines; it was
split into `fixtures/catalog-objects.ts` (147) and `fixtures/catalog-tables.ts` (329 after the undescribed-table row) to hold the
repo's 400-line rule.

Fixture rows deliberately exercise every edge in the contracts: a publisher-verified object, an
own-upload object, an unverified object with a null digest, three objects with null
`first_uploaded_at`, eight FASTQs carrying lane/read/flowcell metadata, two tables with no lineage
edge, one table with **no description**, and a table whose description states its count is
approximate.

## Commands run

```
$ curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8900/health                 # 200
$ curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8900/api/catalog/objects    # 404
$ curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8900/api/catalog/tables     # 404

$ cd app && npm run typecheck        # tsc -b
$ npm run build                      # tsc -b && vite build
$ find src -name '*.ts*' | xargs wc -l | sort -rn | head

# fixture path forced by pointing the app at a dead port (a 404 does NOT fall back)
$ VITE_API_URL=http://127.0.0.1:9 npx vite --port 5199 --host 127.0.0.1
$ "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu \
    --user-data-dir=<tmp> --virtual-time-budget=16000 --dump-dom http://127.0.0.1:5199/catalog
# filter box driven in-page via CDP (native value setter + input event)
```

## Observed output

`npm run typecheck` and `npm run build`: both clean, no warnings.

```
✓ 135 modules transformed.
dist/assets/Catalog-CnW-t84l.js    19.19 kB │ gzip: 6.17 kB   (new)
dist/assets/plotly.min-*.js      4,066.60 kB │ gzip: 1,244.94 kB
✓ built in 1.16s
```

The Catalog chunk imports no `Plot`, so it never pulls the Plotly chunk — the second such page
after Provenance. Largest source file after the fixture split is `fixtures/catalog-tables.ts` at
329 lines.

Post-JavaScript DOM, fixture path, `/catalog`: 3 figures · 3 legends · 3 `fixture` chips ·
**0 error cards** · 0 loading skeletons. Read straight out of the DOM:

```
delivery summary ..... 12 objects · total 80.2 GiB · 11 hash-verified (10 against the publisher)
                       · 3 with no first-upload record
object cards ......... 12, in 3 groups; 8 carry an L<lane> R<read> chip
hash badges .......... 10 "verified · publisher", 1 "verified · own-upload",
                       1 red "no digest" (the publisher's own checksum manifest)
ledger gap ........... 3 cards show the yellow "last modified — predates the ledger" chip
table catalogue ...... showing 32 of 32 tables · results 18 · warehouse 14
                       · yellow "no lineage edge" on exactly warehouse.gnomad_af_panel and
                         results.kmer_counts; yellow "undescribed" on warehouse.vep_staging
read store card ...... s3://mva/reads/ · 8 partitions · 272 shards · 1,071,835,104 reads (1.07 B)
                       · 63.02 GiB · engine polars · 100 min of conversion
                       · "converted at: not carried by the runs table"
nav .................. 9 links, Catalog active
```

Filter box, driven in-page:

```
""            → 31 rows      "bcftools" → 5 rows (all five warehouse.bcftools_* tables)
"ANEUPLOIDY"  → 1 row        (description-only match, upper case → case-insensitive holds)
"estimate"    → 1 row        (warehouse.variants_raw, matched on description)
"zzzz"        → 0 rows       and the designed empty state renders: no table matches "zzzz"
cleared       → 31 rows
```

(run before the `vep_staging` row below was added, hence 31 rather than 32.)

## What was NOT verified

Both endpoints answered `404` throughout, so **no row on this page has ever been rendered from a
live catalogue**. Two consequences, the same pair [033](033-compare-page.md) recorded:

1. Every value on `/catalog` is fixture shape, not a measurement — file names, object keys,
   digests, descriptions and row counts included. The app badges all three exhibits `fixture`.
2. A `404` is not a fallback trigger (only `501` and a network-level failure are), so while the
   viz API is up and 404-ing, these exhibits show **error cards**. The fixture path had to be
   forced with a dead `VITE_API_URL`. Nothing needs changing when the endpoints land; until then a
   live demo of `/catalog` needs the API stopped or repointed.

### Read against the backend source instead

The backend for these two routes was written concurrently in another session and landed as
`src/mva/viz/catalog.py` (see [034](034-data-catalog-endpoints.md)); the running server was simply
an older process. Reading its projections rather than a live response found no breaking mismatch
and **two things the contract text did not say**, both of which changed the client:

1. `_table()` builds `description` from three sources tried in order and falls through to `None`.
   The contract implied a string. The type is now `string | null`, the filter guards it, and an
   undescribed table draws a second yellow gap chip — without that, the filter would have thrown
   on the first such row.
2. `_counts()` runs one pushed-down `UNION ALL` of `count(*)` and documents that
   `pg_class.reltuples` was rejected as unusable, so live counts are **exact**, not planner
   estimates. The legend was rewritten from "is a planner estimate on the large raw tables" to a
   statement about the cached refresh time, which is true of both the shipped implementation and
   the contract's weaker promise.

Both routes are registered at exactly `/api/catalog/objects` and `/api/catalog/tables` and return
the standard envelope, so nothing else in the client needs changing. This is still "no mismatch
observed", not "the contract is confirmed".

## Conclusions

- The design work was again in the nulls, and again the wrong rendering was the easy one. A blank
  `produced at` cell reads as "fine, nothing to report"; the same absence written as
  `no lineage edge` reads as what it is — a table nobody can re-derive or invalidate. Chips beat
  blanks for exactly the reason a labelled novel lane beat `0` in [033](033-compare-page.md).
- `hash_verified` alone is not a claim worth showing. `verified · publisher` and
  `verified · own-upload` are different guarantees — one says our bytes are the publisher's, the
  other only that our own upload round-tripped — and collapsing them into one green tick would
  overstate the weaker case.
- Reusing the reads hooks for `ReadStoreCard` cost one import and removed a whole class of drift:
  the card cannot disagree with the Reads page about the shard count, because it is the same query.
- Fixture-first held for a third page. It is still not evidence of correctness — re-verify every
  column against the live service once the routes answer.
