import type { Step1Gate } from '../../../api/types';
import { cx } from '../../../lib/ui';

/** Percentages where the metric is a fraction; a bare count otherwise. */
function show(gate: Step1Gate, value: number | null): string {
  if (value === null) return '—';
  return gate.metric === 'mechanism_term_genes'
    ? value.toLocaleString()
    : `${(value * 100).toFixed(1)}%`;
}

/**
 * The four promises step 1 filed **before** the run, each beside what the run measured.
 *
 * Three of them were missed, and they stay on the page in red. The verdict column is
 * computed from the served numbers rather than typed, so a re-run that moves a measurement
 * moves the colour with it and nobody can leave a stale "pass" behind.
 */
export function Gates({ rows }: { rows: Step1Gate[] }) {
  return (
    <div className="space-y-2">
      {rows.map((gate) => (
        <div
          key={gate.claim}
          className={cx(
            'border-l-2 py-1 pl-3',
            gate.held === null
              ? 'border-chrome-700'
              : gate.held
                ? 'border-good-500'
                : 'border-broken-500',
          )}
        >
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <span className="text-sm font-medium">
              {gate.claim} — {gate.unit}
            </span>
            <span
              className={cx(
                'tabular-nums text-sm font-semibold',
                gate.held === null
                  ? 'text-chrome-400'
                  : gate.held
                    ? 'text-good-400'
                    : 'text-broken-400',
              )}
            >
              {show(gate, gate.observed)} vs {show(gate, gate.predicted)}{' '}
              {gate.held === null ? 'not run' : gate.held ? 'held' : 'REFUTED'}
            </span>
          </div>
          <div className="text-xs text-chrome-400">{gate.question}</div>
        </div>
      ))}
    </div>
  );
}
