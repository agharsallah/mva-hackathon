/**
 * The reader's starred definitions — the words they want to come back to, in the order they
 * were starred, each a jump to its entry and a star to let it go. Lives in the rail so it is
 * one click away from any chapter; the star on the entry card is the other end of it.
 *
 * Two ways to keep a long list out of the way: the whole section folds (a native `<details>`,
 * open by default), and past `SHOWN` items the list shows the first few with a "show all"
 * toggle, so twenty starred words do not push the chapter list off screen.
 */

import { useState } from 'react';
import { Link } from 'react-router-dom';

import { type Dictionary, entriesOf } from '../../lib/dictionary';
import type { StoredSet } from './storedSet';

/** Items shown before the list folds behind "show all". */
const SHOWN = 6;

export function Star({ on }: { on: boolean }) {
  return (
    <span aria-hidden="true" className={on ? 'text-decision-400' : 'text-chrome-600'}>
      {on ? '★' : '☆'}
    </span>
  );
}

export function Starred({ dictionary, stars }: { dictionary: Dictionary; stars: StoredSet }) {
  const bySlug = new Map(entriesOf(dictionary).map((e) => [e.slug, e]));
  const chapterOf = new Map(
    dictionary.chapters.flatMap((c) =>
      c.blocks.flatMap((b) => (b.kind === 'entry' ? [[b.slug, c.number] as const] : [])),
    ),
  );
  const items = stars.list.filter((slug) => bySlug.has(slug));
  const [all, setAll] = useState(false);
  const shown = all ? items : items.slice(0, SHOWN);
  const hidden = items.length - shown.length;
  return (
    <details open aria-label="Starred definitions" className="group space-y-2">
      <summary className="flex cursor-pointer list-none items-baseline justify-between rounded-control px-1 transition hover:bg-chrome-900 [&::-webkit-details-marker]:hidden">
        <h3 className="text-micro font-semibold text-chrome-500">
          <Star on={items.length > 0} /> Starred
        </h3>
        <span className="tabular-nums text-micro text-chrome-600">
          {items.length}
          <span aria-hidden="true" className="ml-1.5 inline-block transition group-open:rotate-90">
            ›
          </span>
        </span>
      </summary>
      {items.length === 0 ? (
        <p className="font-serif text-note leading-relaxed text-chrome-500">
          Star a definition to keep it here. Starred words stay across reloads, in this browser.
        </p>
      ) : (
        <ol className="space-y-0.5">
          {shown.map((slug) => {
            const e = bySlug.get(slug)!;
            return (
              <li key={slug} className="flex items-baseline gap-1 text-xs">
                <button
                  type="button"
                  onClick={() => stars.remove(slug)}
                  aria-label={`Unstar ${e.term}`}
                  title="Remove from starred"
                  className="shrink-0 rounded-pill px-1 text-micro transition hover:bg-chrome-900"
                >
                  <Star on />
                </button>
                <Link
                  to={{ hash: `#${slug}` }}
                  className="flex min-w-0 flex-1 items-baseline justify-between gap-2 rounded-control px-1 py-0.5 text-chrome-300 transition hover:bg-chrome-900 hover:text-chrome-50"
                >
                  <span className="truncate">{e.term}</span>
                  <span className="shrink-0 tabular-nums text-micro text-chrome-600">
                    ch. {chapterOf.get(slug)}
                  </span>
                </Link>
              </li>
            );
          })}
        </ol>
      )}
      {items.length > SHOWN && (
        <button
          type="button"
          onClick={() => setAll((v) => !v)}
          aria-expanded={all}
          className="w-full rounded-control px-2 py-1 text-left text-micro text-chrome-500 transition hover:bg-chrome-900 hover:text-chrome-300"
        >
          {all ? 'Show fewer' : `Show all ${items.length} (${hidden} more)`}
        </button>
      )}
    </details>
  );
}
