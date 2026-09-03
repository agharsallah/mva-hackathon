/**
 * The short paths: one collapsible list per track, each term a jump to its anchor. The
 * chapters are the complete course; a track is the subset to read before one part of the app.
 */

import { Link } from 'react-router-dom';

import { type Dictionary, entriesOf } from '../../lib/dictionary';
import { TRACKS } from './tracks';

export function TrackList({ dictionary }: { dictionary: Dictionary }) {
  const byslug = new Map(entriesOf(dictionary).map((e) => [e.slug, e]));
  return (
    <section aria-label="Short paths" className="space-y-2">
      <h3 className="text-micro font-semibold text-chrome-500">Short paths</h3>
      {TRACKS.map((t) => (
        <details key={t.id} className="group">
          <summary className="flex cursor-pointer list-none items-baseline gap-2 rounded-control px-2 py-1 text-xs text-chrome-300 transition hover:bg-chrome-900 hover:text-chrome-100 [&::-webkit-details-marker]:hidden">
            <span
              aria-hidden="true"
              className="inline-block text-chrome-600 transition group-open:rotate-90"
            >
              ›
            </span>
            <span className="min-w-0">
              <span className="block">{t.title}</span>
              <span className="block text-micro text-chrome-600">
                {t.slugs.length} terms · before {t.forPages}
              </span>
            </span>
          </summary>
          <ol className="mt-1 space-y-0.5 pl-2">
            {t.slugs.map((slug, i) => {
              const e = byslug.get(slug);
              return (
                <li key={slug} className="flex items-baseline gap-2 text-xs">
                  <span className="w-4 shrink-0 text-right tabular-nums text-micro text-chrome-600">
                    {i + 1}
                  </span>
                  <Link
                    to={{ hash: `#${slug}` }}
                    className="truncate text-chrome-400 transition hover:text-chrome-100"
                  >
                    {e?.term ?? slug}
                  </Link>
                </li>
              );
            })}
          </ol>
        </details>
      ))}
    </section>
  );
}
