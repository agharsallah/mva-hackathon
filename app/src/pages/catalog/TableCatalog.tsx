import { useMemo, useState } from 'react';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Loaded } from '../../components/QueryState';
import { TextFilter } from '../../components/Controls';
import { DataTable, type Column } from '../../components/DataTable';
import { useCatalogTables } from '../../api/hooks';
import type { CatalogTableRow } from '../../api/types';
import { C } from '../../lib/palette';
import { int, iso } from '../../lib/format';

/**
 * Every derived table, with the lineage edge that produced it.
 *
 * A derived table with no recorded input is not "fine, just undocumented" — it is a table
 * nobody can re-derive or invalidate. So a missing edge is rendered as a stated gap, not
 * as an empty cell that reads like a rounding-down of the truth.
 */

const hasLineage = (r: CatalogTableRow): boolean =>
  r.produced_at !== null || r.source_kind !== null || r.source_ref !== null || r.tool !== null;

/** Shorten a long source reference from the left — the tail is the identifying part. */
function shortRef(ref: string): string {
  return ref.length <= 42 ? ref : `…${ref.slice(-41)}`;
}

function NoEdge() {
  return (
    <span
      className="rounded bg-amber-500/10 px-1.5 py-px text-[10px] text-amber-400/90"
      title="No row in meta.lineage names an input for this table. It exists, but nothing records where it came from."
    >
      no lineage edge
    </span>
  );
}

export function TableCatalog() {
  const q = useCatalogTables();
  const [filter, setFilter] = useState('');

  const columns: Column<CatalogTableRow>[] = useMemo(
    () => [
      {
        key: 'schema',
        header: 'schema',
        render: (r) => <span className="font-mono text-zinc-500">{r.schema}</span>,
      },
      {
        key: 'table',
        header: 'table',
        render: (r) => <span className="font-mono font-semibold text-zinc-100">{r.table}</span>,
      },
      {
        key: 'description',
        header: 'what it contains',
        render: (r) =>
          r.description ? (
            <span className="text-zinc-300">{r.description}</span>
          ) : (
            <span
              className="rounded bg-amber-500/10 px-1.5 py-px text-[10px] text-amber-400/90"
              title="Nothing describes this table — no catalogue entry, and no derivation records the question it answers."
            >
              undescribed
            </span>
          ),
      },
      { key: 'rows', header: 'rows', align: 'right', render: (r) => int(r.rows) },
      {
        key: 'produced',
        header: 'produced at',
        render: (r) =>
          r.produced_at ? (
            <span className="font-mono text-zinc-500">{iso(r.produced_at)}</span>
          ) : (
            <NoEdge />
          ),
      },
      {
        key: 'source',
        header: 'from',
        render: (r) =>
          r.source_ref ? (
            <span className="font-mono text-zinc-400" title={r.source_ref}>
              <span className="text-zinc-600">{r.source_kind ?? '?'} </span>
              {shortRef(r.source_ref)}
            </span>
          ) : (
            <span className="text-zinc-600">—</span>
          ),
      },
      {
        key: 'tool',
        header: 'tool',
        render: (r) =>
          r.tool ? <span className="font-mono text-zinc-500">{r.tool}</span> : <span className="text-zinc-600">—</span>,
      },
    ],
    [],
  );

  return (
    <Exhibit
      title="Derived tables — what each one holds and what produced it"
      controls={
        <TextFilter
          value={filter}
          onChange={setFilter}
          label="filter"
          placeholder="table name or description"
          width={240}
        />
      }
      legend={
        <>
          One row per table in the warehouse. <Chip color={C.machinery}>schema · table</Chip> is the address you
          would query; <span className="font-mono">from</span> is the lineage edge — the input this table was
          derived from, by the named <span className="font-mono">tool</span>.{' '}
          <Chip color={C.decision}>yellow chips mark a gap</Chip>: “no lineage edge” = nothing records what
          produced that table; “undescribed” = nothing says what it holds. Both are shown rather than blanked.{' '}
          <span className="font-mono">rows</span> is the catalogue&apos;s count as of its last refresh — the
          endpoint is cached, and a count can be an estimate wherever an exact one is too expensive, so read the
          magnitude before the digits. The filter box matches table name and description, case-insensitively.
        </>
      }
      reading="Every row here should be reproducible from the raw delivery by following its lineage edge back. The yellow chips are the exceptions — tables that exist but cannot state their input."
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={320}>
        {(rows) => {
          const needle = filter.trim().toLowerCase();
          const shown = needle
            ? rows.filter(
                (r) =>
                  r.table.toLowerCase().includes(needle) ||
                  (r.description ?? '').toLowerCase().includes(needle) ||
                  `${r.schema}.${r.table}`.toLowerCase().includes(needle),
              )
            : rows;
          const orphans = rows.filter((r) => !hasLineage(r)).length;
          const schemas = [...new Set(rows.map((r) => r.schema))].sort();

          return (
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-[11px] text-zinc-500">
                <span>
                  showing <span className="font-mono text-zinc-200">{int(shown.length)}</span> of {int(rows.length)}{' '}
                  tables
                </span>
                {schemas.map((s) => (
                  <span key={s}>
                    <span className="font-mono text-zinc-400">{s}</span> {rows.filter((r) => r.schema === s).length}
                  </span>
                ))}
                <span className={orphans ? 'text-amber-400' : 'text-emerald-400'}>
                  {orphans ? `${orphans} with no lineage edge` : 'every table has a lineage edge'}
                </span>
              </div>
              <DataTable
                rows={shown}
                columns={columns}
                rowKey={(r) => `${r.schema}.${r.table}`}
                maxHeight={520}
                empty={`no table matches “${filter}”`}
              />
            </div>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}
