# 043 — Sorting, filtering and pagination in the shared data table

**A step-0 platform entry, so it carries no hypothesis.** It records an upgrade to one shared
component, `app/src/components/DataTable.tsx`, and the evidence that it changed no call site.

## Question

Thirteen exhibits render through one table component. It dumped every row into a `maxHeight`
scroll box in the order the caller supplied — no sorting, no filtering, no paging. Can those
three be added **without touching a single consumer**, and without moving a pixel on the small
tables that are already the right shape?

The constraint is not stylistic. Four other agents were editing consumer pages concurrently, so
any change that forced a call-site edit would have collided.

## Inputs

| Input | Version / shape |
|---|---|
| Component | `app/src/components/DataTable.tsx`, 63 lines before, 288 after |
| Consumers | 12 files under `app/src/pages/` — none edited |
| Reused | `TextFilter` from `app/src/components/Controls.tsx` — imported, not modified |
| Toolchain | vite 8.2.2, typescript 7.0.2, react 18.3.1 — **no new npm dependency** |
| Fixture path | `VITE_API_URL` pointed at a dead port (`8999`) so every page renders fixtures |

## What was built

Three behaviours, all additive.

**Sort** — every header is a `<button>` inside its `<th>` unless the column sets
`sortable: false`. Tri-state per column: unsorted → ascending → descending → back to the order
the caller supplied. The indicator (`▲`/`▼`) renders **only while that column is sorted**, so a
table at rest is byte-identical to the old markup. `aria-sort` is set on the active `<th>`.

The sort key is resolved in three steps, first hit wins:

| Step | Source | Why |
|---|---|---|
| 1 | `column.sortValue(row)` | The escape hatch for a computed cell. New optional prop. |
| 2 | `row[column.key]` when the key names a field | Sorts the *value*, not the formatted string — so `rows` sorts `5012204` numerically, never `"5,012,204"` lexically. |
| 3 | text of the rendered cell | Last resort for a column whose key names no field (`produced` → `produced_at`). |

Comparison is type-aware: two numbers compare numerically, anything else with
`localeCompare(…, { numeric: true, sensitivity: 'base' })`. `null` and `undefined` sort **last in
both directions** — they are pulled out before the direction multiplier, so reversing never
floats missing data to the top. The sort is stable: rows are decorated with their input index and
ties fall back to it.

**Filter** — off by default (`filterable`). On, it renders the existing `TextFilter` above the
table and matches the needle case-insensitively against the concatenated *visible text* of every
cell in a row, flattened out of the rendered `ReactNode` tree. A `X of N match` count sits beside
the box.

**Pagination** — automatic above `pageSize` rows (default 100); `pageSize={0}` disables it. The
pager is one line, right-aligned: `‹ 1–100 of 484 ›`, real `<button>`s with `aria-label`s,
disabled at the ends. Page resets to 1 whenever the filter or the sort changes; the current page
is clamped rather than reset when the row count shrinks under it.

**Empty states** — the pre-existing `empty` prop is untouched for a genuinely empty `rows` array
(same dashed box, same markup, no wrapper). A filter that hides everything gets a *different*
message, `0 of N match`, with the filter box still rendered above it so the reader can clear it.

### Prop surface added

All optional; every existing call site compiles unchanged.

| On `Column<R>` | Meaning |
|---|---|
| `sortValue?: (row) => string \| number \| boolean \| null \| undefined` | Sort key for a computed cell |
| `sortable?: boolean` | `false` makes the header inert |

| On `DataTable` | Default | Meaning |
|---|---|---|
| `filterable?: boolean` | `false` | Render the free-text box |
| `filterLabel?: string` | `'filter'` | Label on that box |
| `filterPlaceholder?: string` | `'match any cell'` | Placeholder on that box |
| `pageSize?: number` | `100` | Rows per page; `0` never paginates |

## Commands run

```
$ cd app && npm run typecheck                       # tsc -b
$ cd app && npm run build                           # tsc -b && vite build
$ VITE_API_URL=http://127.0.0.1:8999 npx vite --port 5197 --host 127.0.0.1
```

Headless Chrome (devtools protocol) then drove `/catalog`, `/provenance`, `/compare` and a
throwaway harness page mounting 484 synthetic rows. The harness (`app/c2probe.html`,
`app/src/c2probe.tsx`) existed only for the run and was deleted before the commit — pagination
and filtering have no consumer yet, so there was nothing else to exercise them against.

Pixel-identity was checked by measurement, not by eye: the same script read
`getBoundingClientRect()` for every `<table>`, every `<th>` and the first `<td>` on a page,
before and after the change.

## Observed output

**`/provenance` — table geometry, before vs after: identical to the hundredth of a pixel.**

```
table 0   w 1388.00  h 180.50  rows 5   td h 29.50
          th widths 254.39 / 799.32 /  90.77 / 243.52   all h 32.50
table 1   w 1388.00  h 371.00  rows 7   td h 46.00
          th widths 226.30 / 117.92 / 298.52 / 90.16 / 390.38 / 119.34 / 145.37   all h 48.50
```

`/compare` likewise: the 2-row candidate table (`w 1354.00 h 92.00`, ten headers at `h 32.50`),
the 9-row funnel and the 8-row observed-expected table all matched their pre-change geometry
exactly. Below the pagination threshold and with `filterable` off, the component returns the same
single `<div>` it always did — no wrapper element is introduced.

**`/catalog` — sorting the 32-row fixture catalogue.**

```
rows column, natural   5,012,204 · 5,012,204 · 41,388,912 · 25 · 14
rows column, ▲          0 · 0 · 5 · 6 · 6            tail  5,012,204 · 5,012,204 · 41,388,912
rows column, ▼          41,388,912 · 5,012,204 · 5,012,204 · 5,012,204 · 31,968
third click             natural order restored exactly (deep-equal to the first read)
header text             "rows▲" → "rows▼" → "rows",  aria-sort ascending → descending → absent
table column, ▲         allele_balance_flags · bcftools_dp · bcftools_filter
produced at, ▲          2026-08-28 09:02:00 · 09:14:00 · 09:21:00   (step-3 text fallback)
```

The formatted cell reads `5,012,204`; sorting it numerically rather than lexically is step 2 of
the key resolution doing its job.

**Harness, 484 rows.**

```
pager, page 1         ‹ 1–100 of 484 ›     prev disabled
next ×1               first cell row-100
last page             ‹ 401–484 of 484 ›   84 rows rendered, next disabled
filter "BETA"         161 of 484 match  ·  pager ‹ 1–100 of 161 ›  ·  case-insensitive hit
on page 3, filter     ‹ 201–300 of 484 › → ‹ 1–100 of 161 ›        (reset to page 1)
on page 3, sort       ‹ 201–300 of 484 › → ‹ 1–100 of 484 ›        (reset to page 1)
filter "zzzz"         no <table>; one dashed box reading "0 of 484 match"
clear filter          100 rows, ‹ 1–100 of 484 › restored
n column ▲            2 · 5 · 8 · 11        ▼  999 · 996 · 993 · 990
n column ▼, last page trailing rows all "—"  (nulls last in the descending direction too)
sortable:false column no <button> in its <th>;  sortable column has one
pageSize={0}          484 rows, no pager
rows={[]}             renders the `empty` prop verbatim, unchanged
```

`npm run typecheck` and `npm run build` both clean. Console on `/catalog`, `/provenance` and
`/compare`: **zero React errors or warnings** — the only entries are the expected
`ERR_CONNECTION_REFUSED` from the deliberately dead API port, which is what forces the fixture
path.

## What was NOT verified

- **No consumer opts in yet.** `filterable` and a non-default `pageSize` have been exercised only
  against the synthetic harness. No shipped exhibit has more than ~100 rows, so automatic
  pagination is dormant in the app as it stands.
- The rendered-text sort fallback (step 3) sorts by *what the cell says*. On `/catalog`'s
  `produced at` column the placeholder chip sorts as the string `no lineage edge`, not as a
  missing value. That is correct-as-specified but is not what a reader means by "empty last"; the
  fix is one `sortValue` on that column, in a file this work was not allowed to touch.
- Pixel-identity was verified on `/provenance` and `/compare` only. The other eight pages were
  not re-measured; they share the same code path and the same rest-state markup.
- Sorting was driven programmatically (`button.click()`), not with a real pointer, and keyboard
  traversal of the header buttons and the pager was not exercised by a key-event test — only the
  markup that makes it possible (real `<button>`s, `aria-label`, `aria-sort`) was checked.

## Conclusions

- A shared component can gain three interactive behaviours with **zero call-site churn** if every
  addition is an optional prop with the old behaviour as its default. The test that this held is
  not "it compiles" — it is the geometry table above, which says the resting render is unchanged.
- The one design decision that mattered: **render the sort indicator only when sorting is
  active.** A permanently-present ghost caret, even at `opacity-0`, would have widened every
  header cell in the app and broken the pixel-identity claim. Discoverability comes from the
  hover colour change and the cursor instead.
- Sorting *formatted* cells is the trap this component would otherwise have fallen into. Resolving
  the key from the row field before the rendered text — with `sortValue` as the explicit override
  — means a thousands-separated number sorts as a number by default, and a caller has to opt in to
  be wrong.
- Nulls have to be lifted out of the comparator, not folded into it. Pushing them last "by making
  them large" inverts the moment the direction flips, and a table that floats its missing data to
  the top on a descending sort reads as if the missing data were the extreme values.
