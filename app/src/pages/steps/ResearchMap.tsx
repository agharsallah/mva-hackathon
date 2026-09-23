import { Link } from 'react-router-dom';

import { useSteps } from '../../api/hooksSteps';
import type { IterationSummary, StepRow } from '../../api/types';
import { Chip, Exhibit } from '../../components/Exhibit';
import { useJourney } from '../../components/journeyContext';
import { Loaded, Skeleton } from '../../components/QueryState';
import { C } from '../../lib/palette';
import { BOX, cx } from '../../lib/ui';
import { iterationLabel, stepLabel, type TrackId, tracksShownOn } from './route';
import { detailPath, stepTone, verdictCounts } from './status';
import { findPage, isStepPath } from './tree';

/**
 * Every step of every iteration of one track, on one screen — the map the header's three
 * rows only show one branch of at a time.
 *
 * One row per declared iteration, one tile per step in dependency order, coloured by the
 * step's status and carrying its verdict tally and figure count; the row ends with what the
 * iteration produced (its submission, and any page of its own such as the zoo). Every tile
 * is a link, so a reader can go from "which iteration refuted something?" to the entry that
 * did it in one click.
 *
 * Each row asks `/api/steps?iteration=` for its own map. Nothing is typed: a new iteration
 * or a new step appears here the moment the step map declares it.
 */

const LINK =
  'focus:outline-none focus-visible:ring-1 focus-visible:ring-focus transition hover:border-line-strong';

function Tile({ step, to }: { step: StepRow; to: string }) {
  const v = verdictCounts(step);
  const body = (
    <>
      <span className="font-mono text-micro text-chrome-400">{stepLabel(step.slug)}</span>
      <span className="block text-micro leading-snug font-medium text-chrome-100">
        {step.title}
      </span>
      <span className="mt-1 flex flex-wrap gap-x-2 text-micro text-chrome-400">
        {v.supported > 0 && <span className="text-good-300">✓{v.supported}</span>}
        {v.refuted > 0 && <span className="text-broken-300">✗{v.refuted}</span>}
        {v.open > 0 && <span className="text-machinery-300">?{v.open}</span>}
        {step.figures.length > 0 && <span>▦{step.figures.length}</span>}
      </span>
    </>
  );
  const shell = cx('block w-40 rounded-control border p-2', BOX[stepTone(step)]);
  return to ? (
    <Link to={to} title={step.goal} className={cx(shell, LINK)}>
      {body}
    </Link>
  ) : (
    <div title={step.goal} className={shell}>
      {body}
    </div>
  );
}

function Row({ row, track }: { row: IterationSummary; track: TrackId }) {
  const q = useSteps(row.iteration);
  const groups = useJourney();
  const base = `/${track}/${row.iteration}`;
  const node = groups.map((g) => findPage(g.pages, base)).find(Boolean);
  const pages = (node?.children ?? []).filter((c) => !isStepPath(c.to));
  const submission = row.submissions.find((s) => s.track === track);
  const wanted = tracksShownOn(track);
  const steps = (q.data?.data.steps ?? []).filter(
    (s) => s.kind !== 'platform' && wanted.includes(String(s.track)),
  );

  return (
    <li className="grid gap-3 border-t border-line-soft py-3 first:border-t-0 lg:grid-cols-[9rem_1fr_12rem]">
      <Link to={base} className={cx('self-start rounded-control', LINK)}>
        <span className="block text-sm font-semibold text-chrome-50 capitalize">
          {iterationLabel(row.iteration)}
        </span>
        <span className="text-micro text-machinery-300">overview →</span>
      </Link>

      <div className="flex flex-wrap gap-2">
        {q.isPending ? (
          <Skeleton height={64} />
        ) : steps.length === 0 ? (
          <p className="text-micro text-chrome-500">No step of this track is declared here.</p>
        ) : (
          steps.map((s) => (
            // Track 2's steps have no page of their own; the iteration page shows them whole.
            <Tile key={s.slug} step={s} to={detailPath(s, row.iteration, track) || base} />
          ))
        )}
      </div>

      <div className="space-y-1 text-micro">
        <p className="text-chrome-400">
          submission{' '}
          {submission ? (
            <Link to="/submissions" className="font-mono text-machinery-300 underline">
              {submission.state}
            </Link>
          ) : (
            <span className="font-mono text-chrome-500">none</span>
          )}
        </p>
        {pages.map((p) => (
          <Link key={p.to} to={p.to} className="block text-machinery-300 underline">
            {p.label} →
          </Link>
        ))}
      </div>
    </li>
  );
}

export function ResearchMap({ index, track }: { index: IterationSummary[]; track: TrackId }) {
  return (
    <ul>
      {index
        .filter((row) => row.declared)
        .map((row) => (
          <Row key={row.iteration} row={row} track={track} />
        ))}
    </ul>
  );
}

/**
 * The map as an exhibit, with its own fetch of the iteration index: what a track page drops
 * in to show every route it has walked.
 */
export function TrackMap({ track }: { track: TrackId }) {
  const q = useSteps();
  return (
    <Exhibit
      title={`Every ${track === 'track1' ? 'Track 1' : 'Track 2'} step, iteration by iteration`}
      legend={
        <>
          One row per declared iteration, one tile per step in dependency order.{' '}
          <Chip color={C.good}>green</Chip> = done · <Chip color={C.decision}>amber</Chip> = open ·{' '}
          <Chip color={C.absent}>grey</Chip> = planned. On a tile: ✓ supported, ✗ refuted, ? still
          open claims, ▦ figures drawn. Hover a tile for the step&apos;s question.
        </>
      }
      reading={
        <>
          Read across a row for one route&apos;s progress, down a column for how far each route got
          at the same depth. Every tile opens its step; the right edge says what the iteration
          produced.
        </>
      }
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
      data={q.data?.data.index}
    >
      <Loaded query={q} height={260}>
        {(data) => <ResearchMap index={data.index} track={track} />}
      </Loaded>
    </Exhibit>
  );
}
