import { Link } from 'react-router-dom';

import type { StepSubmission } from '../../api/types';
import { Callout } from '../../components/Explainer';

/**
 * What this iteration's steps were *for*.
 *
 * A step contributes to a submission; it does not own one. The journey page never said
 * which folder its work ended up in, so the two halves of the record — the steps here and
 * the dossier on `/submissions` — read as unrelated pages. This is the link between them,
 * built from the folders that exist on disk rather than from a hand-kept list.
 */
export function Submissions({ rows, iteration }: { rows: StepSubmission[]; iteration: string }) {
  if (rows.length === 0) {
    return (
      <Callout tone="machinery" title="This iteration files no submission of its own">
        No <span className="font-mono">submissions/&lt;track&gt;/iteration-*</span> folder carries
        its number. Its result is method and tooling that the other iterations&apos; reports quote —
        which is a contribution, not a deliverable.
      </Callout>
    );
  }
  return (
    <Callout tone="machinery" title="What this iteration's steps were for">
      The steps below contributed to{' '}
      {rows.map((row, i) => (
        <span key={row.folder}>
          {i > 0 && ' and '}
          <Link
            // The dossier's picker reads `?it=<track>/iteration-<n>`; the API builds the
            // folder path from the same two fields, so the two spellings cannot drift.
            to={`/submissions?it=${row.track}/iteration-${row.number}`}
            className="font-mono text-machinery-300 underline decoration-machinery-700 underline-offset-2 hover:text-machinery-200"
          >
            {row.folder}
          </Link>{' '}
          <span className="text-chrome-500">({row.state})</span>
        </span>
      ))}
      . The dossier page carries what would be uploaded, the decode table it was designed against,
      and what the oracle replied; this page carries how the rows in it were arrived at.{' '}
      <span className="text-chrome-500">({iteration})</span>
    </Callout>
  );
}
