/**
 * The module manifest: one entry per page. This list is the only place a page's
 * route, nav label, title, group, parent and lazy chunk are declared — AppShell turns it
 * into <Route>s, Header into the nav rows, PageFrame into the h1 and journey links.
 *
 * Order here is journey order: within a group, the order a reader should walk the
 * pages; groups follow `NAV_GROUPS`. The overview is first and belongs to no group.
 *
 * A page that declares a `parent` is a *detail* of that page: it keeps its place in the
 * reading order but leaves the section row, appearing in a further row while its branch
 * is open. Adding a page is adding one entry here and one file under `src/pages/`.
 */

import type { FeatureModule } from './types';

export const modules: FeatureModule[] = [
  {
    id: 'overview',
    path: '/',
    navLabel: 'Overview',
    title: 'Overview',
    description: 'What this app is, and the map of the questions it answers.',
    load: () => import('../../pages/Overview'),
  },

  // ── Learn: what do the words mean? ───────────────────────────────────────────
  {
    id: 'learn',
    path: '/learn',
    navLabel: 'Learn',
    title: 'The dictionary, as a course',
    group: 'learn',
    description:
      'Every domain word in the repository, chapter by chapter, ordered so each one only uses words defined before it — with its diagrams.',
    load: () => import('../../pages/Learn'),
  },

  // ── Platform: what is this app built from? ───────────────────────────────────
  {
    id: 'style-guide',
    path: '/style-guide',
    navLabel: 'Style',
    title: 'Design system',
    group: 'platform',
    description:
      'Generated colour tokens, tones and the primitives every page is built from — the visual contract a new page inherits.',
    load: () => import('../../pages/StyleGuide'),
  },
];
