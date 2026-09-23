import { Link, useLocation } from 'react-router-dom';

import { useJourney } from '../../components/journeyContext';
import { findPage, isStepPath } from './tree';

/**
 * The pages an iteration carries besides its steps — iteration 4's model zoo, say.
 *
 * Read from the manifest tree the header draws (a page declares `parent`), not typed here, so
 * a dashboard added under any iteration shows up on that iteration's overview by itself. A
 * step is already a card on this page and is left out; an iteration with no other page
 * renders nothing.
 */
export function Companions() {
  const { pathname } = useLocation();
  const groups = useJourney();
  const self = groups.map((g) => findPage(g.pages, pathname)).find(Boolean);
  const extra = (self?.children ?? []).filter((c) => !isStepPath(c.to));
  if (extra.length === 0) return null;

  return (
    <section aria-label="Pages of this iteration" className="space-y-2">
      <h2 className="text-sm font-semibold text-chrome-100">Pages of this iteration</h2>
      <div className="grid gap-3 md:grid-cols-2">
        {extra.map((p) => (
          <Link
            key={p.to}
            to={p.to}
            onPointerEnter={p.preload}
            onFocus={p.preload}
            className="block rounded-card border border-line bg-panel p-4 transition hover:border-line-strong hover:bg-chrome-900/60 focus:outline-none focus-visible:ring-1 focus-visible:ring-machinery-500"
          >
            <p className="text-xs font-semibold text-machinery-300">{p.title} →</p>
            <p className="mt-1 text-micro leading-relaxed text-chrome-400">{p.description}</p>
          </Link>
        ))}
      </div>
    </section>
  );
}
