import { useOverview, useProbeLedger } from '../../api/hooks';
import type { ProbeLedgerRow } from '../../api/types';
import { Card } from '../../components/Card';
import { type Column, DataTable } from '../../components/DataTable';
import { EmptyState } from '../../components/EmptyState';
import { Loaded } from '../../components/QueryState';
import { StatTile } from '../../components/StatTile';
import { int, iso } from '../../lib/format';

/**
 * The oracle budget. 6 probes for the whole challenge, non-renewable — closer to an API
 * rate limit you cannot buy your way out of than to a query cost. The widget's job is to
 * make the remaining balance impossible to overlook, and to make the empty state read as
 * "nothing spent yet" rather than "nothing here".
 */
export function ProbeLedger() {
  const ledger = useProbeLedger();
  const overview = useOverview();
  const total = overview.data?.data.probe_budget_total ?? 6;
  const spent = overview.data?.data.probe_budget_spent ?? 0;
  const remaining = total - spent;

  const columns: Column<ProbeLedgerRow>[] = [
    {
      key: 'id',
      header: 'probe',
      render: (r) => <span className="font-mono text-chrome-100">{r.probe_id}</span>,
    },
    {
      key: 'at',
      header: 'logged',
      render: (r) => <span className="font-mono text-chrome-400">{iso(r.logged_at)}</span>,
    },
    { key: 'track', header: 'track', render: (r) => r.track },
    {
      key: 'type',
      header: 'type',
      render: (r) => <span className="font-mono">{r.probe_type}</span>,
    },
    { key: 'rows', header: 'rows', align: 'right', render: (r) => int(r.n_rows) },
    {
      key: 'score',
      header: 'score',
      align: 'right',
      render: (r) => (r.score === null ? '—' : r.score),
    },
    {
      key: 'rationale',
      header: 'why it was worth a probe',
      render: (r) => <span className="text-chrome-400">{r.rationale ?? '—'}</span>,
    },
  ];

  return (
    <Card className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <StatTile
          label="oracle budget"
          tone="good"
          value={
            <>
              {remaining}
              <span className="text-lg text-chrome-400"> / {total}</span>
            </>
          }
          sub={`probes remaining · ${spent} spent`}
        />
        {/* 6 slots, one square each: the budget as a resource bar, not a number. */}
        <div className="flex flex-wrap gap-1">
          {Array.from({ length: total }, (_, i) => (
            <span
              key={i}
              title={i < spent ? `probe ${i + 1} — spent` : `probe ${i + 1} — unspent`}
              className={`h-5 w-5 rounded-sm border ${
                i < spent
                  ? 'border-broken-800 bg-broken-900/50'
                  : 'border-good-900/60 bg-good-950/30'
              }`}
            />
          ))}
        </div>
      </div>

      <Loaded query={ledger} height={140}>
        {(rows) =>
          rows.length === 0 ? (
            <EmptyState tone="good" title={`Budget untouched — 0 of ${total} spent`}>
              Nothing has been asked of the oracle yet. Every entry that lands here must carry the
              question it answered and why that question was worth one of eighteen irreversible
              spends — the ledger is the record of judgement, not just of calls.
            </EmptyState>
          ) : (
            <DataTable rows={rows} columns={columns} rowKey={(r) => r.probe_id} maxHeight={300} />
          )
        }
      </Loaded>
      <p className="text-micro text-chrome-600">
        Local k-mer counts against our own read store are <strong>free</strong> and do not touch
        this budget. Only queries to the challenge oracle do.
      </p>
    </Card>
  );
}
