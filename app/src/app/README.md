# App shell

**Standing:** current as of 2026-10-05.

Micro-frontend-style shell for one deployable SPA — no Module Federation, no separate
deploys. "Modules" are lazily-loaded chunks, each isolated by its own error/Suspense boundary.

## The contract

A page registers itself once, in `modules/index.ts`, as a `FeatureModule` (`modules/types.ts`):

```ts
{
  id: 'learn', path: '/learn', navLabel: 'Learn', title: 'The dictionary, as a course',
  group: 'learn', description: 'Every domain word in the repository, chapter by chapter …',
  load: () => import('../../pages/Learn'),
}
```

`AppShell.tsx` reads that array once and derives everything a reader sees about the app's
shape from it — one source, so none of these can disagree:

| Reader                        | What it draws from the manifest                                                   |
| ----------------------------- | --------------------------------------------------------------------------------- |
| `<Routes>`                    | one `<Route>` per entry                                                           |
| `Header` row 1 (Sections)     | one tab per `NAV_GROUPS` entry, landing on the group's first page                 |
| `Header` row 2 (Pages)        | the active group's pages, with the group's `question`                             |
| `Header` rows 3–4 (Branches)  | the open page's `parent` chain, so a detail page shows the path that leads to it  |
| `PageFrame` → `PageHeader`    | eyebrow (group · question), "n of m", `title` as the h1, `description`, prev/next |
| `PageFrame` → `JourneyFooter` | the previous and next page with their descriptions                                |
| `JourneyProvider`             | the same groups, as context, so `JourneyMap` and `Footer` can draw the sitemap    |

## Information architecture

Every page serves exactly one of the questions declared in `NAV_GROUPS`, named by its
`group`; manifest order inside a group is reading order. The overview has no group — it is
the map of all of them.

A page that declares a `parent` is a **detail** of that page: it keeps its place in the
reading order, but the section row lists only its parent and the page itself appears in a
further row while that branch is open. That is what keeps a section from degenerating into a
flat inventory of every leaf page as the app grows.

## Adding a page

1. Write the component under `src/pages/`, default-exported.
2. Add one entry to `modules/index.ts`. Nothing else is wired by hand.
3. If it introduces a new section, add the id to `NavGroupId` and an entry to `NAV_GROUPS`
   in `modules/types.ts`. A section with no pages has nothing to link to, so give it one.

## Files

| File                 | Role                                                                  |
| -------------------- | --------------------------------------------------------------------- |
| `AppShell.tsx`       | header, routes, footer; builds the nav tree from the manifest         |
| `PageFrame.tsx`      | the page heading, the "on this page" rail and the journey hand-off    |
| `ModuleBoundary.tsx` | one error boundary + Suspense boundary per page, with a real retry    |
| `ScrollToTop.tsx`    | scroll behaviour on navigation, including `#anchor` deep links        |
| `providers.tsx`      | StrictMode → QueryClientProvider → BrowserRouter                      |
| `modules/index.ts`   | **the manifest** — the only place a page is declared                  |
| `modules/types.ts`   | `FeatureModule`, `NavGroup`, and the section list                     |
| `modules/journey.ts` | pure lookups over the manifest (group of, children of, previous/next) |
