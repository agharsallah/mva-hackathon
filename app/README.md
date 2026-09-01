# `app/` — MVA Case Explorer

A data-understanding and visualization web app for one whole-genome case (Mosaic Variegated
Aneuploidy, single sample `PROBAND01`). It is a **reading tool**, not a dashboard: every page
opens with an explainer that names its domain concepts in the repo's `technical term (plain-English
meaning)` pattern, and every chart carries a `Legend` line decoding its own colours.

There is **no trio** in this dataset — one sample only. The app never renders a parent column.

**Verified:** 2026-09-01 — `npm run check` green (typecheck, lint, format, 59 tests).

## Quickstart

```bash
cd app
npm install
npm run dev      # http://127.0.0.1:5173
```

The app runs with **no backend**: when the viz API is unreachable it serves committed fixture
data and says so in the header. To see live data, start the API from the repo root with
`uv run mva-viz-api`.

| Script                            | Does                                                                            |
| --------------------------------- | ------------------------------------------------------------------------------- |
| `npm run dev`                     | Vite dev server, port 5173, strict (a busy port is an error, not a silent 5174) |
| `npm run build`                   | `tsc -b && vite build` — must pass clean                                        |
| `npm run typecheck`               | `tsc -b` alone                                                                  |
| `npm run lint` / `lint:fix`       | ESLint 9 flat config                                                            |
| `npm run format` / `format:check` | Prettier                                                                        |
| `npm run test` / `test:watch`     | Vitest (jsdom + testing-library)                                                |
| `npm run check`                   | all four gates, in order — run this before committing                           |

### Environment

| Variable            | Default                 | Meaning                                                                                |
| ------------------- | ----------------------- | -------------------------------------------------------------------------------------- |
| `VITE_API_URL`      | `http://127.0.0.1:8900` | base URL of `mva-viz-api`                                                              |
| `VITE_USE_FIXTURES` | unset (= on)            | `false` disables the fixture fallback, so an unreachable API surfaces as an error card |

The Probes page additionally needs the reads API behind the viz API; when that upstream is down
the viz API answers `503` and the page shows the start command instead of an error.

## Stack

| Concern            | Choice                                                       |
| ------------------ | ------------------------------------------------------------ |
| build / dev server | Vite 8                                                       |
| UI                 | React 18 + TypeScript 7 (strict)                             |
| data fetching      | `@tanstack/react-query` v5 — retries off, 5 min `staleTime`  |
| routing            | `react-router-dom` v7                                        |
| charts (2D and 3D) | `plotly.js-dist-min`, lazily `import()`ed into its own chunk |
| styling            | Tailwind CSS v4 via `@tailwindcss/vite`                      |
| tests              | Vitest + `@testing-library/react` + jsdom                    |
| lint / format      | ESLint 9 (flat) + Prettier                                   |

Charts are Plotly because the repo's existing figures are Plotly — same visual language. Plotly is
wrapped by a small in-repo component (`src/components/Plot.tsx`) rather than `react-plotly.js`, so
the ~4 MB bundle is loaded on demand and the dark template lives in one place.

**`typescript-eslint` is deliberately absent.** Every published 8.x release fails at import time
against `typescript@7` (it reads `ts.Extension.Cjs`, which the Go-ported compiler does not expose),
so TS/TSX are parsed with `@babel/eslint-parser`. The trade-off — no type-aware rules — is covered
by `tsc`, which owns unused-code detection via `noUnusedLocals` / `noUnusedParameters`. Full
rationale sits at the top of [`eslint.config.js`](eslint.config.js).

## Architecture

Three layers, each with its own README:

```
src/
  app/        the shell — module manifest, per-module boundaries, providers   → app/README.md
  components/ shared primitives — Exhibit, Plot, DataTable, Card, Badge, …    → components/README.md
  fixtures/   the offline data layer — JSON rows + lazy loaders               → fixtures/README.md
  api/        types.ts (transcribed from the contract) · client.ts (one fetch wrapper) · hooks.ts
  lib/        palette.ts (colours) · ui.ts (class recipes) · format.ts · hooks/ · aiExport/
  pages/      one folder per page, one file per exhibit
  test/       fixture request matrix, blessed payload hashes, setup
```

**Pages are feature modules.** [`src/app/modules`](src/app/README.md) declares each page once —
route, nav label, lazy `import()` — and the shell derives both the router and the nav bar from that
one array, so they cannot drift. Each module mounts inside its own error boundary and Suspense
boundary: a module that fails to load renders a contained card with a Retry that re-issues the
import, instead of blanking the app. Hovering a nav link preloads that module's chunk.

**`Exhibit` is the only way a chart enters the app.** It makes `legend` a **required** prop — the
repo's "every figure carries a legend" rule enforced by the type checker rather than by review —
and it is the single hook the AI export uses: each exhibit registers its narrative, provenance and
payload while mounted, so page-level and case-level exports need nothing from the call sites.

**Colour lives in one place.** `lib/palette.ts` owns the hex values; `lib/ui.ts` owns the Tailwind
class recipes built on them (`CARD`, `BOX`, `BADGE`, `EMPTY_DASHED`, plus a `cx()` joiner). A
component never re-types a class string that three files already share.

## Pages

| Page           | Question it answers                                              | Exhibits                                                                                                                                                                                                          |
| -------------- | ---------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Overview**   | What is this case, in numbers?                                   | stat tiles (variants, PASS %, reads, coverage, Ts/Tv, samples, probe budget); delivery-integrity board (one card per object, green per verified sha256); genotype donut with the `1/2` slice called out           |
| **Genome**     | Is any chromosome present in the wrong number of copies?         | allele-balance dot plot on the 0.5 line (**the headline**); depth-vs-VAF scatter with crosshair; karyotype ideogram to real chromosome length; 1 Mb density heat strips **+ 3D surface toggle**; BAF karyogram    |
| **Callset**    | Is the delivered callset healthy, and what did it suppress?      | filtering funnel (log axis, suppressed broken out by reason); depth histogram (log-y, mode annotated); substitution spectrum with Ts/Tv; indel length spectrum; zygosity split; VCF header fields                 |
| **Panel**      | Which MVA candidate genes have evidence, and how much is hidden? | gene scorecard (PASS/suppressed stacked + PASS % axis); constraint scorecard; domain lollipop; locus explorer — pick a gene, get a QUAL track and a VAF track; het-pair matrix; suppressed calls; gene background |
| **Compare**    | Which candidate pair survives comparison?                        | candidate funnel and table; pair comparator and fields; rarity scatter; observed-vs-expected QC norms; ClinVar presence                                                                                           |
| **Reads**      | What does the raw measurement look like?                         | yield per lane (R1/R2); read-store treemap; flowcell heatmap **+ 3D by tile**; per-cycle quality curves **+ 3D surface**; the 4-level phred binning                                                               |
| **Probes**     | Ask the raw reads a new question                                 | k-mer probe console (submit → server-side long-poll → result bars vs the expectation line); payload table; jobs monitor with cancel; oracle probe ledger (0/18)                                                   |
| **Science**    | What is claimed, and what is it worth?                           | hypothesis board; evidence ledger; the loop diagram; probe budget                                                                                                                                                 |
| **Provenance** | Where did every number come from?                                | lineage graph (hand-drawn SVG, hover an edge for its transform); derivations with their questions; flat lineage table                                                                                             |
| **Catalog**    | What data exists, and what does each column mean?                | delivery inventory; warehouse table catalog; column-meaning explainer; read-store card                                                                                                                            |
| **Search**     | Where is this gene / region / rsID?                              | query box over the three canonical forms; resolved results; density strip                                                                                                                                         |

Exactly **three** views are 3D, and each has a genuine third axis: density bins
(chromosome × position × count), flowcell (x × y × tile), cycle quality (cycle × partition × mean Q).

## Fixture fallback

Rows live in [`src/fixtures/data/*.json`](src/fixtures/README.md) — data, not code — and are
`import()`ed only when a request actually falls back, so a healthy API costs the visitor nothing.
The fetch wrapper serves them **only** when the API is genuinely unreachable (a network-level
failure) or answers `501`, and `VITE_USE_FIXTURES !== 'false'`; a `404`, `422` or `503` is the live
API answering and reaches the user as an error. When a fixture is served, a `fixture data` badge
appears in the header and a `fixture` chip appears on the affected exhibit.

Each registry entry states which of its numbers are **measured**, which are **PLACEHOLDER**, and
which are **SYNTHETIC** — the word travels into the UI inside the `fixture: …` source string.

Payload equivalence is tested, not assumed: `src/test/fixtures.test.ts` hashes all 55 requests in
the matrix against blessed values.

> **Patient-data rule (binding).** No genomic coordinate is committed anywhere in this repo. The
> locus endpoint returns real positions at runtime; its fixture uses a synthetic counter
> (1000, 2000, 3000 …) and says so. Reference-genome constants (GRCh38 chromosome lengths) are the
> coordinate _system_, not patient data, and are fine.

## Where to look first

| You want to                                  | Start at                                                      |
| -------------------------------------------- | ------------------------------------------------------------- |
| add a page                                   | [`src/app/README.md`](src/app/README.md) — one manifest entry |
| add a chart                                  | `src/components/Exhibit.tsx`, then the page's folder          |
| reuse a UI piece                             | [`src/components/README.md`](src/components/README.md)        |
| make the app work offline for a new endpoint | [`src/fixtures/README.md`](src/fixtures/README.md)            |
| understand a domain word                     | [`docs/dictionary.md`](../docs/dictionary.md)                 |
| know how a number was produced               | [`docs/step-0/methodology/`](../docs/step-0/methodology/)     |
