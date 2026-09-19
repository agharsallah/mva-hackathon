import { Link } from 'react-router-dom';

import type { StepJoin, StepNarrative } from '../../api/types';
import { Callout } from '../../components/Explainer';
import { BOX, cx } from '../../lib/ui';
import { stepLabel, type TrackId } from './route';

/**
 * What a step *says* — the half of the record that no query can produce.
 *
 * The goal comes from the step map, the claims from the register, the entries from the
 * blind gate, the figures from the filesystem. None of that says what the step concluded,
 * why the question had to be asked where it was, or what the next step does with the
 * answer. Those are judgements, written by hand beside the step's README and validated by
 * `tools/check_step_narrative.py`, which fails the build when a step that has run has none.
 *
 * **The joins are the point.** A journey is not a list: step 4 exists because step 2's
 * filter threw away the thing step 4 had to score. `inherits` and `hands_to` carry that,
 * and each names real steps, so the reader can walk the argument in either direction.
 */

function Join({
  join,
  track,
  iteration,
  label,
  arrow,
  linkable,
}: {
  join: StepJoin;
  track: TrackId;
  iteration: string;
  label: string;
  arrow: string;
  /** Slugs that have a page. A narrative may name `step-0`, the platform, which has none. */
  linkable: ReadonlySet<string>;
}) {
  const chip = 'rounded-pill border border-line px-2 py-px font-mono text-micro transition';
  return (
    <div className={cx('space-y-2 rounded-card border p-3', BOX.machinery)}>
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="text-micro tracking-wide text-chrome-500 uppercase">{label}</span>
        {join.steps.length > 0 ? (
          join.steps.map((slug) =>
            linkable.has(slug) ? (
              <Link
                key={slug}
                to={`/${track}/${iteration}/${slug}`}
                className={cx(
                  chip,
                  'text-machinery-300 hover:border-line-strong hover:text-machinery-200',
                )}
              >
                {arrow} {stepLabel(slug)}
              </Link>
            ) : (
              <span key={slug} className={cx(chip, 'text-chrome-500')} title="no page of its own">
                {arrow} {stepLabel(slug)}
              </span>
            ),
          )
        ) : (
          <span className="text-micro text-chrome-500">nothing</span>
        )}
      </div>
      <p className="text-xs leading-relaxed text-chrome-300">{join.what}</p>
    </div>
  );
}

export function Narrative({
  narrative,
  track,
  iteration,
  linkable,
}: {
  narrative: StepNarrative;
  track: TrackId;
  iteration: string;
  /** Slugs the tree has a page for — the caller knows, this component does not guess. */
  linkable: ReadonlySet<string>;
}) {
  return (
    <div className="space-y-3">
      <p className="font-serif text-note leading-relaxed text-chrome-100">{narrative.summary}</p>

      <div className="grid gap-3 lg:grid-cols-2">
        <Callout tone="machinery" title="Why this step exists here">
          {narrative.why}
        </Callout>
        <Callout tone="good" title="What it concluded">
          {narrative.verdict}
        </Callout>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <Join
          join={narrative.inherits}
          track={track}
          iteration={iteration}
          label="it could not start without"
          arrow="←"
          linkable={linkable}
        />
        <Join
          join={narrative.hands_to}
          track={track}
          iteration={iteration}
          label="what happens next with it"
          arrow="→"
          linkable={linkable}
        />
      </div>

      <details className="rounded-control border border-line-soft bg-well/40">
        <summary className="cursor-pointer px-2 py-1.5 text-micro text-chrome-400 hover:text-chrome-200">
          Written from {narrative.sources.length} source
          {narrative.sources.length === 1 ? '' : 's'}
        </summary>
        <ul className="space-y-1 border-t border-line-soft p-2">
          {narrative.sources.map((source) => (
            <li key={source} className="font-mono text-micro break-all text-chrome-500">
              {source}
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}
