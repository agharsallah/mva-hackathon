/**
 * Which exhibits are on screen right now.
 *
 * Every Exhibit registers itself on mount and drops out on cleanup, and pages are lazy
 * routes, so navigating away really does unmount the old page — which is what makes
 * `getByPage` the current page rather than everything ever visited.
 *
 * `version` is the snapshot for `useSyncExternalStore`: the record list is rebuilt on every
 * read, so returning it directly would fail React's identity check.
 */

import type { ExhibitRecord } from './types';

const records = new Map<string, ExhibitRecord>();
const listeners = new Set<() => void>();
let version = 0;

function bump(): void {
  version += 1;
  listeners.forEach((fn) => fn());
}

export function exhibitKey(page: string, title: string): string {
  return `${page}::${title}`;
}

export const exhibitRegistry = {
  subscribe(fn: () => void): () => void {
    listeners.add(fn);
    return () => {
      listeners.delete(fn);
    };
  },
  version: (): number => version,
  register(record: ExhibitRecord): void {
    records.set(exhibitKey(record.page, record.title), record);
    bump();
  },
  unregister(page: string, title: string): void {
    if (records.delete(exhibitKey(page, title))) bump();
  },
  getAll: (): ExhibitRecord[] => [...records.values()],
  getByPage: (page: string): ExhibitRecord[] => [...records.values()].filter((r) => r.page === page),
};
