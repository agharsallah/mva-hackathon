import { useOverview, useProbeLedger } from '../../api/hooks';
import type { ProbeLedgerRow } from '../../api/types';
import { type Column, DataTable } from '../../components/DataTable';
import { Loaded } from '../../components/QueryState';
import { int, iso } from '../../lib/format';

/**
 * The oracle budget. 18 probes for the whole challenge, non-renewable — closer to an API
 * rate limit you cannot buy your way out of than to a query cost. The widget's job is to
 * make the remaining balance impossible to overlook, and to make the empty state read as
 * "nothing spent yet" rather than "nothing here".
 */
export function ProbeLedger() {
  const ledger = useProbeLedger();
  const overview = useOverview();
  const total = overview.data?.data.probe_budget_total ?? 18;
  const spent = overview.data?.data.probe_budget_spent ?? 0;
  const remaining = total - spent;

  const columns: Column<ProbeLedgerRow>[] = [
    {
      key: 'id',
      header: 'probe',
      render: (r) => <span className="font-mono text-zinc-100">{r.probe_id}</span>,
    },
    {
      key: 'at',
      header: 'logged',
      render: (r) => <span className="font-mono text-zinc-500">{iso(r.logged_at)}</span>,
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
      render: (r) => <span className="text-zinc-400">{r.rationale ?? '—'}</span>,
    },
  ];

  return (
    <div className="space-y-3 rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="text-[11px] font-medium uppercase tracking-wider text-zinc-500">
            oracle budget
          </div>
          <div className="mt-1 font-mono text-3xl leading-none text-emerald-400">
            {remaining}
            <span className="text-lg text-zinc-500"> / {total}</span>
          </div>
          <div className="mt-1 text-[11px] text-zinc-500">probes remaining · {spent} spent</div>
        </div>
        {/* 18 slots, one square each: the budget as a resource bar, not a number. */}
        <div className="flex flex-wrap gap-1">
          {Array.from({ length: total }, (_, i) => (
            <span
              key={i}
              title={i < spent ? `probe ${i + 1} — spent` : `probe ${i + 1} — unspent`}
              className={`h-5 w-5 rounded-sm border ${
                i < spent
                  ? 'border-red-800 bg-red-900/50'
                  : 'border-emerald-900/60 bg-emerald-950/30'
              }`}
            />
          ))}
        </div>
      </div>

      <Loaded query={ledger} height={140}>
        {(rows) =>
          rows.length === 0 ? (
            <div className="rounded-lg border border-dashed border-emerald-900/50 bg-emerald-950/10 p-6 text-center">
              <div className="text-sm font-medium text-emerald-400">
                Budget untouched — 0 of {total} spent
              </div>
              <p className="mx-auto mt-1 max-w-xl text-xs leading-relaxed text-zinc-400">
                Nothing has been asked of the oracle yet. Every entry that lands here must carry the
                question it answered and why that question was worth one of eighteen irreversible
                spends — the ledger is the record of judgement, not just of calls.
              </p>
            </div>
          ) : (
            <DataTable rows={rows} columns={columns} rowKey={(r) => r.probe_id} maxHeight={300} />
          )
        }
      </Loaded>
      <p className="text-[11px] text-zinc-600">
        Local k-mer counts against our own read store are <strong>free</strong> and do not touch
        this budget. Only queries to the challenge oracle do.
      </p>
    </div>
  );
}
