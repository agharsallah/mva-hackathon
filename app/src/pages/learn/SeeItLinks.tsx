/**
 * "See it in the app" — the line under an entry that turns a definition into a figure over
 * this case's data, plus the methodology entry that measured it. Rendered only for entries
 * `seeIt.ts` knows about; most words are background and get no line.
 */

import { Link } from 'react-router-dom';

import type { EntryBlock } from '../../lib/dictionary';
import { docUrl, seeIt } from './seeIt';

const LINK =
  'rounded-pill border border-machinery-900 bg-machinery-950/40 px-2 py-0.5 text-micro text-machinery-300 transition hover:border-machinery-700 hover:text-machinery-100';
const DOC =
  'rounded-pill border border-line px-2 py-0.5 text-micro text-chrome-400 transition hover:border-line-strong hover:text-chrome-200';

export function SeeItLinks({ entry }: { entry: EntryBlock }) {
  const links = seeIt(entry.slug);
  if (!links) return null;
  return (
    <div className="mt-2 flex flex-wrap items-center gap-1.5">
      <span className="mr-1 text-micro text-chrome-400">See it in the app</span>
      {links.app.map((l) => (
        <Link key={l.to} to={l.to} className={LINK}>
          {l.label} <span aria-hidden="true">→</span>
        </Link>
      ))}
      {links.docs?.map((d) => (
        <a key={d.path} href={docUrl(d.path)} target="_blank" rel="noreferrer" className={DOC}>
          how it was measured: {d.label}
        </a>
      ))}
    </div>
  );
}
