import { Link } from 'react-router-dom';

import type { HubLink } from './model';

/**
 * A compact row of links back to the iterations hub, for the pages that open one iteration
 * (a research iteration, a track, a submission dossier). Two numberings exist and a reader
 * lost between them needs one click to the page that lays both side by side.
 */

const LINK =
  'rounded-pill border border-machinery-900 bg-machinery-950/40 px-2 py-0.5 text-micro text-machinery-300 transition hover:border-machinery-700 hover:text-machinery-200';

export function HubLinks({ links, lead = 'Overview' }: { links: HubLink[]; lead?: string }) {
  return (
    <nav aria-label="Iteration overview links" className="flex flex-wrap items-center gap-2">
      <span className="text-micro text-chrome-400">{lead}</span>
      {links.map((l) => (
        <Link key={l.to} to={l.to} title={l.title} className={LINK}>
          {l.label} <span aria-hidden="true">→</span>
        </Link>
      ))}
    </nav>
  );
}
