import { Link } from 'react-router-dom';

import type { SubmissionIteration } from '../../api/types';
import { Badge } from '../../components/Badge';
import { StatTile } from '../../components/StatTile';
import { cx, WELL } from '../../lib/ui';
import { blobUrl, iterationKey, PANEL_DELIVERABLES, STATE_MEANING, STATE_TONE } from './iteration';

/**
 * The header strip: which iteration this is, whether it has been sent, and the one number
 * that identifies the file the organisers would receive.
 *
 * The predictions CSV is the only artefact of this project that carries genomic positions,
 * so it is deliberately **not** in the repository. Its sha256 is — a content hash names
 * bytes without carrying them, which is what lets this page talk about the file at all.
 */
export function IterationHeader({
  iteration,
  panelJudged = false,
}: {
  iteration: SubmissionIteration;
  /** A track with no scorer: no predictions file, and the oracle budget is not its to spend. */
  panelJudged?: boolean;
}) {
  const { csv, state } = iteration;
  const spent = iteration.audit.probes.length;

  return (
    <div className={cx(WELL, 'space-y-3')}>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-2">
        <h2 className="text-sm font-semibold tracking-tight text-chrome-100">
          <span className="font-mono">{iteration.track}</span> · iteration {iteration.number}
        </h2>
        <Badge tone={STATE_TONE[state]} title={STATE_MEANING[state]}>
          {state}
          {state === 'frozen' ? ' · uploaded' : ''}
        </Badge>
        <a
          href={blobUrl(iteration.folder)}
          className="font-mono text-micro text-machinery-300 underline decoration-machinery-700 underline-offset-2 hover:text-machinery-200"
        >
          {iterationKey(iteration)}
        </a>
      </div>

      <p className="max-w-[90ch] font-serif text-note leading-relaxed text-chrome-300">
        {iteration.standing}
      </p>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {panelJudged ? (
          <StatTile
            label="how it is judged"
            tone="machinery"
            value="panel"
            sub={PANEL_DELIVERABLES.join(' · ')}
          />
        ) : (
          <StatTile
            label="predictions CSV"
            tone="raw"
            value={
              <span className="font-mono text-sm break-all" title={csv.sha256 ?? 'not built'}>
                {csv.sha256 ? `${csv.sha256.slice(0, 16)}…` : '—'}
              </span>
            }
            sub={
              <>
                sha256 · {csv.rows ?? '—'} rows ·{' '}
                <span className="text-raw-300">never committed</span> — it holds real coordinates,
                so it lives at <span className="font-mono">{csv.path ?? 'build/submission/'}</span>,
                outside the repository
              </>
            }
          />
        )}
        <StatTile
          label="oracle budget"
          tone={spent === 0 ? 'good' : 'decision'}
          value={
            <>
              {6 - spent}
              <span className="text-lg text-chrome-400"> / 6</span>
            </>
          }
          sub={
            <>
              {panelJudged
                ? 'Track 2 has no scorer — the six uploads belong to Track 1'
                : `${spent} spent on this iteration`}{' '}
              · irreversible ·{' '}
              <Link
                to="/probes"
                className="underline decoration-chrome-600 underline-offset-2 hover:text-chrome-200"
              >
                open Probes
              </Link>
            </>
          }
        />
        <StatTile
          label="claims behind it"
          tone="machinery"
          value={iteration.hypotheses.length}
          sub={`${iteration.contributions.length} roadmap steps contributed · ${iteration.deliverables.length} files in the folder`}
        />
      </div>
    </div>
  );
}
