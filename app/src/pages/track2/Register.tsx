/**
 * The step-8 claims, as the research register holds them.
 *
 * Both were filed **before** any search ran, each with the observation that would kill it.
 * That ordering is the whole method: a drug list assembled first and justified afterwards
 * cannot be wrong, and a claim that cannot be wrong is not evidence.
 */

import { Link } from 'react-router-dom';

import type { Track2RegisterEntry } from '../../api/types';
import { Badge } from '../../components/Badge';
import { Chip, Exhibit } from '../../components/Exhibit';
import { type Tone } from '../../lib/palette';
import { C } from '../../lib/palette';
import { cx, RULE, WELL } from '../../lib/ui';
import { T } from './Term';

const STATUS_TONE: Record<string, Tone> = {
  supported: 'good',
  refuted: 'broken',
  testing: 'decision',
  proposed: 'machinery',
};

const toneOf = (s: string): Tone => STATUS_TONE[s] ?? 'neutral';

export function Register({
  register,
  source,
}: {
  register: Track2RegisterEntry[];
  source?: string;
}) {
  return (
    <Exhibit
      title="The register — what Track 2 claimed before it searched"
      legend={
        <>
          One card per claim. <Chip color={C.good}>green = supported</Chip> by evidence recorded
          against it; <Chip color={C.machinery}>blue = proposed</Chip>, filed but not yet tested;{' '}
          <Chip color={C.decision}>yellow = testing</Chip>, waiting on a measurement;{' '}
          <Chip color={C.broken}>red = refuted</Chip>. The confidence figure is a stated triage
          heuristic with its arithmetic printed on the Science page — never quote it as a
          probability.
        </>
      }
      reading={`${register.length} claims, both filed before the first snapshot ran. Each carries the observation that would refute it, which is what makes the drug table below testable rather than decorative.`}
      data={register}
      source={source}
    >
      <ul className="grid gap-3 lg:grid-cols-2">
        {register.map((h) => {
          const tone = toneOf(h.status);
          return (
            <li
              key={h.hypothesis_id}
              data-hypothesis={h.hypothesis_id}
              data-status={h.status}
              className={cx(WELL, 'space-y-2 border-l-2', RULE[tone])}
            >
              <div className="flex flex-wrap items-center gap-2">
                <Link to={`/science?hypothesis=${h.hypothesis_id}`}>
                  <Badge tone="machinery">{h.hypothesis_id}</Badge>
                </Link>
                <Badge tone={tone}>{h.status}</Badge>
                <span className="font-mono text-micro text-chrome-600">
                  revision {h.revision}
                  {h.confidence === null
                    ? ' · no verdict yet'
                    : ` · heuristic ${h.confidence.toFixed(2)}`}
                </span>
              </div>
              <p className="text-sm leading-relaxed text-chrome-200">{h.statement}</p>
              <dl className="space-y-1 text-micro leading-relaxed">
                <div>
                  <dt className="inline font-semibold text-chrome-300">Prediction: </dt>
                  <dd className="inline text-chrome-400">{h.prediction}</dd>
                </div>
                <div>
                  <dt className="inline font-semibold text-broken-400">Refuted by: </dt>
                  <dd className="inline text-chrome-400">{h.refuted_by}</dd>
                </div>
              </dl>
            </li>
          );
        })}
      </ul>
      <p className="mt-3 max-w-[95ch] text-micro leading-relaxed text-chrome-500">
        A{' '}
        <T
          slug="hypothesis"
          term="hypothesis"
          plain="a claim written down with a prediction and the observation that would kill it, before the test runs"
        />{' '}
        is the unit of belief in this repository. The full board, with every evidence row behind
        these two, is on the{' '}
        <Link
          to="/science"
          className="underline decoration-chrome-600 underline-offset-2 hover:text-chrome-50"
        >
          Science
        </Link>{' '}
        page.
      </p>
    </Exhibit>
  );
}
