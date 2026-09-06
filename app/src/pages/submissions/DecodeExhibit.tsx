import type { DecodeTable } from '../../api/types';
import { Chip, Exhibit } from '../../components/Exhibit';
import { C } from '../../lib/palette';
import { cx, TEXT, TINT } from '../../lib/ui';
import { decodeRows, type DecodeTone } from './iteration';

/**
 * The decode table: what every reply the scorer can give would mean.
 *
 * A submission here is treated as a **measurement**, not a guess. Before the file is sent,
 * every plausible answer key is simulated and the results are grouped by the reply they
 * would produce — so the reply is informative whatever it says, and the row it lands on
 * names the next iteration.
 *
 * The table is hand-rolled rather than a `DataTable` because the colour of a row *is* the
 * content: each row is tinted by what that reply would mean, and the shared table renders
 * uniform rows on purpose.
 */

const CELL_TONE: Record<DecodeTone, string> = {
  good: TEXT.good,
  broken: TEXT.broken,
  decision: TEXT.decision,
  machinery: TEXT.machinery,
};

export function DecodeExhibit({ table, source }: { table: DecodeTable; source?: string }) {
  const rows = decodeRows(table);

  return (
    <Exhibit
      title="Decode table — what every possible reply would mean"
      legend={
        <>
          One row per distinguishable reply the scorer can return.{' '}
          <Chip color={C.good}>green = the goal</Chip> — a full match at rank 1: the pair is right
          and there is nothing left to ask.{' '}
          <Chip color={C.decision}>yellow = a decision point</Chip> — a reply that two hypotheses
          share, so it narrows without deciding; this is the ambiguity that caps the information
          gain. <Chip color={C.broken}>red = lost points</Chip> — no match at all: neither allele is
          causal, and the search restarts. <Chip color={C.machinery}>blue = neutral machinery</Chip>{' '}
          — an informative wrong answer that names which alternative pairing is real. Hover a row
          for the one clause behind its colour.
        </>
      }
      reading="This is the argument for spending a probe at all: the prior over the hypothesis space is not uniform, so the expected reply carries more than a yes/no. Read the summary line as the price of the question — the bits it buys — and the rank order as what was actually submitted to buy them."
      data={table}
      source={source}
    >
      <div className="space-y-3">
        <div className="overflow-x-auto rounded-card border border-line">
          <table className="w-full border-collapse text-xs">
            <caption className="sr-only">
              Every reply the challenge scorer can return, with the hypotheses it would leave
              standing
            </caption>
            <thead className="bg-chrome-900 text-chrome-400">
              <tr>
                {table.columns.map((c) => (
                  <th
                    key={c}
                    scope="col"
                    className="border-b border-line px-3 py-2 text-left font-medium"
                  >
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr
                  key={row.cells.join('|') || i}
                  data-tone={row.tone}
                  title={row.why}
                  className={cx(TINT[row.tone])}
                >
                  {row.cells.map((cell, j) => (
                    <td
                      key={j}
                      className={cx(
                        'border-b border-line-soft px-3 py-2',
                        j === 0 ? cx('font-mono', CELL_TONE[row.tone]) : 'text-chrome-300',
                      )}
                    >
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <p className="max-w-[90ch] text-xs leading-relaxed text-chrome-300">
          <span className="mr-2 font-semibold text-chrome-400">Summary</span>
          {table.summary}
        </p>
        <p className="max-w-[90ch] text-xs leading-relaxed text-chrome-400">
          <span className="mr-2 font-semibold text-chrome-400">Row order</span>
          {table.row_order}
        </p>
      </div>
    </Exhibit>
  );
}
