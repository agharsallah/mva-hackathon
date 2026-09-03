/**
 * Find a word. Matches the term and its aliases first, then the definition text, across
 * every chapter; picking a result jumps to that entry's anchor, which is also what the URL
 * then says — so a search result is a shareable link.
 */

import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { type Dictionary, type EntryBlock } from '../../lib/dictionary';

interface Indexed {
  entry: EntryBlock;
  chapter: number;
  /** Lower-cased names to match on. */
  names: string[];
  /** Definition as plain lower-cased text, for the fallback match. */
  plain: string;
}

const strip = (html: string) =>
  html
    .replace(/<[^>]+>/g, '')
    .replace(/\s+/g, ' ')
    .trim();

function index(d: Dictionary): Indexed[] {
  return d.chapters.flatMap((c) =>
    c.blocks.flatMap((b) =>
      b.kind === 'entry'
        ? [
            {
              entry: b,
              chapter: c.number,
              names: [b.term, ...b.aliases].map((n) => n.toLowerCase()),
              plain: strip(b.html).toLowerCase(),
            },
          ]
        : [],
    ),
  );
}

/** Lower is better: exact name, name prefix, name contains, definition contains. */
function rank(row: Indexed, q: string): number {
  if (row.names.some((n) => n === q)) return 0;
  if (row.names.some((n) => n.startsWith(q))) return 1;
  if (row.names.some((n) => n.includes(q))) return 2;
  if (row.plain.includes(q)) return 3;
  return Infinity;
}

const LIMIT = 12;

export function TermSearch({ dictionary }: { dictionary: Dictionary }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const rows = useMemo(() => index(dictionary), [dictionary]);
  const q = query.trim().toLowerCase();

  const hits = useMemo(() => {
    if (q.length < 2) return [];
    return rows
      .map((row) => ({ row, score: rank(row, q) }))
      .filter((x) => x.score < Infinity)
      .sort((a, b) => a.score - b.score)
      .slice(0, LIMIT);
  }, [rows, q]);

  const go = (slug: string) => {
    setQuery('');
    navigate({ hash: `#${slug}` });
  };

  return (
    <div className="relative">
      <label className="flex items-center gap-2 text-micro text-chrome-500">
        <span className="sr-only">Search the dictionary</span>
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && hits[0]) go(hits[0].row.entry.slug);
            if (e.key === 'Escape') setQuery('');
          }}
          placeholder={`Search ${dictionary.counts.entries} terms…`}
          spellCheck={false}
          aria-label="Search the dictionary"
          aria-controls={q.length >= 2 ? 'learn-search-results' : undefined}
          className="w-full rounded-control border border-line-strong bg-chrome-900 px-3 py-1.5 text-sm text-chrome-100 placeholder:text-chrome-600 focus:border-machinery-700 focus:outline-none"
        />
      </label>
      {q.length >= 2 && (
        <ul
          id="learn-search-results"
          aria-label="Search results"
          className="absolute z-20 mt-1 max-h-[60vh] w-full overflow-y-auto rounded-card border border-line bg-chrome-950 p-1 shadow-lg"
        >
          {hits.length === 0 && (
            <li className="px-3 py-2 text-xs text-chrome-500">No term matches “{query}”.</li>
          )}
          {hits.map(({ row }) => (
            <li key={row.entry.slug}>
              <button
                type="button"
                onClick={() => go(row.entry.slug)}
                className="flex w-full flex-col items-start gap-0.5 rounded-control px-3 py-1.5 text-left transition hover:bg-chrome-900 focus:bg-chrome-900 focus:outline-none"
              >
                <span className="flex items-baseline gap-2">
                  <span className="text-sm font-medium text-chrome-100">{row.entry.term}</span>
                  <span className="text-micro text-chrome-500">chapter {row.chapter}</span>
                </span>
                <span className="line-clamp-1 font-serif text-note text-chrome-400">
                  {strip(row.entry.html).slice(0, 120)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
