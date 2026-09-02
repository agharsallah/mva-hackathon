import type { DependencyCheck, DependencyKind, HealthStatus } from '../../api/types';

/**
 * Pure helpers over a `checks` array — no fetching, no JSX, so the verdict logic can be
 * read (and unit-tested) without a query client. `DependencyBoard` and `OverallVerdict`
 * both import from here rather than re-deriving the same grouping/tone rules.
 */

/** Group order for the board — internal first (ours, required), snapshot last (data at
 * rest, never a live probe target in the usual sense). */
export const KIND_GROUPS: { key: DependencyKind; title: string; note: string }[] = [
  { key: 'internal', title: 'Internal', note: 'ours, required — a down check here breaks the app' },
  {
    key: 'upstream',
    title: 'Upstream',
    note: 'ours, optional — a page-scoped feature, not the app',
  },
  { key: 'third-party', title: 'Third-party', note: "someone else's live service" },
  { key: 'snapshot', title: 'Reference snapshot', note: 'ingested data, not a live service' },
];

/**
 * Grouping must never lose a check. Rendering only the four known kinds means a check the
 * API labels with anything else — a kind added server-side, or a typo — disappears from a
 * page whose whole job is to account for every dependency. This splits the payload into
 * the known groups plus one catch-all, so the board always renders `checks.length` cards.
 */
export function groupChecks(
  checks: DependencyCheck[],
): { key: string; title: string; note: string; checks: DependencyCheck[] }[] {
  const known = new Set(KIND_GROUPS.map((g) => g.key as string));
  const groups = KIND_GROUPS.map((g) => ({
    ...g,
    key: g.key as string,
    checks: checks.filter((c) => c.kind === g.key),
  }));
  const unknown = checks.filter((c) => !known.has(c.kind));
  if (unknown.length > 0) {
    groups.push({
      key: 'other',
      title: 'Other',
      note: 'the API reported a kind this build does not know — shown so nothing is hidden',
      checks: unknown,
    });
  }
  return groups.filter((g) => g.checks.length > 0);
}

/** The tone vocabulary `Badge`/`Callout`/`StatTile` already share (good/decision/broken +
 * neutral for "not configured", which is not a failure and must not read as one). */
export function statusTone(status: HealthStatus): 'good' | 'decision' | 'broken' | 'neutral' {
  switch (status) {
    case 'up':
      return 'good';
    case 'degraded':
      return 'decision';
    case 'down':
      return 'broken';
    case 'skipped':
      return 'neutral';
  }
}

/** `skipped` must read as "not configured" — the contract's own words for what it means,
 * not a raw enum value that looks like a fourth kind of failure. */
export function statusLabel(status: HealthStatus): string {
  return status === 'skipped' ? 'not configured' : status;
}

export interface Verdict {
  overall: HealthStatus;
  working: DependencyCheck[];
  /** `down` or `degraded` — the two states that cost the user something right now. */
  broken: DependencyCheck[];
  skipped: DependencyCheck[];
  /** Every distinct page name named in a broken check's `powers` — the cost, derived from
   * the payload rather than hard-coded, so it can never drift from what the checks say. */
  affectedPages: string[];
}

export function deriveVerdict(checks: DependencyCheck[], overall: HealthStatus): Verdict {
  const working = checks.filter((c) => c.status === 'up');
  const broken = checks.filter((c) => c.status === 'down' || c.status === 'degraded');
  const skipped = checks.filter((c) => c.status === 'skipped');
  const affectedPages = Array.from(new Set(broken.flatMap((c) => c.powers))).sort();
  return { overall, working, broken, skipped, affectedPages };
}
