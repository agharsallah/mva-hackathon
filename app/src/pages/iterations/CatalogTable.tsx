import { useMemo, useState } from 'react';

import type { CatalogDataset, IterationCatalog, LineageStatus } from '../../api/types';
import { Badge } from '../../components/Badge';
import { Toggle } from '../../components/Controls';
import { type Column, DataTable } from '../../components/DataTable';
import { int } from '../../lib/format';
import { blobUrl } from '../submissions/iteration';
import { LINEAGE_MEANING, LINEAGE_TONE, ROLE_MEANING, shortDigest } from './model';

/**
 * The data catalogue of one iteration as a table: every dataset its methodology entries
 * name, with the record that explains it. Reused by the iterations hub (research iterations
 * and submission folders) and by the submission dossier, so both read one component.
 *
 * Filters are local view state: a free-text box over every cell (`DataTable`), and a
 * lineage-status toggle row, because "which datasets have no lineage" is the question a
 * reviewer asks first.
 */

const STATUSES: readonly LineageStatus[] = ['edge', 'manifest', 'none'];

/** `docs/iteration2/step-3/methodology/084-x.md` → `084`, so an entry chip can link its file. */
function entryIndex(paths: string[]): Map<string, string> {
  const out = new Map<string, string>();
  for (const p of paths) {
    const m = /\/(\d{3})[^/]*\.md$/.exec(p);
    if (m) out.set(m[1], p);
  }
  return out;
}

const isRepoFile = (ref: string): boolean =>
  ref !== '' && !ref.startsWith('warehouse.') && !ref.includes('://') && ref.includes('/');

/** `iteration2/step-8` → `it2/step-8`: the iteration prefix is repeated on every row. */
const shortStep = (step: string): string => step.replace(/^iteration(\d+)\//, 'it$1/');

const basename = (path: string): string => path.slice(path.lastIndexOf('/') + 1);

const storedMeaning = (r: CatalogDataset): string =>
  r.kind === 'table'
    ? 'a warehouse table: stored in the database, not in git'
    : r.committed
      ? 'tracked in git'
      : 'a gitignored build/ file: rebuilt, never committed';

/** Where the bytes live: the database, git, or a gitignored build directory. */
const stored = (r: CatalogDataset): string =>
  r.kind === 'table' ? 'warehouse' : r.committed ? 'git' : 'gitignored';

function Inputs({ row }: { row: CatalogDataset }) {
  if (row.inputs.length === 0) return <span className="text-chrome-600">—</span>;
  return (
    <details className="group">
      <summary className="cursor-pointer text-micro whitespace-nowrap text-machinery-300 hover:text-machinery-200">
        {row.inputs.length} input{row.inputs.length === 1 ? '' : 's'}
      </summary>
      <ul className="mt-1 space-y-1">
        {row.inputs.map((i) => (
          <li key={i.ref} className="font-mono text-micro break-all text-chrome-300">
            {i.ref}{' '}
            <span className="text-chrome-500" title={i.sha256 || 'no digest recorded'}>
              {shortDigest(i.sha256)}
            </span>
          </li>
        ))}
      </ul>
    </details>
  );
}

function columns(entries: Map<string, string>): Column<CatalogDataset>[] {
  return [
    {
      key: 'ref',
      header: 'dataset · kind · stored',
      render: (r) => (
        <span className="flex flex-col gap-0.5" title={r.sha256 || undefined}>
          <span className="font-mono [overflow-wrap:anywhere] text-chrome-100">
            {r.committed && isRepoFile(r.ref) ? (
              <a href={blobUrl(r.ref)} className="hover:text-machinery-200 hover:underline">
                {r.ref}
              </a>
            ) : (
              r.ref
            )}
          </span>
          <span className="flex flex-wrap items-center gap-1.5 text-micro text-chrome-500">
            <span className="font-mono">{r.kind}</span>·
            <span title={storedMeaning(r)}>{stored(r)}</span>
            {!r.exists && (
              <Badge tone="neutral" title="not present on this checkout">
                absent here
              </Badge>
            )}
          </span>
        </span>
      ),
      className: 'min-w-[15rem] max-w-[22rem]',
    },
    {
      key: 'role',
      header: 'role',
      render: (r) => (
        <Badge tone={r.role === 'produced' ? 'good' : 'neutral'} title={ROLE_MEANING[r.role]}>
          {r.role}
        </Badge>
      ),
    },
    {
      key: 'lineage',
      header: 'lineage',
      render: (r) => (
        <Badge tone={LINEAGE_TONE[r.lineage]} title={LINEAGE_MEANING[r.lineage]}>
          {r.lineage}
        </Badge>
      ),
    },
    {
      key: 'entries',
      header: 'entries',
      sortValue: (r) => r.entries[0] ?? null,
      render: (r) => (
        <span className="flex flex-wrap gap-1">
          {r.entries.slice(0, 4).map((e) => {
            const path = entries.get(e);
            return path ? (
              <a
                key={e}
                href={blobUrl(path)}
                title={path}
                className="font-mono text-micro text-machinery-300 hover:text-machinery-200"
              >
                {e}
              </a>
            ) : (
              <span key={e} className="font-mono text-micro">
                {e}
              </span>
            );
          })}
          {r.entries.length > 4 && (
            <span className="text-micro text-chrome-500" title={r.entries.join(', ')}>
              +{r.entries.length - 4}
            </span>
          )}
        </span>
      ),
    },
    {
      key: 'steps',
      header: 'steps',
      sortValue: (r) => r.steps[0] ?? null,
      render: (r) =>
        r.steps.length === 0 ? (
          <span className="text-chrome-600">—</span>
        ) : (
          <span className="flex flex-col font-mono text-micro whitespace-nowrap">
            {r.steps.map((st) => (
              <span key={st}>{shortStep(st)}</span>
            ))}
          </span>
        ),
    },
    {
      key: 'rows',
      header: 'rows',
      align: 'right',
      render: (r) => (r.rows === null ? '—' : int(r.rows)),
    },
    {
      key: 'provenance',
      header: 'provenance',
      render: (r) =>
        !r.provenance ? (
          <span className="text-chrome-600">—</span>
        ) : isRepoFile(r.provenance) ? (
          <a
            href={blobUrl(r.provenance)}
            title={r.provenance}
            className="block max-w-[11rem] truncate font-mono text-micro text-machinery-300 hover:text-machinery-200"
          >
            {basename(r.provenance)}
          </a>
        ) : (
          <span className="font-mono text-micro whitespace-nowrap" title={r.provenance}>
            {r.provenance === 'warehouse.data_lineage' ? 'ledger edge' : r.provenance}
          </span>
        ),
    },
    {
      key: 'built_by',
      header: 'built by · at',
      render: (r) => (
        <span
          className="flex flex-col font-mono text-micro"
          title={[r.built_by, r.version, r.built_at].filter(Boolean).join(' · ') || undefined}
        >
          <span className="max-w-[10rem] truncate">{r.built_by || '—'}</span>
          <span className="whitespace-nowrap text-chrome-500">
            {r.built_at ? r.built_at.slice(0, 10) : 'date unknown'}
            {r.version && ` · ${r.version.length > 14 ? `${r.version.slice(0, 13)}…` : r.version}`}
          </span>
        </span>
      ),
    },
    { key: 'inputs', header: 'inputs', sortable: false, render: (r) => <Inputs row={r} /> },
  ];
}

export function CatalogTable({ catalog }: { catalog: IterationCatalog }) {
  const [only, setOnly] = useState<LineageStatus | null>(null);
  const cols = useMemo(() => columns(entryIndex(catalog.entries)), [catalog.entries]);
  const rows = only ? catalog.datasets.filter((d) => d.lineage === only) : catalog.datasets;

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-micro text-chrome-400">lineage</span>
        <Toggle on={only === null} onChange={() => setOnly(null)}>
          all {catalog.datasets.length}
        </Toggle>
        {STATUSES.map((s) => (
          <Toggle key={s} on={only === s} onChange={(on) => setOnly(on ? s : null)}>
            {s} {catalog.datasets.filter((d) => d.lineage === s).length}
          </Toggle>
        ))}
      </div>
      <DataTable
        rows={rows}
        columns={cols}
        rowKey={(r) => `${r.kind}:${r.ref}`}
        filterable
        filterPlaceholder="dataset, entry, step, tool…"
        maxHeight={560}
        pageSize={50}
        empty={
          catalog.datasets.length === 0
            ? 'no dataset named by these entries'
            : `no dataset with lineage "${only ?? ''}"`
        }
      />
    </div>
  );
}
