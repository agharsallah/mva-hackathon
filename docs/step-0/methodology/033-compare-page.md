# 033 — The Compare page and the constraint scorecard

**A step-0 platform entry, so it carries no hypothesis.** It records what was added to `app/`
after [029](029-viz-app.md), and what could not be verified because the endpoints behind it do
not exist yet.

## Question

The app reads the case in isolation. Nothing in it answers the comparative question a
rare-disease case turns on: **is this variant unusual in healthy people, and is this callset
unusual as a piece of engineering?** Can a page be built against three not-yet-implemented
endpoints, fixture-first, that answers both — and that renders the two nullable fields in
those contracts (`gnomad_af`, the constraint columns) as *unknown* rather than as zero?

## Inputs

| Input | Version / shape |
|---|---|
| Endpoint contracts | `/api/panel/constraint`, `/api/panel/annotations?gene=`, `/api/callset/observed-expected` — supplied verbatim, not yet implemented |
| Existing app | `app/` at commit `40eb901`, conventions from [029](029-viz-app.md) |
| Live viz API | `mva-viz-api` on `127.0.0.1:8900` — **up**, but `404` on all three new routes |
| Node toolchain | vite 8.2.2, typescript 7.0.2 (unchanged; **no new npm dependency added**) |

## What was built

**New page `Compare` (`/compare`)** — three exhibits:

| Exhibit | Figure | The rule it encodes |
|---|---|---|
| `RarityScatter` | log gnomAD AF × VAF, coloured by VEP impact, white ring = ClinVar pathogenic | Novel variants (`gnomad_af: null`) get a **dedicated lane** a decade left of the rarest measured AF, behind a dashed rule and labelled — never dropped, never plotted as 0. `1/2` records with `vaf: null` get a second lane below the axis rather than silently vanishing. |
| `CandidateTable` | `is_protein_altering && is_rare_recessive`, sorted impact then AF, nulls first | Two hits in one gene fires a callout naming the compound-het *shape* and stating that **phase is unproven** and unprovable from a single sample. A short list is the intended outcome, so the small state is designed, not an empty state. |
| `ObservedExpected` | horizontal dumbbells: expected band as a bar, observed as a verdict-coloured marker | The metrics do not share a unit, so x is each metric **relative to its own band midpoint** (1.0 = dead centre); real values and units live in the hover and the table. Point estimates (`low == high`) draw as a tick, not a zero-width bar. |

**Extended page `Panel`** — `ConstraintScorecard`: LOEUF bars (left axis) against ClinVar P/LP
counts (right axis), with the conventional LOEUF 0.35 line. Its callout states the
counter-intuitive fact the exhibit exists to show: MVA is recessive, single-copy carriers are
healthy, so the two established MVA genes score as *unconstrained* and a constraint-sorted
ranking would put them last. **Constraint is shown as context and must not be used to rank
recessive candidates.** Null constraint renders as the word `unknown`, plus an in-place chart
label so an absent bar cannot be read as a bar of height zero.

**Plumbing** — 3 interfaces, 3 one-line hooks, 3 fixture builders registered by exact path
(`/api/panel/annotations` handles an *optional* `gene` param, unlike `/api/panel/locus` where it
is required). Fixture data deliberately exercises every edge in the contracts: novel AF nulls, a
ClinVar `Pathogenic` string, both booleans true, a null constraint row, a null VAF, and all four
`verdict` values.

**One refactor forced by the repo's 400-line rule:** transcribing the three contracts pushed
`app/src/api/types.ts` to 398 lines. It was split into `app/src/api/types/` — one module per API
domain (`envelope`, `overview`, `genome`, `callset`, `panel`, `reads`, `provenance`, `jobs`)
behind a barrel `index.ts`. Every importer still writes `from '../api/types'`; no call site
changed.

## Commands run

```
$ curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8900/health                      # 200
$ curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8900/api/panel/constraint         # 404
$ curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8900/api/panel/annotations        # 404
$ curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8900/api/callset/observed-expected # 404

$ cd app && npm run typecheck        # tsc -b
$ npm run build                      # tsc -b && vite build
$ find src -name '*.ts*' | xargs wc -l | sort -rn | head

# fixture path forced by pointing the app at a dead port, then dumping the post-JS DOM
$ VITE_API_URL=http://127.0.0.1:9 npx vite --port 5199 --host 127.0.0.1
$ "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu \
    --user-data-dir=<tmp> --virtual-time-budget=16000 --dump-dom http://127.0.0.1:5199/<route>
```

## Observed output

`npm run typecheck` and `npm run build`: both clean, no warnings.

```
✓ 129 modules transformed.
dist/assets/Panel-BALT_WUs.js      16.94 kB │ gzip: 5.55 kB   (was 11.24 kB)
dist/assets/Compare-BjHHJqLa.js    19.25 kB │ gzip: 6.74 kB   (new)
dist/assets/plotly.min-*.js      4,066.60 kB │ gzip: 1,244.94 kB
✓ built in 1.19s
```

Plotly stayed in its own chunk; the new page is a 19 kB chunk like every other page. Largest
source file after the types split is `fixtures/panel.ts` at 273 lines — the 400-line rule holds.

Post-JavaScript DOM, fixture path, both routes:

| Route | Plotly figures | Legends | `fixture` chips | Error cards |
|---|---|---|---|---|
| `/compare` | 3 | 3 | 3 | 0 |
| `/panel` | 3 | 3 | 3 | 0 |

Every contract edge rendered as intended, read straight out of the DOM:

```
novel lane annotation ...... "novel · absent from gnomAD (77)"
VAF n/a lane ............... "VAF n/a — 1/2 multiallelic (12)"
candidate funnel ........... 863 annotated records in → 2 survive both filters, in 1 gene
candidate table ............ 2 rows, both BUB1B: a stop_gained (ClinVar Pathogenic)
                             and a novel missense rendered "novel", not 0
compound-het callout ....... fired, and states phase is unproven
observed-expected .......... all four verdicts present (3 within · 2 above · 2 below · 1 unknown)
constraint scorecard ....... 6 "unknown" renderings for the null-constraint gene; no zero bar
gene filter options ........ ALL + BUB1B CENPE CEP192 CEP57 DICER1 SMC5 TP53 TRIP13
                             — derived from the rows, not hardcoded
```

## What was NOT verified

**No exhibit on this page has ever been rendered from a live measurement.** All three endpoints
answered `404` throughout. Two consequences worth stating plainly:

1. Every number visible on `/compare` and in the constraint scorecard is **fixture shape**, not a
   result. The constraint values, the ClinVar counts and the expected QC bands in particular are
   placeholders with no measurement behind them; only the `observed` column of
   `observed-expected` reuses aggregates this repo actually measured. The app badges all of it
   `fixture`.
2. The 404 is *not* a state the client falls back on — only `501` and a network-level failure
   are. So while the viz API is up and 404-ing, these exhibits show **error cards**, not
   fixtures. The fixture path had to be forced with a dead `VITE_API_URL` to be tested. When the
   endpoints land, nothing needs changing; until then a live demo of `/compare` needs the API
   stopped or repointed.

### Read against the backend source instead

The routes exist in `src/mva/viz/routes_warehouse.py` and their queries in
`src/mva/viz/queries.py` — the running server was simply an older process. Reading the SQL
projections rather than a live response found no breaking mismatch and three things worth
recording:

1. `panel_candidates` selects exactly the 18 columns of `PanelAnnotationRow`, in order. `vaf` is
   `NULL` for a `1/2` site by the same convention the locus endpoint uses, as the contract said.
2. `qc_observed_expected` emits **two columns beyond the contract** — `applies_to` (which
   population the norm is stated for) and `observed_from` (which table the observation was
   re-parsed from). Extra fields are harmless to a structurally-typed client and are currently
   ignored; both look worth surfacing in the hover once the endpoint is live.
3. That same query ends `WHERE o.obs IS NOT NULL`, so its `'unknown'` verdict branch is
   **unreachable in practice** — a metric with no observation is dropped rather than emitted as
   unknown. The UI renders `unknown` correctly regardless (grey, hollow marker), and the fixture
   exercises it, but a live run should be expected to show only three of the four verdicts.

This is still "no mismatch observed", not "the contract is confirmed". [029](029-viz-app.md)
recorded that two of its three contract corrections were invisible in the contract text and only
surfaced against the running service. Expect the same here.

## Conclusions

- Fixture-first against a written contract works well enough to build and visually verify a full
  page with the backend absent — the same finding as [029](029-viz-app.md), now reconfirmed for
  three endpoints — and it remains **insufficient for correctness**. Re-verify against the live
  service.
- The design work that mattered was not the charts, it was deciding what `null` looks like. Both
  nullable fields in these contracts have a wrong rendering that is easy to reach by accident
  (`0`, "unconstrained") and that would have inverted the reading. Encoding "novel" as a labelled
  lane and "unknown" as a word makes the wrong reading unavailable rather than merely discouraged.
- The constraint exhibit is the clearest case in the app of a metric that is *actively misleading*
  if applied without its precondition. Showing it with the inversion spelled out is worth more
  than omitting it, because a reader who meets LOEUF elsewhere will otherwise apply it to a
  recessive candidate list.
- `Exhibit`'s required `legend` prop again cost nothing and held for all four new exhibits.
