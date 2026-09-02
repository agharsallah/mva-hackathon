/**
 * The three accepted query shapes, as one-click examples for `SearchBox`.
 *
 * Split out of `SearchBox.tsx` so that module can export components only — Vite's fast
 * refresh only hot-swaps a module whose every export is a component, and a non-primitive
 * constant export alongside one forces a full reload on every edit.
 */

/** The three forms, as one-click examples. Kept in step with the server's `EXAMPLES`. */
export const EXAMPLES: { q: string; what: string }[] = [
  { q: 'BUB1B', what: 'a panel gene' },
  { q: 'TTN', what: 'an off-panel gene, resolved by Ensembl' },
  { q: 'chr15:40140983-40241137', what: 'a region, either chr spelling' },
  { q: 'rs1042522', what: 'an rsID the callset carries' },
  { q: 'rs137852899', what: 'an rsID dbSNP knows and this callset never called' },
];
