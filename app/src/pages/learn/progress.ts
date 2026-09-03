/**
 * Reading progress — which chapters this reader has marked done. Per browser, in
 * `localStorage`, on the same "a convenience, never a record" footing as the Explainer's
 * open/closed preference: it may come back empty (private window, another device), and the
 * page renders correctly without it.
 */

import { useCallback, useSyncExternalStore } from 'react';

const KEY = 'mva.learn.read';
const listeners = new Set<() => void>();
let cache: readonly string[] | null = null;

function read(): readonly string[] {
  if (cache) return cache;
  try {
    const raw = window.localStorage.getItem(KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    cache = Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === 'string') : [];
  } catch {
    cache = [];
  }
  return cache;
}

function write(next: readonly string[]): void {
  cache = next;
  try {
    window.localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    /* storage blocked: the state still holds for this page */
  }
  listeners.forEach((fn) => fn());
}

function subscribe(fn: () => void): () => void {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

/** The set of chapter ids marked read, and the two verbs on it. */
export function useProgress(): {
  read: ReadonlySet<string>;
  markRead: (id: string) => void;
  toggle: (id: string) => void;
} {
  const list = useSyncExternalStore(subscribe, read, read);
  const markRead = useCallback((id: string) => {
    if (!read().includes(id)) write([...read(), id]);
  }, []);
  const toggle = useCallback((id: string) => {
    const current = read();
    write(current.includes(id) ? current.filter((x) => x !== id) : [...current, id]);
  }, []);
  return { read: new Set(list), markRead, toggle };
}
