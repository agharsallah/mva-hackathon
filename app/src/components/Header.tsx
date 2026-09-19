/**
 * Persistent three-tier header.
 *
 * Row 1 — identity and the four questions: brand, case id, one tab per section
 * (`Sections` landmark), then the chrome that must stay visible on every page: export,
 * fixture badge, API health. Row 2 — the pages inside the active section (`Pages`
 * landmark) with the section's question at the far end, so the reader always knows which
 * question the page in front of them is serving. Row 2 is absent on Overview, which is
 * the map rather than a stop on the journey.
 *
 * Row 3 — the detail pages of the open page, when it has any (`Detail pages` landmark).
 * It exists because `decide` had grown to twelve sibling tabs, seven of them one
 * iteration's step pages: a reader could not see that `Step 4` is part of `Steps` and not
 * a peer of `Submissions`. A page declares its parent in the manifest and lands here.
 *
 * The fixture badge is not decoration — it is the difference between a live measurement
 * and a committed placeholder, so it stays visible on every page.
 */

import { useIsFetching, useQuery } from '@tanstack/react-query';
import { useSyncExternalStore } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';

import {
  API_LABEL,
  API_URL,
  fixtureModeStore,
  FIXTURES_ENABLED,
  health,
  unauthorizedStore,
} from '../api/client';
import { cx } from '../lib/ui';
import { AiExport } from './AiExport';
import { CommandPalette } from './CommandPalette';
import { ThemeToggle } from './ThemeToggle';

export interface HeaderNavItem {
  to: string;
  label: string;
  preload?: () => void;
  /** Detail pages of this one, shown in row 3 while this branch is open. */
  children?: HeaderNavItem[];
}

/** One section tab: where it lands, and the pages row 2 shows while it is active. */
export interface HeaderSection {
  id: string;
  label: string;
  /** The question this section answers; shown at the end of row 2. */
  question: string;
  pages: HeaderNavItem[];
}

/** How often the header's status dot re-checks liveness while the tab is in front. */
const HEALTH_DOT_POLL_MS = 60_000;

function useApiHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: health,
    retry: false,
    // A minute, not fifteen seconds. The dot answers "is the API alive"; at 15 s an open
    // tab spent 240 requests an hour on that question, each one two Vercel invocations
    // plus a WAN round trip. react-query does not run the timer while the tab is hidden
    // (`refetchIntervalInBackground` defaults false), so this is the cost of a tab being
    // *looked at*, and a minute is well inside how fast anyone reacts to a red dot.
    refetchInterval: HEALTH_DOT_POLL_MS,
    refetchOnWindowFocus: true,
    // Matched to the interval so returning to a page does not re-ask on top of the poll.
    staleTime: HEALTH_DOT_POLL_MS,
  });
}

/**
 * In development a blocked fetch and a dead server look identical from JavaScript — both
 * are a bare `TypeError`, and the browser prints the CORS reason only to the console. So
 * the dot names both causes and both origins, which is what tells them apart.
 *
 * The hosted deployment cannot have the CORS half of that problem: the browser talks to
 * its own origin and Vercel's proxy talks to the API server-to-server, where CORS does not
 * apply. There, "down" means the proxy could not reach `mva-viz-api`.
 */
function statusTitle(state: 'checking' | 'up' | 'down' | 'refused'): string {
  if (state === 'refused') {
    return (
      `${API_LABEL} answered, then refused: it requires an X-API-Key and a browser has ` +
      `none.\nPoint this build at a local API (leave VITE_API_URL unset) or run the proxy ` +
      `with \`vercel dev\`. The token must never go in a VITE_ variable — Vite inlines those.`
    );
  }
  if (state !== 'down') return API_LABEL;
  if (!API_URL) {
    return (
      `${API_LABEL} did not answer.\n` +
      `Vercel's proxy could not reach mva-viz-api — check MVA_VIZ_API_URL and ` +
      `MVA_VIZ_API_TOKEN in the project, and that the service is up on the server.`
    );
  }
  return (
    `${API_LABEL} did not answer.\n` +
    `Either mva-viz-api is not running, or this page's origin (${window.location.origin}) ` +
    `is blocked by the API's CORS policy — check the browser console for the CORS message.`
  );
}

const TAB =
  'rounded-control px-3 py-1 text-xs font-medium transition focus:outline-none focus-visible:ring-1 focus-visible:ring-machinery-500';
const TAB_ON = 'bg-chrome-800 text-chrome-50';
const TAB_OFF = 'text-chrome-400 hover:bg-chrome-900 hover:text-chrome-200';

const SUB =
  'rounded-control px-2 py-0.5 text-micro transition focus:outline-none focus-visible:ring-1 focus-visible:ring-machinery-500';
const SUB_ON = 'bg-machinery-950/60 text-chrome-50';
const SUB_OFF = 'text-chrome-400 hover:bg-chrome-900 hover:text-chrome-200';

function ApiHealth() {
  const h = useApiHealth();
  const refused = useSyncExternalStore(unauthorizedStore.subscribe, unauthorizedStore.get);
  // "up" is about liveness, and /health is deliberately unauthenticated — so the service can
  // be answering while every exhibit is empty. When that happens the dot must not read
  // green: the reader's problem is authorisation, not availability.
  const state = refused ? 'refused' : h.isPending ? 'checking' : h.data?.ok ? 'up' : 'down';
  const dot =
    state === 'up'
      ? 'bg-good-500'
      : state === 'refused'
        ? 'bg-decision-500'
        : state === 'down'
          ? 'bg-broken-500'
          : 'bg-chrome-500 animate-pulse';
  return (
    <span className="flex items-center gap-2 text-xs text-chrome-400" title={statusTitle(state)}>
      <span className={`h-2 w-2 rounded-full ${dot}`} />
      API {state === 'refused' ? 'unauthorized' : state}
    </span>
  );
}

/**
 * A 2 px bar along the header's bottom edge while any query is in flight. One signal for
 * "the page is still fetching", so a refetch of an exhibit already on screen does not need
 * its own spinner.
 */
function FetchBar() {
  const fetching = useIsFetching();
  if (fetching === 0) return null;
  return (
    <div
      role="progressbar"
      aria-label="Loading data"
      aria-valuetext="loading"
      className="absolute inset-x-0 bottom-0 h-0.5 overflow-hidden"
    >
      <div className="fetch-bar h-full w-1/3 bg-machinery-500" />
    </div>
  );
}

export function Header({ home, sections }: { home: HeaderNavItem; sections: HeaderSection[] }) {
  const onFixtures = useSyncExternalStore(fixtureModeStore.subscribe, fixtureModeStore.get);
  const { pathname } = useLocation();
  const active = sections.find((s) =>
    s.pages.some((p) => p.to === pathname || p.children?.some((c) => c.to === pathname)),
  );
  // The branch whose detail row is open: the page itself when it has children, or the
  // parent of the open child. A page with neither keeps row 3 absent.
  const branch = active?.pages.find(
    (p) =>
      (p.to === pathname && p.children && p.children.length > 0) ||
      p.children?.some((c) => c.to === pathname),
  );

  return (
    <header className="relative sticky top-0 z-20 border-b border-line bg-chrome-950/95 backdrop-blur">
      <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-x-5 gap-y-1 px-5 py-2">
        <Link
          to={home.to}
          onPointerEnter={home.preload}
          onFocus={home.preload}
          className="flex items-baseline gap-2 rounded-control focus:outline-none focus-visible:ring-1 focus-visible:ring-machinery-500"
        >
          <span className="text-sm font-semibold tracking-tight text-chrome-50">
            MVA Case Explorer
          </span>
          <span className="hidden items-baseline gap-2 text-xs text-chrome-400 md:inline-flex">
            <span className="rounded-pill border border-line px-2 py-px text-micro text-chrome-400">
              PROBAND01
            </span>
            single sample, no trio
          </span>
        </Link>

        {/* Labelled because row 2 and the footer carry further navs: three unnamed
            navigation landmarks are indistinguishable to a screen reader. */}
        <nav aria-label="Sections" className="flex flex-1 flex-wrap items-center gap-1">
          <NavLink
            to={home.to}
            end
            onPointerEnter={home.preload}
            onFocus={home.preload}
            className={({ isActive }) => cx(TAB, isActive ? TAB_ON : TAB_OFF)}
          >
            {home.label}
          </NavLink>
          <span aria-hidden="true" className="mx-1 h-4 w-px bg-chrome-800" />
          {sections.map((s) => {
            const entry = s.pages[0];
            const isActive = active?.id === s.id;
            return (
              <Link
                key={s.id}
                to={entry.to}
                onPointerEnter={entry.preload}
                onFocus={entry.preload}
                aria-current={isActive ? 'true' : undefined}
                title={s.question}
                className={cx(TAB, isActive ? TAB_ON : TAB_OFF)}
              >
                {s.label}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-3">
          <CommandPalette />
          <AiExport />
          {onFixtures && (
            <span
              className="rounded-control bg-decision-500/15 px-2 py-1 text-micro font-medium text-decision-300"
              title="At least one panel on this session was served from a committed fixture, not the live API."
            >
              fixture data
            </span>
          )}
          {!FIXTURES_ENABLED && (
            <span
              className="rounded-control bg-chrome-800 px-2 py-1 text-micro text-chrome-400"
              title="VITE_USE_FIXTURES=false"
            >
              fixtures off
            </span>
          )}
          <ThemeToggle />
          <ApiHealth />
        </div>
      </div>

      {active && (
        <div className="border-t border-line-soft bg-chrome-950/60">
          <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-x-4 gap-y-1 px-5">
            <nav aria-label="Pages" className="-mb-px flex flex-wrap items-center">
              {active.pages.map((p) => (
                <NavLink
                  key={p.to}
                  to={p.to}
                  end
                  onPointerEnter={p.preload}
                  onFocus={p.preload}
                  className={({ isActive }) =>
                    cx(
                      'border-b-2 px-3 py-2 text-xs transition focus:outline-none focus-visible:bg-chrome-900',
                      isActive
                        ? 'border-machinery-500 text-chrome-50'
                        : 'border-transparent text-chrome-400 hover:border-line-strong hover:text-chrome-200',
                    )
                  }
                >
                  {p.label}
                </NavLink>
              ))}
            </nav>
            <p className="ml-auto hidden py-2 font-serif text-note text-chrome-400 italic sm:block">
              {active.question}
            </p>
          </div>
        </div>
      )}

      {branch && (
        <div className="border-t border-line-soft bg-chrome-950/40">
          <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-x-2 px-5 py-1">
            <span className="text-micro text-chrome-500">{branch.label} —</span>
            <nav aria-label="Detail pages" className="flex flex-wrap items-center gap-1">
              <NavLink
                to={branch.to}
                end
                onPointerEnter={branch.preload}
                onFocus={branch.preload}
                className={({ isActive }) => cx(SUB, isActive ? SUB_ON : SUB_OFF)}
              >
                overview
              </NavLink>
              {branch.children?.map((c) => (
                <NavLink
                  key={c.to}
                  to={c.to}
                  end
                  onPointerEnter={c.preload}
                  onFocus={c.preload}
                  className={({ isActive }) => cx(SUB, isActive ? SUB_ON : SUB_OFF)}
                >
                  {c.label}
                </NavLink>
              ))}
            </nav>
          </div>
        </div>
      )}
      <FetchBar />
    </header>
  );
}
