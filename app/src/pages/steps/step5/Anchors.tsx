import type { Step5Anchor } from '../../../api/types';
import { ANCHOR_TERMS } from './metrics';

/**
 * Papers that discuss a candidate gene alongside several of the child's clinical features.
 *
 * **Every row was produced by a script, not chosen by a reader.** One PubTator search per
 * (gene, clinical term) pair; a paper returned by five of the seven searches matches five
 * of the child's features. That matters more than it sounds: a hand-picked reading list in
 * a blind design is a leak wearing a citation, because the papers a human would reach for
 * are the discovery papers of the gene the previous iteration already found.
 *
 * **The decoy rows belong here.** A paper linking a control gene to several of the same
 * features is exactly what says whether the target rows mean anything.
 */
export function Anchors({ rows }: { rows: Step5Anchor[] }) {
  if (rows.length === 0) {
    return <p className="text-sm text-chrome-400">No anchor has been derived yet.</p>;
  }
  return (
    <div className="max-h-[32rem] overflow-auto">
      <table className="w-full text-sm">
        <thead className="text-xs text-chrome-400">
          <tr className="border-b border-chrome-800">
            <th className="py-1 pr-3">gene</th>
            <th className="py-1 pr-3">origin</th>
            <th className="py-1 pr-3 text-right">terms</th>
            <th className="py-1 pr-3">matched features</th>
            <th className="py-1 pr-3">paper</th>
            <th className="py-1 pr-3">PMID</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.gene}-${row.pmid}`} className="border-b border-chrome-900/60">
              <td className="py-1 pr-3 font-medium">{row.gene}</td>
              <td className="py-1 pr-3">
                {row.is_decoy ? 'decoy' : row.is_target ? 'target' : 'neither'}
              </td>
              <td
                className={`py-1 pr-3 text-right tabular-nums ${
                  row.terms_matched >= ANCHOR_TERMS ? 'font-semibold' : 'text-chrome-400'
                }`}
              >
                {row.terms_matched}/{row.terms_total}
              </td>
              <td className="py-1 pr-3 text-xs text-chrome-400">{row.matched_terms}</td>
              <td className="py-1 pr-3">
                <span className="line-clamp-2">{row.title}</span>
                <span className="text-xs text-chrome-500">
                  {row.journal} {row.year}
                </span>
              </td>
              <td className="py-1 pr-3">
                <a
                  className="text-machinery-400 hover:underline"
                  href={`https://pubmed.ncbi.nlm.nih.gov/${row.pmid}/`}
                  target="_blank"
                  rel="noreferrer"
                >
                  {row.pmid}
                </a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
