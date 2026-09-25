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
    '/api/panel/structure-genes',
    '/api/panel/gene-structure',
    '/api/panel/protein-structure',
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
    '/api/provenance/reference',
    '/api/probe/ledger',
    '/api/steps',
    '/api/steps/step-1',
    '/api/steps/step-2',
    '/api/steps/step-3',
    '/api/steps/step-4',
    '/api/steps/step-5',
    '/api/steps/step-6',
    '/api/steps/step-8',
    '/api/science/hypotheses',
    '/api/science/evidence',
    '/api/search',
    '/api/callset/region',
    '/api/health/dependencies',
    '/api/submissions',
    '/api/iterations',
    '/api/track2',
  ],
  // The model zoo. The two path-parameter routes are listed once per captured key: a
  // fixture answers concrete paths, and `ownerOf` matches a path exactly.
  zoo: [
    '/api/zoo/case',
    '/api/zoo/models',
    '/api/zoo/ranks',
    '/api/zoo/merge',
    '/api/zoo/runs',
    '/api/zoo/lineage',
    '/api/zoo/reports/merged',
    '/api/zoo/reports/alphamissense',
    '/api/zoo/reports/esm1b',
    '/api/zoo/reports/esm2',
    '/api/zoo/reports/gpnmsa',
    '/api/zoo/reports/revel',
    '/api/zoo/reports/spliceai',
    '/api/zoo/scores/gene/BUB1B',
    '/api/zoo/scores/gene/NBPF3',
  ],
};

const FRAGMENTS: Record<string, () => Promise<Record<string, Entry>>> = {
  callset: () => import('./registry/callset').then((m) => m.callsetEntries),
  genome: () => import('./registry/genome').then((m) => m.genomeEntries),
  panel: () => import('./registry/panel').then((m) => m.panelEntries),
  phenotype: () => import('./registry/phenotype').then((m) => m.phenotypeEntries),
  platform: () => import('./registry/platform').then((m) => m.platformEntries),
  zoo: () => import('./registry/zoo').then((m) => m.zooEntries),
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
