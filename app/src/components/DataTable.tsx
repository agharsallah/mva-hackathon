import type { ReactNode } from 'react';

export interface Column<R> {
  key: string;
  header: ReactNode;
  render: (row: R) => ReactNode;
  align?: 'left' | 'right';
  className?: string;
}

export function DataTable<R>({
  rows,
  columns,
  empty = 'no rows',
  rowKey,
  maxHeight,
}: {
  rows: R[];
  columns: Column<R>[];
  empty?: ReactNode;
  rowKey: (row: R, i: number) => string;
  maxHeight?: number;
}) {
  if (rows.length === 0) {
    return <div className="rounded-lg border border-dashed border-zinc-800 p-6 text-center text-sm text-zinc-500">{empty}</div>;
  }
  return (
    <div className="overflow-auto rounded-lg border border-zinc-800" style={{ maxHeight }}>
      <table className="w-full min-w-full border-collapse text-xs">
        <thead className="sticky top-0 bg-zinc-900 text-zinc-400">
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                className={`border-b border-zinc-800 px-3 py-2 font-medium ${
                  c.align === 'right' ? 'text-right' : 'text-left'
                }`}
              >
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
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
}
