/**
 * Fixture registry: path → entry.
 *
 * The fetch wrapper consults this only when the API is unreachable (or the endpoint is
 * not implemented yet) and fixtures are enabled. Rows live in `data/*.json`; anything
 * param-driven (a gene, a chromosome, a flowcell shard) is shaped by a small module in
 * `shape/`. The registry itself is split by domain under `registry/`, and each fragment
 * is `import()`ed on first use — so an app talking to a healthy API never downloads a
 * fixture fragment, a shape module or a data file at all.
 *
 * `cached_at` is null and `source` is prefixed "fixture:" so the origin is visible in the
 * UI and can never be mistaken for a live table.
 */

import type { Params } from '../api/client';
import type { Envelope } from '../api/types';
import { type Entry, isEnvelopeEntry } from './loader';

/** Fragment name → its paths. Static, so no fragment is loaded to find out who owns a path. */
const OWNERS: Record<string, readonly string[]> = {
  callset: [
    '/api/overview',
    '/api/callset/filters',
    '/api/callset/genotypes',
    '/api/callset/depth-distribution',
    '/api/callset/substitutions',
    '/api/callset/tstv',
    '/api/callset/indel-lengths',
    '/api/callset/observed-expected',
    '/api/callset/funnel',
    '/api/callset/zygosity-split',
    '/api/callset/fields',
  ],
  genome: [
    '/api/genome/allele-balance',
    '/api/genome/contig-density',
    '/api/genome/density-bins',
    '/api/genome/baf-bins',
    '/api/reads/runs',
    '/api/reads/partitions',
    '/api/reads/flowcell',
    '/api/reads/cycle-quality',
    '/api/reads/quality-levels',
    '/api/reads/yield',
  ],
  panel: [
    '/api/panel/genes',
    '/api/panel/constraint',
    '/api/panel/background',
    '/api/panel/annotations',
    '/api/panel/locus',
    '/api/panel/het-pairs',
    '/api/panel/clinvar-presence',
    '/api/panel/suppressed',
    '/api/panel/gene-structure',
  ],
  phenotype: [
    '/api/phenotype/terms',
    '/api/phenotype/genes',
    '/api/phenotype/delta',
    '/api/phenotype/gene',
  ],
  platform: [
    '/api/catalog/objects',
    '/api/catalog/tables',
    '/api/catalog/columns',
    '/api/provenance/lineage',
    '/api/provenance/derivations',
    '/api/provenance/sources',
    '/api/probe/ledger',
    '/api/science/hypotheses',
    '/api/science/evidence',
    '/api/search',
    '/api/callset/region',
    '/api/health/dependencies',
  ],
};

const FRAGMENTS: Record<string, () => Promise<Record<string, Entry>>> = {
  callset: () => import('./registry/callset').then((m) => m.callsetEntries),
  genome: () => import('./registry/genome').then((m) => m.genomeEntries),
  panel: () => import('./registry/panel').then((m) => m.panelEntries),
  phenotype: () => import('./registry/phenotype').then((m) => m.phenotypeEntries),
  platform: () => import('./registry/platform').then((m) => m.platformEntries),
};

const ownerOf = (path: string): string | undefined =>
  Object.keys(OWNERS).find((name) => OWNERS[name].includes(path));

async function entryFor(path: string): Promise<Entry | undefined> {
  const owner = ownerOf(path);
  if (!owner) return undefined;
  return (await FRAGMENTS[owner]())[path];
}

export async function fixtureFor(
  path: string,
  params?: Params,
): Promise<Envelope<unknown> | undefined> {
  const entry = await entryFor(path);
  if (!entry) return undefined;
  if (isEnvelopeEntry(entry)) return entry.envelope(params);
  const source = typeof entry.source === 'function' ? entry.source(params) : entry.source;
  return { data: await entry.load(params), cached_at: null, source: `fixture: ${source}` };
}

/** Every path the fixture layer can answer. Used by the fixture tests. */
export function fixturePaths(): string[] {
  return Object.values(OWNERS).flat();
}
