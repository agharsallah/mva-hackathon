/**
 * Whether the "On this page" rail is open. One store rather than component state because
 * two components need it — the rail itself and the page frame whose grid column it sits in —
 * and because the choice is remembered across pages and reloads (localStorage `app.rail`).
 */

import { useSyncExternalStore } from 'react';

const KEY = 'app.rail';
const listeners = new Set<() => void>();

function read(): boolean {
  try {
    return window.localStorage.getItem(KEY) !== 'closed';
  } catch {
    return true;
  }
}

let open = typeof window === 'undefined' ? true : read();

export const railStore = {
  get: (): boolean => open,
  set(next: boolean): void {
    if (next === open) return;
    open = next;
    try {
      window.localStorage.setItem(KEY, next ? 'open' : 'closed');
    } catch {
      /* private mode or blocked storage: the choice still holds for this session */
    }
    listeners.forEach((fn) => fn());
  },
  toggle(): void {
    railStore.set(!open);
  },
  subscribe(fn: () => void): () => void {
    listeners.add(fn);
    return () => {
      listeners.delete(fn);
    };
  },
};

export function useRailOpen(): boolean {
  return useSyncExternalStore(railStore.subscribe, railStore.get, () => true);
}
