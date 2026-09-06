/**
 * The Track 1 iterations this report is linked to.
 *
 * The link is not a folder reference — it is the set of **hypothesis ids the mechanism card
 * cites**. So when an oracle reply changes what one of those claims says, the card is
 * revised and every table below is rebuilt; a card that cited nothing would make the drug
 * list unfalsifiable.
 */

import { Link } from 'react-router-dom';

import type { LinkedIteration } from '../../api/types';
import { Badge } from '../../components/Badge';
import { EmptyState } from '../../components/EmptyState';
import { cx, WELL } from '../../lib/ui';

const iterationKey = (it: LinkedIteration): string => `${it.track}/iteration-${it.number}`;

export function LinkedIterations({ iterations }: { iterations: LinkedIteration[] }) {
  if (iterations.length === 0) {
    return (
      <EmptyState title="No linked iteration yet">
        No submission folder shares a hypothesis with the mechanism card, so nothing in Track 1
        currently constrains this report.
      </EmptyState>
    );
  }

  return (
    <ul className="grid gap-3 md:grid-cols-2" data-testid="linked-iterations">
      {iterations.map((it) => {
        const key = iterationKey(it);
        return (
          <li key={key} className={cx(WELL, 'space-y-2')}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <Link
                to={`/submissions?it=${key}`}
                className="font-mono text-sm text-machinery-300 underline decoration-machinery-800 underline-offset-2 hover:text-machinery-200"
              >
                {key}
              </Link>
              <Badge tone={it.state === 'frozen' ? 'good' : 'neutral'}>{it.state}</Badge>
            </div>
            <p className="text-micro leading-relaxed text-chrome-400">{it.standing}</p>
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-micro text-chrome-400">shared claims</span>
              {it.hypotheses.map((h) => (
                <Link key={h} to={`/science?hypothesis=${h}`}>
                  <Badge tone="machinery">{h}</Badge>
                </Link>
              ))}
            </div>
            <p className="text-micro text-chrome-600">
              The card is rewritten — a new version, never an edit — whenever one of these claims
              changes.
            </p>
          </li>
        );
      })}
    </ul>
  );
}
