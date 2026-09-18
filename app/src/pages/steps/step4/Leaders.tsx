import type { Step4Leader } from '../../../api/types';
import { count, ratio } from './metrics';

/** Where a gene came from, in one word — the column that makes the ordering readable. */
function origin(row: Step4Leader): string {
  if (row.is_decoy) return 'decoy';
  if (row.is_target) return row.tier ?? 'target';
  return row.curated ? 'curated' : 'uncurated';
}

/**
 * The top of the genome-wide ordering, one row per gene.
 *
 * Four columns exist to stop the first one being read as a diagnosis. **origin** says
 * whether the child's symptoms nominated the gene at all, and a decoy in this table is not
 * an error — the controls went through the identical scoring and where they land is the
 * measurement. **behind** is how many times smaller this gene's ratio is than the leader's,
 * which is the number the one-order-of-magnitude claim was filed against. **P(trans)** is
 * the population co-occurrence state, and `undetermined` is its usual honest value here.
 * **read route** is step 3's confirmation triple, carried but contributing no rank.
 */
export function Leaders({ rows }: { rows: Step4Leader[] }) {
  if (rows.length === 0) {
    return <p className="text-sm text-chrome-400">The ranking has not been loaded yet.</p>;
  }
  return (
    <div className="max-h-[32rem] overflow-auto">
      <table className="w-full text-sm">
        <thead className="text-xs text-chrome-400">
          <tr className="border-b border-chrome-800">
            <th className="py-1 pr-3 text-right">#</th>
            <th className="py-1 pr-3">gene</th>
            <th className="py-1 pr-3">shape</th>
            <th className="py-1 pr-3">origin</th>
            <th className="py-1 pr-3 text-right">symptom rank</th>
            <th className="py-1 pr-3 text-right">likelihood ratio</th>
            <th className="py-1 pr-3 text-right">behind leader</th>
            <th className="py-1 pr-3">P(trans)</th>
            <th className="py-1 pr-3">read route</th>
          </tr>
        </thead>
        <tbody className="tabular-nums">
          {rows.map((row) => (
            <tr key={row.gene} className="border-b border-chrome-900/60">
              <td className="py-1 pr-3 text-right text-chrome-400">{row.gene_rank}</td>
              <td className="py-1 pr-3 font-medium">{row.gene}</td>
              <td className="py-1 pr-3">{row.shape}</td>
              <td className="py-1 pr-3">{origin(row)}</td>
              <td className="py-1 pr-3 text-right">{count(row.phenotype_rank)}</td>
              <td className="py-1 pr-3 text-right">{ratio(row.combined_lr)}</td>
              <td className="py-1 pr-3 text-right">
                {row.behind_leader === null ? '—' : `${ratio(row.behind_leader)}×`}
              </td>
              <td className="py-1 pr-3">{row.p_trans_state ?? '—'}</td>
              <td className="py-1 pr-3">
                {row.biallelic_confirmed === null
                  ? 'not typed'
                  : row.biallelic_confirmed
                    ? 'two confirmed'
                    : 'not confirmed'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
