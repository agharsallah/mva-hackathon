/**
 * A feature module is one page, described data-first instead of hand-wired into a
 * <Route> list. The manifest built from these descriptors is the single source of
 * truth that the router, the two-tier nav, the page header and the journey footer all
 * read, so none of them can drift apart.
 */

import type { ComponentType } from 'react';

/**
 * The four questions the app answers, in the order a reader should ask them. A page
 * belongs to exactly one; Overview belongs to none because it is the map of all four.
 */
export type NavGroupId = 'data' | 'case' | 'decide' | 'platform';

export interface NavGroup {
  id: NavGroupId;
  /** Short word shown as the section tab. */
  label: string;
  /** The question every page in the group is trying to answer, shown as the eyebrow. */
  question: string;
}

export const NAV_GROUPS: readonly NavGroup[] = [
  { id: 'data', label: 'Data', question: 'Is the measurement trustworthy?' },
  { id: 'case', label: 'Case', question: 'Which gene, and which pair inside it, is causal?' },
  {
    id: 'decide',
    label: 'Decide',
    question: 'What do we believe, and what has it cost to find out?',
  },
  {
    id: 'platform',
    label: 'Platform',
    question: 'What exists, where did it come from, and is it up?',
  },
];

export interface FeatureModule {
  /** Stable key: route key, error-boundary label, React key. Not shown to users. */
  id: string;
  /** react-router path, exactly as registered today (e.g. '/', '/genome'). */
  path: string;
  /** Short label shown in the nav tab, verbatim. */
  navLabel: string;
  /** The page's h1 — a full phrase, where `navLabel` is one word. */
  title: string;
  /** Which of the four questions this page serves. Omitted only for Overview, the map. */
  group?: NavGroupId;
  /** One line under the h1 saying what the page shows. Also the Overview map's blurb. */
  description: string;
  /** Dynamic import of the page's default export — the existing code-split boundary. */
  load: () => Promise<{ default: ComponentType }>;
}
