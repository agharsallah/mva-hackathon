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
 *
 * `normalise` is the third piece of that glue: a URL is typed by hand and by other pages, so
 * the raw value may be a spelling the vocabulary does not literally contain (`bub1b`, or an
 * outdated gene alias). It runs **before** `known()`, so a recognisable spelling resolves to
 * its canonical form instead of silently falling back to `fallback` — and, because the
 * canonical form is what every query key and every title downstream sees, `?gene=bub1b`
 * spends no extra request and never titles an exhibit in the reader's own casing.
 *
 * The hook also **writes the canonical spelling back to the URL** once the vocabulary confirms
 * it. Other exhibits on the same page read the same key through plain `useUrlState`, and they
 * would otherwise keep firing requests with the raw spelling; rewriting the address once makes
 * every reader agree. It happens only when the normalised value is known — an unknown symbol
 * stays in the URL untouched, so the reader can see what they typed.
 */
import { useCallback, useEffect } from 'react';

import { known, useUrlState } from '../urlstate';

export function useUrlKnownOption<T extends string>(
  key: string,
  fallback: T,
  options: readonly T[],
  normalise?: (raw: string) => T,
): [T, (next: T) => void] {
  const [raw, setRaw] = useUrlState(key, fallback);
  const normalised = normalise ? normalise(raw) : (raw as T);
  const value = known(normalised, options, fallback);
  const set = useCallback((next: T) => setRaw(next), [setRaw]);
  useEffect(() => {
    if (normalised === raw || !options.includes(normalised)) return;
    // `useUrlState`'s setter merges into the *live* address bar, so the rewrite only happens
    // when that bar actually carries the raw spelling. Under a MemoryRouter (tests) it does
    // not, and a write there would clobber the sibling keys the merge could not see.
    if (typeof window === 'undefined') return;
    if (new URLSearchParams(window.location.search).get(key) !== raw) return;
    setRaw(normalised);
  }, [key, normalised, raw, options, setRaw]);
  return [value, set];
}
