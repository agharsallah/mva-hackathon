/**
 * Every shared primitive, rendered once, with the import line that produces it.
 *
 * This is the half of `src/components/README.md` that prose cannot carry: what the thing
 * looks like. A newcomer reads the barrel here instead of grepping pages for an example, and
 * a change to a primitive shows up in one screenshot rather than eleven pages.
 */

import { useState } from 'react';

import {
  Badge,
  Callout,
  Card,
  DataTable,
  EmptyState,
  Exhibit,
  FieldList,
  Flag,
  Section,
  Select,
  StatTile,
  TextFilter,
  Toggle,
} from '../../components';

interface DemoRow {
  gene: string;
  records: number;
  verdict: string;
}

const ROWS: DemoRow[] = [
  { gene: 'BUB1B', records: 1284, verdict: 'candidate' },
  { gene: 'CEP57', records: 311, verdict: 'candidate' },
  { gene: 'TRIP13', records: 502, verdict: 'screened' },
];

export function PrimitiveGallery() {
  const [showTable, setShowTable] = useState(true);
  const [scope, setScope] = useState<'panel' | 'genome'>('panel');
  const [filter, setFilter] = useState('');

  return (
    <Section
      title="The primitives"
      subtitle="Everything src/components/index.ts exports, rendered with throwaway data. Charts are covered by Exhibit itself — this figure is one."
    >
      <Exhibit
        title="Tiles, marks and boxes"
        legend={
          <>
            Live components, not screenshots: <code>StatTile</code> (a figure with a tone),{' '}
            <code>Badge</code>/<code>Flag</code> (a mark), <code>Callout</code> (the one thing that
            changes the conclusion), <code>EmptyState</code> (nothing here — grey for a gap, green
            when nothing recorded is the expected state), <code>Card</code> (its <code>panel</code>{' '}
            and <code>well</code> variants nested), <code>FieldList</code>, <code>DataTable</code>,
            and the control row.
          </>
        }
        reading="A page composes these; it never types the class strings behind them."
        source="src/components/index.ts"
      >
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile label="records" value="5.2M" sub="delivered" hint="StatTile, neutral tone" />
            <StatTile label="pass rate" value="98.4%" sub="of all calls" tone="good" />
            <StatTile label="suppressed" value="1.6%" sub="filtered out" tone="broken" />
            <StatTile label="het pairs" value="41" sub="needs a call" tone="decision" />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Badge>neutral</Badge>
            <Badge tone="good">present</Badge>
            <Badge tone="broken">HIGH impact</Badge>
            <Badge tone="decision">gap</Badge>
            <Badge tone="machinery">MODIFIER</Badge>
            <Badge tone="raw">as delivered</Badge>
            <Flag on yes="rare" no="common" />
            <Flag on={false} yes="rare" no="common" />
            <Flag on={null} yes="rare" no="common" />
          </div>

          <div className="grid gap-3 lg:grid-cols-2">
            <Callout tone="good" title="Callout, good tone">
              The state we wanted. Used for a guarantee the page can back up.
            </Callout>
            <Callout title="Callout, decision tone">
              The default: a judgement call the reader has to make before believing a figure.
            </Callout>
          </div>

          <div className="grid gap-3 lg:grid-cols-2">
            <Card className="space-y-2">
              <div className="text-xs font-semibold text-chrome-400">Card, panel variant</div>
              <FieldList
                fields={[
                  { key: 'assembly', label: 'assembly', value: 'GRCh38' },
                  { key: 'caller', label: 'caller', value: 'DRAGEN 4.2' },
                  { key: 'samples', label: 'samples', value: '1 (proband)' },
                ]}
              />
              <Card variant="well" padding="sm">
                <p className="text-micro text-chrome-500">
                  Card, well variant — the recessed panel a card nests inside itself. The third,{' '}
                  <code>plain</code>, keeps the padding rhythm and drops the border; all three are
                  laid out side by side under &ldquo;The tokens&rdquo; above.
                </p>
              </Card>
            </Card>
            <div className="grid gap-3">
              <EmptyState title="No matches">
                EmptyState, neutral tone — a filtered table with nothing left.
              </EmptyState>
              <EmptyState tone="good" title="Nothing recorded yet">
                EmptyState, good tone — for a register where empty is the expected state.
              </EmptyState>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Toggle on={showTable} onChange={setShowTable}>
              {showTable ? 'table shown' : 'table hidden'}
            </Toggle>
            <Select
              label="scope"
              value={scope}
              options={[
                { value: 'panel', label: 'panel' },
                { value: 'genome', label: 'genome' },
              ]}
              onChange={setScope}
            />
            <TextFilter value={filter} onChange={setFilter} label="filter" placeholder="gene…" />
          </div>

          {showTable && (
            <DataTable
              rows={ROWS.filter((r) => r.gene.toLowerCase().includes(filter.toLowerCase()))}
              rowKey={(r) => r.gene}
              columns={[
                { key: 'gene', header: 'gene', render: (r) => r.gene },
                {
                  key: 'records',
                  header: 'records',
                  align: 'right',
                  render: (r) => r.records.toLocaleString('en-US'),
                },
                {
                  key: 'verdict',
                  header: 'verdict',
                  render: (r) => (
                    <Badge tone={r.verdict === 'candidate' ? 'good' : 'neutral'}>{r.verdict}</Badge>
                  ),
                },
              ]}
            />
          )}
        </div>
      </Exhibit>
    </Section>
  );
}
