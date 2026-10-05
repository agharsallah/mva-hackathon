/**
 * The section registry: every mounted `Section` announces itself here, so the "On this page"
 * rail and the jump palette can list a page's sections without any page wiring them up.
 * Same shape as the exhibit registry — a mutable store with a version counter, read through
 * `useSyncExternalStore`.
 */

import { useSyncExternalStore } from 'react';

export interface SectionEntry {
  /** The DOM id, also the `#anchor`. */
  id: string;
  title: string;
  el: HTMLElement;
}

const entries = new Map<string, SectionEntry>();
const listeners = new Set<() => void>();
let version = 0;

function bump(): void {
  version += 1;
  listeners.forEach((fn) => fn());
}

/** "Which inputs have evidence?" → "which-inputs-have-evidence". */
export function slugify(title: string): string {
  return title
    .toLowerCase()
    .normalize('NFKD')
    .replace(/\p{Mark}/gu, '')
    .replace(/[^\p{Letter}\p{Number}]+/gu, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80);
}

export const sectionRegistry = {
  subscribe(fn: () => void): () => void {
    listeners.add(fn);
    return () => {
      listeners.delete(fn);
    };
  },
  version: (): number => version,
  register(entry: SectionEntry): void {
    entries.set(entry.id, entry);
    bump();
  },
  unregister(id: string): void {
    if (entries.delete(id)) bump();
  },
  /** Mounted sections in document order, so the rail reads top to bottom. */
  list(): SectionEntry[] {
    return [...entries.values()].sort((a, b) =>
      a.el.compareDocumentPosition(b.el) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1,
    );
  },
};

/** Mounted sections, re-read whenever one registers or leaves. */
export function useSections(): SectionEntry[] {
  const version = useSyncExternalStore(sectionRegistry.subscribe, sectionRegistry.version);
  void version; // read, so a registry change re-runs the list
  return sectionRegistry.list();
}

/**
 * Whether the page has enough sections for a rail. Below two there is nothing to navigate,
 * so `OnThisPage` renders nothing — and `PageFrame` must not reserve its column either, or a
 * page that brings its own left rail (Learn) is pushed right by an empty gutter.
 */
export function useHasSectionRail(): boolean {
  return useSections().length >= 2;
}
