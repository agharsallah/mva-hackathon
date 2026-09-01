/**
 * Persistent header: what this is, where the data comes from, and whether the API is up.
 * The fixture badge is not decoration — it is the difference between a live measurement
 * and a committed placeholder, so it stays visible on every page.
 */

import { useSyncExternalStore } from 'react';
import { NavLink } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { API_URL, FIXTURES_ENABLED, fixtureModeStore, health } from '../api/client';
import { AiExport } from './AiExport';

/**
 * Nav items are supplied by the caller (the module manifest in src/app), not
 * hard-coded here, so the nav bar and the router read from one source and can
 * never list different pages. `preload` is optional so Header stays usable
 * without the app-shell's lazy-loading wiring.
 */
export interface HeaderNavItem {
  to: string;
  label: string;
  preload?: () => void;
}

function useApiHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: health,
    retry: false,
    refetchInterval: 15_000,
    refetchOnWindowFocus: true,
    staleTime: 0,
  });
}

/**
 * A blocked fetch and a dead server look identical from JavaScript — both are a bare
 * `TypeError`. The browser only prints the CORS reason to the console, so the dot names
 * both causes and both origins, which is what tells them apart.
 */
function statusTitle(state: 'checking' | 'up' | 'down'): string {
  if (state !== 'down') return API_URL;
  return (
    `${API_URL} did not answer.\n` +
    `Either mva-viz-api is not running, or this page's origin (${window.location.origin}) ` +
    `is blocked by the API's CORS policy — check the browser console for the CORS message.`
  );
}

export function Header({ items }: { items: HeaderNavItem[] }) {
  const onFixtures = useSyncExternalStore(fixtureModeStore.subscribe, fixtureModeStore.get);
  const h = useApiHealth();
  const state = h.isPending ? 'checking' : h.data?.ok ? 'up' : 'down';
  const dot =
    state === 'up' ? 'bg-emerald-500' : state === 'down' ? 'bg-red-500' : 'bg-zinc-500 animate-pulse';

  return (
    <header className="sticky top-0 z-20 border-b border-zinc-800 bg-zinc-950/95 backdrop-blur">
      <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-x-6 gap-y-2 px-5 py-2.5">
        <div className="flex items-baseline gap-2">
          <span className="text-sm font-semibold tracking-tight text-zinc-100">MVA Case Explorer</span>
          <span className="font-mono text-[11px] text-zinc-500">PROBAND01 · single sample, no trio</span>
        </div>

        <nav className="flex flex-1 flex-wrap items-center gap-1">
          {items.map((p) => (
            <NavLink
              key={p.to}
              to={p.to}
              end={p.to === '/'}
              onPointerEnter={p.preload}
              onFocus={p.preload}
              className={({ isActive }) =>
                `rounded-md px-2.5 py-1 text-xs transition ${
                  isActive ? 'bg-zinc-800 text-zinc-100' : 'text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200'
                }`
              }
            >
              {p.label}
            </NavLink>
          ))}
        </nav>

        <div className="flex items-center gap-3">
          <AiExport />
          {onFixtures && (
            <span
              className="rounded-md bg-amber-500/15 px-2 py-1 text-[11px] font-medium text-amber-400"
              title="At least one panel on this session was served from a committed fixture, not the live API."
            >
              fixture data
            </span>
          )}
          {!FIXTURES_ENABLED && (
            <span className="rounded-md bg-zinc-800 px-2 py-1 text-[11px] text-zinc-400" title="VITE_USE_FIXTURES=false">
              fixtures off
            </span>
          )}
          <span className="flex items-center gap-1.5 font-mono text-[11px] text-zinc-500" title={statusTitle(state)}>
            <span className={`h-2 w-2 rounded-full ${dot}`} />
            api {state}
          </span>
        </div>
      </div>
    </header>
  );
}
