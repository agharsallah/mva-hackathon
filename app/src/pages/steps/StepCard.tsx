import { Link } from 'react-router-dom';

import type { StepRow } from '../../api/types';
import { Badge } from '../../components/Badge';
import { FieldList } from '../../components/FieldList';
import { BOX, cx } from '../../lib/ui';
import { EntryList } from './EntryList';
import { FigureStrip } from './FigureStrip';
import { claimTone, detailPath, statusLabel, stepTone, TRACK_LABEL, verdictCounts } from './status';

/**
 * One step, as a card: its goal, which deliverable it feeds, what it claimed, what became
 * of the claims, what it wrote, and what it drew.
 *
 * Everything here is read from `/api/steps`. Nothing is written by hand, which is the
 * property that makes a new step — or a whole new iteration — appear on this page the
 * moment `mva.science.steps` declares it. The card used to end at a comma-joined list of
 * filenames; the figures are now shown and the methodology entries are readable in place,
 * so a reader can check a verdict without leaving the page.
 */
export function StepCard({
  step,
  iteration,
  track,
  origin,
  open = false,
}: {
  step: StepRow;
  iteration: string;
  /** Which track's page this card is on — it decides where "open the full step" goes. */
  track: string;
  /** `fixture` when the page is offline — the figure strip then names files, not images. */
  origin?: string;
  /** Start with the entries and figures shown. Track 2's iterations have one step each. */
  open?: boolean;
}) {
  const counts = verdictCounts(step);
  const detail = detailPath(step, iteration, track);

  return (
    <article className={cx('rounded border', BOX[stepTone(step)], 'space-y-3 p-4')} id={step.slug}>
      <header className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h3 className="text-sm font-semibold text-chrome-50">
          {step.slug} — {step.title}
        </h3>
        <Badge tone={stepTone(step)}>{statusLabel(step)}</Badge>
        <Badge tone={step.track === 'track2' ? 'raw' : 'machinery'}>
          {TRACK_LABEL[step.track] ?? step.track}
        </Badge>
        {counts.supported > 0 && <Badge tone="good">{counts.supported} supported</Badge>}
        {counts.refuted > 0 && <Badge tone="broken">{counts.refuted} refuted</Badge>}
        {counts.open > 0 && <Badge tone="machinery">{counts.open} open</Badge>}
        {detail && (
          <Link
            to={detail}
            className="ml-auto text-micro text-machinery-300 underline decoration-machinery-700 underline-offset-2 hover:text-machinery-200"
          >
            open the full step →
          </Link>
        )}
      </header>

      <p className="text-xs text-chrome-300">{step.goal}</p>

      {step.narrative && (
        <p className="border-l-2 border-line-soft pl-3 text-xs leading-relaxed text-chrome-200">
          {step.narrative.summary}
        </p>
      )}

      {step.hypotheses.length > 0 && (
        <ul className="space-y-2">
          {step.hypotheses.map((claim) => (
            <li key={claim.hypothesis_id} className="flex gap-2 text-xs">
              <Badge tone={claimTone(String(claim.status))}>{claim.hypothesis_id}</Badge>
              <span className="text-chrome-300">
                {claim.statement}
                {claim.confidence !== null && (
                  <span className="text-chrome-500">
                    {' '}
                    · confidence {claim.confidence.toFixed(2)}
                  </span>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}

      {step.kind === 'platform' && (
        <p className="text-micro text-chrome-500">
          A platform step records decisions, not claims about the patient, so it files no
          hypotheses.
        </p>
      )}

      {step.takes_hypotheses && (
        <details open={open} className="rounded-control border border-line-soft bg-well/40">
          <summary className="cursor-pointer px-2 py-1.5 text-micro text-chrome-300 hover:text-chrome-50">
            What this step wrote and drew — {step.entries.length}{' '}
            {step.entries.length === 1 ? 'entry' : 'entries'}, {step.figures.length}{' '}
            {step.figures.length === 1 ? 'figure' : 'figures'}
          </summary>
          <div className="space-y-3 border-t border-line-soft p-2">
            <EntryList iteration={iteration} slug={step.slug} entries={step.entries} />
            <FigureStrip figures={step.figures} origin={origin} />
          </div>
        </details>
      )}

      <FieldList
        fields={[
          { key: 'record', label: 'record', value: step.docs },
          {
            key: 'unblocks',
            label: 'unblocks',
            value: step.unblocks.length > 0 ? step.unblocks.join(', ') : 'nothing downstream',
          },
        ]}
      />
    </article>
  );
}
