/**
 * A set of strings the reader owns, kept in `localStorage`: chapters marked read, starred
 * definitions. Per browser, on the "a convenience, never a record" footing of the Explainer's
 * open/closed preference — it may come back empty (private window, another device), and every
 * page renders correctly without it.
 *
 * One store per key, module-level, read through `useSyncExternalStore` so two components
 * showing the same set (a star button and the starred list) never disagree. A `storage` event
 * for the key — another tab starring a word — drops the cache so this tab re-reads it.
 */

import { useCallback, useSyncExternalStore } from 'react';

interface Store {
  read: () => readonly string[];
  write: (next: readonly string[]) => void;
  subscribe: (fn: () => void) => () => void;
}

const stores = new Map<string, Store>();

function storeFor(key: string): Store {
  const found = stores.get(key);
  if (found) return found;
  const listeners = new Set<() => void>();
  let cache: readonly string[] | null = null;
  const store: Store = {
    read() {
      if (cache) return cache;
      try {
        const raw = window.localStorage.getItem(key);
        const parsed: unknown = raw ? JSON.parse(raw) : [];
        cache = Array.isArray(parsed)
          ? parsed.filter((x): x is string => typeof x === 'string')
          : [];
      } catch {
        cache = [];
      }
      return cache;
    },
    write(next) {
      cache = next;
      try {
        window.localStorage.setItem(key, JSON.stringify(next));
      } catch {
        /* storage blocked: the state still holds for this page */
      }
      listeners.forEach((fn) => fn());
    },
    subscribe(fn) {
      listeners.add(fn);
      return () => {
        listeners.delete(fn);
      };
    },
  };
  stores.set(key, store);
  if (typeof window !== 'undefined') {
    window.addEventListener('storage', (e) => {
      if (e.key !== key) return;
      cache = null;
      listeners.forEach((fn) => fn());
    });
  }
  return store;
}

export interface StoredSet {
  /** Members in insertion order. */
  list: readonly string[];
  has: (id: string) => boolean;
  add: (id: string) => void;
  remove: (id: string) => void;
  toggle: (id: string) => void;
}

export function useStoredSet(key: string): StoredSet {
  const store = storeFor(key);
  const list = useSyncExternalStore(store.subscribe, store.read, store.read);
  const add = useCallback(
    (id: string) => {
      const cur = store.read();
      if (!cur.includes(id)) store.write([...cur, id]);
    },
    [store],
  );
  const remove = useCallback(
    (id: string) => {
      const cur = store.read();
      if (cur.includes(id)) store.write(cur.filter((x) => x !== id));
    },
    [store],
  );
  const toggle = useCallback(
    (id: string) => {
      const cur = store.read();
      store.write(cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]);
    },
    [store],
  );
  return { list, has: (id) => list.includes(id), add, remove, toggle };
}
