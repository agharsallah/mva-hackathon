/**
 * The right half of the builder: the payload as it will be written, in file order.
 *
 * File order is rank order — the scorer sorts by descending epcr and breaks ties by file
 * position, so the ladder (0.99, 0.98, …) is re-laid on every move and a row's place in
 * this list *is* the rank an oracle reply will be decoded from. The epcr cell stays
 * editable because a deliberate gap is sometimes the point; the server refuses the file
 * if an edit breaks the descent.
 */

import type { DraftRow } from './probePayload';
import { MAX_ROWS, variantLabel } from './probePayload';
import type { FindingType } from '../../api/types/probebuild';

export interface PayloadTableProps {
  rows: DraftRow[];
  onMove: (id: string, delta: number) => void;
  onRemove: (id: string) => void;
  onPatch: (id: string, patch: Partial<DraftRow>) => void;
}

const cell = 'border-b border-zinc-900 px-2 py-1.5 align-top text-zinc-300';
const iconButton =
  'rounded border border-zinc-700 px-1 text-[10px] leading-4 text-zinc-400 hover:bg-zinc-800 disabled:opacity-25';

export function PayloadTable({ rows, onMove, onRemove, onPatch }: PayloadTableProps) {
  if (rows.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-zinc-800 p-6 text-center text-sm text-zinc-500">
        Nothing staged. Add a pair row for each compound-het hypothesis, or single rows to fish for a
        partial match.
      </div>
    );
  }

  return (
    <div className="overflow-auto rounded-lg border border-zinc-800">
      <table className="w-full border-collapse text-xs">
        <thead className="bg-zinc-900 text-zinc-400">
          <tr>
            <th className="border-b border-zinc-800 px-2 py-2 text-left font-medium">rank</th>
            <th className="border-b border-zinc-800 px-2 py-2 text-left font-medium">variant 1</th>
            <th className="border-b border-zinc-800 px-2 py-2 text-left font-medium">variant 2</th>
            <th className="border-b border-zinc-800 px-2 py-2 text-left font-medium">epcr</th>
            <th className="border-b border-zinc-800 px-2 py-2 text-left font-medium">finding</th>
            <th className="border-b border-zinc-800 px-2 py-2 text-left font-medium">notes</th>
            <th className="border-b border-zinc-800 px-2 py-2 text-left font-medium" />
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={row.id} className="odd:bg-zinc-900/30">
              <td className={`${cell} font-mono text-zinc-500`}>
                <div className="flex items-center gap-1">
                  <span className={i === 0 ? 'text-emerald-400' : ''}>{i + 1}</span>
                  <span className="flex flex-col gap-0.5">
                    <button
                      type="button"
                      aria-label="move up"
                      className={iconButton}
                      disabled={i === 0}
                      onClick={() => onMove(row.id, -1)}
                    >
                      ▲
                    </button>
                    <button
                      type="button"
                      aria-label="move down"
                      className={iconButton}
                      disabled={i === rows.length - 1}
                      onClick={() => onMove(row.id, 1)}
                    >
                      ▼
                    </button>
                  </span>
                </div>
              </td>
              <td className={`${cell} font-mono`}>
                {variantLabel(row.variant1)}
                {row.label && <div className="text-[10px] text-zinc-600">{row.label}</div>}
              </td>
              <td className={`${cell} font-mono`}>
                {row.variant2 ? (
                  variantLabel(row.variant2)
                ) : (
                  <span className="text-zinc-600">— single</span>
                )}
              </td>
              <td className={cell}>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  max="1"
                  value={row.epcr}
                  onChange={(e) => onPatch(row.id, { epcr: Number(e.target.value) })}
                  className="w-16 rounded border border-zinc-700 bg-zinc-950 px-1 py-0.5 font-mono text-[11px] text-zinc-100"
                />
              </td>
              <td className={cell}>
                <select
                  value={row.findingType}
                  onChange={(e) => onPatch(row.id, { findingType: e.target.value as FindingType })}
                  className="rounded border border-zinc-700 bg-zinc-900 px-1 py-0.5 text-[11px] text-zinc-200"
                >
                  <option value="primary">primary</option>
                  <option value="secondary">secondary</option>
                </select>
              </td>
              <td className={cell}>
                <input
                  type="text"
                  value={row.notes}
                  placeholder="why this row"
                  onChange={(e) => onPatch(row.id, { notes: e.target.value })}
                  className="w-full min-w-[10rem] rounded border border-zinc-700 bg-zinc-950 px-1.5 py-0.5 text-[11px] text-zinc-100 placeholder:text-zinc-600"
                />
              </td>
              <td className={cell}>
                <button
                  type="button"
                  onClick={() => onRemove(row.id)}
                  aria-label="remove row"
                  className="rounded border border-red-900/60 px-1.5 py-0.5 text-[10px] text-red-400 hover:bg-red-950/40"
                >
                  ×
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length >= MAX_ROWS && (
        <div className="border-t border-zinc-800 px-2 py-1.5 text-[11px] text-amber-400">
          {MAX_ROWS} rows — the scorer's cap. Remove one before adding another.
        </div>
      )}
    </div>
  );
}
