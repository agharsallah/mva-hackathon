import { isValidElement, useMemo, useState, type ReactNode } from 'react';
import { TextFilter } from './Controls';

/**
 * The shared table. Sorting, filtering and pagination are additive: a call site that passes
 * only rows/columns/rowKey renders exactly what it always did, and small tables (under
 * `pageSize` rows, unfiltered) are unchanged down to the pixel.
 */

/** What a column sorts by. `null`/`undefined` sort last in both directions. */
export type SortValue = string | number | boolean | null | undefined;

export interface Column<R> {
  key: string;
  header: ReactNode;
  render: (row: R) => ReactNode;
  align?: 'left' | 'right';
  className?: string;
  /**
   * Sort key for a computed cell. Defaults to `row[key]` when the key names a field on the
   * row, and to the rendered cell's text otherwise.
   */
  sortValue?: (row: R) => SortValue;
  /** `false` makes the header inert — no click target, no indicator. */
  sortable?: boolean;
}

type Sort = { key: string; dir: 'asc' | 'desc' };

/** Rows above this count paginate automatically; `pageSize` overrides, `pageSize={0}` disables. */
const DEFAULT_PAGE_SIZE = 100;

/** Flatten a rendered cell to the text a reader sees — used for filtering and as sort fallback. */
function cellText(node: ReactNode): string {
  if (node === null || node === undefined || typeof node === 'boolean') return '';
  if (typeof node === 'string') return node;
  if (typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(cellText).join(' ');
  if (isValidElement(node)) return cellText((node.props as { children?: ReactNode }).children);
  return '';
}

function sortKeyOf<R>(col: Column<R>, row: R): string | number | null {
  if (col.sortValue) {
    const v = col.sortValue(row);
    if (v === null || v === undefined) return null;
    return typeof v === 'boolean' ? (v ? 1 : 0) : v;
  }
  if (row && typeof row === 'object' && col.key in (row as object)) {
    const raw = (row as Record<string, unknown>)[col.key];
    if (typeof raw === 'number' || typeof raw === 'string') return raw;
    if (typeof raw === 'boolean') return raw ? 1 : 0;
    if (raw === null || raw === undefined) return null;
  }
  return cellText(col.render(row)) || null;
}

function compareKeys(a: string | number, b: string | number): number {
  if (typeof a === 'number' && typeof b === 'number') return a - b;
  return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: 'base' });
}

function Pager({
  from,
  to,
  total,
  page,
  pages,
  onPage,
}: {
  from: number;
  to: number;
  total: number;
  page: number;
  pages: number;
  onPage: (p: number) => void;
}) {
  const btn =
    'rounded border border-zinc-700 bg-zinc-900 px-1.5 py-0.5 text-zinc-400 transition enabled:hover:bg-zinc-800 enabled:hover:text-zinc-200 disabled:opacity-30 focus:outline-none focus-visible:border-blue-700';
  return (
    <div className="flex items-center justify-end gap-2 text-[11px] text-zinc-500">
      <button type="button" className={btn} aria-label="previous page" disabled={page === 0} onClick={() => onPage(page - 1)}>
        ‹
      </button>
      <span>
        <span className="font-mono text-zinc-300">
          {from}–{to}
        </span>{' '}
        of <span className="font-mono text-zinc-400">{total}</span>
      </span>
      <button
        type="button"
        className={btn}
        aria-label="next page"
        disabled={page >= pages - 1}
        onClick={() => onPage(page + 1)}
      >
        ›
      </button>
    </div>
  );
}

export function DataTable<R>({
  rows,
  columns,
  empty = 'no rows',
  rowKey,
  maxHeight,
  filterable = false,
  filterLabel = 'filter',
  filterPlaceholder = 'match any cell',
  pageSize = DEFAULT_PAGE_SIZE,
}: {
  rows: R[];
  columns: Column<R>[];
  empty?: ReactNode;
  rowKey: (row: R, i: number) => string;
  maxHeight?: number;
  /** Show a free-text box above the table matching case-insensitively across visible cell text. */
  filterable?: boolean;
  filterLabel?: string;
  filterPlaceholder?: string;
  /** Rows per page; `0` never paginates. */
  pageSize?: number;
}) {
  const [sort, setSort] = useState<Sort | null>(null);
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(0);

  const needle = filterable ? query.trim().toLowerCase() : '';

  const filtered = useMemo(() => {
    if (!needle) return rows;
    return rows.filter((r) =>
      columns
        .map((c) => cellText(c.render(r)))
        .join(' ')
        .toLowerCase()
        .includes(needle),
    );
  }, [rows, columns, needle]);

  const sorted = useMemo(() => {
    const col = sort ? columns.find((c) => c.key === sort.key) : undefined;
    if (!sort || !col) return filtered;
    const dir = sort.dir === 'asc' ? 1 : -1;
    // Decorate with the original index so ties — and the null block — keep input order.
    const decorated = filtered.map((row, i) => ({ row, i, k: sortKeyOf(col, row) }));
    decorated.sort((x, y) => {
      if (x.k === null || y.k === null) {
        if (x.k === null && y.k === null) return x.i - y.i;
        return x.k === null ? 1 : -1;
      }
      const c = compareKeys(x.k, y.k);
      return c !== 0 ? c * dir : x.i - y.i;
    });
    return decorated.map((d) => d.row);
  }, [filtered, columns, sort]);

  const size = pageSize > 0 ? pageSize : 0;
  const paged = size > 0 && sorted.length > size;
  const pages = paged ? Math.ceil(sorted.length / size) : 1;
  const current = Math.min(page, pages - 1);
  const visible = paged ? sorted.slice(current * size, current * size + size) : sorted;

  // Tri-state: unsorted → asc → desc → back to the order the caller supplied.
  function toggle(key: string) {
    setPage(0);
    setSort((s) => (s?.key !== key ? { key, dir: 'asc' } : s.dir === 'asc' ? { key, dir: 'desc' } : null));
  }

  function onQuery(v: string) {
    setPage(0);
    setQuery(v);
  }

  // Genuinely empty: unchanged from before this component could filter.
  if (rows.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-zinc-800 p-6 text-center text-sm text-zinc-500">
        {empty}
      </div>
    );
  }

  const controls = filterable ? (
    <div className="flex flex-wrap items-center gap-3">
      <TextFilter value={query} onChange={onQuery} label={filterLabel} placeholder={filterPlaceholder} />
      {needle && filtered.length > 0 && (
        <span className="text-[11px] text-zinc-500">
          <span className="font-mono text-zinc-300">{filtered.length}</span> of {rows.length} match
        </span>
      )}
    </div>
  ) : null;

  // Filtered to nothing — said differently from an empty table, so the box reads as a filter miss.
  if (visible.length === 0) {
    return (
      <div className="space-y-2">
        {controls}
        <div className="rounded-lg border border-dashed border-zinc-800 p-6 text-center text-sm text-zinc-500">
          0 of {rows.length} match
        </div>
      </div>
    );
  }

  const table = (
    <div className="overflow-auto rounded-lg border border-zinc-800" style={{ maxHeight }}>
      <table className="w-full min-w-full border-collapse text-xs">
        <thead className="sticky top-0 bg-zinc-900 text-zinc-400">
          <tr>
            {columns.map((c) => {
              const on = c.sortable !== false;
              const active = sort?.key === c.key;
              return (
                <th
                  key={c.key}
                  aria-sort={active ? (sort.dir === 'asc' ? 'ascending' : 'descending') : undefined}
                  className={`border-b border-zinc-800 px-3 py-2 font-medium ${
                    c.align === 'right' ? 'text-right' : 'text-left'
                  }`}
                >
                  {on ? (
                    <button
                      type="button"
                      onClick={() => toggle(c.key)}
                      title={active && sort.dir === 'desc' ? 'clear sort' : 'sort'}
                      className={`inline-flex w-full cursor-pointer items-center gap-1 text-left font-medium text-inherit transition hover:text-zinc-200 focus:outline-none focus-visible:text-blue-300 ${
                        c.align === 'right' ? 'justify-end text-right' : ''
                      }`}
                    >
                      {c.header}
                      {active && (
                        <span aria-hidden className="text-[9px] leading-none text-zinc-300">
                          {sort.dir === 'asc' ? '▲' : '▼'}
                        </span>
                      )}
                    </button>
                  ) : (
                    c.header
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {visible.map((row, i) => (
            <tr key={rowKey(row, i)} className="odd:bg-zinc-900/30 hover:bg-zinc-800/50">
              {columns.map((c) => (
                <td
                  key={c.key}
                  className={`border-b border-zinc-900 px-3 py-1.5 text-zinc-300 ${
                    c.align === 'right' ? 'text-right font-mono' : ''
                  } ${c.className ?? ''}`}
                >
                  {c.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  if (!controls && !paged) return table;

  return (
    <div className="space-y-2">
      {controls}
      {table}
      {paged && (
        <Pager
          from={current * size + 1}
          to={current * size + visible.length}
          total={sorted.length}
          page={current}
          pages={pages}
          onPage={setPage}
        />
      )}
    </div>
  );
}
