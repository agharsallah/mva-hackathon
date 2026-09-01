/**
 * Fixture loading: data out of the bundle, code in it.
 *
 * The rows themselves live in `data/*.json` — no TypeScript, no logic, nothing to
 * execute. Each file is its own lazily-imported chunk, so the entry bundle no longer
 * carries ~66 kB of offline payloads that a healthy API never needs. A chunk is fetched
 * the first time an endpoint actually falls back, then stays in the module cache.
 *
 * `import.meta.glob` is Vite's static-analysis-friendly directory import: it expands at
 * build time into a map of path → `() => import(path)`, so every JSON file is a known
 * chunk rather than a runtime string the bundler cannot follow.
 */

import type { Params } from '../api/client';

const files = import.meta.glob<{ default: unknown }>('./data/*.json');

/**
 * Load one `data/<name>.json` payload, cast to its row type.
 *
 * The cast is the single unchecked seam in the fixture layer: JSON has no types, so the
 * shape is asserted here once per file instead of at every call site. `fixtures.test.ts`
 * is what keeps the assertion honest.
 */
export async function rows<T>(name: string): Promise<T> {
  const load = files[`./data/${name}.json`];
  if (!load) throw new Error(`fixture data file not found: data/${name}.json`);
  return (await load()).default as T;
}

/** A fixture's provenance string: either fixed, or derived from the request params. */
export type Source = string | ((p?: Params) => string);

export interface FixtureEntry {
  /**
   * Where these rows came from, shown next to the exhibit. Prefixed `fixture:` by the
   * registry so a reader can never mistake an offline payload for a live table.
   */
  source: Source;
  /** Resolve the payload for these params. */
  load: (p?: Params) => Promise<unknown>;
}

/**
 * An endpoint that answers with its own envelope — `/api/search` and
 * `/api/callset/region` refuse a query they cannot resolve honestly, so they own their
 * `source` line and their errors rather than being wrapped by the registry.
 */
export interface EnvelopeEntry {
  envelope: (p?: Params) => Promise<import('../api/types').Envelope<unknown>>;
}

export type Entry = FixtureEntry | EnvelopeEntry;

export function isEnvelopeEntry(e: Entry): e is EnvelopeEntry {
  return 'envelope' in e;
}
