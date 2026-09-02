# Components

**Verified:** 2026-09-01. Import from `src/components` (the barrel) — never reach past it into
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

| Name                               | Purpose                                                                                                                                               | Usage                                                             |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| `Card`                             | The bordered panel every non-chart section sits in.                                                                                                   | `<Card className="space-y-3">…</Card>`                            |
| `Section`                          | Page-level heading + optional subtitle over a block of content.                                                                                       | `<Section title="…" subtitle="…">…</Section>`                     |
| `Explainer`                        | The page's intro panel: plain-English intro, a term glossary, an optional caveat.                                                                     | `<Explainer intro={…} terms={[{term, plain}]} />`                 |
| `Callout`                          | A tone-coloured box for one thing the reader must not miss.                                                                                           | `<Callout tone="decision" title="…">…</Callout>`                  |
| `EmptyState`                       | The dashed "nothing here" box. `tone="good"` for a register/ledger that is empty _by design_.                                                         | `<EmptyState tone="good" title="Budget untouched">…</EmptyState>` |
| `Toggle` / `Select` / `TextFilter` | Small controls for an `Exhibit`'s title-row `controls` slot.                                                                                          | `<Toggle on={v} onChange={setV}>3D</Toggle>`                      |
| `Footer`                           | App-wide footer: what this app is, the live dependency-status link (`/status`), in-app and repo-doc links. Mounted once by `AppShell`, like `Header`. | `<Footer />`                                                      |

## Small marks

| Name    | Purpose                                                                                        | Usage                                                |
| ------- | ---------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| `Badge` | A small coloured pill — five tones matching `StatTile`'s (`neutral/good/broken/decision/raw`). | `<Badge tone="decision">gap</Badge>`                 |
| `Flag`  | A boolean rendered as a `Badge`: green when true, grey when false, a third state for `null`.   | `<Flag on={v.is_rare} yes="rare" no="too common" />` |

## Async / query state

| Name                     | Purpose                                                                                                   | Usage                                                   |
| ------------------------ | --------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| `Loaded`                 | Render-prop gate over a react-query result — one loading skeleton, one error card, everywhere.            | `<Loaded query={q}>{(data) => <Exhibit .../>}</Loaded>` |
| `Skeleton` / `ErrorCard` | The two states `Loaded` renders; used directly where a page can't wait on `Loaded`'s data-callback shape. | `{q.error && <ErrorCard error={q.error} />}`            |

## Export tooling

| Name       | Purpose                                                                         |
| ---------- | ------------------------------------------------------------------------------- |
| `AiExport` | Header-mounted "export page" / "export case" buttons over the exhibit registry. |

## Tokens (`src/lib/ui.ts`)

Not components — the Tailwind class strings the primitives above are built from, plus `cx()`,
a class-joiner that drops falsy arguments. `CARD`, `BOX` (4-tone alert box), `BADGE` (5-tone
pill), `EMPTY_DASHED` (2-tone dashed box). Colours themselves stay owned by `lib/palette.ts` —
`ui.ts` only names Tailwind recipes built on top of it, never a raw hex value.

## Hooks (`src/lib/hooks/`)

| Name                | Purpose                                                                                                                                                                                              |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `useUrlKnownOption` | A URL-held selection whose option list arrives async (e.g. a gene picker fed by an API call) — wraps `useUrlState` + `known()` from `lib/urlstate.ts` so call sites stop retyping the two-line glue. |

> **Legend:** table rows only — no diagram in this file.
