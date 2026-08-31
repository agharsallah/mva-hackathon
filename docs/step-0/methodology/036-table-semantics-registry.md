# 036 — Every table explained, and a test that refuses to let it go stale

**A step-0 platform entry, so it carries no hypothesis.** It records what was built, the
measurements that decided two design choices, and the enforcement rule that answers "how
does this stay current".

## Question

[034](034-data-catalog-endpoints.md) made the database enumerable: 38 tables, each with a
description, a row count and a lineage edge. Three questions it left unanswered, all of
which a reviewer asks within a minute of opening the page:

1. **What does this column mean?** `information_schema` says `mean_vaf` is a
   `double precision`. It cannot say that 0.50 is the value a diploid genome gives.
2. **What writes this table, and what would a re-run do to it?** A lineage edge names the
   *last* run. It does not say whether re-running replaces the table, rebuilds it, or only
   appends.
3. **Why does it exist?** A description says what is in a table. It does not defend it.

And the question behind those three: **how does the answer stay true when table 39
arrives?** A registry of prose about a database is exactly the kind of documentation that
rots. Can the rot be made to fail a build?

## Inputs

| Input | Shape as read |
|---|---|
| `pg.information_schema.tables` | 38 tables across `warehouse` + `results` |
| `pg.information_schema.columns` | **262** columns across those 38 tables |
| Writers read for semantics | `warehouse/stage.py`, `vcfstage.py`, `annotate.py`, `lineage.py`, `source.py`, `probes.py`, `science/hypothesis.py`, `science/evidence.py`, and the SQL in `warehouse/analysis.py` + `analysis_reference.py` |
| New code | `src/mva/viz/catalog_semantics.py`, `catalog_columns.py`, `catalog_columns_ingest.py`, `catalog_columns_results.py`; endpoint in `catalog.py`, route in `routes_warehouse.py` |
| New UI | `app/src/pages/catalog/TableExplainer.tsx`, fixture `app/src/fixtures/catalog-semantics.ts` |
| New test | `tests/test_catalog_semantics.py` |

## Commands run

```bash
uv run mva-warehouse pg-check
uv run python -c "…information_schema.columns…"        # the 262-column ground truth
uv run pytest -q
cd app && npm run typecheck && npm run build
pkill -f '.venv/bin/mva-viz-api'
nohup uv run mva-viz-api > /tmp/mva-viz-api.log 2>&1 &
curl -s -w '%{time_total}' http://127.0.0.1:8900/api/catalog/objects
curl -s -w '%{time_total}' http://127.0.0.1:8900/api/catalog/columns
curl -s -w '%{time_total}' 'http://127.0.0.1:8900/api/catalog/tables?refresh=true'
```

## Observed output

### Measurement 1 — the column endpoint is cheap enough to stay live

`information_schema.columns` is metadata, so the read never touches a table's rows.
Timed in-process inside one `attached(read_only=True)` session, and end to end over HTTP:

| Path | Cold | Warm |
|---|---|---|
| `catalog.columns()` in-process | 1.07 s | 0.53–0.58 s |
| `GET /api/catalog/columns` | 1.59–4.00 s | 0.95 s |
| `GET /api/catalog/tables?refresh=true` (for scale) | 11.81 s | 3.34 s |

The exact row counts in `/api/catalog/tables` cost 3–12 s over the same link and are why
*that* endpoint is cached. The column list costs about a second. Caching it would buy that
second and add a way for the answer to be stale after a schema change — which is the exact
change the endpoint exists to surface. **Left live.**

### Measurement 2 — the shared-column map is what makes the registry small

262 columns, but not 262 sentences. Resolution is table-specific first, then a shared map
keyed by bare column name:

| Map | Entries | Covers |
|---|---|---|
| `SHARED` (recurring names) | 50 | `chrom`, `pos`, `ref`, `alt`, `qual`, `filter`, `sha256`, `loeuf`, … |
| `BY_TABLE` (one table only) | 161 | `contig_counts.length`, `variants_raw.line_no`, `probe_ledger.payload`, … |
| **Total written** | **211** | **262 columns, 0 with a null meaning** |

`chrom` alone is written once and answers for the fourteen tables carrying it. The
table-specific map has to win, and a single case proves why: **`length` is the contig's
size in `contig_counts` and the indel's size in `stats_idd`**. One shared answer would be
wrong in one of them, so `length` is deliberately absent from `SHARED` and present twice in
`BY_TABLE`. A test asserts exactly that.

### The enforcement rule — how this stays current

`tests/test_catalog_semantics.py::test_every_declared_table_is_described` walks
`catalog_semantics.declared_tables()`, which enumerates **40** table names from code
constants alone — no database, no network:

| Source of the name | Count |
|---|---|
| `warehouse.catalog.OVERRIDES` (headerless / sectioned profile files) | 5 |
| `warehouse.catalog.NOTES` (sniffed profile files) | 7 |
| `warehouse.reference.datasets()` (committed public tables) | 3 |
| `warehouse.analysis.DERIVATIONS` | 14 |
| the ledgers, the raw layer, the annotation table, the catalogue, the scalars | 9 |
| the research register (`hypotheses`, `evidence`) | 2 |

40 declared, 38 live: `hypotheses` and `evidence` exist in code and have not been created
in the database yet. Both are described anyway, so the day they land the page is already
right.

Any of those 40 without a `created_by` and a `why` fails the test with the edit to make:

```
2 table(s) exist in code with no semantics:
  - 'brand_new_table' (declared in mva.warehouse.catalog.NOTES)

Add a TableFact for each in src/mva/viz/catalog_semantics.py:
    "<table>": TableFact("<the verb that writes it>", "<why it exists>"),
A derivation needs no entry — its `why` is the question declared beside its SQL …
```

A second test (`test_the_gate_would_actually_catch_a_new_table`) injects a table name into
`NOTES` and asserts the gate trips, so the gate is itself covered rather than trusted.

**The one gap the gate cannot close**, stated rather than hidden: a *new source file*
dropped into the profile directory is staged by the sniffer in `warehouse/catalog.py` under
a name no constant mentions. Giving it a `NOTES` entry — which it needs anyway, to carry a
description — brings it back under the check. Everything a developer writes by hand is
covered; only a file appearing on disk is not.

### `created_by` says what a re-run would do

The field is not "which tool", it is "which verb, and with what write semantics" — the
fact a reader needs *before* re-running anything:

| Family | `created_by` | Tables |
|---|---|---|
| staged profile + reference | `mva-warehouse stage + pg-ingest` | 17 |
| the raw callset | `mva-warehouse vcf-ingest (replaces the table wholesale)` | 1 |
| the annotations | `mva-warehouse annotate-panel (replaces the table wholesale)` | 1 |
| derivations | `mva-warehouse pg-derive (the output table is rebuilt from scratch, never appended to)` | 14 |
| ledgers and registers | `append-only ledger — written by <verb>` | 7 |

A derivation's `why` is **read off `Derivation.question`**, never restated. Copying the
sentence into the registry would create a second version that could drift from the SQL it
describes, and a test asserts the two are the same object.

### Live payloads, as served

```json
{"schema": "warehouse", "table": "variants_raw",
 "description": "The callset as delivered, one row per VCF record …",
 "rows": 5012204, "produced_at": "2026-08-29T21:02:49.217464",
 "source_kind": "object", "source_ref": "s3://mva/source/…vcf.gz", "tool": "mva-warehouse",
 "created_by": "mva-warehouse vcf-ingest (replaces the table wholesale)",
 "why": "The lossless landing layer: every VCF record, every field as text, nothing coerced. …"}
```

```json
{"schema": "results", "table": "allele_balance_flags", "column": "chrom",
 "data_type": "character varying", "ordinal": 1,
 "meaning": "Contig (chromosome) the row is about, spelled as that table stores it — bare on the callset side, `chr`-prefixed on the panel side."}
```

### Coverage against the live database

| Endpoint | Rows | Nulls |
|---|---|---|
| `/api/catalog/objects` | 12 | unchanged |
| `/api/catalog/tables` | 38 | **0** null `created_by`, **0** null `why` |
| `/api/catalog/columns` | 262 | **0** null `meaning` |

Zero nulls is today's state, not a contract. All three fields stay nullable and the UI
renders each gap in yellow, because the honest answer for an undescribed column is a
visible blank, not an invented sentence.

## Conclusions

1. **Metadata is enumerable; semantics is not.** Row counts, types and ordinals come out of
   `information_schema`. What a column *means* exists only in the code that writes it, so
   it has to be written down — and the only two things worth writing down beyond the
   description are the write semantics and the reason.
2. **A shared map is what keeps a column registry maintainable.** 211 sentences cover 262
   columns, and the next table carrying `chrom` needs none. The table-specific override is
   not a nicety: `length` means two different things two tables apart.
3. **Documentation discipline belongs in the test suite.** "Please describe new tables" in
   a README is advice. `pytest` failing with the exact dict entry to add is a gate. The
   enumeration is code constants only, so the gate is hermetic and runs in 0.19 s.
4. **The UI needs no edit when the schema grows.** Both lists are enumerated live, so a new
   table renders itself; the only thing that has to be written is the sentence the gate
   demands.

## Tests

`tests/test_catalog_semantics.py`, 13 tests, hermetic (no database, no network): the
enforcement gate and a proof that the gate trips; the declaration map naming where each
table name came from; every derivation and every ledger being enumerated; a derivation's
`why` being its declared question object; the three write-semantics families; the
shared-map coverage of recurring columns; a table-specific meaning beating the shared one
both ways round; and the null fallback.

`tests/test_viz_catalog.py` grew from 23 to 31: the two new table fields and their nulls, a
derivation's `why`, the column endpoint's field order and types, the shared/specific
resolution order, the null meaning, and the HTTP surface being live rather than cached.

```
uv run pytest -q      → 751 passed, 11 failed
cd app && npm run typecheck && npm run build   → clean
```

The 11 failures are the pre-existing ones in `tests/test_reads_api.py`, unchanged by this
work (751 = 730 before + 21 new).
