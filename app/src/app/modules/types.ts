/**
 * A feature module is one page, described data-first instead of hand-wired into a
 * <Route> list. The manifest built from these descriptors is the single source of
 * truth that the router, the nav rows, the page header and the journey footer all
 * read, so none of them can drift apart.
 */

import type { ComponentType } from 'react';

/**
 * The questions the app answers, in the order a reader should ask them. A page belongs to
 * exactly one; the overview belongs to none, because it is the map of all of them.
 * `learn` comes first because the other sections are written in its words.
 *
 * Adding a section is adding an id here plus an entry in `NAV_GROUPS` — and at least one
 * page in the manifest that declares it, because a section with no pages has nothing to
 * link to.
 */
export type NavGroupId = 'learn' | 'platform';

export interface NavGroup {
  id: NavGroupId;
  /** Short word shown as the section tab. */
  label: string;
  /** The question every page in the group is trying to answer, shown as the eyebrow. */
  question: string;
}

export const NAV_GROUPS: readonly NavGroup[] = [
  { id: 'learn', label: 'Learn', question: 'What do the words mean?' },
  { id: 'platform', label: 'Platform', question: 'What is this app built from?' },
];

export interface FeatureModule {
  /** Stable key: route key, error-boundary label, React key. Not shown to users. */
  id: string;
  /** react-router path, exactly as registered today (e.g. '/', '/learn'). */
  path: string;
  /** Short label shown in the nav tab, verbatim. */
  navLabel: string;
  /** The page's h1 — a full phrase, where `navLabel` is one word. */
  title: string;
  /** Which question this page serves. Omitted only for the overview, the map. */
  group?: NavGroupId;
  /**
   * The page this one is a detail of, by `id`. A child stays in its parent's group and in
   * the reading order, but the section row lists only the parent — so a section that grows
   * a subtree stays a navigation instead of becoming an inventory of every leaf. A child
   * appears in a further row, shown while the parent or one of its children is open.
   */
  parent?: string;
  /** One line under the h1 saying what the page shows. Also the overview map's blurb. */
  description: string;
  /** Dynamic import of the page's default export — the existing code-split boundary. */
  load: () => Promise<{ default: ComponentType }>;
}
