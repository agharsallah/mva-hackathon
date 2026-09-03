/**
 * Reading progress — which chapters this reader has marked done — and the definitions they
 * starred to come back to. Both are `useStoredSet`s in `localStorage`; see `storedSet.ts` for
 * why that is a convenience and never a record.
 */

import { useStoredSet } from './storedSet';

/** The set of chapter ids marked read, and the two verbs on it. */
export function useProgress(): {
  read: ReadonlySet<string>;
  markRead: (id: string) => void;
  toggle: (id: string) => void;
} {
  const set = useStoredSet('mva.learn.read');
  return { read: new Set(set.list), markRead: set.add, toggle: set.toggle };
}

/** Starred entry slugs, in the order they were starred. */
export function useStars() {
  return useStoredSet('mva.learn.starred');
}
