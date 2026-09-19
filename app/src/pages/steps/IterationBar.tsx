import type { IterationSummary } from '../../api/types';
import { Badge } from '../../components/Badge';
import { BOX, cx } from '../../lib/ui';

/**
 * The switcher, and the only place the whole journey is visible at once.
 *
 * `/steps` used to show one iteration — the one `mva.science.steps.ITERATION` names — so
 * iteration 1 (the route that produced the uploaded submission, answered *full match at
 * rank 1*) and iteration 4 (the model zoo, running now) had no surface in the app at all,
 * although `/api/steps?iteration=` had always served them.
 *
 * An iteration that was drafted and never declared is shown too, greyed and unclickable:
 * a journey that reads 1 → 2 → 4 with no explanation of the gap is a worse record than one
 * that says what happened to 3.
 */

function label(iteration: string): string {
  const digits = iteration.replace(/\D/g, '');
  return digits ? `Iteration ${digits}` : iteration;
}

/** Green once every step is finished, amber while one is open, grey before it starts. */
function tone(row: IterationSummary) {
  if (!row.declared) return 'neutral' as const;
  if (row.steps > 0 && row.done === row.steps) return 'good' as const;
  if (row.open > 0 || row.done > 0) return 'decision' as const;
  return 'neutral' as const;
}

export function IterationBar({
  index,
  selected,
  onSelect,
}: {
  index: IterationSummary[];
  selected: string;
  onSelect: (iteration: string) => void;
}) {
  return (
    <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      {index.map((row) => {
        const active = row.iteration === selected;
        return (
          <li key={row.iteration}>
            <button
              type="button"
              disabled={!row.declared}
              onClick={() => onSelect(row.iteration)}
              aria-current={active ? 'true' : undefined}
              className={cx(
                'h-full w-full space-y-2 rounded-card border p-3 text-left transition',
                BOX[tone(row)],
                active && 'ring-1 ring-machinery-500',
                row.declared
                  ? 'cursor-pointer hover:border-line-strong'
                  : 'cursor-not-allowed opacity-60',
                'focus:outline-none focus-visible:ring-1 focus-visible:ring-focus',
              )}
            >
              <div className="flex flex-wrap items-baseline gap-2">
                <span className="text-sm font-semibold text-chrome-50">{label(row.iteration)}</span>
                {row.current && <Badge tone="machinery">current</Badge>}
                {!row.declared && <Badge tone="neutral">not declared</Badge>}
              </div>

              <p className="text-micro leading-relaxed text-chrome-300">{row.summary}</p>

              <dl className="flex flex-wrap gap-x-4 gap-y-1 text-micro text-chrome-400">
                <div>
                  <dt className="inline text-chrome-500">steps </dt>
                  <dd className="inline font-mono text-chrome-200">
                    {row.done}/{row.steps}
                  </dd>
                </div>
                <div>
                  <dt className="inline text-chrome-500">claims </dt>
                  <dd className="inline font-mono text-chrome-200">{row.claims}</dd>
                </div>
                <div>
                  <dt className="inline text-chrome-500">submissions </dt>
                  <dd className="inline font-mono text-chrome-200">
                    {row.submissions.length > 0
                      ? row.submissions
                          .map((s) => `${s.track.replace('track', 'T')} ${s.state}`)
                          .join(' · ')
                      : 'none'}
                  </dd>
                </div>
              </dl>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
