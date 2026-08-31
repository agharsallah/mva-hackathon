# `app/` — MVA Case Explorer

A data-understanding and visualization web app for one whole-genome case (Mosaic Variegated
Aneuploidy, single sample `PROBAND01`). It is a **reading tool**, not a dashboard: every page
opens with an explainer that names its domain concepts in the repo's `technical term (plain-English
meaning)` pattern, and every chart carries a `Legend` line decoding its own colours.

There is **no trio** in this dataset — one sample only. The app never renders a parent column.

## Stack

| Concern | Choice |
|---|---|
| build / dev server | Vite 8 |
| UI | React 18 + TypeScript (strict) |
| data fetching | `@tanstack/react-query` v5 — retries off, 5 min `staleTime` |
| routing | `react-router-dom` v7 |
| charts (2D and 3D) | `plotly.js-dist-min`, lazily `import()`ed into its own chunk |
| styling | Tailwind CSS v4 via `@tailwindcss/vite` |

Charts are Plotly because the repo's existing figures are Plotly — same visual language. Plotly is
wrapped by a small in-repo component (`src/components/Plot.tsx`) rather than `react-plotly.js`, so
the ~4 MB bundle is loaded on demand and the dark template lives in one place.

## Run

```bash
cd app
npm install
npm run dev      # http://127.0.0.1:5173
npm run build    # tsc -b && vite build — must pass clean
```

### Environment

| Variable | Default | Meaning |
|---|---|---|
| `VITE_API_URL` | `http://127.0.0.1:8900` | base URL of `mva-viz-api` |
| `VITE_USE_FIXTURES` | unset (= on) | `false` disables the fixture fallback, so an unreachable API surfaces as an error card |

Start the API from the repo root with `uv run mva-viz-api`. The Probes page additionally needs the
reads API behind it; when that upstream is down the viz API answers `503` and the page shows the
start command instead of an error.

## Pages

| Page | Question it answers | Exhibits |
|---|---|---|
| **Overview** | What is this case, in numbers? | stat tiles (variants, PASS %, reads, coverage, Ts/Tv, samples, probe budget); delivery-integrity board (one card per object, green per verified sha256); genotype donut with the `1/2` slice called out |
| **Genome** | Is any chromosome present in the wrong number of copies? | allele-balance dot plot on the 0.5 line (**the headline**); depth-vs-VAF scatter with crosshair; karyotype ideogram to real chromosome length; 1 Mb density heat strips **+ 3D surface toggle** |
| **Callset** | Is the delivered callset healthy, and what did it suppress? | filtering funnel (log axis, suppressed broken out by reason); depth histogram (log-y, mode annotated); substitution spectrum with Ts/Tv; indel length spectrum |
| **Panel** | Which MVA candidate genes have evidence, and how much is hidden? | gene scorecard (PASS/suppressed stacked + PASS % axis); locus explorer — pick a gene, get a QUAL track and a VAF track |
| **Reads** | What does the raw measurement look like? | yield per lane (R1/R2); read-store treemap; flowcell heatmap **+ 3D by tile**; per-cycle quality curves **+ 3D surface**; the 4-level phred binning |
| **Probes** | Ask the raw reads a new question | k-mer probe console (submit → server-side long-poll → result bars vs the expectation line); jobs monitor with cancel; oracle probe ledger (0/18) |
| **Provenance** | Where did every number come from? | lineage graph (hand-drawn SVG, hover an edge for its transform); derivations with their questions; flat lineage table |

Exactly **three** views are 3D, and each has a genuine third axis: density bins
(chromosome × position × count), flowcell (x × y × tile), cycle quality (cycle × partition × mean Q).

## Fixture fallback

`src/fixtures/` holds one module per endpoint. The fetch wrapper serves them **only** when the API
is genuinely unreachable (a network-level failure) and `VITE_USE_FIXTURES !== 'false'`; a `404`,
`422` or `503` is the live API answering and reaches the user as an error. When a fixture is served,
a `fixture data` badge appears in the header and a `fixture` chip appears on the affected exhibit.

Each fixture module states which of its numbers are **measured** and which fill a *shape* so a chart
has something to draw offline.

> **Patient-data rule (binding).** No genomic coordinate is committed anywhere in this repo. The
> locus endpoint returns real positions at runtime; its fixture uses a synthetic counter
> (1000, 2000, 3000 …) and says so in the module docstring. Reference-genome constants
> (GRCh38 chromosome lengths) are the coordinate *system*, not patient data, and are fine.

## Layout

```
src/
  api/        types.ts (transcribed from the contract) · client.ts (one fetch wrapper) · hooks.ts
  fixtures/   one module per endpoint + the registry
  components/ Plot · Exhibit (legend is a required prop) · Explainer · StatTile · DataTable · …
  lib/        palette.ts (the repo's colour language) · format.ts
  pages/      one folder per page, one file per exhibit
```

`Exhibit` makes `legend` a **required** prop — the repo's "every figure carries a legend" rule
enforced by the type checker rather than by review.
