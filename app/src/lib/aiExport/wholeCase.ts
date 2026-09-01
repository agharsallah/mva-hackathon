/**
 * The whole case in one document: every dataset the app can fetch without a user choosing
 * something first, plus the database's own field dictionary.
 *
 * Endpoints are fetched through the shared QueryClient rather than as bare requests, so
 * whatever the open page already loaded is reused instead of asked for twice. Failures are
 * settled, not thrown: one dead endpoint must not cost the other thirty, and a failed
 * endpoint is written into the document as a failure rather than dropped.
 */

import { get } from '../../api/client';
import { FIVE_MIN, queryClient } from '../queryClient';
import { bundleMarkdown, endpointSection } from './markdown';
import { withoutCoordinates } from './redact';
import type { EndpointRecord } from './types';

interface Entry {
  path: string;
  /** Strip chromosome and position from every row — a variant-level payload. */
  redact?: boolean;
}

/**
 * Parameter-free endpoints only. The six that need a user's choice — `/api/panel/locus`,
 * `/api/panel/gene-structure`, `/api/panel/het-pairs`, `/api/search`, `/api/callset/region`,
 * `/api/reads/flowcell` — have no safe default and are exported from their own exhibit
 * instead. `/api/jobs` is a live queue, not a dataset.
 */
const MANIFEST: Entry[] = [
  { path: '/api/overview' },
  { path: '/api/genome/allele-balance' },
  { path: '/api/genome/contig-density' },
  { path: '/api/genome/density-bins' },
  { path: '/api/genome/baf-bins' },
  { path: '/api/callset/filters' },
  { path: '/api/callset/genotypes' },
  { path: '/api/callset/depth-distribution' },
  { path: '/api/callset/substitutions' },
  { path: '/api/callset/tstv' },
  { path: '/api/callset/indel-lengths' },
  { path: '/api/callset/observed-expected' },
  { path: '/api/callset/funnel' },
  { path: '/api/callset/zygosity-split' },
  { path: '/api/callset/fields' },
  { path: '/api/panel/genes' },
  { path: '/api/panel/constraint' },
  { path: '/api/panel/annotations', redact: true },
  { path: '/api/reads/runs' },
  { path: '/api/reads/partitions' },
  { path: '/api/reads/cycle-quality' },
  { path: '/api/reads/quality-levels' },
  { path: '/api/reads/yield' },
  { path: '/api/catalog/objects' },
  { path: '/api/provenance/lineage' },
  { path: '/api/provenance/derivations' },
  { path: '/api/provenance/sources' },
  { path: '/api/probe/ledger' },
  { path: '/api/science/hypotheses' },
  { path: '/api/science/evidence' },
];

/** The machine-readable data dictionary, printed last because it explains everything above. */
const DICTIONARY: Entry[] = [{ path: '/api/catalog/tables' }, { path: '/api/catalog/columns' }];

const DICTIONARY_NOTE = [
  '## Field dictionary',
  '',
  'The two payloads below are the warehouse’s own catalogue: one row per table (what it holds,',
  'why it exists, which command writes it, what it was derived from) and one row per column',
  '(type, and what the value means). Use them to interpret the field names in every payload above.',
  'A `null` meaning is a stated gap in the registry, not an empty value.',
].join('\n');

const EXCLUDED_NOTE = [
  '**Not included.** Six endpoints need a gene, an rsID or a region chosen by hand and have no',
  'safe default: `/api/panel/locus`, `/api/panel/gene-structure`, `/api/panel/het-pairs`,',
  '`/api/search`, `/api/callset/region`, `/api/reads/flowcell`. Export those from their own',
  'exhibit, in the app, with a selection made. `/api/jobs` is a live job queue and carries no',
  'case data.',
].join(' ');

async function fetchEntry(entry: Entry): Promise<EndpointRecord> {
  try {
    const result = await queryClient.fetchQuery({
      queryKey: [entry.path, null],
      queryFn: () => get<unknown>(entry.path),
      staleTime: FIVE_MIN,
    });
    const data =
      entry.redact && Array.isArray(result.data)
        ? withoutCoordinates(result.data as object[])
        : result.data;
    return {
      path: entry.path,
      source: result.source,
      cachedAt: result.cachedAt,
      origin: result.origin,
      data,
    };
  } catch (err) {
    return { path: entry.path, error: err instanceof Error ? err.message : String(err) };
  }
}

async function sectionsFor(entries: Entry[]): Promise<string[]> {
  const settled = await Promise.allSettled(entries.map(fetchEntry));
  return settled.map((outcome, i) =>
    outcome.status === 'fulfilled'
      ? endpointSection(outcome.value)
      : endpointSection({ path: entries[i].path, error: String(outcome.reason) }),
  );
}

export async function buildWholeCaseBundle(): Promise<string> {
  const [datasets, dictionary] = await Promise.all([
    sectionsFor(MANIFEST),
    sectionsFor(DICTIONARY),
  ]);
  return bundleMarkdown(
    `the whole case — ${MANIFEST.length} datasets and the field dictionary`,
    [...datasets, DICTIONARY_NOTE, ...dictionary],
    [EXCLUDED_NOTE],
  );
}
