import type { Step4Leader } from '../../../api/types';
import { C } from '../../../lib/palette';
import { log10, ratio, terms } from './metrics';

/**
 * The leading hypothesis's arithmetic, term by term.
 *
 * Every lane keeps its row, including the ones that contributed exactly 1. Two different
 * things produce a 1 and both matter: the lane had nothing to say, or it was **damped** —
 * it shares a correlation group with a stronger lane, and counting a missense predictor
 * tuned on ClinVar beside ClinVar itself would inflate the answer. A table that showed only
 * the lanes that moved the number would hide how much was consulted.
 */
export function Decomposition({ row }: { row: Step4Leader | undefined }) {
  const rows = terms(row);
  if (rows.length === 0) {
    return <p className="text-sm text-chrome-400">No arithmetic is recorded for this row.</p>;
  }
  // Two numbers, deliberately: the ratio the ranking stored, and the product of the terms
  // as they are *printed* here. The terms are rounded to four significant figures on their
  // way into the table, so the product drifts by a fraction of a percent — and a reader who
  // multiplies the column and gets a different number should find that explained rather
  // than have to wonder which one the ordering used.
  const stored = row?.combined_lr;
  const printed = rows.reduce((product, term) => product * term.value, 1);
  const drift = stored ? Math.abs(printed / stored - 1) : 0;
  return (
    <table className="w-full text-sm">
      <thead className="text-xs text-chrome-400">
        <tr className="border-b border-chrome-800">
          <th className="py-1 pr-3">lane</th>
          <th className="py-1 pr-3 text-right">×</th>
          <th className="py-1 pr-3 text-right">log₁₀</th>
          <th className="py-1 pr-3">what it did</th>
        </tr>
      </thead>
      <tbody className="tabular-nums">
        {rows.map((term) => {
          const tone = term.value > 1 ? C.good : term.value < 1 ? C.broken : undefined;
          return (
            <tr key={term.name} className="border-b border-chrome-900/60">
              <td className="py-1 pr-3 font-medium">{term.name}</td>
              <td className="py-1 pr-3 text-right" style={{ color: tone }}>
                {ratio(term.value)}
              </td>
              <td className="py-1 pr-3 text-right" style={{ color: tone }}>
                {log10(term.value).toFixed(2)}
              </td>
              <td className="py-1 pr-3 text-chrome-400">
                {term.value > 1
                  ? 'argues for the gene'
                  : term.value < 1
                    ? 'argues against it'
                    : 'said nothing, or lost its correlation group'}
              </td>
            </tr>
          );
        })}
        <tr className="border-t border-chrome-700">
          <td className="py-1 pr-3 font-semibold">combined</td>
          <td className="py-1 pr-3 text-right font-semibold">{ratio(stored)}</td>
          <td className="py-1 pr-3 text-right font-semibold">{log10(stored).toFixed(2)}</td>
          <td className="py-1 pr-3 text-chrome-400">
            the ratio every other gene is ordered against
            {drift > 0
              ? ` — the printed terms multiply to ${ratio(printed)}, a ${(drift * 100).toFixed(2)}% rounding drift`
              : ''}
          </td>
        </tr>
      </tbody>
    </table>
  );
}
