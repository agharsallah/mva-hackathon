/**
 * A URL-held selection whose vocabulary arrives from an API call, not a static list.
 *
 * `useUrlEnum` (in `lib/urlstate.ts`) needs `allowed` synchronously, at hook-call time — right
 * for a fixed set of options. A gene picker's option list is not known until `usePanelGenes()`
 * answers, so four pages (`panel/LocusExplorer`, `panel/PairMatrix`, `panel/PairComparator`,
 * `compare/RarityScatter`) were each hand-writing the same two lines: read the raw URL value
 * with `useUrlState`, then fall back with `known()` once the options are in. Read `known()`'s
 * own doc for why "not loaded yet" and "loaded but doesn't contain this value" must be told
 * apart — this hook exists only to stop retyping the glue between the two.
 */
import { useCallback } from 'react';
import { known, useUrlState } from '../urlstate';

export function useUrlKnownOption<T extends string>(
  key: string,
  fallback: T,
  options: readonly T[],
): [T, (next: T) => void] {
  const [raw, setRaw] = useUrlState(key, fallback);
  const value = known(raw as T, options, fallback);
  const set = useCallback((next: T) => setRaw(next), [setRaw]);
  return [value, set];
}
