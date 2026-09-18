/**
 * Measured facts F1-F9 — what iteration 2 actually knows about this genotype.
 *
 * Version 3 of the mechanism card added this block for one reason: a repurposing argument
 * is only as good as the genotype it rests on, and until now the card asserted the genotype
 * in prose. Each row here names the measurement, the methodology entry that made it, and
 * what it changes for a drug. One row — F8 — says the measurement was never made, which is
 * the row that keeps the block honest.
 */

import type { MeasuredFact } from '../../api/types';
import { Badge } from '../../components/Badge';
import { DataTable } from '../../components/DataTable';
import { Chip, Exhibit } from '../../components/Exhibit';
import { C } from '../../lib/palette';
import { cx, RULE, WELL } from '../../lib/ui';
import { isUnmeasured } from './ladderModel';
import { T } from './Term';

export function MeasuredFacts({ facts, source }: { facts: MeasuredFact[]; source?: string }) {
  const unmeasured = facts.filter(isUnmeasured).length;

  return (
    <Exhibit
      title="Measured facts — what the card rests on, F1 to F9"
      legend={
        <>
          One row per fact the card carries. <Chip color={C.good}>green = measured</Chip> — a run
          happened and its entry is named in the source column.{' '}
          <Chip color={C.decision}>yellow = UNMEASURED</Chip> — the fact is on the card as a stated
          gap, because leaving it off would read as though nobody had asked. The{' '}
          <em>implication</em> column is the only place the card is allowed to reason: it says what
          the measurement changes for a drug, and nothing more.
        </>
      }
      reading={`${facts.length} facts, ${unmeasured} of them explicitly unmeasured. Every row names the methodology entry that produced it, so a reader can follow a drug argument back to the run that licensed it rather than to the card's own prose.`}
      data={facts}
      source={source}
    >
      <div className="space-y-3">
        <p className="max-w-[95ch] font-serif text-note leading-relaxed text-chrome-300">
          A{' '}
          <T
            slug="measured-fact-on-the-card"
            term="measured fact"
            plain="one thing iteration 2 measured about the genotype, with the entry that measured it and what it implies for a drug"
          />{' '}
          is the card&rsquo;s unit of evidence. Think of it as a test assertion pinned to the
          hand-off document: the claim, the run that proved it, and what breaks if it is wrong. F8
          is the assertion nobody has run yet, and it says so in its own value rather than being
          quietly absent.
        </p>
        <DataTable<MeasuredFact>
          rows={facts}
          rowKey={(r) => r.id}
          pageSize={0}
          columns={[
            {
              key: 'id',
              header: 'id',
              render: (r) => (
                <Badge tone={isUnmeasured(r) ? 'decision' : 'machinery'}>{r.id}</Badge>
              ),
            },
            {
              key: 'fact',
              header: 'fact',
              render: (r) => <span className="text-chrome-100">{r.fact}</span>,
            },
            {
              key: 'value',
              header: 'what was measured',
              render: (r) => (
                <span
                  className={cx(
                    'inline-block max-w-[60ch]',
                    isUnmeasured(r) ? 'text-decision-300' : 'text-chrome-400',
                  )}
                >
                  {isUnmeasured(r) && (
                    <Badge tone="decision" className="mr-2">
                      UNMEASURED
                    </Badge>
                  )}
                  {r.value}
                </span>
              ),
            },
            {
              key: 'source',
              header: 'source',
              render: (r) => (
                <span className="font-mono text-micro break-all text-chrome-500">{r.source}</span>
              ),
            },
            {
              key: 'implication',
              header: 'what it changes for a drug',
              render: (r) => (
                <span className="inline-block max-w-[55ch] text-chrome-300">{r.implication}</span>
              ),
            },
          ]}
        />
        <div className={cx(WELL, 'border-l-2', RULE.decision)} data-testid="unmeasured-note">
          <p className="max-w-[95ch] font-serif text-note leading-relaxed text-chrome-300">
            <strong className="text-decision-300">F8 is UNMEASURED.</strong> The aneuploid fraction
            in the sequenced sample — how much of the child&rsquo;s tissue actually carries the
            wrong chromosome count — has not been measured in iteration 2; its step has not run.
            Nothing below is allowed to lean on it.
          </p>
        </div>
      </div>
    </Exhibit>
  );
}
