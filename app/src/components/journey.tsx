/**
 * Journey context — the manifest's groups and pages, handed down from the shell so a page
 * (which may not import `app/`) can still draw the map of the app. `JourneyMap` is that
 * map: one card per question, listing its pages in reading order.
 */

import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

import { JourneyContext, type JourneyGroup, useJourney } from './journeyContext';

export function JourneyProvider({
  groups,
  children,
}: {
  groups: readonly JourneyGroup[];
  children: ReactNode;
}) {
  return <JourneyContext.Provider value={groups}>{children}</JourneyContext.Provider>;
}

/** Group index → the tone the map paints it with: green start → purple raw input → blue → yellow → grey. */
const GROUP_ACCENT = [
  'border-l-good-500',
  'border-l-raw-500',
  'border-l-machinery-500',
  'border-l-decision-500',
  'border-l-chrome-500',
];

/**
 * The five questions as five cards, each a numbered reading list. Renders nothing when
 * mounted outside the shell (tests that mount a page alone), so it never throws.
 */
export function JourneyMap() {
  const groups = useJourney();
  if (groups.length === 0) return null;
  return (
    <ol className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      {groups.map((g, i) => (
        <li
          key={g.id}
          className={
            'rounded-card border border-line border-l-2 bg-panel p-4 ' +
            GROUP_ACCENT[i % GROUP_ACCENT.length]
          }
        >
          <div className="flex items-baseline gap-2">
            <span className="text-xs text-chrome-400">{i + 1}</span>
            <h3 className="text-sm font-semibold tracking-tight text-chrome-100">{g.label}</h3>
          </div>
          <p className="mt-1 font-serif text-note leading-relaxed italic text-chrome-400">
            {g.question}
          </p>
          <ol className="mt-3 space-y-2">
            {g.pages.map((p) => (
              <li key={p.to}>
                <Link
                  to={p.to}
                  onPointerEnter={p.preload}
                  onFocus={p.preload}
                  title={p.description}
                  className="group flex items-baseline gap-2 text-xs text-chrome-300 transition hover:text-chrome-50"
                >
                  <span className="shrink-0 font-medium text-chrome-100 group-hover:text-chrome-50">
                    {p.label}
                  </span>
                  <span className="truncate text-chrome-400 group-hover:text-chrome-300">
                    {p.title}
                  </span>
                </Link>
              </li>
            ))}
          </ol>
        </li>
      ))}
    </ol>
  );
}
