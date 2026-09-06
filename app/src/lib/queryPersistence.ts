/**
 * The query cache, kept across reloads — so the hosted dashboard stops re-asking the API
 * for tables that did not change.
 *
 * Without this the cache is in-memory only: every hard reload, every new tab and every
 * return to the deployment refetches every panel on the page. On Vercel each of those is
 * two invocations (the middleware gate, then `api/proxy`) plus a WAN round trip to
 * `mva-viz-api`, and on the free plan that is the budget being spent on rows the browser
 * already had.
 *
 * ```
 *   first visit   ──▶ fetch ──▶ render ──▶ write to localStorage
 *   reload        ──▶ read localStorage ──▶ render at once ──▶ refetch only if stale
 * ```
 *
 * ## What is allowed to be written to the visitor's disk
 *
 * An **allowlist**, never a denylist: a path not named here is not persisted, so a new
 * endpoint is coordinate-free-by-default only after someone puts it in this list on
 * purpose. Excluded on purpose and permanently:
 *
 * | Path | Why never |
 * |---|---|
 * | `/api/panel/locus`, `/api/callset/region`, `/api/search` | real patient positions |
 * | `/api/panel/het-pairs`, `/api/panel/clinvar-presence` | carry `pos` per variant |
 * | `/api/health/dependencies`, `/api/jobs`, `health` | liveness — a stale answer is a wrong answer |
 *
 * The same rule that keeps coordinates out of tracked files (`tools/check_coordinates.py`)
 * is what this list encodes for the browser's storage.
 *
 * ## Invalidation
 *
 * Three fences: `PERSIST_BUSTER` (the deployment's commit — a new build never reads the
 * previous build's shapes), `PERSIST_MAX_AGE` (a day, so an ingest is never more than that
 * far from being seen), and react-query's own `staleTime`, which decides whether a restored
 * entry is served as-is or refetched in the background.
 */

import { createSyncStoragePersister } from '@tanstack/query-sync-storage-persister';

/** Injected by `vite.config.ts`: the commit of this build, or `dev` outside production. */
declare const __BUILD_ID__: string | undefined;

/** The localStorage key holding the dehydrated cache. */
export const PERSIST_KEY = 'mva-dashboard-query-cache';

/** A restored entry older than this is dropped rather than shown. */
export const PERSIST_MAX_AGE = 24 * 60 * 60 * 1000;

/** A cache written by another build is not readable by this one. */
export const PERSIST_BUSTER: string = typeof __BUILD_ID__ === 'undefined' ? 'dev' : __BUILD_ID__;

/**
 * The paths whose payloads may be written to the visitor's disk.
 *
 * Every one is an aggregate over the callset, a reference table, or the research record —
 * none carries a genomic position. Read the table above before adding to it.
 */
export const PERSISTED_PATHS: ReadonlySet<string> = new Set([
  '/api/overview',
  '/api/callset/depth-distribution',
  '/api/callset/fields',
  '/api/callset/filters',
  '/api/callset/funnel',
  '/api/callset/genotypes',
  '/api/callset/indel-lengths',
  '/api/callset/observed-expected',
  '/api/callset/substitutions',
  '/api/callset/tstv',
  '/api/callset/zygosity-split',
  '/api/catalog/columns',
  '/api/catalog/objects',
  '/api/catalog/tables',
  '/api/genome/allele-balance',
  '/api/genome/baf-bins',
  '/api/genome/contig-density',
  '/api/genome/density-bins',
  '/api/panel/annotations',
  '/api/panel/background',
  '/api/panel/constraint',
  '/api/panel/gene-structure',
  '/api/panel/genes',
  '/api/panel/protein-structure',
  '/api/panel/structure-genes',
  '/api/panel/suppressed',
  '/api/phenotype/delta',
  '/api/phenotype/gene',
  '/api/phenotype/genes',
  '/api/phenotype/terms',
  '/api/probe/ledger',
  '/api/provenance/derivations',
  '/api/provenance/lineage',
  '/api/provenance/reference',
  '/api/provenance/sources',
  '/api/reads/cycle-quality',
  '/api/reads/flowcell',
  '/api/reads/partitions',
  '/api/reads/quality-levels',
  '/api/reads/runs',
  '/api/reads/yield',
  '/api/science/evidence',
  '/api/science/hypotheses',
  '/api/submissions',
  '/api/track2',
]);

/**
 * The two fields of a react-query `Query` this decision reads. Structural rather than the
 * library's own type so a test can hand in a two-field object instead of building a whole
 * `Query` — a real one satisfies it as-is.
 */
export interface PersistableQuery {
  queryKey: readonly unknown[];
  state: { status: string };
}

/**
 * True when this query may be written to disk.
 *
 * Keys are `[path, params | null]` (`useEndpoint`), so the first element decides. A query
 * that failed is never persisted — a restored error would render as a broken page against
 * an API that has since come back.
 */
export function shouldPersistQuery(query: PersistableQuery): boolean {
  if (query.state.status !== 'success') return false;
  const [path] = query.queryKey;
  return typeof path === 'string' && PERSISTED_PATHS.has(path);
}

/**
 * A persister, or `null` when there is nowhere to write.
 *
 * `localStorage` throws rather than returning undefined in a Safari private window and in
 * a browser configured to block site data, and it is absent altogether under jsdom without
 * a window. Both are "run without persistence", not "fail to boot" — the app is fully
 * functional on a cold cache, that is exactly what every visit did before this existed.
 */
export function createPersister() {
  let storage: Storage;
  try {
    storage = globalThis.localStorage;
    if (!storage) return null;
    // Touch it: presence is not permission.
    const probe = `${PERSIST_KEY}:probe`;
    storage.setItem(probe, '1');
    storage.removeItem(probe);
  } catch {
    return null;
  }
  return createSyncStoragePersister({
    storage,
    key: PERSIST_KEY,
    // One write per second at most: navigating a section resolves a dozen queries at once,
    // and serializing the whole cache on each of them is the one way this costs more than
    // it saves.
    throttleTime: 1000,
    /** A quota error (the cache outgrew ~5 MB) drops the store instead of breaking a render. */
    retry: () => undefined,
  });
}

/** The options `PersistQueryClientProvider` needs, in one place so tests can assert them. */
export const persistOptions = {
  maxAge: PERSIST_MAX_AGE,
  buster: PERSIST_BUSTER,
  dehydrateOptions: { shouldDehydrateQuery: shouldPersistQuery },
} as const;
