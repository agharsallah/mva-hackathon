import type { ObservedExpectedRow } from '../api/types';

/**
 * Find the row a tile should be graded against.
 *
 * `ids` is a *preference list*, not a single key: the live warehouse names the Ts/Tv norm
 * `tstv_genome_wide` while the offline fixture names it `tstv`, and a tile should chip in
 * both worlds. The first id present wins, so the live name is always listed first and the
 * fixture alias behind it.
 */
export function pickNorm(
  rows: ObservedExpectedRow[] | undefined,
  ids: readonly string[],
): ObservedExpectedRow | undefined {
  if (!rows) return undefined;
  for (const id of ids) {
    const hit = rows.find((r) => r.metric === id);
    if (hit) return hit;
  }
  return undefined;
}
