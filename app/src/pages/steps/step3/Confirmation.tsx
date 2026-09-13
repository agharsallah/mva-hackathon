import type { Step3Contrast } from '../../../api/types';
import { count, share } from './metrics';

/**
 * The step's headline, as a table beside its chart.
 *
 * Four numbers rather than one rate, deliberately. H020 is refuted — a target-gene result
 * does not outweigh a decoy-gene one before the filter — so a single confirmation rate
 * invites exactly the reading the decoy set exists to prevent.
 */
export function Confirmation({ rows }: { rows: Step3Contrast[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-xs text-chrome-400">
          <tr className="border-b border-chrome-800">
            <th className="py-1 pr-3">allele set</th>
            <th className="py-1 pr-3 text-right">target alleles</th>
            <th className="py-1 pr-3 text-right">confirmed</th>
            <th className="py-1 pr-3 text-right">decoy alleles</th>
            <th className="py-1 pr-3 text-right">confirmed</th>
          </tr>
        </thead>
        <tbody className="tabular-nums">
          {rows.map((row) => (
            <tr key={row.allele_set} className="border-b border-chrome-900/60">
              <td className="py-1 pr-3">{row.allele_set}</td>
              <td className="py-1 pr-3 text-right">{count(row.target_alleles)}</td>
              <td className="py-1 pr-3 text-right font-medium">
                {count(row.target_confirmed)} ({share(row.target_rate)})
              </td>
              <td className="py-1 pr-3 text-right">{count(row.decoy_alleles)}</td>
              <td className="py-1 pr-3 text-right">
                {count(row.decoy_confirmed)} ({share(row.decoy_rate)})
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
