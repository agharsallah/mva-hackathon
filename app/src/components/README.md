# Components

**Verified:** 2026-09-03. Import from `src/components` (the barrel) — never reach past it into
a file directly, so a page never needs to know where a primitive lives.

## Charts

| Name                     | Purpose                                                                                                                                                    | Usage                                                      |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| `Exhibit`                | The only way a chart enters the app; enforces a `legend` and registers itself for AI export.                                                               | `<Exhibit title="…" legend={<>…</>}><Plot .../></Exhibit>` |
| `Chip`                   | Colour dot + label, for use inside an `Exhibit`'s legend.                                                                                                  | `<Chip color={C.good}>balanced</Chip>`                     |
| `Plot`                   | Thin wrapper over Plotly with the app's dark template.                                                                                                     | `<Plot data={traces} layout={baseLayout({...})} />`        |
| `baseLayout` / `scene3d` | The dark Plotly template (`src/components/plotLayout.ts`) — split from `Plot.tsx` so the two function exports don't sit next to `Plot`'s component export. | `layout={baseLayout({ title: '...' })}`                    |

## Data display

| Name        | Purpose                                                                                                                                                                        | Usage                                                               |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------- |
| `DataTable` | Sortable, filterable, paginated table. Additive: pass only `rows`/`columns`/`rowKey` for a plain table.                                                                        | `<DataTable rows={r} columns={cols} rowKey={(r) => r.id} />`        |
| `StatTile`  | One number, a label, an optional sub-line and tone.                                                                                                                            | `<StatTile label="Ts/Tv" value={dec(x)} tone="good" />`             |
| `NormChip`  | Verdict badge for a `results.qc_observed_expected` row; links to `/compare`.                                                                                                   | `<NormChip row={pickNorm(norms, ['tstv'])} />`                      |
| `pickNorm`  | Finds the observed/expected row a tile should be graded against (`src/components/pickNorm.ts` — split out of `NormChip.tsx` for the same fast-refresh reason as `baseLayout`). | `pickNorm(norms, ['tstv_genome_wide', 'tstv'])`                     |
| `FieldList` | A key/value list as `<dl>`. `layout="columns"` for fixed-width labels beside facts; `layout="inline"` for a label-and-sentence pair.                                           | `<FieldList fields={[{key:'sha', label:'sha256', value: hash}]} />` |

## Layout and structure

| Name                                            | Purpose                                                                                                                                                                                                                                                                           | Usage                                                             |
| ----------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| `Card`                                          | The bordered panel every non-chart section sits in. `variant`: `panel` (default, the bordered card) · `well` (recessed, for a block inside a card) · `plain` (the padding rhythm, no border). `padding`: `md` (16px, default) · `sm` (12px) · `none` (a table flush to the edge). | `<Card variant="well" padding="sm">…</Card>`                      |
| `Section`                                       | Page-level heading + optional subtitle over a block of content. `id` makes it an anchor target (`/provenance#reference`) with the scroll offset already applied.                                                                                                                  | `<Section title="…" subtitle="…">…</Section>`                     |
| `PageHeader` / `JourneyFooter`                  | The page's one h1 with its section question, position and prev/next; and the bottom-of-page hand-off. Rendered by the shell (`app/PageFrame.tsx`), never by a page.                                                                                                               | `<PageHeader title="…" eyebrow="Data · …" next={{to, label}} />`  |
| `Explainer`                                     | The page's background panel: a ≤ 2-sentence intro, terms as chips (click one for its definition; "all definitions" opens the glossary and is remembered), optional caveat. Sits _below_ the headline `Callout`.                                                                   | `<Explainer intro={…} terms={[{term, plain}]} />`                 |
| `JourneyProvider` / `JourneyMap` / `useJourney` | The manifest's four groups handed down as context; `JourneyMap` draws them as the Overview's reading-order map. Null outside the shell.                                                                                                                                           | `<JourneyMap />`                                                  |
| `Callout`                                       | A tone-coloured box for one thing the reader must not miss.                                                                                                                                                                                                                       | `<Callout tone="decision" title="…">…</Callout>`                  |
| `EmptyState`                                    | The dashed "nothing here" box. `tone="good"` for a register/ledger that is empty _by design_.                                                                                                                                                                                     | `<EmptyState tone="good" title="Budget untouched">…</EmptyState>` |
| `Toggle` / `Select` / `TextFilter`              | Small controls for an `Exhibit`'s title-row `controls` slot.                                                                                                                                                                                                                      | `<Toggle on={v} onChange={setV}>3D</Toggle>`                      |
| `Footer`                                        | App-wide footer: what this app is, the live dependency-status link (`/status`), the four-section sitemap (from `useJourney`) and repo-doc links. Mounted once by `AppShell`, like `Header`.                                                                                       | `<Footer />`                                                      |

## Small marks

| Name    | Purpose                                                                                                    | Usage                                                |
| ------- | ---------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| `Badge` | A small coloured pill. Takes a `Tone` (see Tokens below), the same vocabulary as `StatTile` and `Callout`. | `<Badge tone="decision">gap</Badge>`                 |
| `Flag`  | A boolean rendered as a `Badge`: green when true, grey when false, a third state for `null`.               | `<Flag on={v.is_rare} yes="rare" no="too common" />` |

## Async / query state

| Name                     | Purpose                                                                                                   | Usage                                                   |
| ------------------------ | --------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| `Loaded`                 | Render-prop gate over a react-query result — one loading skeleton, one error card, everywhere.            | `<Loaded query={q}>{(data) => <Exhibit .../>}</Loaded>` |
| `Skeleton` / `ErrorCard` | The two states `Loaded` renders; used directly where a page can't wait on `Loaded`'s data-callback shape. | `{q.error && <ErrorCard error={q.error} />}`            |

## Export tooling

| Name       | Purpose                                                                         |
| ---------- | ------------------------------------------------------------------------------- |
| `AiExport` | Header-mounted "export page" / "export case" buttons over the exhibit registry. |

## Type (`src/index.css`)

Two voices, both self-hosted from fontsource (latin subsets, ~144 kB woff2):

| Voice     | Face                                       | Used for                                                                                               |
| --------- | ------------------------------------------ | ------------------------------------------------------------------------------------------------------ |
| reading   | Literata (variable serif)                  | page h1, `Section` subtitle, `Explainer` intro and definitions, `Callout` body, `Exhibit` reading line |
| operating | Atkinson Hyperlegible Next (variable sans) | everything else: nav, labels, tables, controls, `StatTile` values (`tabular-nums`)                     |
| mono      | system monospace                           | identifiers only: hashes, table names, commands, ids                                                   |

Rules: sentence case everywhere, no tracked-out capitals for labels; prose measures capped
around 70–90 characters (`max-w-[70ch]`); numbers set `tabular-nums`; arrows and middle-dot
chains are not used as punctuation.

## Tokens (`src/index.css` + `src/lib/ui.ts`)

Two layers, both named by **role**. A page never types a pixel size, a radius, a grey or a
class string: it names the role, or it composes the recipe.

### Role tokens (`@theme` in `src/index.css`)

Written as ordinary Tailwind utilities, so `text-heading` and `rounded-card` are as cheap to
type as the literal they replace — and changing the role in one place moves every user of it.

| Group         | Token                                                                                                                                       | Role                                                                                                                                                                                                |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **type**      | `text-micro` 11 · `text-xs` 12 · `text-note` 13 · `text-sm` 14 · `text-reading` 15 · `text-heading` 17 · `text-figure` 26 · `text-title` 30 | chip/provenance · label · serif footnote · body · serif prose · `Section` h2 · a `StatTile` number · the page h1. `text-note` and `text-reading` are the reading voice and are set in `font-serif`. |
| **radii**     | `rounded-pill` 4 · `rounded-control` 6 · `rounded-card` 8                                                                                   | a badge/chip/tag · a button/select/input · a card/exhibit/callout                                                                                                                                   |
| **hairlines** | `border-line-soft` · `border-line` · `border-line-strong` · `ring-focus`                                                                    | chrome-900 (a well's edge) · chrome-800 (the default card and table rule) · chrome-700 (a hover or emphasised edge) · machinery-600 (the keyboard focus ring)                                       |
| **surfaces**  | `bg-panel` · `bg-panel-raised` · `bg-well`                                                                                                  | the card lift off the page · a control sitting on a card · the recessed block inside one. Translucent steps, so a nested panel stays distinguishable in both themes.                                |
| **spacing**   | `2` (8) · `3` (12) · `4` (16) · `6` (24)                                                                                                    | a strict 4px grid: tight (two chips on a row) · inner rhythm (rows inside a card) · card padding · between sections. Half steps are out except `0.5` (2px) for a chip's vertical padding.           |
| **fonts**     | `font-sans` · `font-serif` · `font-mono`                                                                                                    | Atkinson Hyperlegible Next (the operating voice) · Literata (the reading voice) · identifiers only                                                                                                  |

### Recipes (`src/lib/ui.ts`)

Not components — the Tailwind class strings the primitives above are built from, written once
because they were being hand-typed identically in three or more page files. Plus `cx()`, a
class-joiner that drops falsy arguments.

| Recipe         | What it is                                                                              |
| -------------- | --------------------------------------------------------------------------------------- |
| `CARD`         | the bordered panel — `rounded-card border border-line bg-panel p-4` (`Card`, `Exhibit`) |
| `WELL`         | the recessed panel inside a card — a code block, a legend well, a nested list           |
| `CONTROL`      | a button/select/input: radius, hairline, `text-micro`, hover and focus ring; no colour  |
| `BOX`          | the tinted, bordered alert region (legacy; `Callout` now uses `RULE` + `TINT`)          |
| `BADGE`        | the pill (`Badge`, `NormChip`)                                                          |
| `EMPTY_DASHED` | the dashed nothing-here box (`EmptyState`)                                              |
| `RULE`         | the 2px left rule in a tone's colour (`StatTile`, `Callout`) — a verdict without a box  |
| `TINT`         | the faint background behind a `Callout`, no border of its own                           |
| `TEXT`         | just the text colour for a tone (`StatTile`, verdicts)                                  |

The tone-keyed maps (`BOX`, `BADGE`, `EMPTY_DASHED`, `RULE`, `TINT`, `TEXT`) are
`Record<Tone, string>` over the **one** `Tone` union exported by `lib/palette`
(`neutral · good · broken · decision · machinery · raw`), so adding a meaning breaks compilation
at every recipe until each answers for it, and `src/test/theme-tokens.test.ts` fails if a recipe
tints a tone in the wrong hue family.

Colour itself is owned by [`lib/palette/`](../lib/palette/index.ts) and generated: `pnpm theme`
writes the hex ramps (`ramps.generated.ts`, for Plotly and SVG) and the matching `--color-*`
custom properties (`src/theme.generated.css`, for the classes here) from one conversion of
Tailwind's own theme. A recipe therefore names a **semantic family** (`bg-good-950`,
`text-chrome-300`) and never a Tailwind hue or a hex — both are eslint errors
(`local/no-builtin-tailwind-color`, `local/no-raw-hex-color`).

**Every role token, every recipe, every primitive, every tone and every ramp is rendered live at
`/style-guide`** — the type scale, the radii, the hairlines, the nested surfaces and the spacing
grid under "The tokens", measured off the DOM rather than restated. Read it before adding a new
size, box, tint or pill: the thing you want probably exists.

## Hooks (`src/lib/hooks/`)

| Name                | Purpose                                                                                                                                                                                              |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `useUrlKnownOption` | A URL-held selection whose option list arrives async (e.g. a gene picker fed by an API call) — wraps `useUrlState` + `known()` from `lib/urlstate.ts` so call sites stop retyping the two-line glue. |

> **Legend:** table rows only — no diagram in this file.
