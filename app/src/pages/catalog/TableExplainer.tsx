import { useMemo, useState } from 'react';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Skeleton, ErrorCard } from '../../components/QueryState';
import { TextFilter } from '../../components/Controls';
import { useCatalogColumns, useCatalogTables } from '../../api/hooks';
import type { CatalogColumnRow, CatalogTableRow } from '../../api/types';
import { C } from '../../lib/palette';
import { int } from '../../lib/format';

/**
 * Every table in the database, explained: what it is for, which command writes it, and
 * what each of its columns means.
 *
 * `TableCatalog` above answers "what exists and where did it come from". This answers the
 * question a reader asks next and no metadata catalogue can: **what does this column
 * mean?** `information_schema` knows `mean_vaf` is a float. That 0.50 is the healthy value
 * is knowledge that lives in a registry on the server, and a column the registry does not
 * cover is rendered as a stated gap — never as an empty cell that reads like "nothing to
 * say here".
 *
 * The mechanism is self-maintaining by construction. Tables and columns are both
 * enumerated live from `information_schema`, so a new table appears here the moment it
 * lands; a hermetic test on the server then fails the build until somebody writes its
 * `created_by` and `why`. Nothing in this component needs editing when the schema grows.
 */

/** A stated gap. Yellow, per the repo's palette: something a reviewer may ask about. */
function Gap({ children, title }: { children: string; title: string }) {
  return (
    <span
      className="rounded bg-amber-500/10 px-1.5 py-px text-[10px] whitespace-nowrap text-amber-400/90"
      title={title}
    >
      {children}
    </span>
  );
}

const NO_CREATOR = 'Nothing in the server registry names the command that writes this table.';
const NO_REASON = 'Nothing in the server registry says why this table exists.';
const NO_MEANING = 'No entry in the column-meaning registry covers this column.';

/** Does this table, its description, its reason or any of its column names match? */
function matches(row: CatalogTableRow, columns: CatalogColumnRow[], needle: string): boolean {
  if (!needle) return true;
  const haystack = [
    `${row.schema}.${row.table}`,
    row.description ?? '',
    row.why ?? '',
    row.created_by ?? '',
    ...columns.map((c) => c.column),
  ];
  return haystack.some((text) => text.toLowerCase().includes(needle));
}

/** The lineage edge as one sentence, or null when the table has no edge. */
function lineageLine(row: CatalogTableRow): string | null {
  if (!row.tool && !row.source_ref) return null;
  const from = row.source_ref ? ` from ${row.source_kind ?? 'input'} ${row.source_ref}` : '';
  return `${row.tool ?? 'an unnamed tool'}${from}`;
}

function ColumnTable({ columns }: { columns: CatalogColumnRow[] }) {
  if (columns.length === 0) {
    return <p className="text-[11px] text-zinc-500">No column metadata was returned for this table.</p>;
  }
  return (
    <table className="w-full border-collapse text-left text-[11px]">
      <thead>
        <tr className="border-b border-zinc-800 text-zinc-500">
          <th className="py-1 pr-3 font-normal">column</th>
          <th className="py-1 pr-3 font-normal">type</th>
          <th className="py-1 font-normal">what it means</th>
        </tr>
      </thead>
      <tbody>
        {columns.map((c) => (
          <tr key={c.column} className="border-b border-zinc-900 align-top">
            <td className="py-1 pr-3 font-mono whitespace-nowrap text-zinc-200">{c.column}</td>
            <td className="py-1 pr-3 font-mono whitespace-nowrap text-zinc-500">{c.data_type}</td>
            <td className="py-1 text-zinc-300">
              {c.meaning ?? <Gap title={NO_MEANING}>no recorded meaning</Gap>}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function TableCard({ row, columns }: { row: CatalogTableRow; columns: CatalogColumnRow[] }) {
  const lineage = lineageLine(row);
  const undocumented = columns.filter((c) => c.meaning === null).length;

  return (
    <details className="group rounded-lg border border-zinc-800 bg-zinc-900/40">
      <summary className="flex cursor-pointer flex-wrap items-baseline gap-x-3 gap-y-1 px-3 py-2 hover:bg-zinc-900/70">
        <span className="font-mono text-xs text-zinc-100">
          <span className="text-zinc-500">{row.schema}.</span>
          <span className="font-semibold">{row.table}</span>
        </span>
        {row.created_by ? (
          <span
            className="rounded bg-blue-500/10 px-1.5 py-px text-[10px] whitespace-nowrap text-blue-300"
            title="The command that writes this table, and whether it replaces it or appends to it."
          >
            {row.created_by}
          </span>
        ) : (
          <Gap title={NO_CREATOR}>undocumented — no created_by</Gap>
        )}
        <span className="text-[11px] text-zinc-500">
          {int(row.rows)} rows · {columns.length} columns
        </span>
        {undocumented > 0 && <Gap title={NO_MEANING}>{`${undocumented} column(s) unexplained`}</Gap>}
        <span className="ml-auto text-[11px] text-zinc-600 group-open:hidden">show columns ▸</span>
      </summary>

      <div className="space-y-2 border-t border-zinc-800 px-3 py-2">
        <p className="text-xs text-zinc-300">
          <span className="text-zinc-500">what it holds — </span>
          {row.description ?? <Gap title="Nothing describes this table.">undescribed</Gap>}
        </p>
        <p className="text-xs text-zinc-300">
          <span className="text-zinc-500">why it exists — </span>
          {row.why ?? <Gap title={NO_REASON}>undocumented — no reason recorded</Gap>}
        </p>
        <p className="text-xs text-zinc-300">
          <span className="text-zinc-500">how it is created — </span>
          {row.created_by ?? <Gap title={NO_CREATOR}>undocumented</Gap>}
          {lineage && <span className="text-zinc-500">; last run: {lineage}</span>}
          {!lineage && <span className="text-zinc-500">; no lineage edge records a run</span>}
        </p>
        <ColumnTable columns={columns} />
      </div>
    </details>
  );
}

export function TableExplainer() {
  const tables = useCatalogTables();
  const columns = useCatalogColumns();
  const [filter, setFilter] = useState('');

  const byTable = useMemo(() => {
    const grouped = new Map<string, CatalogColumnRow[]>();
    for (const row of columns.data?.data ?? []) {
      const key = `${row.schema}.${row.table}`;
      const bucket = grouped.get(key);
      if (bucket) bucket.push(row);
      else grouped.set(key, [row]);
    }
    for (const list of grouped.values()) list.sort((a, b) => a.ordinal - b.ordinal);
    return grouped;
  }, [columns.data]);

  const rows = tables.data?.data ?? [];
  const needle = filter.trim().toLowerCase();
  const shown = rows.filter((r) => matches(r, byTable.get(`${r.schema}.${r.table}`) ?? [], needle));
  const schemas = [...new Set(rows.map((r) => r.schema))].sort();
  const allColumns = columns.data?.data ?? [];
  const unexplained = allColumns.filter((c) => c.meaning === null).length;
  const undescribed = rows.filter((r) => r.why === null || r.created_by === null).length;

  return (
    <Exhibit
      title="Every table, explained — what it is for, what writes it, what each column means"
      controls={
        <TextFilter
          value={filter}
          onChange={setFilter}
          label="filter"
          placeholder="table, description or column name"
          width={260}
        />
      }
      legend={
        <>
          One expandable card per table, grouped by <strong>schema</strong> — a schema is a namespace
          inside the database, the way a package is in code. <span className="font-mono">warehouse</span>{' '}
          holds ingested data and the hand-written ledgers; <span className="font-mono">results</span>{' '}
          holds tables computed from them, every one re-derivable and stamped with a lineage edge.{' '}
          <Chip color={C.machinery}>blue chip = the command that writes the table</Chip> — it also says
          whether a re-run <em>replaces</em> the table, <em>rebuilds</em> it, or only <em>appends</em> to
          it, which is what a reader needs before re-running anything.{' '}
          <Chip color={C.decision}>yellow = a stated gap</Chip>: a table with no recorded reason or
          creator, or a column no entry in the meaning registry covers. Gaps are rendered, never blanked.
          Both lists are enumerated live from{' '}
          <span className="font-mono">information_schema</span>, so a table added to the database shows up
          here on its own — and the server&apos;s test suite then refuses to pass until somebody writes
          its reason.
        </>
      }
      reading="Read the blue chip first: it tells you what a re-run would do to the table. Then the reason — a table nobody can say the purpose of is a table that should be deleted or defended, not left in place."
      source={tables.data?.source}
      cachedAt={tables.data?.cachedAt}
      origin={tables.data?.origin}
    >
      {tables.error ? (
        <ErrorCard error={tables.error} />
      ) : tables.isPending ? (
        <Skeleton height={320} />
      ) : (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-[11px] text-zinc-500">
            <span>
              showing <span className="font-mono text-zinc-200">{int(shown.length)}</span> of{' '}
              {int(rows.length)} tables
            </span>
            <span>
              <span className="font-mono text-zinc-400">{int(allColumns.length)}</span> columns
              {columns.isPending && ' (loading)'}
            </span>
            <span className={undescribed ? 'text-amber-400' : 'text-emerald-400'}>
              {undescribed
                ? `${undescribed} table(s) with no recorded reason`
                : 'every table states why it exists'}
            </span>
            <span className={unexplained ? 'text-amber-400' : 'text-emerald-400'}>
              {unexplained
                ? `${unexplained} column(s) with no recorded meaning`
                : 'every column has a recorded meaning'}
            </span>
          </div>

          {columns.error && <ErrorCard error={columns.error} />}

          {schemas.map((schema) => {
            const inSchema = shown.filter((r) => r.schema === schema);
            if (inSchema.length === 0) return null;
            return (
              <div key={schema} className="space-y-1.5">
                <h4 className="font-mono text-xs text-zinc-400">
                  {schema}
                  <span className="ml-2 font-sans text-[11px] text-zinc-600">
                    {schema === 'results'
                      ? 'derived — rebuilt from the ingest schema, never edited in place'
                      : 'ingested data and the append-only ledgers'}
                  </span>
                </h4>
                {inSchema.map((row) => (
                  <TableCard
                    key={`${row.schema}.${row.table}`}
                    row={row}
                    columns={byTable.get(`${row.schema}.${row.table}`) ?? []}
                  />
                ))}
              </div>
            );
          })}

          {shown.length === 0 && (
            <p className="py-6 text-center text-xs text-zinc-500">no table matches “{filter}”</p>
          )}
        </div>
      )}
    </Exhibit>
  );
}
