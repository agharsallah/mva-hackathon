# The visualization app

**Standing:** built and verified against the live `mva-viz-api` on 2026-08-31. Page map and
env vars re-checked against `app/` on 2026-08-31 after the Catalog page's table explainer
landed ([036](methodology/036-table-semantics-registry.md)); that exhibit is the first one
verified against the **live** API rather than fixtures — all three catalogue endpoints
answered 200. Measured dataset numbers are owned by
[`ideation/data-findings.md`](../../ideation/data-findings.md); this page never restates them.
The design-system section and the **Style** page row were added 2026-09-02 and verified against
the running app on that date ([055](methodology/055-design-tokens.md)).

> The **Compare** page and the Panel page's constraint scorecard were added on 2026-08-31 and
> are verified **against fixtures only** — their three endpoints
> (`/api/panel/constraint`, `/api/panel/annotations`, `/api/callset/observed-expected`) still
> answered `404` on the live API at that date. See
> [033](methodology/033-compare-page.md).
>
> The **Catalog** page was added on 2026-08-31, likewise verified **against fixtures only** —
> `/api/catalog/objects` and `/api/catalog/tables` answered `404` on the live API at that date.
> See [035](methodology/035-catalog-page.md).

A browser front end for understanding one whole-genome case. It is the reading surface over the
platform: [`mva-viz-api`](methodology/029-viz-app.md) serves the derived tables, `app/` renders them
with the words that make them readable.

Its job is **understanding**, not decoration. Every page opens with an explainer written for a
software engineer with no genomics background, in the repo's `technical term (plain-English meaning)`
pattern; every chart carries a `Legend` line decoding its own colours.

Single sample `PROBAND01`. **No trio** — the app never renders a parent column.

## Stack

- Vite 8 · React 18 · TypeScript strict
- `@tanstack/react-query` v5 (retries off, 5 min staleTime) · `react-router-dom` v7
- `plotly.js-dist-min`, dynamically imported into its own chunk — same chart engine as the repo's
  existing figures, so the visual language matches
- Tailwind CSS v4 via `@tailwindcss/vite`

## Run

```bash
uv run mva-viz-api            # from the repo root, serves 127.0.0.1:8900
cd app && pnpm install && pnpm run dev    # http://127.0.0.1:5173
```

| Env var | Default | Meaning |
|---|---|---|
| `VITE_API_URL` | `http://127.0.0.1:8900` | base URL of the viz API |
| `VITE_USE_FIXTURES` | unset (= on) | `false` turns off the fixture fallback |

## Page map

| Page | The question | Exhibits |
|---|---|---|
| Overview | What is this case, in numbers? | stat tiles, each carrying a **norm chip** where its metric has a published band — green within / red above-below, linking to Compare, and absent entirely on the five tiles with no published norm ([`methodology/047`](methodology/047-observed-expected-extension.md)); delivery-integrity board (green per verified sha256); genotype donut with the `1/2` compound-het slice pulled out |
| Genome | Is any chromosome present in the wrong number of copies? | allele-balance dot plot on the 0.5 line (**headline**); depth-vs-VAF with crosshair; karyotype to real length; 1 Mb density heat strips + 3D surface |
| Callset | Is the delivered callset healthy, and what did it suppress? | filtering funnel; depth histogram; substitution spectrum; indel length spectrum; **zygosity split** (the `bcftools` AF section, which on one sample is het-vs-hom and *not* population frequency — the exhibit says so, and puts each half's Ts/Tv against the random-error line); **header fields** (all 31 FILTER/INFO/FORMAT declarations, verbatim — the checkable evidence that the delivery ships no annotation worth ranking on) |
| Panel | Which MVA candidate genes have evidence, and how much is hidden? | gene scorecard (PASS/suppressed + PASS % axis); **constraint scorecard** (LOEUF bars against ClinVar P/LP counts, with the recessive-inversion caveat); **gene-vs-background dot-and-band** (each gene's density and PASS share as a z-score against the 1 Mb windows of its own chromosome or of the whole callset, neutral band at |z| < 2, yellow past 2 σ and red past 3 σ — TRIP13 is the only gene outside the band on PASS share at −4.02 σ, which the legend states is a *callability* reading and not a pathogenicity one, [`methodology/048`](methodology/048-gene-background.md)); **suppressed-call mining view** (two stacked panels — every record as a share of its gene, then the suppressed ones alone as counts — green = PASS against one red or yellow per FILTER reason, with a per-gene record table carrying QUAL, the verbatim reason, GT, depths, VAF, consequence and gnomAD AF; TRIP13 is 6 suppressed of 12, and all six are common polymorphisms with thin support in hard-to-map sequence, so the panel's suppressed set holds nothing rare *and* protein-altering, [`methodology/049`](methodology/049-suppressed-calls.md)); locus explorer with QUAL, VAF and **gene-structure** tracks (exons/introns/TSS from Ensembl); **protein-domain lollipop** placing each protein-altering allele in amino-acid space; **compound-het pair matrix** (the het × het grid, green = resolved trans, red = resolved cis, yellow = `1/2` auto-trans, blue = unknown shaded by pair rarity — 99.7 % of BUB1B's cells are unknown and the exhibit says so) |
| Compare | How does this patient differ from the normal population? | rarity scatter (gnomAD AF on a log axis against VAF, with a dedicated **novel lane** for variants absent from gnomAD); candidate table (rare **and** protein-altering — a deliberately short list); **candidate waterfall** (nine filter stages on a log-x axis, blue = genome scope → purple = panel scope with the scope change drawn as a dashed rule and annotated: annotation exists only inside the 8-gene panel, so there is no genome-wide ranking to show); **pair comparator** (any two heterozygous alleles of one panel gene side by side over QUAL, VAF, DP, gnomAD AF/grpmax, consequence, ClinVar, GT and the raw phase fields, with the pair verdict — trans / cis / auto-trans / unknown — looked up in the endpoint's own resolved-pair list, and one click that stages the pair as a validated submission row on the Probes page, [`methodology/050`](methodology/050-pair-comparator.md)); **ClinVar presence** (the reference join run inward — one track per gene whose width is that gene's pathogenic/likely-pathogenic record count, segmented green = present + PASS · yellow = present but suppressed · blue = ClinVar states no alternate allele · grey = comparable and absent, with a floor on every non-zero segment so one hit among a thousand absences stays visible, plus a filterable table of the present sites with their gold-star review tier, and the exact-match lower-bound caveat stated in the exhibit itself, [`methodology/051`](methodology/051-clinvar-presence.md)); observed-vs-expected QC dumbbells against published healthy-genome bands |
| Reads | What does the raw measurement look like? | lane yield; store treemap; **delivered yield** (reads estimated from the gzip bytes against reads counted in the parquet store — the estimate runs +0.32 % to +1.10 % high on every lane); flowcell heatmap + 3D by tile; per-cycle quality + 3D surface; the 4-level phred binning |
| Probes | Ask the raw reads a new question | k-mer console (submit → long-poll → result bars vs the expectation line); jobs monitor with cancel; submission builder (candidates → validated Track 1 CSV, [`methodology/046`](methodology/046-probe-builder.md)); oracle ledger |
| Science | What do we believe, how strongly, and on what basis? | method loop diagram (claim → predict → test → verdict → revise); hypothesis board (one card per claim, latest revision, expandable revision history); evidence ledger (direction-coloured, filterable by hypothesis id); oracle budget read as research narrative. **Empty today by design** — the register tables do not exist until the first claim, and the page renders that as a designed state |
| Provenance | Where did every number come from? | lineage graph (SVG, hover an edge for its transform); derivations with their questions; flat lineage table |
| Catalog | What data do we hold, what is in it, when did it arrive, where does it live? | delivery inventory (one card per raw object: description, size, sha256 short-form + who verified it, arrival time); table catalogue (every warehouse/results table with its lineage edge, free-text filter); **table explainer** (one expandable card per table: why it exists, the verb that writes it, and every column's type and meaning); read-store card |
| Style | What is the design system, and is it still one system? | the token pipeline (source → generator → two artifacts → four gates); the generated ramps (7 families × 11 shades, each swatch labelled with its hex); the six tones with every live recipe; every Plotly colourscale as its gradient with each stop named `family-shade`; every shared primitive rendered with throwaway data. Nothing hand-listed — the grids iterate the palette's own exports ([`055`](methodology/055-design-tokens.md)) |
| Search | What is at *this* locus — one I chose, not one the server pre-selected? | one box taking a gene symbol, a region in either `chr` spelling, or an rsID, with one-click examples; **resolution line** naming the window *and the resolver that placed it* (query string / candidate panel / the callset's own rsID column / Ensembl) plus its caveat; **density strip** (PASS stacked under suppressed, per adaptive bin so the strip stays ~120 bars at any span); the full record table. The query lives in the URL, so a result is a shareable link. Four states are drawn distinctly: unparseable-or-too-wide, unknown name, Ensembl down, and **resolved-with-zero-rows** — for an rsID placed by dbSNP that means *the site was never called*, which is a finding, not a failure. Verified **live** against the hosted database and Ensembl, [`methodology/042`](methodology/042-universal-search.md) |

Exactly three views are 3D, each with a real third axis: density bins (chromosome × position ×
count), flowcell (x × y × tile), cycle quality (cycle × partition × mean Q). 3D is never used for a
two-dimensional relationship.

## Fixture behaviour

`app/src/fixtures/` holds one module per endpoint so the app is fully demoable with no API running.

- Served **only** when the API is unreachable at the network level and `VITE_USE_FIXTURES !== 'false'`.
- A `404`, `422` or `503` is the live API answering correctly and reaches the user as an error card —
  never masked by a fixture.
- When a fixture is used, a `fixture data` badge appears in the header and a `fixture` chip on the
  affected exhibit, so a placeholder can never be mistaken for a measurement.
- Each module states which of its numbers are measured and which fill a shape.

**Patient-data rule.** No genomic coordinate is committed. The locus, panel-annotation and search
fixtures use a synthetic counter (1000, 2000, 3000 … / a 1,000,000-based ladder) and say so; real
positions exist only in the browser at runtime, served live. GRCh38 chromosome lengths are the
coordinate *system*, not patient data, and are committed.

**A fixture may answer nothing.** `fixtures/search.ts` is the one module that can decline: it
mirrors the server's query grammar but knows only the example queries, and for anything else it
returns no envelope at all, so the client re-raises the real error. An offline search box that
invented a resolution for every string typed into it would be the worst possible fixture.

**Null is not zero.** Two nullable fields carry meaning the UI must not flatten, and both are
enforced in the rendering rather than left to the reader:

- `gnomad_af` null = **absent from gnomAD** (novel), which is rarer than any measured frequency.
  It gets its own plotted lane and sorts ahead of every number; it is never drawn or written as `0`.
- `loeuf` / `pli` / `mis_z` / `oe_lof` null = **no row in the constraint source** (it is
  autosome-only). Rendered as the word `unknown`, never as a zero bar and never as
  "unconstrained".

## Design rules the code enforces

- `Exhibit` makes `legend` a **required** prop — the "every figure carries a legend" rule checked by
  the type checker, not by review.
- One file per exhibit; no source file over 400 lines. `api/types.ts` reached 398 when the three
  new endpoints were transcribed and was split into `api/types/` — one module per API domain
  behind a barrel `index.ts`, so every importer still writes `from '../api/types'`. Largest file
  is now `fixtures/catalog-tables.ts` at 337 — the catalogue fixture was split from
  `fixtures/catalog-objects.ts` for the same reason, and the `created_by` / `why` / column
  meanings it needed went into `fixtures/catalog-semantics.ts` rather than growing it
  further. On the server the same limit split the column registry into
  `catalog_columns_ingest.py` and `catalog_columns_results.py`, one per managed schema.
- **The catalogue explains itself, and the build enforces it.** `TableExplainer` enumerates
  tables and columns from `/api/catalog/tables` and `/api/catalog/columns`, both of which
  read `information_schema` live — so a table added to the database appears in the UI with
  no front-end edit. What it appears *with* is the server's business: a hermetic test
  (`tests/test_catalog_semantics.py`) walks every table name declared anywhere in the
  Python and fails until it has a `created_by` (which command writes it, and whether that
  replaces, rebuilds or appends) and a `why`. Adding a table without describing it breaks
  `pytest`, and the failure names the entry to add and the file to add it to.
- **A gap is rendered, never blanked.** A derived table with no lineage edge and a delivered
  object with no ingest-ledger row both draw a yellow chip saying which record is missing, in
  place of an empty cell. Same rule as "null is not zero" above, applied to provenance.
- `DataTable` sorts (tri-state headers, type-aware, nulls last), filters (`filterable`) and paginates
  (over `pageSize`, default 100) — all optional, defaults keep every existing call site and its pixels
  unchanged ([043](methodology/043-datatable-upgrade.md)).
- **A pair leaves one page as a URL, not as shared state.** The Compare page's pair comparator
  hands a candidate pair to the Probes builder through `/probes?pair=chrom:pos:ref:alt+chrom:pos:ref:alt`,
  written by `pages/compare/comparator.ts` and read by `probePayload.ingestPairParam` — which parses it
  with `parseLines`, the grammar the builder's free-entry box already owns, so there is exactly one
  parser. The builder stages the row once on mount and deletes the parameter. Both hand-off buttons
  disable when the payload came from a fixture, because staging synthetic positions into a submission
  file is the one thing worse than typing them ([050](methodology/050-pair-comparator.md)).
- **Every exhibit selection lives in the URL, not in `useState`** — contig, metric, 2D/3D, gene,
  filter text — via `lib/urlstate.ts`. A default writes no parameter, updates `replace` rather than
  push, exhibit keys are namespaced (`bins.chrom` vs `baf.chrom`), and an invalid value falls back
  silently. So one link is one complete figure reference for the report; the full key table is in
  [044](methodology/044-url-state.md).
- **Colour is generated, and lint enforces it.** One script (`app/tools/gen-theme.mjs`) converts the
  installed Tailwind theme once and writes both halves the app needs: hex ramps for Plotly, SVG and
  inline style, and the matching `--color-*` custom properties for every Tailwind class. Seven
  semantic families carry the legend — green = good, red = broken/suppressed, yellow = a decision,
  blue = neutral machinery, purple = the raw input, grey (`chrome`) = furniture, orange
  (`severity`) = the one extra severity step in a chart ramp. Components take one of six `Tone`s
  and never a hue; a raw hex or a bare `emerald-400` is an eslint error, and `pnpm theme:check`
  fails if the two halves stop agreeing. Owned by
  [colour is generated](notes/colour-is-generated.md), measured in
  [`055`](methodology/055-design-tokens.md).
- **The design system renders itself** at `/style-guide`: every generated ramp, every tone with its
  live recipes, every chart colourscale as the gradient it paints, and every shared primitive. It is
  built from the same exports the app uses, so a new tone or a changed number appears with no edit —
  which makes it the screenshot to diff after a styling change.
