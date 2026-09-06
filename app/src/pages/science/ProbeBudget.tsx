import { useOverview, useProbeLedger } from '../../api/hooks';
import type { ProbeLedgerRow } from '../../api/types';
import { type Column, DataTable } from '../../components/DataTable';
import { EmptyState } from '../../components/EmptyState';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Loaded } from '../../components/QueryState';
import { StatTile } from '../../components/StatTile';
import { int, iso } from '../../lib/format';
import { C } from '../../lib/palette';

/**
 * The oracle budget, read as part of the research narrative rather than as a console.
 *
 * The Probes page owns the *operational* view of this same ledger — submit a probe, watch
 * the job, read the reply. This one asks a different question: what did each spend buy in
 * belief? A reply is recorded twice on purpose — in `warehouse.probe_ledger` as what
 * happened, and in `warehouse.evidence` as what it means — so a probe row here should have
 * an evidence row facing it in the ledger above.
 *
 * Same endpoint, no duplicate query: `/api/probe/ledger` and `/api/overview` are shared
 * hooks, so react-query serves both pages from one cache entry.
 */
export function ProbeBudget() {
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
      render: (r) => (
        <span className="font-mono text-micro text-chrome-400">{iso(r.logged_at)}</span>
      ),
    },
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
      key: 'why',
      header: 'what belief it was meant to move',
      render: (r) => <span className="text-chrome-400">{r.rationale ?? '—'}</span>,
    },
  ];

  return (
    <Exhibit
      title="Oracle budget — the research view"
      legend={
        <>
          Eighteen squares, one per allowed submission. <Chip color={C.good}>green = unspent</Chip>,{' '}
          <Chip color={C.broken}>red = spent, gone</Chip>. The budget is non-renewable, so a red
          square is a question that can never be asked again. Local k-mer counts against our own
          read store are free and touch none of these.
        </>
      }
      reading="The Probes page spends this budget; this panel asks what each spend bought in belief. Every reply should appear twice — once here as what happened, once in the evidence ledger as what it means."
      data={ledger.data?.data}
      source={ledger.data?.source}
      cachedAt={ledger.data?.cachedAt}
      origin={ledger.data?.origin}
    >
      <div className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <StatTile
            label="probes remaining"
            tone="good"
            value={
              <>
                {remaining}
                <span className="text-lg text-chrome-400"> / {total}</span>
              </>
            }
            sub={`${spent} spent · irreversible`}
          />
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

        <Loaded query={ledger} height={120}>
          {(rows) =>
            rows.length === 0 ? (
              <EmptyState tone="good" title={`Budget untouched — 0 of ${total} spent`}>
                Nothing has been asked of the oracle, which is consistent with an empty hypothesis
                board: there is no claim yet whose confidence a reply could move. The first spend
                should be the one that changes a belief the most, and the rationale column is where
                that argument gets written down.
              </EmptyState>
            ) : (
              <DataTable rows={rows} columns={columns} rowKey={(r) => r.probe_id} maxHeight={280} />
            )
          }
        </Loaded>
      </div>
    </Exhibit>
  );
}
