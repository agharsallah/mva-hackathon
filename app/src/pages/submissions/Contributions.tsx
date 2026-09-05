import { Link } from 'react-router-dom';

import type { StepContribution, SubmissionIteration } from '../../api/types';
import { Badge } from '../../components/Badge';
import { type Column, DataTable } from '../../components/DataTable';
import { Chip, Exhibit } from '../../components/Exhibit';
import { C } from '../../lib/palette';
import { blobUrl } from './iteration';

/**
 * Which roadmap steps contributed, and where the evidence is.
 *
 * A step does not own a deliverable — it *contributes* to an iteration. This table is that
 * relation, and every methodology link is the append-only entry that produced the claim:
 * question, inputs, exact commands, observed output, verdict. Following one is how a
 * reviewer checks a number without re-running anything.
 */
export function Contributions({
  iteration,
  source,
}: {
  iteration: SubmissionIteration;
  source?: string;
}) {
  const columns: Column<StepContribution>[] = [
    {
      key: 'step',
      header: 'step',
      render: (r) => <span className="font-mono text-chrome-100">{r.step}</span>,
    },
    {
      key: 'contribution',
      header: 'what it contributed',
      render: (r) => <span className="text-chrome-300">{r.contribution}</span>,
    },
    {
      key: 'methodology',
      header: 'methodology entry',
      render: (r) =>
        r.methodology.length === 0 ? (
          <span className="text-chrome-600">—</span>
        ) : (
          <span className="flex flex-wrap gap-2">
            {r.methodology.map((m) => (
              <a
                key={m.path}
                href={blobUrl(m.path)}
                title={m.path}
                className="rounded-pill border border-machinery-900 bg-machinery-950/60 px-2 py-0.5 font-mono text-micro text-machinery-400 hover:text-machinery-200"
              >
                {m.label}
              </a>
            ))}
          </span>
        ),
    },
  ];

  return (
    <Exhibit
      title="Which steps contributed"
      legend={
        <>
          One row per roadmap step that put something into this iteration.{' '}
          <Chip color={C.machinery}>blue = neutral machinery</Chip> — a methodology entry, linked to
          its file on GitHub; the entries are append-only, so a link cannot rot into a rewritten
          claim. The badges below are the register claims this iteration rests on: each one was
          filed with a prediction and a refutation condition <em>before</em> its test ran.
        </>
      }
      reading="An iteration folder is frozen once uploaded, but its evidence is not in the folder — it stays in the step that produced it. This table is the join, and it is the shortest path from the file the organisers receive to the run that justified a row in it."
      data={iteration.contributions}
      source={source}
    >
      <div className="space-y-3">
        <DataTable
          rows={iteration.contributions}
          columns={columns}
          rowKey={(r) => r.step}
          empty="no step contribution table in this iteration's README"
        />
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-chrome-500">Claims referenced</span>
          {iteration.hypotheses.length === 0 ? (
            <span className="text-xs text-chrome-600">none named in this folder</span>
          ) : (
            iteration.hypotheses.map((id) => (
              <Link key={id} to="/science" title={`open ${id} in the research register`}>
                <Badge tone="machinery">{id}</Badge>
              </Link>
            ))
          )}
        </div>
      </div>
    </Exhibit>
  );
}
