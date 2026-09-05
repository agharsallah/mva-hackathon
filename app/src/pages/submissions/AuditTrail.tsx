import type { RegisterRevision, SubmissionAudit, SubmissionProbe } from '../../api/types';
import { Badge } from '../../components/Badge';
import { type Column, DataTable } from '../../components/DataTable';
import { EmptyState } from '../../components/EmptyState';
import { Chip, Exhibit } from '../../components/Exhibit';
import { dec, int, iso } from '../../lib/format';
import type { Tone } from '../../lib/palette';
import { C } from '../../lib/palette';

/**
 * What this iteration has cost, and what it moved.
 *
 * Two ledgers, both append-only, both about the same events read from different sides. The
 * probe ledger records what happened — a file went to the scorer and a reply came back. The
 * register records what it meant — which claim moved, to what status, at what stated
 * confidence, and on whose reasoning. A probe with no facing register revision is an
 * unexplained spend; a revision with no probe was moved by something else.
 */

const STATUS_TONE: Record<string, Tone> = {
  proposed: 'machinery',
  testing: 'decision',
  supported: 'good',
  refuted: 'broken',
  superseded: 'neutral',
};

export function AuditTrail({ audit, source }: { audit: SubmissionAudit; source?: string }) {
  const probeColumns: Column<SubmissionProbe>[] = [
    {
      key: 'probe_id',
      header: 'probe',
      render: (r) => <span className="font-mono text-chrome-100">{r.probe_id}</span>,
    },
    {
      key: 'logged_at',
      header: 'logged',
      render: (r) => (
        <span className="font-mono text-micro text-chrome-500">{iso(r.logged_at)}</span>
      ),
    },
    {
      key: 'probe_type',
      header: 'type',
      render: (r) => <span className="font-mono">{r.probe_type}</span>,
    },
    { key: 'n_rows', header: 'rows', align: 'right', render: (r) => int(r.n_rows) },
    { key: 'score', header: 'score', align: 'right', render: (r) => dec(r.score, 3) },
    {
      key: 'response',
      header: 'reply',
      render: (r) => <span className="text-chrome-300">{r.response ?? '—'}</span>,
    },
    {
      key: 'rationale',
      header: 'what belief it was meant to move',
      render: (r) => <span className="text-chrome-400">{r.rationale ?? '—'}</span>,
    },
  ];

  const registerColumns: Column<RegisterRevision>[] = [
    {
      key: 'hypothesis_id',
      header: 'claim',
      render: (r) => (
        <span className="font-mono text-chrome-100" title={r.statement}>
          {r.hypothesis_id}
        </span>
      ),
    },
    { key: 'step', header: 'step', render: (r) => <span className="font-mono">{r.step}</span> },
    { key: 'revision', header: 'rev', align: 'right', render: (r) => r.revision },
    {
      key: 'status',
      header: 'status',
      render: (r) => <Badge tone={STATUS_TONE[r.status] ?? 'neutral'}>{r.status}</Badge>,
    },
    {
      key: 'confidence',
      header: 'confidence',
      align: 'right',
      render: (r) => (r.confidence === null ? '—' : dec(r.confidence, 3)),
    },
    {
      key: 'reasoning',
      header: 'reasoning',
      render: (r) => <span className="text-chrome-400">{r.reasoning || '—'}</span>,
    },
    {
      key: 'recorded_at',
      header: 'recorded',
      render: (r) => (
        <span className="font-mono text-micro text-chrome-500">{iso(r.recorded_at)}</span>
      ),
    },
  ];

  return (
    <Exhibit
      title="Audit trail — what it cost, and what it moved"
      legend={
        <>
          Top: the oracle ledger, one row per irreversible submission. Bottom: the register, one row
          per revision of a claim this iteration rests on.{' '}
          <Chip color={C.good}>green = supported</Chip>,{' '}
          <Chip color={C.decision}>yellow = testing — the open decision</Chip>,{' '}
          <Chip color={C.broken}>red = refuted</Chip>,{' '}
          <Chip color={C.machinery}>blue = proposed, not yet tested</Chip>. Both tables are
          append-only: a changed belief is a new revision row, never an edit.
        </>
      }
      reading="Confidence here is a transparent triage heuristic with its arithmetic printed, not a calibrated posterior — it exists so a number can be argued with. Read the two tables as a pair: every probe reply should appear once above as what happened and once below as what it changed."
      data={audit}
      source={source}
    >
      <div className="space-y-4">
        {audit.probes.length === 0 ? (
          <EmptyState tone="good" title="no upload yet — 0 of 6 spent">
            Nothing has been sent to the scorer for this iteration, which is the honest state of a
            folder marked ready: it is built and rehearsed against a replica of the published
            scorer, and the non-renewable budget is untouched. The decode table above is the
            argument for what the first spend would buy.
          </EmptyState>
        ) : (
          <DataTable rows={audit.probes} columns={probeColumns} rowKey={(r) => r.probe_id} />
        )}

        <DataTable
          rows={audit.register}
          columns={registerColumns}
          rowKey={(r) => `${r.hypothesis_id}#${r.revision}`}
          empty="no register revision names a claim from this iteration"
          maxHeight={340}
        />
      </div>
    </Exhibit>
  );
}
