import type { Step2Lead } from '../../../api/types';
import { cx } from '../../../lib/ui';

/**
 * Every gene the filter leaves standing — targets and decoys in one table, in the order
 * the SQL produced.
 *
 * **Not re-sorted to put a target on top.** Ten targets and ten decoys survive, and by the
 * table's own key (truncating alleles, then a ClinVar assertion, then heterozygote count)
 * the first row is a decoy. Reordering the column priority until a target wins would be
 * choosing the answer and calling it a result; the honest reading is that the read route
 * alone does not rank a causal gene first, and the page says so.
 *
 * `novel` counts the qualifying alleles the delivered callset never reported. A gene whose
 * count equals its allele count reached this table entirely on unvalidated calls.
 */
export function Leads({ rows }: { rows: Step2Lead[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-xs text-chrome-400">
          <tr className="border-b border-chrome-800">
            <th className="py-1 pr-3 text-left">gene</th>
            <th className="py-1 pr-3 text-left">tier</th>
            <th className="py-1 pr-3 text-right">rare het</th>
            <th className="py-1 pr-3 text-right">hom alt</th>
            <th className="py-1 pr-3 text-right">truncating</th>
            <th className="py-1 pr-3 text-right">ClinVar</th>
            <th className="py-1 pr-3 text-right">novel</th>
            <th className="py-1 pr-3 text-right">bait density</th>
            <th className="py-1 text-right">depth</th>
          </tr>
        </thead>
        <tbody className="tabular-nums">
          {rows.map((row) => {
            const thin = row.mean_depth < 10;
            return (
              <tr key={row.symbol} className="border-b border-chrome-900/60">
                <td className="py-1 pr-3 font-medium">{row.symbol}</td>
                <td
                  className={cx(
                    'py-1 pr-3',
                    row.tier === 'decoy' ? 'text-broken-400' : 'text-good-400',
                  )}
                >
                  {row.tier}
                </td>
                <td className="py-1 pr-3 text-right">{row.rare_het}</td>
                <td className="py-1 pr-3 text-right">{row.rare_hom_alt}</td>
                <td className="py-1 pr-3 text-right">{row.truncating || ''}</td>
                <td className="py-1 pr-3 text-right">{row.clinvar_flagged || ''}</td>
                <td className="py-1 pr-3 text-right text-chrome-400">
                  {row.novel_qualifying || ''}
                </td>
                <td className="py-1 pr-3 text-right">{row.bait_density.toFixed(2)}</td>
                <td className={cx('py-1 text-right', thin && 'text-broken-400')}>
                  {row.mean_depth.toFixed(1)}×
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
