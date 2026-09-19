import type { HypothesisRow } from '../../api/types';
import { Badge } from '../../components/Badge';
import { BOX, cx } from '../../lib/ui';
import { claimTone } from './status';

/**
 * One claim, in full: what was predicted, what would have killed it, and what became of it.
 *
 * The journey page shows a claim as one line, which is the right density for a list of
 * twenty. A step's own page has room for the thing that makes the record worth keeping —
 * the **prediction** and the **refutation condition**, both written before the run. A
 * confirmation nobody could have failed is not evidence, and the only way a reader can tell
 * the difference is to see the sentence that was at risk.
 *
 * The confidence is a stated triage heuristic with its arithmetic printed in the register,
 * never a calibrated probability, and the caption says so wherever it appears.
 */
export function ClaimCard({ claim }: { claim: HypothesisRow }) {
  const tone = claimTone(String(claim.status));
  return (
    <article className={cx('space-y-2 rounded-card border p-3', BOX[tone])}>
      <header className="flex flex-wrap items-baseline gap-2">
        <Badge tone={tone}>{claim.hypothesis_id}</Badge>
        <Badge tone={tone}>{claim.status}</Badge>
        {claim.gene && <span className="font-mono text-micro text-chrome-400">{claim.gene}</span>}
        {claim.confidence !== null && (
          <span className="text-micro text-chrome-500">
            confidence {claim.confidence.toFixed(2)} — a stated heuristic, not a probability
          </span>
        )}
        <span className="ml-auto font-mono text-micro text-chrome-600">rev {claim.revision}</span>
      </header>

      <p className="text-xs text-chrome-200">{claim.statement}</p>

      <dl className="space-y-1 text-micro">
        <div className="flex gap-2">
          <dt className="w-28 shrink-0 text-chrome-500">predicted</dt>
          <dd className="text-chrome-300">{claim.prediction || '—'}</dd>
        </div>
        <div className="flex gap-2">
          <dt className="w-28 shrink-0 text-chrome-500">refuted if</dt>
          <dd className="text-chrome-300">{claim.refuted_by || '—'}</dd>
        </div>
        {claim.reasoning && (
          <div className="flex gap-2">
            <dt className="w-28 shrink-0 text-chrome-500">verdict</dt>
            <dd className="text-chrome-300">{claim.reasoning}</dd>
          </div>
        )}
      </dl>
    </article>
  );
}
