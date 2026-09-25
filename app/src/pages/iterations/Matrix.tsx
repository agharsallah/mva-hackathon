import { Link } from 'react-router-dom';

import type {
  IterationsOverview,
  ResearchIterationOverview,
  SubmissionOverview,
} from '../../api/types';
import { Badge } from '../../components/Badge';
import { REPO_BLOB } from '../../lib/dictionary';
import { TONE_MARK } from '../../lib/palette';
import { cx } from '../../lib/ui';
import { plainSummary } from '../steps/route';
import { claimTone } from '../steps/status';
import { STATE_MEANING, STATE_TONE } from '../submissions/iteration';
import {
  claimSegments,
  claimTotal,
  foldersFor,
  iterationNumber,
  primaryResearch,
  shortReply,
  stepsFor,
  type TrackKey,
  TRACKS,
} from './model';
import { SegmentBar } from './SegmentBar';

/**
 * The matrix: research iterations down, the two tracks across. A cell answers "what did
 * this route through the case do for this track" — how many declared steps feed it, where
 * they are, and which submission folders cite it. The row header carries what belongs to
 * the iteration as a whole: its summary, its claims (the register is per iteration, not per
 * track) and a link to the data its entries name.
 */

const TRACK_HEAD: Record<TrackKey, string> = {
  track1: 'Track 1 — the variant pair (oracle-scored)',
  track2: 'Track 2 — the drugs (panel-judged)',
};

/** A folder, not a file: GitHub's tree view of the iteration's docs. */
const REPO_TREE = REPO_BLOB.replace('/blob/', '/tree/');

const LINK =
  'text-machinery-300 underline decoration-machinery-800 underline-offset-2 hover:text-machinery-200';

export function Matrix({ data }: { data: IterationsOverview }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] border-separate border-spacing-2 text-left text-xs">
        <thead>
          <tr>
            <th scope="col" className="w-[34%] px-1 font-medium text-chrome-400">
              research iteration
            </th>
            {TRACKS.map((t) => (
              <th key={t} scope="col" className="w-[33%] px-1 font-medium text-chrome-400">
                {TRACK_HEAD[t]}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.research.map((r) => (
            <tr key={r.iteration} className="align-top">
              <RowHead research={r} />
              {TRACKS.map((t) => (
                <Cell key={t} research={r} track={t} submissions={data.submissions} />
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RowHead({ research: r }: { research: ResearchIterationOverview }) {
  const claims = claimSegments(r.claims);
  const total = claimTotal(r.claims);
  return (
    <th
      scope="row"
      className={cx(
        'space-y-2 rounded-card border p-3 font-normal',
        r.declared ? 'border-line bg-panel' : 'border-dashed border-line bg-transparent',
      )}
    >
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="text-sm font-semibold text-chrome-50">
          Iteration {iterationNumber(r.iteration)}
        </span>
        {r.current && <Badge tone="machinery">current</Badge>}
        {!r.declared && (
          <Badge tone="neutral" title="a plan with no step map: nothing ran under this number">
            plan only
          </Badge>
        )}
      </div>
      <p className="text-micro leading-relaxed text-chrome-300">{plainSummary(r.summary)}</p>
      {r.declared && (
        <dl className="flex flex-wrap gap-x-3 gap-y-1 text-micro text-chrome-400">
          <div>
            <dt className="inline text-chrome-500">steps </dt>
            <dd className="inline font-mono text-chrome-200">
              {r.done}/{r.steps}
            </dd>
          </div>
          <div>
            <dt className="inline text-chrome-500">entries </dt>
            <dd className="inline font-mono text-chrome-200">
              {r.entries.count}
              {r.entries.count > 0 && (
                <span className="text-chrome-500">
                  {' '}
                  ({r.entries.first}–{r.entries.last})
                </span>
              )}
            </dd>
          </div>
          <div>
            <dt className="inline text-chrome-500">datasets </dt>
            <dd className="inline font-mono text-chrome-200">{r.catalog.coverage.datasets}</dd>
          </div>
        </dl>
      )}
      {total > 0 && (
        <div className="space-y-1">
          <SegmentBar
            label={`claims of ${r.iteration}`}
            height={6}
            segments={claims.map(([status, n]) => ({
              key: status,
              value: n,
              color: TONE_MARK[claimTone(status)],
              label: status,
            }))}
          />
          <p className="text-micro text-chrome-400">
            {total} claims ·{' '}
            {claims.map(([status, n], i) => (
              <span key={status}>
                {i > 0 && ' · '}
                {n} {status}
              </span>
            ))}
          </p>
        </div>
      )}
      <div className="flex flex-wrap gap-x-3 text-micro">
        {r.declared && (
          <Link to={`/iterations?cat=${r.iteration}#data-catalog`} className={LINK}>
            its data catalogue
          </Link>
        )}
        <a href={`${REPO_TREE}${r.docs}`} className={LINK}>
          {r.docs}
        </a>
      </div>
    </th>
  );
}

function Cell({
  research,
  track,
  submissions,
}: {
  research: ResearchIterationOverview;
  track: TrackKey;
  submissions: SubmissionOverview[];
}) {
  const steps = stepsFor(research, track);
  const route = research.routes[track];
  const folders = foldersFor(research, track, submissions);
  const empty = steps === 0 && folders.length === 0;
  const built = folders.filter((f) => primaryResearch(f) === research.iteration);
  const cited = folders.filter((f) => primaryResearch(f) !== research.iteration);

  return (
    <td
      className={cx(
        'space-y-2 rounded-card border p-3',
        empty ? 'border-dashed border-line-soft' : 'border-line bg-panel',
      )}
    >
      {route ? (
        <Link to={route} className={cx(LINK, 'text-xs')}>
          {steps} step{steps === 1 ? '' : 's'} feed{steps === 1 ? 's' : ''} this track →
        </Link>
      ) : (
        <p className="text-micro text-chrome-500">
          {research.declared ? 'no step for this track' : 'nothing ran'}
        </p>
      )}
      {built.length > 0 && (
        <div className="space-y-1">
          <p className="text-micro text-chrome-400">built from here</p>
          <ul className="space-y-1">
            {built.map((f) => (
              <li key={f.key} className="flex flex-wrap items-center gap-2">
                <Link to={`/submissions?it=${f.key}`} className={cx(LINK, 'font-mono text-micro')}>
                  {f.key}
                </Link>
                <Badge tone={STATE_TONE[f.state]} title={STATE_MEANING[f.state]}>
                  {f.state}
                </Badge>
                {f.reply && (
                  <span className="text-micro text-good-300" title={f.reply}>
                    {shortReply(f.reply)}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      {cited.length > 0 && (
        <p className="text-micro text-chrome-500">
          also cited by{' '}
          {cited.map((f, i) => (
            <span key={f.key}>
              {i > 0 && ', '}
              <Link
                to={`/submissions?it=${f.key}`}
                className="font-mono text-chrome-400 hover:text-machinery-200"
                title={`${f.key} (${f.state}) quotes an entry of this iteration; it is built from a later one`}
              >
                {f.key}
              </Link>
            </span>
          ))}
        </p>
      )}
      {folders.length === 0 && research.declared && (
        <p className="text-micro text-chrome-500">cited by no submission folder</p>
      )}
    </td>
  );
}
