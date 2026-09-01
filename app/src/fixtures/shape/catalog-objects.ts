import type { CatalogObjectRow, ReadRunRow } from '../../api/types';
import { rows } from '../loader';
import { prng } from '../prng';

/**
 * FIXTURE — the raw-data inventory, one row per object in the store.
 *
 * MEASURED: 12 delivered objects; 78.9 GiB of gzipped FASTQ across 4 lanes × R1/R2;
 * every publisher-hashed object verified. File names, object keys and digests fill a
 * shape — the live API reads the object ledger. Digests come from a seeded PRNG so every
 * reload shows the same 64 hex characters.
 *
 * The rows deliberately exercise every edge in the contract: a publisher-verified object,
 * an own-upload object, an unverified object, a null `first_uploaded_at` (predates the
 * ingest ledger) and FASTQ lane/read metadata.
 *
 * The four non-FASTQ rows are seeded from `data/catalog-objects.json` (sha256 left null
 * there); FASTQ rows are derived from `data/reads-runs.json`. Both paths recompute sha256
 * here.
 */

/** 64 deterministic hex characters keyed by the file name. */
function digest(key: string): string {
  let seed = 2166136261;
  for (let i = 0; i < key.length; i++) {
    seed = (seed ^ key.charCodeAt(i)) * 16777619;
  }
  const rand = prng(seed >>> 0);
  let out = '';
  while (out.length < 64) out += Math.floor(rand() * 16).toString(16);
  return out.slice(0, 64);
}

const BUCKET = 's3://mva';

function fastqObject(run: ReadRunRow): CatalogObjectRow {
  const key = `source/${run.source}`;
  return {
    file_name: run.source,
    object_key: key,
    location: `${BUCKET}/${key}`,
    kind: 'fastq.gz',
    role: 'reads',
    description: `Raw sequencing reads, lane ${run.lane} read ${run.read_num} — ${run.read_length} bp ${
      run.read_num === 1 ? 'first' : 'second'
    } ends, gzipped FASTQ as delivered by the publisher.`,
    size_bytes: run.source_bytes,
    content_type: 'application/gzip',
    sha256: digest(run.source),
    sha256_source: 'publisher',
    hash_verified: true,
    version_id: 'v1',
    last_modified: '2026-08-26T08:12:00Z',
    first_uploaded_at: '2026-08-26T08:12:00Z',
    sample: 'PROBAND01',
    flowcell: run.flowcell,
    lane: run.lane,
    read_num: run.read_num,
  };
}

/** Seed rows straight from JSON, sha256 still null. */
interface ObjectSeeds {
  vcf: CatalogObjectRow;
  tbi: CatalogObjectRow;
  bcftoolsStats: CatalogObjectRow;
  checksums: CatalogObjectRow;
}

/** sha256 is null in the seed exactly when the live object carries no computed hash. */
function finalize(seed: CatalogObjectRow): CatalogObjectRow {
  return seed.sha256_source === null ? seed : { ...seed, sha256: digest(seed.file_name) };
}

export async function catalogObjectsFixture(): Promise<CatalogObjectRow[]> {
  const [seeds, readRuns] = await Promise.all([
    rows<ObjectSeeds>('catalog-objects'),
    rows<ReadRunRow[]>('reads-runs'),
  ]);
  return [
    finalize(seeds.vcf),
    finalize(seeds.tbi),
    ...readRuns.map(fastqObject),
    finalize(seeds.bcftoolsStats),
    finalize(seeds.checksums),
  ];
}
