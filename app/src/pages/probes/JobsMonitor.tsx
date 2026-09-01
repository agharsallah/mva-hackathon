import { useQueryClient } from '@tanstack/react-query';
import { useMemo } from 'react';

import { ApiError, post } from '../../api/client';
import { useJobs } from '../../api/hooks';
import type { Job } from '../../api/types';
import { type Column, DataTable } from '../../components/DataTable';
import { dec, iso } from '../../lib/format';
import { jobStateColor } from '../../lib/palette';
import { UpstreamDownBanner } from './UpstreamDownBanner';

const LIVE = new Set(['queued', 'running']);

/**
 * Jobs monitor. The reads API keeps every job it has been asked to run, so this table is
 * the audit trail for read-store queries — including ones submitted from the CLI rather
 * than from this app.
 */
export function JobsMonitor() {
  const qc = useQueryClient();
  const jobs = useJobs();
  const data = jobs.data ?? [];
  const anyLive = data.some((j) => LIVE.has(j.state));

  const columns: Column<Job>[] = useMemo(
    () => [
      {
        key: 'state',
        header: 'state',
        render: (j) => (
          <span
            className="rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase"
            style={{ background: `${jobStateColor(j.state)}22`, color: jobStateColor(j.state) }}
          >
            {j.state}
          </span>
        ),
      },
      { key: 'verb', header: 'verb', render: (j) => <span className="font-mono">{j.verb}</span> },
      {
        key: 'id',
        header: 'id',
        render: (j) => <span className="font-mono text-zinc-500">{j.id.slice(0, 12)}</span>,
      },
      {
        key: 'submitted',
        header: 'submitted',
        render: (j) => <span className="font-mono text-zinc-500">{iso(j.submitted_at)}</span>,
      },
      {
        key: 'elapsed',
        header: 'elapsed',
        align: 'right',
        render: (j) => (j.elapsed_seconds === null ? '—' : `${dec(j.elapsed_seconds, 1)} s`),
      },
      {
        key: 'probes',
        header: 'probes',
        align: 'right',
        render: (j) => {
          const p = j.params?.probes;
          return Array.isArray(p) ? String(p.length) : '—';
        },
      },
      {
        key: 'error',
        header: 'error',
        render: (j) =>
          j.error ? (
            <span className="font-mono text-red-400" title={j.error}>
              {j.error.split('\n')[0].slice(0, 60)}
              {j.error.length > 60 ? '…' : ''}
            </span>
          ) : (
            <span className="text-zinc-700">—</span>
          ),
      },
      {
        key: 'action',
        header: '',
        render: (j) =>
          LIVE.has(j.state) ? (
            <button
              onClick={() =>
                post(`/api/jobs/${j.id}/cancel`).then(() =>
                  qc.invalidateQueries({ queryKey: ['/api/jobs'] }),
                )
              }
              className="rounded border border-red-800 px-1.5 py-0.5 text-[10px] text-red-300 hover:bg-red-950/40"
            >
              cancel
            </button>
          ) : null,
      },
    ],
    [qc],
  );

  if (jobs.error) {
    return jobs.error instanceof ApiError && jobs.error.isUpstreamDown ? (
      <UpstreamDownBanner detail={jobs.error.message} />
    ) : (
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4 text-xs text-zinc-500">
        Job list unavailable — the viz API is not reachable. This table has no fixture: a job queue
        only exists on a live server.
        <p className="mt-1 font-mono text-[11px] text-zinc-600">{jobs.error.message}</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-x-4 text-[11px] text-zinc-500">
        <span>
          <span className="font-mono text-zinc-300">{data.length}</span> jobs known to the reads API
        </span>
        {anyLive && <span className="text-blue-400">polling every 4 s while a job is live</span>}
        {jobs.isPending && <span>loading…</span>}
      </div>
      <DataTable
        rows={data}
        columns={columns}
        rowKey={(j) => j.id}
        maxHeight={340}
        empty="No jobs yet. Submit a probe count above and it will appear here."
      />
      <ul className="space-y-0.5 text-[11px] text-zinc-500">
        <li>
          <span className="font-mono text-blue-400">queued / running</span> — accepted, machinery
          working
        </li>
        <li>
          <span className="font-mono text-emerald-400">done</span> — result available
        </li>
        <li>
          <span className="font-mono text-red-400">failed / lost</span> — errored, or the worker
          vanished mid-run
        </li>
        <li>
          <span className="font-mono text-zinc-400">cancelled</span> — stopped on request
        </li>
      </ul>
    </div>
  );
}
