import type { Step5Catalogue } from '../../../api/types';
import { count } from './metrics';

/** What a gene got into this table for — the column that stops a row being over-read. */
function why(row: Step5Catalogue): string {
  if (row.carried_pathogenic > 0) return 'carries a ClinVar pathogenic allele';
  if (row.described > 0) return 'an allele of it has been published about';
  return 'a leading gene';
}

/**
 * Per gene: how many of this child's alleles the literature could be asked about, and how
 * many it had an answer for.
 *
 * **Three counts, never one percentage.** `alleles` is every allele the ranking scored in
 * this gene. `unqueryable` are the ones with no dbSNP identifier — a literature index keyed
 * on dbSNP could not have had an opinion about them, so they are not evidence of absence.
 * `described` are the ones somebody has actually published about.
 *
 * **`carries` is the only column that is about the child.** It comes from a different
 * instrument entirely: step 3 counted k-mers of the public ClinVar pathogenic catalogue in
 * the raw reads, with no aligner and no caller. A publication count says the variant is
 * known; this says the child has it.
 */
export function Catalogue({ rows }: { rows: Step5Catalogue[] }) {
  if (rows.length === 0) {
    return <p className="text-sm text-chrome-400">The catalogue has not been loaded yet.</p>;
  }
  return (
    <div className="max-h-[32rem] overflow-auto">
      <table className="w-full text-sm">
        <thead className="text-xs text-chrome-400">
          <tr className="border-b border-chrome-800">
            <th className="py-1 pr-3">gene</th>
            <th className="py-1 pr-3">origin</th>
            <th className="py-1 pr-3 text-right">alleles</th>
            <th className="py-1 pr-3 text-right">askable</th>
            <th className="py-1 pr-3 text-right">never askable</th>
            <th className="py-1 pr-3 text-right">published</th>
            <th className="py-1 pr-3 text-right">most-cited</th>
            <th className="py-1 pr-3 text-right">carries</th>
            <th className="py-1 pr-3">in the table because</th>
          </tr>
        </thead>
        <tbody className="tabular-nums">
          {rows.map((row) => (
            <tr key={row.gene} className="border-b border-chrome-900/60">
              <td className="py-1 pr-3 font-medium">{row.gene}</td>
              <td className="py-1 pr-3">
                {row.is_decoy ? 'decoy' : row.is_target ? 'target' : 'neither'}
              </td>
              <td className="py-1 pr-3 text-right">{count(row.alleles)}</td>
              <td className="py-1 pr-3 text-right">{count(row.queryable)}</td>
              <td className="py-1 pr-3 text-right text-chrome-400">{count(row.unqueryable)}</td>
              <td className="py-1 pr-3 text-right">{count(row.described)}</td>
              <td className="py-1 pr-3 text-right">{count(row.most_cited_allele)}</td>
              <td className="py-1 pr-3 text-right font-medium">{count(row.carried_pathogenic)}</td>
              <td className="py-1 pr-3 text-chrome-400">{why(row)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
