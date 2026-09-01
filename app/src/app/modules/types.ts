/**
 * A feature module is one page, described data-first instead of hand-wired into a
 * <Route> list. The manifest built from these descriptors is the single source of
 * truth that both the router and the nav bar read, so they cannot drift apart.
 */

import type { ComponentType } from 'react';

export interface FeatureModule {
  /** Stable key: route key, error-boundary label, React key. Not shown to users. */
  id: string;
  /** react-router path, exactly as registered today (e.g. '/', '/genome'). */
  path: string;
  /** Label shown in the top nav, verbatim. */
  navLabel: string;
  /** Optional nav grouping, for a future multi-section nav. Unused today. */
  navGroup?: string;
  /** One-line note on what the page shows; not rendered, kept for self-documentation. */
  description?: string;
  /** Dynamic import of the page's default export — the existing code-split boundary. */
  load: () => Promise<{ default: ComponentType }>;
}
