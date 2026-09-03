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

| Name                                            | Purpose                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | Usage                                                             |
| ----------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| `Card`                                          | The bordered panel every non-chart section sits in. `variant`: `panel` (default, the bordered card) · `well` (recessed, for a block inside a card) · `plain` (the padding rhythm, no border). `padding`: `md` (16px, default) · `sm` (12px) · `none` (a table flush to the edge).                                                                                                                                                                                                   | `<Card variant="well" padding="sm">…</Card>`                      |
| `Section`                                       | Page-level heading + optional subtitle over a block of content. **Self-registering**: on mount it announces `{id, title, element}` to the section registry, so the rail and the palette list it with no page wiring. Its anchor id defaults to `slugify(title)` (`/callset#zygosity-split`); pass `id` to pin one a doc links to. Scroll offset already applied.                                                                                                                    | `<Section title="…" subtitle="…">…</Section>`                     |
| `OnThisPage` / `JumpToSection`                  | The two faces of the same list. `OnThisPage` is the sticky rail beside the content at `xl` and up — a `nav` landmark named "On this page", one anchor per section in **document order**, the one in view marked with an `IntersectionObserver` scroll-spy, plus "Back to top". `JumpToSection` is the same list as a `select` below `xl`. Both render **nothing** under two sections. Mounted by `app/PageFrame.tsx`, never by a page.                                              | `<OnThisPage />` · `<JumpToSection />`                            |
| `CommandPalette` (+ `PaletteDialog`)            | The ⌘K / Ctrl+K jump palette: the button and the hotkey only, mounted once by `Header`. `PaletteDialog` — the dialog body, `lazy()`-loaded on first open (and preloaded on button hover) so the entry chunk stays small — lists **sections on this page**, then **pages** from the journey context, then app-wide **actions** (overview, theme, top), filtered as you type. `combobox` + `listbox` roles, arrows to move, Enter to go, Esc to close and return focus to the button. | mounted by `Header`; nothing to call                              |
| `PageHeader` / `JourneyFooter`                  | The page's one h1 with its section question, position and prev/next; and the bottom-of-page hand-off. Rendered by the shell (`app/PageFrame.tsx`), never by a page.                                                                                                                                                                                                                                                                                                                 | `<PageHeader title="…" eyebrow="Data · …" next={{to, label}} />`  |
| `Explainer`                                     | The page's background panel: a ≤ 2-sentence intro, terms as chips (click one for its definition; "all definitions" opens the glossary and is remembered), optional caveat; a term with `dict: '<slug>'` shows "full definition →" into `/learn`. Sits _below_ the headline `Callout`.                                                                                                                                                                                               | `<Explainer intro={…} terms={[{term, plain, dict?}]} />`          |
| `JourneyProvider` / `JourneyMap` / `useJourney` | The manifest's five groups handed down as context; `JourneyMap` draws them as the Overview's reading-order map. Null outside the shell.                                                                                                                                                                                                                                                                                                                                             | `<JourneyMap />`                                                  |
| `Callout`                                       | A tone-coloured box for one thing the reader must not miss.                                                                                                                                                                                                                                                                                                                                                                                                                         | `<Callout tone="decision" title="…">…</Callout>`                  |
| `EmptyState`                                    | The dashed "nothing here" box. `tone="good"` for a register/ledger that is empty _by design_.                                                                                                                                                                                                                                                                                                                                                                                       | `<EmptyState tone="good" title="Budget untouched">…</EmptyState>` |
| `Toggle` / `Select` / `TextFilter`              | Small controls for an `Exhibit`'s title-row `controls` slot.                                                                                                                                                                                                                                                                                                                                                                                                                        | `<Toggle on={v} onChange={setV}>3D</Toggle>`                      |
| `Footer`                                        | App-wide footer: what this app is, the live dependency-status link (`/status`), the four-section sitemap (from `useJourney`) and repo-doc links. Mounted once by `AppShell`, like `Header`.                                                                                                                                                                                                                                                                                         | `<Footer />`                                                      |

**Section registry** ([`lib/sections.ts`](../lib/sections.ts)). One mutable store with a version
counter, read through `useSyncExternalStore` — the same shape as the exhibit registry. A mounted
`Section` registers; unmounting unregisters; `list()` returns the entries sorted by
`compareDocumentPosition`, so the rail reads top to bottom even though React's effect order is
mount order. `slugify(title)` is the anchor generator: lowercase, every punctuation run collapsed
to one hyphen, capped at 80 characters. Nothing else writes to the store, and no page imports it —
`OnThisPage`, `JumpToSection` and `PaletteDialog` are its only readers. Covered by
`src/test/sections.test.ts` (the store) and `src/test/section-nav.test.tsx` (the three readers).

## Small marks

| Name    | Purpose                                                                                                    | Usage                                                |
| ------- | ---------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| `Badge` | A small coloured pill. Takes a `Tone` (see Tokens below), the same vocabulary as `StatTile` and `Callout`. | `<Badge tone="decision">gap</Badge>`                 |
| `Flag`  | A boolean rendered as a `Badge`: green when true, grey when false, a third state for `null`.               | `<Flag on={v.is_rare} yes="rare" no="too common" />` |

## Async / query state

Loading and failure are designed states, not fallbacks. A page never writes
`isLoading ? … : error ? … : …`: it hands its query to `Loaded` and gets all four states.
All three are rendered live under "Loading and failure" on `/style-guide` — four skeletons
and one card per failure kind, built from constructed errors.

| Name            | Purpose                                                                                                                                                                                                                                                                                                                                                                                         | Usage                                                   |
| --------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| `Loaded`        | Render-prop gate over a react-query result. Pending → `Skeleton`; failed with nothing cached → `ErrorCard` wired to `refetch`; succeeded → the children; **failed with a cached answer → the children _plus_ a stale strip**, so a failed refresh never replaces a chart with an error.                                                                                                         | `<Loaded query={q}>{(data) => <Exhibit .../>}</Loaded>` |
| `Skeleton`      | The waiting state, shaped like the thing it stands in for: `variant` `exhibit` (default — axes, bars, caption) · `table` (header rule + `rows` body rows) · `tiles` (the four-up `StatTile` row) · `block` (a plain box holding `height`). `role="status"`, `aria-busy`, and an sr-only `label`.                                                                                                | `<Skeleton variant="table" rows={12} height={420} />`   |
| `ErrorCard`     | The failure state. `role="alert"`, the classified title and explanation, and always three controls: **Retry** (`onRetry`, omitted where nothing can be retried), **Open Status** (`/status`) and **Details** (a `<dl>`: endpoint + status for an `ApiError`, message + timestamp for anything else). `title` overrides the heading (a module boundary names the module); children add guidance. | `<ErrorCard error={q.error} onRetry={q.refetch} />`     |
| `classifyError` | The data half of `ErrorCard`, in `failure.ts` so that file exports only components. Returns a `Failure` — `kind`, `title`, `explain`, and where one exists a `remedy` and a fix `command`.                                                                                                                                                                                                      | `classifyError(err).kind === 'route-missing'`           |
| `FetchBar`      | The 2px machinery-coloured bar under the header while anything is in flight — react-query's `useIsFetching`, so no page wires it. Lives in `Header.tsx`, **not** the barrel: the shell mounts it once.                                                                                                                                                                                          | mounted by `Header`; nothing to call                    |

**Two timings, both in `Skeleton`.** It paints nothing for the first **150 ms** (`opacity-0`),
so an answer that arrives fast never flashes grey; then it fades in and pulses. At **6 s** it
grows a "Still loading" note linking to `/status`, because by then the honest message is that
something is wrong and here is where to look.

**Six named failures plus a fallback**, each with its own sentence and remedy, because each has
a different fix:

| `kind`          | What happened                                                         | What the card offers                        |
| --------------- | --------------------------------------------------------------------- | ------------------------------------------- |
| `unreachable`   | A `TypeError` from `fetch` — no API answered (or CORS refused).       | Names the URL tried; `uv run mva-viz-api`.  |
| `route-missing` | 404/501, or FastAPI's bare `Not Found` — the API predates this build. | Restart the API; `uv run mva-viz-api`.      |
| `upstream-down` | 503 — the viz API is up, the reads service behind it is not.          | The Status page card names the remedy.      |
| `bad-request`   | Any other 4xx — the API refused these parameters.                     | Change the selection, or reset to defaults. |
| `server-fault`  | 5xx — the API accepted the request then failed.                       | The API log has the traceback.              |
| `aborted`       | `error.name === 'AbortError'` — the page moved on first.              | Retry.                                      |
| `unknown`       | The honest fallback; nothing is guessed.                              | Retry, and report the Details block.        |

**Retries are policy, not per-call** ([`lib/queryClient.ts`](../lib/queryClient.ts)):
`shouldRetry` retries a network failure or a 5xx twice with a short back-off (the API may be
restarting), and never retries a 4xx — that is the API saying no to _this_ request, and asking
again gets the same answer. So an `ErrorCard` for a `bad-request` appears immediately, and one
for a `server-fault` only after the retries are spent.

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
