import { Link } from 'react-router-dom';

import type { IterationSummary } from '../../api/types';
import { Badge } from '../../components/Badge';
import { BOX, cx } from '../../lib/ui';
import { iterationLabel, plainSummary, type TrackId } from './route';

/**
 * The iterations of one track, as the way into them.
 *
 * `/steps` used to show one iteration — the one `mva.science.steps.ITERATION` names — so
 * iteration 1 (the route that produced the uploaded submission, answered *full match at rank
 * 1*) and iteration 4 had no surface in the app at all, although `/api/steps?iteration=` had
 * always served them. Each card is now a link into that iteration's own steps.
 *
 * An iteration that was drafted and never declared is shown too, greyed and unclickable: a
 * journey that reads 1 → 2 → 4 with no explanation of the gap is a worse record than one
 * that says what happened to 3.
 */

/** Green once every step is finished, amber while one is open, grey before it starts. */
function tone(row: IterationSummary) {
  if (!row.declared) return 'neutral' as const;
  if (row.steps > 0 && row.done === row.steps) return 'good' as const;
  if (row.open > 0 || row.done > 0) return 'decision' as const;
  return 'neutral' as const;
}

function Face({ row, track }: { row: IterationSummary; track: TrackId }) {
  return (
    <>
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="text-sm font-semibold text-chrome-50 capitalize">
          {iterationLabel(row.iteration)}
        </span>
        {row.current && <Badge tone="machinery">current</Badge>}
        {!row.declared && <Badge tone="neutral">not declared</Badge>}
      </div>

      <p className="text-micro leading-relaxed text-chrome-300">{plainSummary(row.summary)}</p>

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
          <dt className="inline text-chrome-500">submission </dt>
          <dd className="inline font-mono text-chrome-200">
            {row.submissions.find((s) => s.track === track)?.state ?? 'none'}
          </dd>
        </div>
      </dl>
    </>
  );
}

export function IterationBar({ index, track }: { index: IterationSummary[]; track: TrackId }) {
  return (
    <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      {index.map((row) => {
        const shell = cx('h-full space-y-2 rounded-card border p-3 text-left', BOX[tone(row)]);
        return (
          <li key={row.iteration}>
            {row.declared ? (
              <Link
                to={`/${track}/${row.iteration}`}
                className={cx(
                  shell,
                  'block transition hover:border-line-strong',
                  'focus:outline-none focus-visible:ring-1 focus-visible:ring-focus',
                )}
              >
                <Face row={row} track={track} />
                <p className="text-micro text-machinery-300">open its steps →</p>
              </Link>
            ) : (
              <div className={cx(shell, 'opacity-60')}>
                <Face row={row} track={track} />
                <p className="text-micro text-chrome-500">
                  no step map, so there is nothing to open
                </p>
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
