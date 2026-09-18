import type { Step5Citation } from '../../../api/types';
import { count } from './metrics';

/**
 * The test that decides whether step 5 is a result or a list of famous genes.
 *
 * Every gene appears twice: once at the rank the knowledge queries gave it, once at the
 * rank it would have had from a raw PubMed hit count alone. **moved** is the difference.
 * A positive number means the literature promoted the gene above where its citation volume
 * would have put it, which is the only direction that says the route added information.
 *
 * A table where `moved` is near zero everywhere is a route that has measured fame, and the
 * step reports that as its finding rather than dressing it up as a ranking.
 */
export function Citations({ rows }: { rows: Step5Citation[] }) {
  if (rows.length === 0) {
    return <p className="text-sm text-chrome-400">The baseline comparison has not run yet.</p>;
  }
  return (
    <div className="max-h-[32rem] overflow-auto">
      <table className="w-full text-sm">
        <thead className="text-xs text-chrome-400">
          <tr className="border-b border-chrome-800">
            <th className="py-1 pr-3 text-right">#</th>
            <th className="py-1 pr-3">gene</th>
            <th className="py-1 pr-3">origin</th>
            <th className="py-1 pr-3 text-right">best paper</th>
            <th className="py-1 pr-3 text-right">published alleles</th>
            <th className="py-1 pr-3 text-right">PubMed hits</th>
            <th className="py-1 pr-3 text-right">citation rank</th>
            <th className="py-1 pr-3 text-right">moved</th>
            <th className="py-1 pr-3 text-right">rank by DNA</th>
          </tr>
        </thead>
        <tbody className="tabular-nums">
          {rows.map((row) => (
            <tr key={row.gene} className="border-b border-chrome-900/60">
              <td className="py-1 pr-3 text-right text-chrome-400">{row.knowledge_rank}</td>
              <td className="py-1 pr-3 font-medium">{row.gene}</td>
              <td className="py-1 pr-3">
                {row.is_decoy ? 'decoy' : row.is_target ? 'target' : 'neither'}
              </td>
              <td className="py-1 pr-3 text-right">{row.best_terms_matched}/7</td>
              <td className="py-1 pr-3 text-right">{count(row.described_alleles)}</td>
              <td className="py-1 pr-3 text-right">{count(row.pubmed_count)}</td>
              <td className="py-1 pr-3 text-right">{count(row.citation_rank)}</td>
              <td
                className={`py-1 pr-3 text-right ${row.moved > 0 ? 'text-good-400' : row.moved < 0 ? 'text-broken-400' : 'text-chrome-500'}`}
              >
                {row.moved > 0 ? `+${count(row.moved)}` : count(row.moved)}
              </td>
              <td className="py-1 pr-3 text-right text-chrome-400">{count(row.lr_rank)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
