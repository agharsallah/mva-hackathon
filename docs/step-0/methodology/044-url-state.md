# 044 — Every exhibit selection moves into the URL

**A step-0 platform entry, so it carries no hypothesis.** It records a mechanical conversion
of the viz app's exhibit controls from component state to query-string state, and what was
found and fixed while verifying it.

## Question

The app's figures are selectable: which contig, which metric, 2D or 3D, which gene. Those
selections lived in `useState`, so they died on reload and could not be linked to. That makes
a figure **unciteable** — the report cannot say "see this view", only "open Genome, pick chr7,
switch the metric to mean QUAL, click 3D", which no reader will do and no reviewer can check.

Can every exhibit selection be moved into the URL so that one link is one complete figure
reference, without the URL becoming noise and without flooding browser history?

## Inputs

| Input | Version / shape |
|---|---|
| App | `app/` at commit `40eb901` + this wave's exhibits |
| Router | `react-router-dom` 7.18.3, `BrowserRouter` (not a data router), `useSearchParams` |
| Toolchain | vite 8.2.2, typescript 7.0.2 — **no new npm dependency** |
| Verification server | `vite --port 5196` with `VITE_API_URL=http://127.0.0.1:8999` (dead port ⇒ fixture mode) |

## What was built

**One new module, `app/src/lib/urlstate.ts`** (168 lines). A string-typed core plus four
adapters, all obeying one contract:

| Rule | Why |
|---|---|
| The default value writes **no parameter** | A fresh page has a clean URL; a shared URL names only what was deliberately changed |
| Updates use `replace`, never `push` | Five toggle clicks leave one history entry, so Back still means "the previous page" |
| Every write **merges** into the parameters already present | Two exhibits on one page never overwrite each other |
| An unknown or invalid value reads as the default, silently | A hand-edited or stale link degrades to the default view, never to a broken one |

| Export | Use |
|---|---|
| `useUrlState(key, fallback, allowed?)` | the string core |
| `useUrlEnum(key, fallback, allowed)` | a `Select` over a string union |
| `useUrlNumber(key, fallback, allowed?)` | a numeric `Select` |
| `useUrlToggle(key, fallback?)` | a `Toggle`, written `1` / `0` |
| `useUrlText(key, fallback?, delayMs = 300)` | a filter box: instant locally, debounced into the URL |
| `known(value, options, fallback)` | fall back once an *async* vocabulary (the panel gene list) has arrived |

## Converted controls and their parameter keys

This table doubles as the shareable-URL reference. Keys are namespaced per exhibit so two
exhibits on one page coexist; the namespace is dropped only for `gene`, which is deliberately
page-wide.

| Page | Exhibit | Control | Key | Default (absent from URL) |
|---|---|---|---|---|
| Genome | `DensityBins` | contig | `bins.chrom` | `all` |
| | | metric | `bins.metric` | `n` |
| | | 2D / 3D | `bins.3d` | off |
| Genome | `BafKaryogram` | contig | `baf.chrom` | `all` |
| | | metric | `baf.metric` | `vaf` |
| Reads | `Flowcell` | lane | `fc.lane` | `1` |
| | | read | `fc.read` | `1` |
| | | 2D / 3D | `fc.3d` | off |
| Reads | `CycleQuality` | 2D / 3D | `cq.3d` | off |
| Reads | `StoreShape` | size by | `store.metric` | `gib` |
| Panel | `LocusExplorer` | gene | `gene` | `BUB1B` |
| Panel | `PairMatrix` | gene | `gene` *(shared)* | `BUB1B` |
| | | rare + protein-altering only | `pairs.rare` | off |
| Compare | `RarityScatter` | gene | `gene` | `ALL` |
| Catalog | `TableCatalog` | filter text | `tables.q` | empty |
| Catalog | `TableExplainer` | filter text | `columns.q` | empty |

Worked example — one link, one figure:
`/genome?baf.metric=dp&bins.chrom=7&bins.metric=mean_qual&bins.3d=1`

### One deliberate unification

`LocusExplorer` and `PairMatrix` previously each held their own `gene` state and could
disagree about which gene was open. They now **share the `gene` parameter**: "which gene are
we looking at" is a property of the Panel page, not of one exhibit, so `?gene=TRIP13` moves
the whole page and links to a coherent view. `DomainLollipop` already inherited its gene from
`LocusExplorer` and needed no change. The rare-only filter stays per-exhibit (`pairs.rare`)
because it belongs to that grid alone. `RarityScatter` on the Compare page uses the same key
name with a different default (`ALL`); because a default writes nothing, the two pages never
inherit each other's selection.

## Commands run

```
$ cd app && npm run typecheck && npm run build     # clean; new chunk urlstate-*.js, 1.18 kB
$ uv run pytest -q                                 # 11 failed, 993 passed — the 11 are the
                                                   # pre-existing tests/test_reads_api.py set
$ VITE_API_URL=http://127.0.0.1:8999 npx vite --port 5196 --host 127.0.0.1
```

Headless Chrome against `127.0.0.1:5196`, fixture mode (the API port is dead on purpose).

## Observed output

| Check | Result |
|---|---|
| Two exhibits on one page coexist | Genome: four writes produced `?baf.metric=dp&bins.chrom=7&bins.metric=mean_qual&bins.3d=1` — nothing lost |
| Reload restores | after reload the four Genome controls read back `all, dp, 7, mean_qual`; Reads read back `reads, 3, 2` with both 3D toggles on; Catalog read back both filter boxes and the applied result (`showing 2 of 32`) |
| No history spam | five toggle clicks: `history.length` 3 → 3 |
| Invalid values fall back | `?bins.chrom=chr99&bins.metric=bogus&bins.3d=yes&baf.chrom=42&baf.metric=` rendered the full default view (5 plots, no error); `?gene=NOTAGENE&pairs.rare=maybe` fell back to `BUB1B` with the toggle off |
| Shared `gene` on Panel | selecting `TRIP13` in `LocusExplorer` moved `PairMatrix` to `TRIP13` — one parameter, one page |
| Text debounce | typing 7 characters produced **0** URL writes during typing and 1 after ~300 ms; `history.length` unchanged |
| Nav away and back | `/catalog?tables.q=…` → Genome → Catalog gives clean `/catalog` with empty boxes. **Correct and intended**: nav links carry no parameters, so state survives reload and sharing, not nav-away |
| Console | one error only — `ERR_CONNECTION_REFUSED` ×11, the deliberately dead API port. Zero app errors |

## One real bug the verification caught

The first implementation built each write from the `prev` `URLSearchParams` React Router hands
the updater. React Router v7's `setSearchParams` calls that updater **synchronously against
the parameters captured at the last render**, so two writes in the same tick both saw the same
stale snapshot and the second silently dropped the first. Observed directly: changing a metric
and clicking a toggle together produced `?baf.metric=dp&bins.chrom=7&bins.3d=1` — the metric
write was gone.

Fix: build each write from `window.location.search` instead. `navigate` updates
`window.location` synchronously in a `BrowserRouter`, so same-tick writes compose. `prev`
remains the fallback where there is no `window`. Re-ran the same four-writes-in-one-tick case:
all four parameters present.

## Conclusion

Every exhibit selection in the app is now addressable. A figure in the report is cited by
URL rather than by instructions, and the four contract rules hold under test: clean defaults,
no history spam, coexisting exhibits, silent fallback on junk.

Two limits, stated rather than hidden:

- **Nav links carry no parameters.** Clicking Genome in the header goes to the default Genome
  view, not to your last one. That is the intended trade (a nav link should mean the page, not
  a stale selection); state survives reload and sharing.
- **Junk parameters are left in the address bar** until a control is touched. Rewriting the URL
  on load would be a surprise history change for no gain — the *view* is already the default.
