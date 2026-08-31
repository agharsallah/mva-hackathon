import type { ReactNode } from 'react';
import type { HypothesisRow } from '../../api/types';
import { C } from '../../lib/palette';

/**
 * The bits both register widgets share: the confidence caveat, the status palette, and the
 * latest-revision rule.
 *
 * The caveat is a constant rather than prose typed twice, because `docs/method.md` requires
 * it to appear wherever a confidence number does, in the same words.
 */

/** Repeated verbatim beside every confidence number on this page. */
export const CONFIDENCE_CAVEAT =
  'a transparent heuristic for triage, not a calibrated posterior';

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
      const rank =
        STATUS_ORDER.indexOf(a.latest.status) - STATUS_ORDER.indexOf(b.latest.status);
      return rank !== 0 ? rank : a.latest.hypothesis_id.localeCompare(b.latest.hypothesis_id);
    });
}

/**
 * The empty register, as a designed state.
 *
 * There are two distinct empties and the page must not conflate them: the table has never
 * been written (`table_exists === false`), or it exists and holds nothing. Both mean no
 * claim has been made; only the first also means the register itself does not exist yet.
 */
export function EmptyRegister({
  tableExists,
  title,
  verb,
  children,
}: {
  tableExists: boolean;
  title: string;
  /** The `mva-science` verb that opens this table. */
  verb: string;
  children: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-dashed border-emerald-900/50 bg-emerald-950/10 p-6 text-center">
      <div className="text-sm font-medium text-emerald-400">{title}</div>
      <p className="mx-auto mt-1.5 max-w-2xl text-xs leading-relaxed text-zinc-400">{children}</p>
      <p className="mx-auto mt-2 max-w-2xl text-[11px] leading-relaxed text-zinc-500">
        An empty register is discipline, not absence of work. The method is written down in{' '}
        <span className="font-mono text-zinc-400">docs/method.md</span>, and the register opens the moment
        the first claim is filed with <span className="font-mono text-zinc-400">{verb}</span>.
      </p>
      <p className="mt-2 font-mono text-[11px] text-zinc-600">
        {tableExists
          ? 'table exists · 0 rows'
          : 'table not created yet — written on first record, never by a page load'}
      </p>
    </div>
  );
}

/** A confidence number that always carries its caveat. Renders a gap, never a zero. */
export function Confidence({ value, inline = false }: { value: number | null; inline?: boolean }) {
  if (value === null || value === undefined) {
    return (
      <span className="font-mono text-zinc-600" title="no verdict committed yet">
        —
      </span>
    );
  }
  return (
    <span className={inline ? 'inline-flex items-baseline gap-1.5' : 'flex items-baseline gap-1.5'}>
      <span className="font-mono text-amber-400">{value.toFixed(2)}</span>
      <span className="text-[10px] leading-tight text-zinc-500">{CONFIDENCE_CAVEAT}</span>
    </span>
  );
}
