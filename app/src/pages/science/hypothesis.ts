import type { HypothesisRow } from '../../api/types';
import { C } from '../../lib/palette';

/**
 * Hypothesis status and evidence-direction colour maps, and the append-only-revision
 * collapse that turns a stream of `HypothesisRow`s into one current claim per id.
 *
 * Split out of `register.tsx` so that module can export components only — Vite's fast
 * refresh only hot-swaps a module whose every export is a component, and a constant or a
 * function export alongside one forces a full reload on every edit.
 */

/**
 * Status → colour, mirroring `mva.science.hypothesis.Status.hue` so the browser and the
 * generated report never disagree about what green means.
 */
export const STATUS_COLOR: Record<string, string> = {
  proposed: C.machinery,
  testing: C.decision,
  supported: C.good,
  refuted: C.broken,
  superseded: C.absent,
};

/** The order a board reads in: open claims first, settled ones after. */
export const STATUS_ORDER = ['testing', 'proposed', 'supported', 'refuted', 'superseded'];

export const statusColor = (status: string): string => STATUS_COLOR[status] ?? C.absent;

/** `supports` is the goal, `refutes` is the claim breaking, `neutral` is machinery. */
export function directionColor(direction: string): string {
  if (direction === 'supports') return C.good;
  if (direction === 'refutes') return C.broken;
  return C.absent;
}

export interface Claim {
  /** The current belief: the highest revision recorded for this id. */
  latest: HypothesisRow;
  /** Every revision, oldest first — the record of the belief moving. */
  history: HypothesisRow[];
}

/**
 * Collapse the append-only revision stream into one current claim per id.
 *
 * The API serves every revision on purpose. Picking the maximum here (rather than server
 * side) is what keeps the earlier revisions available to expand: an append-only register
 * whose history the UI throws away is just a mutable table with extra rows.
 */
export function claims(rows: HypothesisRow[]): Claim[] {
  const byId = new Map<string, HypothesisRow[]>();
  for (const row of rows) {
    const existing = byId.get(row.hypothesis_id);
    if (existing) existing.push(row);
    else byId.set(row.hypothesis_id, [row]);
  }
  return [...byId.entries()]
    .map(([, revisions]) => {
      const history = [...revisions].sort((a, b) => a.revision - b.revision);
      return { latest: history[history.length - 1], history };
    })
    .sort((a, b) => {
      const rank = STATUS_ORDER.indexOf(a.latest.status) - STATUS_ORDER.indexOf(b.latest.status);
      return rank !== 0 ? rank : a.latest.hypothesis_id.localeCompare(b.latest.hypothesis_id);
    });
}
