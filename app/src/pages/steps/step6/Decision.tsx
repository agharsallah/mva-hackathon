import type { Step6Decision, Step6Fusion } from '../../../api/types';
import { Badge } from '../../../components/Badge';
import { Exhibit } from '../../../components/Exhibit';
import { Callout } from '../../../components/Explainer';
import { FieldList } from '../../../components/FieldList';
import { StatTile } from '../../../components/StatTile';
import { count } from './metrics';

/**
 * The freeze receipt, and — only once it exists — the comparison against iteration 1.
 *
 * The receipt is always shown: the digest of the frozen ranking is what makes "we did not
 * steer this" checkable rather than asserted, and it is available from the moment the
 * ranking is frozen.
 *
 * The comparison is shown only when the payload carries a `decision` block, which the
 * unblinding entry is what produces. Until then this component renders the blind state
 * explicitly, because a page that simply omitted the section would be indistinguishable
 * from one whose data failed to load.
 */
export function Decision({
  fusion,
  decision,
  source,
  cachedAt,
  origin,
}: {
  fusion: Step6Fusion;
  decision: Step6Decision;
  source?: string;
  cachedAt?: string | null;
  origin?: 'api' | 'fixture';
}) {
  const frozen = fusion.frozen;
  const constants = fusion.constants;
  const unblinded = Boolean(decision.unblinded_at);

  return (
    <div className="space-y-4">
      <Exhibit
        title="Freeze receipt — the ranking predates the comparison"
        reading="The digest below was written into the methodology entry before any iteration-1 table was read. A ranking re-run until it agreed with the answer would not hash to it."
        legend={
          <>
            <strong>sha256</strong> is of the exported file&rsquo;s bytes, so a reader can check it
            with one <code>shasum</code>. <strong>k</strong>, <strong>top per route</strong> and{' '}
            <strong>absent rank</strong> are the constants the plan fixed before any route ran —
            they are shown here so a reader can confirm none of them was chosen afterwards.
          </>
        }
        source={source}
        cachedAt={cachedAt}
        origin={origin}
        data={fusion}
      >
        <FieldList
          labelWidth={132}
          fields={[
            { key: 'file', label: 'file', value: <code>{frozen?.file ?? '—'}</code> },
            {
              key: 'sha256',
              label: 'sha256',
              value: <code className="break-all text-good-300">{frozen?.sha256 ?? '—'}</code>,
            },
            { key: 'rows', label: 'pairs frozen', value: count(frozen?.rows) },
            { key: 'frozen_at', label: 'frozen at', value: frozen?.frozen_at ?? '—' },
            {
              key: 'constants',
              label: 'constants',
              value: constants
                ? `k = ${constants.k} · top ${constants.top_per_route} per route · absent = rank ${constants.missing_rank} · seed ${constants.seed}`
                : '—',
            },
            {
              key: 'pairs',
              label: 'candidates',
              value: fusion.pairs
                ? `${count(fusion.pairs.keys)} coordinate-free keys from ${count(fusion.pairs.scored_rows)} scored hypotheses`
                : '—',
            },
            {
              key: 'confirmation',
              label: 'confirmation',
              value: fusion.confirmation
                ? `${count(fusion.confirmation.pairs_complete)} of ${count(fusion.confirmation.pairs_measured)} measured pairs carry all three booleans, over ${count(fusion.confirmation.genes_measured)} genes`
                : '—',
            },
          ]}
        />
      </Exhibit>

      {!unblinded && (
        <Callout tone="decision" title="Still blind — nothing about iteration 1 is on this page">
          The comparison against the confirmed pair is its own methodology entry, and the payload
          carries no decision block until that entry exists. This is the blind protocol expressed as
          data rather than as a promise: there is nothing here to hide, because there is nothing
          here. <code>mva-science check --blind iteration2</code> is what enforces the order, and
          the blinding checklist below is its own output.
        </Callout>
      )}

      {unblinded && (
        <Exhibit
          title="Unblinding — what the mirror found"
          reading={decision.notes ?? 'The comparison against iteration 1, and what it licenses.'}
          legend={
            <>
              <strong>Outcome</strong> is the row of the decision table fixed in the plan before any
              of this ran. <strong>EIG</strong> is the expected information gain of a second oracle
              upload, in bits: <strong>0</strong> means an upload would measure nothing and the slot
              stays in reserve. <span className="text-good-400">Green</span> — the mirror
              rediscovered the pair; <span className="text-decision-400">yellow</span> — it found
              it, but not first; <span className="text-broken-400">red</span> — it missed it, and
              the miss carries its category.
            </>
          }
          source={source}
          cachedAt={cachedAt}
          origin={origin}
          data={decision}
        >
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile
              label="fused rank of the confirmed pair"
              value={decision.fused_rank_of_confirmed ?? '—'}
              tone={
                decision.fused_rank_of_confirmed === 1
                  ? 'good'
                  : decision.fused_rank_of_confirmed
                    ? 'decision'
                    : 'broken'
              }
              sub={decision.iteration1_pair ?? ''}
            />
            <StatTile
              label="decision-table row"
              value={decision.outcome_row ?? '—'}
              sub="fixed in the plan before the fusion ran"
            />
            <StatTile
              label="expected information gain"
              value={
                decision.expected_information_gain_bits === undefined
                  ? '—'
                  : `${decision.expected_information_gain_bits.toFixed(3)} bits`
              }
              tone={decision.expected_information_gain_bits ? 'decision' : 'good'}
              sub={decision.upload ?? ''}
              chip={
                <Badge tone={decision.expected_information_gain_bits ? 'decision' : 'good'}>
                  {decision.expected_information_gain_bits ? 'upload considered' : 'no upload'}
                </Badge>
              }
            />
            <StatTile
              label="unblinded"
              value={decision.unblinded_at ?? '—'}
              sub={decision.entry ? `entry ${decision.entry}` : ''}
            />
          </div>
          {decision.miss_category && (
            <Callout tone="broken" title="The miss, classified">
              {decision.miss_category}
            </Callout>
          )}
        </Exhibit>
      )}
    </div>
  );
}
