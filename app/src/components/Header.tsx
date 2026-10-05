/**
 * Persistent multi-tier header.
 *
 * Row 1 — identity and the sections: brand, one tab per section (`Sections` landmark), then
 * the chrome that must stay visible on every page: export, theme, API health. Row 2 — the
 * pages inside the active section (`Pages` landmark) with the section's question at the far
 * end, so the reader always knows which question the page in front of them is serving. Row 2
 * is absent on the overview, which is the map rather than a stop on the journey.
 *
 * Rows 3 and 4 — the branch of the open page, and the branch inside it. Every row marks the
 * whole path to the open page — the page itself filled and ringed, its ancestors marked more
 * quietly — so a child's row position is never the only clue to it. A page declares its
 * parent in the manifest and lands in the right row by itself.
 */

import { useIsFetching, useQuery } from '@tanstack/react-query';
import { useSyncExternalStore } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';

import { API_LABEL, API_URL, health, unauthorizedStore } from '../api/client';
import { cx } from '../lib/ui';
import { AiExport } from './AiExport';
import { CommandPalette } from './CommandPalette';
import { ThemeToggle } from './ThemeToggle';

export interface HeaderNavItem {
  to: string;
  label: string;
  /** The page's full title, shown on hover: a one-word label does not say what it holds. */
  title?: string;
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
    // tab spent 240 requests an hour on that question, each one two serverless invocations
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
 * its own origin and the proxy talks to the API server-to-server, where CORS does not
 * apply. There, "down" means the proxy could not reach the backend.
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
      `The proxy could not reach the backend — check API_UPSTREAM_URL and API_UPSTREAM_TOKEN ` +
      `in the project, and that the service is up on the server.`
    );
  }
  return (
    `${API_LABEL} did not answer.\n` +
    `Either the backend is not running, or this page's origin (${window.location.origin}) ` +
    `is blocked by the API's CORS policy — check the browser console for the CORS message.`
  );
}

const TAB =
  'rounded-control px-3 py-1 text-xs font-medium transition focus:outline-none focus-visible:ring-1 focus-visible:ring-machinery-500';
const TAB_ON = 'bg-chrome-800 text-chrome-50';
const TAB_OFF = 'text-chrome-400 hover:bg-chrome-900 hover:text-chrome-200';

const SUB =
  'rounded-control px-2 py-0.5 text-micro transition focus:outline-none focus-visible:ring-1 focus-visible:ring-machinery-500';
/** The page in front of the reader: filled and ringed, so it reads at a glance in both themes. */
const SUB_ON = 'bg-machinery-500/15 font-semibold text-machinery-300 ring-1 ring-machinery-500/60';
/** A row item the open page sits beneath: marked, but quieter than the page itself. */
const SUB_PATH = 'bg-chrome-900 font-medium text-chrome-50';
const SUB_OFF = 'text-chrome-400 hover:bg-chrome-900 hover:text-chrome-200';

/**
 * How one nav item relates to the open page: it is the page, the page is beneath it, or
 * neither. `NavLink`'s own `isActive` answers only the first — with `end` it drops the
 * ancestors, without it `/a` would light up for `/ab` — so the header asks the manifest
 * tree instead, and every ancestor of the open page is marked in its own row.
 */
type Mark = 'on' | 'path' | 'off';

function markOf(item: HeaderNavItem, pathname: string): Mark {
  if (item.to === pathname) return 'on';
  return holds(item, pathname) ? 'path' : 'off';
}

const SUB_TONE: Record<Mark, string> = { on: SUB_ON, path: SUB_PATH, off: SUB_OFF };

/** Whether this item, or anything declared under it, is the page in front of the reader. */
function holds(item: HeaderNavItem, pathname: string): boolean {
  return item.to === pathname || (item.children ?? []).some((c) => holds(c, pathname));
}

/**
 * Whether this item's children should be a row: it is the open page and has children, or
 * the open page is somewhere beneath it. A leaf never opens a row of its own.
 */
function opensRowFor(item: HeaderNavItem, pathname: string): boolean {
  const children = item.children ?? [];
  if (children.length === 0) return false;
  return item.to === pathname || children.some((c) => holds(c, pathname));
}

/**
 * One row of children, with the branch's own page first as "overview". The label in front
 * of it names the branch, so stacked rows stay readable as a path rather than as several
 * unrelated tab strips.
 */
function BranchRow({ branch, tone }: { branch: HeaderNavItem; tone: string }) {
  const { pathname } = useLocation();
  const items = [{ ...branch, label: 'overview', children: undefined }, ...(branch.children ?? [])];
  return (
    <div className={cx('border-t border-line-soft', tone)}>
      <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-x-2 px-5 py-1">
        <span className="text-micro text-chrome-500">{branch.label} ▸</span>
        <nav aria-label={`${branch.label} pages`} className="flex flex-wrap items-center gap-1">
          {items.map((c) => {
            const mark = markOf(c, pathname);
            return (
              <Link
                key={c.to}
                to={c.to}
                onPointerEnter={c.preload}
                onFocus={c.preload}
                aria-current={mark === 'on' ? 'page' : mark === 'path' ? 'true' : undefined}
                title={c.title}
                className={cx(SUB, SUB_TONE[mark])}
              >
                {c.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </div>
  );
}

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

export function Header({
  home,
  sections,
  brand = 'Dashboard',
}: {
  home: HeaderNavItem;
  sections: HeaderSection[];
  /** The product name in the top-left corner. One place, so renaming is one prop. */
  brand?: string;
}) {
  const { pathname } = useLocation();
  const active = sections.find((s) => s.pages.some((p) => holds(p, pathname)));
  // The two rows below the section row: the open page's branch, and the branch inside it.
  // A page with no children keeps both rows absent.
  const branch = active?.pages.find((p) => opensRowFor(p, pathname));
  const sub = branch?.children?.find((c) => opensRowFor(c, pathname));

  return (
    <header className="relative sticky top-0 z-20 border-b border-line bg-chrome-950/95 backdrop-blur">
      <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-x-5 gap-y-1 px-5 py-2">
        <Link
          to={home.to}
          onPointerEnter={home.preload}
          onFocus={home.preload}
          className="flex items-baseline gap-2 rounded-control focus:outline-none focus-visible:ring-1 focus-visible:ring-machinery-500"
        >
          <span className="text-sm font-semibold tracking-tight text-chrome-50">{brand}</span>
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
          <ThemeToggle />
          <ApiHealth />
        </div>
      </div>

      {active && (
        <div className="border-t border-line-soft bg-chrome-950/60">
          <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-x-4 gap-y-1 px-5">
            <nav aria-label="Pages" className="-mb-px flex flex-wrap items-center">
              {active.pages.map((p) => {
                // Underlined while the reader is anywhere beneath it too: on a child page
                // the parent tab must still say which branch the child belongs to.
                const mark = markOf(p, pathname);
                return (
                  <Link
                    key={p.to}
                    to={p.to}
                    onPointerEnter={p.preload}
                    onFocus={p.preload}
                    aria-current={mark === 'on' ? 'page' : mark === 'path' ? 'true' : undefined}
                    title={p.title}
                    className={cx(
                      'border-b-2 px-3 py-2 text-xs transition focus:outline-none focus-visible:bg-chrome-900',
                      mark === 'off'
                        ? 'border-transparent text-chrome-400 hover:border-line-strong hover:text-chrome-200'
                        : 'border-machinery-500 font-medium text-chrome-50',
                    )}
                  >
                    {p.label}
                  </Link>
                );
              })}
            </nav>
            <p className="ml-auto hidden py-2 font-serif text-note text-chrome-400 italic sm:block">
              {active.question}
            </p>
          </div>
        </div>
      )}

      {branch && <BranchRow branch={branch} tone="bg-chrome-950/40" />}
      {sub && <BranchRow branch={sub} tone="bg-chrome-950/25" />}

      <FetchBar />
    </header>
  );
}
