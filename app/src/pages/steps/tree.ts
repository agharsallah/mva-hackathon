import type { JourneyPage } from '../../components/journeyContext';

/** The page at `to`, anywhere in the journey tree the header draws. */
export function findPage(pages: readonly JourneyPage[], to: string): JourneyPage | undefined {
  for (const p of pages) {
    if (p.to === to) return p;
    const hit = findPage(p.children ?? [], to);
    if (hit) return hit;
  }
  return undefined;
}

/** A child that is one of the iteration's steps rather than a page of its own (the zoo). */
export const isStepPath = (to: string) => /\/step-\d+$/.test(to);
