/**
 * Reading the step-2 funnel: one metric out of a long, flat list of them.
 *
 * `it2_bait_qc` is `(stage, metric, value, note)` because a funnel that grows a stage
 * should not need a schema change. The cost is that the page has to look rows up by name,
 * and a typo would silently render a blank rather than fail — so every lookup goes through
 * `metric`, which returns `null` for an absent row, and every caller decides what an
 * absent number should say.
 */

import type { Step2Funnel } from '../../../api/types';

/** One metric's value, or `null` when the run never recorded it. */
export function metric(rows: Step2Funnel[], stage: string, name: string): number | null {
  const found = rows.find((r) => r.stage === stage && r.metric === name);
  return found ? found.value : null;
}

/** The note a metric carries — where a gate failed, this is why. */
export function note(rows: Step2Funnel[], stage: string, name: string): string | null {
  return rows.find((r) => r.stage === stage && r.metric === name)?.note ?? null;
}

/** `1,071,835,104`. An absent number is an em dash, never a zero. */
export function count(value: number | null, digits = 0): string {
  return value === null
    ? '—'
    : value.toLocaleString('en-US', {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      });
}

/** `1.368%` — a fraction as a percentage, at the precision the number deserves. */
export function percent(value: number | null, digits = 2): string {
  return value === null ? '—' : `${(value * 100).toFixed(digits)}%`;
}

/** One pre-registered gate: what it asked, what was measured, and whether it held. */
export interface Gate {
  name: string;
  asked: string;
  measured: string;
  passed: boolean;
  /** Why it failed, or what the failure does not invalidate. */
  note?: string;
}

/**
 * The step's gates, computed from the funnel rather than listed.
 *
 * The off-target gate **failed** and is shown failing. A page that quietly dropped it
 * would be the whole problem this step spent an entry arguing about: a threshold that
 * disappears after it is missed is not a threshold.
 */
export function gates(rows: Step2Funnel[]): Gate[] {
  const expected = metric(rows, 'bait', 'expected_reads');
  const matched = metric(rows, 'pass', 'reads_matched');
  const ratio = expected && matched ? matched / expected : null;
  const offTarget = metric(rows, 'uniqueness', 'off_target_fraction');
  const unseen = metric(rows, 'uniqueness', 'unseen');
  const dropped = metric(rows, 'recover', 'dropped');
  const mapped = metric(rows, 'align', 'mapped_fraction');

  return [
    {
      name: 'bait k-mers found in the reference',
      asked: 'every bait k-mer was cut from this reference, so none may be unseen',
      measured: `${count(unseen)} unseen`,
      passed: unseen === 0,
    },
    {
      name: 'off-target k-mers',
      asked: 'under 5% of the bait also occurs elsewhere in the genome',
      measured: percent(offTarget),
      passed: offTarget !== null && offTarget < 0.05,
      note: note(rows, 'uniqueness', 'off_target_fraction') ?? undefined,
    },
    {
      name: 'reads recovered against prediction',
      asked: 'within 0.5x to 2x of the count the bait footprint predicts',
      measured: ratio === null ? '—' : `${ratio.toFixed(2)}x`,
      passed: ratio !== null && ratio >= 0.5 && ratio <= 2,
    },
    {
      name: 'every fragment complete',
      asked: 'no read is written to FASTQ without its mate',
      measured: `${count(dropped)} dropped`,
      passed: dropped === 0,
    },
    {
      name: 'on-target rate',
      asked: 'at least 80% of recovered reads align',
      measured: percent(mapped),
      passed: mapped !== null && mapped >= 0.8,
    },
  ];
}
