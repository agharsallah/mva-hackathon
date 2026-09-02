/**
 * Pure helper for the footer's dependency-status summary — split out of Footer.tsx so
 * that module exports components only (react-refresh/only-export-components is an
 * error in this repo's eslint config).
 *
 * Depends on nothing but the `status` field of a dependency check, so it stays correct
 * regardless of how the rest of the `GET /api/health/dependencies` contract shakes out
 * (see scratchpad/health-contract.md).
 */
import type { DependencyCheck } from '../api/types/health';

export type HealthTone = 'good' | 'decision' | 'broken' | 'neutral';

export interface HealthSummary {
  tone: HealthTone;
  phrase: string;
}

/**
 * `overall`/`checks` come straight off the query result and are `undefined` while the
 * request is pending, has errored, or the endpoint 404s (no backend yet) — all three
 * collapse to the same "status unknown" phrase and neutral tone. Counts are always
 * derived from `checks.length`, never hard-coded, per the mission's "never hard-code a
 * number" rule.
 */
export function summarizeHealth(
  overall: string | undefined,
  checks: DependencyCheck[] | undefined,
): HealthSummary {
  if (!overall || !checks || checks.length === 0) {
    return { tone: 'neutral', phrase: 'status unknown' };
  }
  const total = checks.length;
  const down = checks.filter((c) => c.status === 'down').length;
  const degraded = checks.filter((c) => c.status === 'degraded').length;
  if (down > 0) return { tone: 'broken', phrase: `${down} of ${total} dependencies down` };
  if (degraded > 0) {
    return { tone: 'decision', phrase: `${degraded} of ${total} dependencies degraded` };
  }
  return { tone: 'good', phrase: `all ${total} dependencies up` };
}
