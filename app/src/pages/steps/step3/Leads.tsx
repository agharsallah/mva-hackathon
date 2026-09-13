import type { Step3Lead } from '../../../api/types';
import { count } from './metrics';

/**
 * Genes still carrying two heterozygous alleles once every call has been through a second
 * instrument. Deliberately unsorted by anything that looks like a score: this step ranks
 * nothing, and the read route was measured to have no discriminating power of its own.
 */
export function Leads({ rows }: { rows: Step3Lead[] }) {
  if (rows.length === 0) {
    return (
      <p className="text-sm text-chrome-400">No gene carries two confirmed heterozygous alleles.</p>
    );
  }
  return (
    <div className="max-h-96 overflow-auto">
      <table className="w-full text-sm">
        <thead className="text-xs text-chrome-400">
          <tr className="border-b border-chrome-800">
            <th className="py-1 pr-3">gene</th>
            <th className="py-1 pr-3">tier</th>
            <th className="py-1 pr-3 text-right">confirmed het</th>
            <th className="py-1 pr-3 text-right">of those, vendor-unreported</th>
            <th className="py-1 pr-3 text-right">bait density</th>
            <th className="py-1 pr-3">reachable</th>
          </tr>
        </thead>
        <tbody className="tabular-nums">
          {rows.map((row) => (
            <tr key={row.symbol} className="border-b border-chrome-900/60">
              <td className="py-1 pr-3 font-medium">{row.symbol}</td>
              <td className="py-1 pr-3">{row.tier}</td>
              <td className="py-1 pr-3 text-right">{count(row.confirmed_het)}</td>
              <td className="py-1 pr-3 text-right">{count(row.confirmed_novel)}</td>
              <td className="py-1 pr-3 text-right">
                {row.bait_density === null ? '—' : row.bait_density.toFixed(3)}
              </td>
              <td className="py-1 pr-3">{row.reachable ? 'yes' : 'no'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
