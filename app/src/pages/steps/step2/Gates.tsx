import type { Step2Funnel } from '../../../api/types';
import { cx } from '../../../lib/ui';
import { gates } from './metrics';

/**
 * The pre-registered gates, with the one that failed still on the page.
 *
 * Each row is a promise made before the run and the number that kept or broke it. The
 * off-target gate failed at 8.79% against a 5% line, and entry 086 showed no available
 * parameter reaches it — so it is drawn red and stays. Removing a gate after missing it
 * is the failure mode this whole step was written to avoid.
 */
export function Gates({ rows }: { rows: Step2Funnel[] }) {
  const checked = gates(rows);
  return (
    <div className="space-y-2">
      {checked.map((gate) => (
        <div
          key={gate.name}
          className={cx(
            'border-l-2 py-1 pl-3',
            gate.passed ? 'border-good-500' : 'border-broken-500',
          )}
        >
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <span className="text-sm font-medium">{gate.name}</span>
            <span
              className={cx(
                'tabular-nums text-sm font-semibold',
                gate.passed ? 'text-good-400' : 'text-broken-400',
              )}
            >
              {gate.measured} {gate.passed ? 'pass' : 'FAIL'}
            </span>
          </div>
          <div className="text-xs text-chrome-400">{gate.asked}</div>
          {gate.note && <div className="mt-1 text-xs text-broken-400">{gate.note}</div>}
        </div>
      ))}
    </div>
  );
}
