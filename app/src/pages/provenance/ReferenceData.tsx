/**
 * Reference data provenance — the public inputs, with a lockfile for each.
 *
 * The rest of this page is *lineage*: table X was computed from object Y by transform Z,
 * an edge the warehouse actually recorded. Reference data has no such edge. A gnomAD
 * constraint table, an HPO release, an Ensembl gene record, an AlphaFold model are
 * **fetched** — there is no upstream table and no transform, so an edge claiming one
 * would be fabricated. What they get instead is a manifest committed beside the bytes,
 * written by the build tool on every run.
 */

import { useState } from 'react';

import { useReferenceProvenance } from '../../api/hooks';
import type { ReferenceProvenanceRow } from '../../api/types';
import { Badge } from '../../components/Badge';
import { type Column, DataTable } from '../../components/DataTable';
import { EmptyState } from '../../components/EmptyState';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Loaded } from '../../components/QueryState';
import { bytes, int, iso } from '../../lib/format';
import { C } from '../../lib/palette';

type Input = ReferenceProvenanceRow['inputs'][number];
type Output = ReferenceProvenanceRow['outputs'][number];

/** First 12 hex characters, with the whole digest on the element's title for copying. */
function Sha({ value }: { value: string | null }) {
  if (!value) return <span className="text-chrome-600">— live API, no digest</span>;
  return (
    <span className="cursor-help font-mono text-good-400" title={value}>
      {value.slice(0, 12)}…
    </span>
  );
}

const INPUT_COLUMNS: Column<Input>[] = [
  {
    key: 'name',
    header: 'input',
    render: (r) => <span className="font-mono text-chrome-100">{r.name}</span>,
  },
  {
    key: 'url',
    header: 'fetched from',
    render: (r) =>
      r.url.startsWith('file://') ? (
        <span className="font-mono text-chrome-500">{r.url}</span>
      ) : (
        <a
          href={r.url}
          target="_blank"
          rel="noreferrer"
          className="font-mono break-all text-machinery-400 underline decoration-dotted hover:text-machinery-300"
        >
          {r.url}
        </a>
      ),
  },
  {
    key: 'release',
    header: 'release / version',
    render: (r) =>
      r.release ? (
        <span className="font-mono text-raw-400">{r.release}</span>
      ) : (
        <span className="text-chrome-600">—</span>
      ),
  },
  { key: 'sha256', header: 'sha256', render: (r) => <Sha value={r.sha256} /> },
  { key: 'bytes', header: 'bytes', align: 'right', render: (r) => bytes(r.bytes) },
];

const OUTPUT_COLUMNS: Column<Output>[] = [
  {
    key: 'path',
    header: 'written to',
    render: (r) => <span className="font-mono break-all text-chrome-100">{r.path}</span>,
  },
  { key: 'sha256', header: 'sha256', render: (r) => <Sha value={r.sha256} /> },
  { key: 'bytes', header: 'bytes', align: 'right', render: (r) => bytes(r.bytes) },
  {
    key: 'rows',
    header: 'rows',
    align: 'right',
    render: (r) => (r.rows === null ? <span className="text-chrome-600">n/a</span> : int(r.rows)),
  },
];

function Manifest({ row }: { row: ReferenceProvenanceRow }) {
  const [open, setOpen] = useState(false);
  const outBytes = row.outputs.reduce((n, o) => n + (o.bytes ?? 0), 0);
  return (
    <div className="rounded-lg border border-chrome-800 bg-chrome-950/60">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="flex w-full flex-wrap items-baseline gap-x-3 gap-y-1 p-3 text-left transition hover:bg-chrome-900/60 focus:outline-none focus-visible:border-machinery-700"
      >
        <span className="text-chrome-500">{open ? '▾' : '▸'}</span>
        <Badge tone={row.kind === 'reference' ? 'raw' : 'decision'}>{row.kind}</Badge>
        <span className="font-mono text-sm text-chrome-100">{row.name}</span>
        <span className="text-[11px] text-chrome-500">
          {row.inputs.length} input{row.inputs.length === 1 ? '' : 's'} → {row.outputs.length} file
          {row.outputs.length === 1 ? '' : 's'}, {bytes(outBytes)}
        </span>
        <span className="ml-auto font-mono text-[11px] text-chrome-600">
          {iso(row.built_at)} · {row.built_by} · {row.code_version}
        </span>
      </button>
      {open && (
        <div className="space-y-3 border-t border-chrome-800 p-3">
          <p className="text-[11px] text-chrome-400">{row.note}</p>
          <div className="space-y-1">
            <h4 className="text-[11px] font-semibold text-chrome-300">
              inputs — what was fetched or read
            </h4>
            <DataTable
              rows={row.inputs}
              columns={INPUT_COLUMNS}
              rowKey={(r, i) => `${r.name}:${i}`}
              empty="No inputs recorded."
            />
          </div>
          <div className="space-y-1">
            <h4 className="text-[11px] font-semibold text-chrome-300">
              outputs — what was written, and its digest
            </h4>
            <DataTable
              rows={row.outputs}
              columns={OUTPUT_COLUMNS}
              rowKey={(r) => r.path}
              maxHeight={280}
              empty="No outputs recorded."
            />
          </div>
          <p className="font-mono text-[11px] text-chrome-600">
            manifest: {row.path} · written by {row.built_by}, never by hand
          </p>
        </div>
      )}
    </div>
  );
}

export function ReferenceData() {
  const q = useReferenceProvenance();
  return (
    <Exhibit
      title="Reference data — where the public inputs came from"
      legend={
        <>
          One row per build.{' '}
          <Chip color={C.raw}>reference = a committed table under ressources/reference</Chip> ·{' '}
          <Chip color={C.decision}>
            fixture = an offline payload directory the app reads with no API
          </Chip>
          . Click a row to open its manifest: <span className="text-machinery-400">inputs</span>{' '}
          (what was fetched, from where, at which release) and{' '}
          <span className="text-chrome-300">outputs</span> (what was written, with a{' '}
          <span className="text-good-400">sha256</span> over the bytes — hover a truncated digest to
          see it whole). A digest of <span className="text-chrome-600">— live API</span> means the
          input was an HTTP service, which has no fixed bytes to hash; its{' '}
          <span className="text-raw-400">release</span> is the pin instead.
        </>
      }
      reading="A provenance manifest is a lockfile for data: URL + version + hash, so the file can be re-fetched and checked. These are the public inputs — no patient bytes — and they carry no lineage edge on purpose: they were fetched, not computed, so there is no upstream table and no transform to record. The manifest is the honest substitute, and the build tool writes it on every run."
      data={q.data?.data}
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={240}>
        {(rows) =>
          rows.length === 0 ? (
            <EmptyState title="No reference manifests found">
              Nothing under <code>ressources/reference</code> or the fixture directories carries a{' '}
              <code>*provenance.json</code> yet. The route answers 200 with an empty list rather
              than failing — an absent manifest is a state, not an error.
            </EmptyState>
          ) : (
            <div className="space-y-2">
              {rows.map((row) => (
                <Manifest key={row.path} row={row} />
              ))}
            </div>
          )
        }
      </Loaded>
    </Exhibit>
  );
}
