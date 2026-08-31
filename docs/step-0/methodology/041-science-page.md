# 041 — The science register in the browser: serving a table that does not exist

**A step-0 platform entry, so it carries no hypothesis.** It records what was built, the
one design problem that made it different from every other viz route, and the live state
the endpoints actually returned.

## Question

`docs/method.md` declares a machine-readable research record: `warehouse.hypotheses` and
`warehouse.evidence`, both append-only, plus `warehouse.probe_ledger` for the 18 oracle
submissions. Nothing in the browser showed any of it.

The register is **empty by design** — no hypothesis has been proposed, 0 of 18 probes
spent — and the two register tables are created on first write by `mva-science`, so today
they are **not in the database at all**. That is the question this entry answers: can a
read-only HTTP surface render an empty research record honestly, without creating the
tables and without pretending an absent table is an empty one?

## Inputs

| Input | Shape as read |
|---|---|
| `pg.warehouse.hypotheses` | **does not exist** — created by `mva-science hypothesis-add` |
| `pg.warehouse.evidence` | **does not exist** — created by `mva-science evidence-add` |
| `pg.warehouse.probe_ledger` | exists, 0 rows ([owned by `current-state.md` §2](../../current-state.md)) |
| `pg.information_schema.tables` | the existence check, one round trip, no scan |
| DDL the contract mirrors | `mva.science.hypothesis.ensure_table`, `mva.science.evidence.ensure_table` |
| Code | `src/mva/viz/science.py`, two lines in `src/mva/viz/routes_warehouse.py` |
| Page | `app/src/pages/Science.tsx` + `app/src/pages/science/` (4 widgets + shared register helpers) |

## Commands run

```bash
uv run mva-viz-api --port 8945                     # own port; the shared 8900 untouched
curl -s -w '%{time_total}' http://127.0.0.1:8945/api/science/hypotheses
curl -s -w '%{time_total}' http://127.0.0.1:8945/api/science/evidence
curl -s -w '%{time_total}' http://127.0.0.1:8945/api/probe/ledger
MVA_VIZ_CORS=http://127.0.0.1:5199 uv run mva-viz-api --port 8945
VITE_API_URL=http://127.0.0.1:8945 npx vite --port 5199   # /science, both states
uv run pytest -q
cd app && npm run typecheck && npm run build
```

## Observed output

### The live register: both tables are absent, not empty

```json
{"data":{"table_exists":false,"rows":[]},"cached_at":null,"source":"pg.warehouse.hypotheses"}
{"data":{"table_exists":false,"rows":[]},"cached_at":null,"source":"pg.warehouse.evidence"}
{"data":[],"cached_at":null,"source":"pg.warehouse.probe_ledger"}
```

So the three ledgers are in **two different states**, and the page says which is which:
`probe_ledger` exists and holds nothing (the budget is tracked, nothing has been spent);
the two register tables have never been written.

### Timings, live against the hosted PostgreSQL

| Endpoint | Cold | Warm (3 runs) |
|---|---|---|
| `/api/science/hypotheses` | 3.80 s | 0.75 / 1.14 / 1.42 s |
| `/api/science/evidence` | 0.88 s | 0.67 / 0.69 / 2.02 s |
| `/api/probe/ledger` | 0.84 s | — |

The cold figure is the first `ATTACH` of the process (~0.33 s per attach is the measured
floor, [entry 034](034-data-catalog-endpoints.md)); everything after it is one round trip
to `information_schema` and, when the table exists, one small table read. No cache: there
is nothing here expensive enough to justify one, and a stale research record would be
worse than a slow one.

## The design problem, and what was decided

**1. A missing table is a state, not an error.** DuckDB raises on a reference to a table
that is not there, and catching that exception would make "the register is not open yet"
indistinguishable from a typo in the SQL. So the endpoint asks `information_schema` first,
on the same connection, and answers `{"table_exists": false, "rows": []}`. One attach pays
for both statements, so the missing-table answer costs no more than the present one.

**2. The endpoint must never call `ensure_table`.** It would have been one import. A GET
that materialises the table turns *"nobody has made a claim"* into *"the register exists
and is empty"* — a different fact, created by a page load. Two hermetic tests assert no
`CREATE` reaches the connection, and that nothing is read after the existence check misses.

**3. `data` is an object, not a bare list.** The envelope is unchanged; the flag lives
inside `data`, the way `/api/callset/tstv` already puts an object there. The browser needs
the distinction to write the right empty state.

**4. Every revision is served; the latest is computed client-side.** The register is
append-only — a changed belief is a new `revision` row of the same `hypothesis_id`. The
API serves the whole stream ordered `hypothesis_id, revision`; the board shows the top of
each stack and keeps the earlier revisions behind an expander. An append-only register
whose history the UI throws away is a mutable table with extra rows.

**5. Columns are named, never `SELECT *`.** A column added to the DDL upstream would
otherwise change the browser's payload silently. A test walks both `ensure_table`
functions and asserts the served column tuples equal the declared DDL, so the two cannot
drift.

**6. The viz layer imports two names from `science/`, and no behaviour.**
`HYPOTHESIS_TABLE` and `EVIDENCE_TABLE` only — the same import `mva.viz.catalog_semantics`
already makes, for the same reason: a renamed table must be one edit. The rows are read by
SQL in the viz layer like every other viz query.

**7. The probe budget appears on two pages on purpose.** `pages/probes/ProbeLedger.tsx`
is the operational view (spend one, watch the job). `pages/science/ProbeBudget.tsx` is the
research view: what did the spend buy in belief. Same hooks, so react-query serves both
from one cache entry, and neither page was modified for the other.

**8. The confidence caveat is a constant, not prose typed twice.** `docs/method.md`
requires "a transparent heuristic for triage, not a calibrated posterior" wherever a
confidence number is quoted, so `CONFIDENCE_CAVEAT` is exported from
`pages/science/register.tsx` and rendered inline beside every number, including inside the
revision history.

### Both browser states were checked

| State | How | Result |
|---|---|---|
| **populated** | fixtures (`app/src/fixtures/science.ts`, invented) | board groups by status, 2 claims × 2 revisions, history expander, evidence table with all three directions and a null lineage |
| **live empty** | `VITE_API_URL` pointed at 8945 | both designed empty states, footer reading `table not created yet — written on first record, never by a page load`, probe budget 18/18, no console errors |

The fixture is labelled `INVENTED research register` in the registry and `FIXTURE` in every
author field, so a reader can never mistake a placeholder claim for a recorded one.

## Conclusions

1. **An empty record needs more design than a full one.** Three distinct empties exist
   here — table absent, table empty, filter matches nothing — and collapsing them into one
   "no rows" box would have thrown away the only information the page currently has.
2. **Ask the catalogue, do not catch the exception.** The existence check costs the same
   round trip the failure would have, and it distinguishes "not created yet" from "your
   SQL is wrong".
3. **Read-only means read-only.** The cheapest way to make this endpoint simple was to
   call `ensure_table`, and it was the one thing that would have made the answer false.
4. **The API serves the history; the client picks the head.** That is what keeps
   append-only visible rather than merely true.

## Tests

`tests/test_viz_science.py`, **18 tests**, hermetic: `science.attached` is replaced by a
fake connection answering on a SQL fragment, in the style of `tests/test_viz_catalog.py`.
Covered: the shared envelope, `table_exists` both ways, no `CREATE` on a miss, nothing read
after a miss, the existence-check parameters, every revision served, the `ORDER BY`, the
nulls an opening revision carries, a refuted claim kept as a revision rather than a
deletion, all three evidence directions with a null `lineage_ref`, named columns matching
both `ensure_table` DDLs, and no genomic position in either payload.

`uv run pytest -q` → **879 passed**, 11 failures, all pre-existing in
`tests/test_reads_api.py` and unrelated to this change.
`cd app && npm run typecheck && npm run build` → clean; `Science` is its own 21.8 kB chunk.
