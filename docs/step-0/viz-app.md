# The visualization app

**Standing:** built and verified against the live `mva-viz-api` on 2026-08-31. Page map and
env vars re-checked against `app/` on 2026-08-31 after the Catalog page landed. Measured dataset numbers are owned by
[`ideation/data-findings.md`](../../ideation/data-findings.md); this page never restates them.

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
cd app && npm install && npm run dev    # http://127.0.0.1:5173
```

| Env var | Default | Meaning |
|---|---|---|
| `VITE_API_URL` | `http://127.0.0.1:8900` | base URL of the viz API |
| `VITE_USE_FIXTURES` | unset (= on) | `false` turns off the fixture fallback |

## Page map

| Page | The question | Exhibits |
|---|---|---|
| Overview | What is this case, in numbers? | stat tiles; delivery-integrity board (green per verified sha256); genotype donut with the `1/2` compound-het slice pulled out |
| Genome | Is any chromosome present in the wrong number of copies? | allele-balance dot plot on the 0.5 line (**headline**); depth-vs-VAF with crosshair; karyotype to real length; 1 Mb density heat strips + 3D surface |
| Callset | Is the delivered callset healthy, and what did it suppress? | filtering funnel; depth histogram; substitution spectrum; indel length spectrum |
| Panel | Which MVA candidate genes have evidence, and how much is hidden? | gene scorecard (PASS/suppressed + PASS % axis); **constraint scorecard** (LOEUF bars against ClinVar P/LP counts, with the recessive-inversion caveat); locus explorer with QUAL and VAF tracks |
| Compare | How does this patient differ from the normal population? | rarity scatter (gnomAD AF on a log axis against VAF, with a dedicated **novel lane** for variants absent from gnomAD); candidate table (rare **and** protein-altering — a deliberately short list); observed-vs-expected QC dumbbells against published healthy-genome bands |
| Reads | What does the raw measurement look like? | lane yield; store treemap; flowcell heatmap + 3D by tile; per-cycle quality + 3D surface; the 4-level phred binning |
| Probes | Ask the raw reads a new question | k-mer console (submit → long-poll → result bars vs the expectation line); jobs monitor with cancel; oracle ledger |
| Provenance | Where did every number come from? | lineage graph (SVG, hover an edge for its transform); derivations with their questions; flat lineage table |
| Catalog | What data do we hold, what is in it, when did it arrive, where does it live? | delivery inventory (one card per raw object: description, size, sha256 short-form + who verified it, arrival time); table catalogue (every warehouse/results table with its lineage edge, free-text filter); read-store card |

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

**Patient-data rule.** No genomic coordinate is committed. The locus and panel-annotation fixtures
use a synthetic counter (1000, 2000, 3000 …) and say so; real positions exist only in the browser at
runtime, served live. GRCh38 chromosome lengths are the coordinate *system*, not patient data, and
are committed.

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
  is now `fixtures/catalog-tables.ts` at 329 — the catalogue fixture was split from
  `fixtures/catalog-objects.ts` for the same reason.
- **A gap is rendered, never blanked.** A derived table with no lineage edge and a delivered
  object with no ingest-ledger row both draw a yellow chip saying which record is missing, in
  place of an empty cell. Same rule as "null is not zero" above, applied to provenance.
- Colours come from `lib/palette.ts` only: green = good, red = broken/suppressed, yellow = a decision,
  blue = neutral machinery, purple = the raw input.
