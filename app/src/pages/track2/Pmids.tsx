/**
 * A PubMed id, rendered as a link the reader can actually open.
 *
 * The visible text always carries the `PMID` prefix. That is not decoration: this page
 * renders thousands of public identifiers next to a case whose genomic positions may never
 * be committed, and `src/test/track2-page.test.tsx` fails the build on any bare run of
 * seven or more digits. A labelled id is both the honest rendering and the one the
 * coordinate check can tell apart from a position.
 */

import { pubmed } from './ladderModel';

export function Pmid({ pmid }: { pmid: string }) {
  return (
    <a
      href={pubmed(pmid)}
      target="_blank"
      rel="noreferrer"
      className="font-mono text-micro whitespace-nowrap text-machinery-300 underline decoration-machinery-800 underline-offset-2 hover:text-machinery-200"
    >
      PMID {pmid}
    </a>
  );
}

/** A list of ids, or an explicit gap — never an empty cell that reads as zero. */
export function PmidList({ pmids, none = '—' }: { pmids: string[]; none?: string }) {
  if (pmids.length === 0) return <span className="text-micro text-chrome-600">{none}</span>;
  return (
    <span className="flex flex-wrap gap-2">
      {pmids.map((p) => (
        <Pmid key={p} pmid={p} />
      ))}
    </span>
  );
}
