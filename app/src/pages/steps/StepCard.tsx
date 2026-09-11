import type { StepRow } from '../../api/types';
import { Badge } from '../../components/Badge';
import { FieldList } from '../../components/FieldList';
import { BOX, cx } from '../../lib/ui';
import { claimTone, statusLabel, stepTone, verdictCounts } from './status';

/**
 * One step, as a card: its goal, what it claimed, and what became of the claims.
 *
 * Everything here is read from `/api/steps`. Nothing is written by hand, which is the
 * property that makes a new step — or a whole new iteration — appear on this page the
 * moment `mva.science.steps` declares it.
 */
export function StepCard({ step }: { step: StepRow }) {
  const counts = verdictCounts(step);

  return (
    <article className={cx('rounded border', BOX[stepTone(step)], 'space-y-3 p-4')} id={step.slug}>
      <header className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h3 className="text-sm font-semibold text-chrome-50">
          {step.slug} — {step.title}
        </h3>
        <Badge tone={stepTone(step)}>{statusLabel(step)}</Badge>
        {counts.supported > 0 && <Badge tone="good">{counts.supported} supported</Badge>}
        {counts.refuted > 0 && <Badge tone="broken">{counts.refuted} refuted</Badge>}
        {counts.open > 0 && <Badge tone="machinery">{counts.open} open</Badge>}
      </header>

      <p className="text-xs text-chrome-300">{step.goal}</p>

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

      <FieldList
        fields={[
          { key: 'record', label: 'record', value: step.docs },
          {
            key: 'unblocks',
            label: 'unblocks',
            value: step.unblocks.length > 0 ? step.unblocks.join(', ') : 'nothing downstream',
          },
          {
            key: 'entries',
            label: 'entries',
            value:
              step.entries.length > 0
                ? step.entries.map((entry) => entry.entry).join(', ')
                : 'none written yet',
          },
          {
            key: 'figures',
            label: 'figures',
            value: step.figures.length > 0 ? step.figures.join(', ') : 'none drawn yet',
          },
        ]}
      />
    </article>
  );
}
