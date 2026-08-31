import type { CatalogObjectRow } from '../api/types';
import { prng } from './prng';
import { readRunsFixture } from './reads';

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

function fastqObject(run: (typeof readRunsFixture)[number]): CatalogObjectRow {
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

export const catalogObjectsFixture: CatalogObjectRow[] = [
  {
    file_name: 'WGS_PROBAND01.vcf.gz',
    object_key: 'source/WGS_PROBAND01.vcf.gz',
    location: `${BUCKET}/source/WGS_PROBAND01.vcf.gz`,
    kind: 'vcf.gz',
    role: 'callset',
    description:
      'The delivered callset: one record per variant site the publisher’s caller emitted for PROBAND01, including records it suppressed behind a FILTER.',
    size_bytes: 1_412_003_776,
    content_type: 'application/gzip',
    sha256: digest('WGS_PROBAND01.vcf.gz'),
    sha256_source: 'publisher',
    hash_verified: true,
    version_id: 'v1',
    last_modified: '2026-08-26T08:04:00Z',
    // Predates the ingest ledger: the object is older than the record of its arrival.
    first_uploaded_at: null,
    sample: 'PROBAND01',
    flowcell: null,
    lane: null,
    read_num: null,
  },
  {
    file_name: 'WGS_PROBAND01.vcf.gz.tbi',
    object_key: 'source/WGS_PROBAND01.vcf.gz.tbi',
    location: `${BUCKET}/source/WGS_PROBAND01.vcf.gz.tbi`,
    kind: 'tbi',
    role: 'callset index',
    description:
      'Tabix index over the callset — the offset table that makes a position range seekable instead of a full scan.',
    size_bytes: 2_310_144,
    content_type: 'application/octet-stream',
    sha256: digest('WGS_PROBAND01.vcf.gz.tbi'),
    sha256_source: 'publisher',
    hash_verified: true,
    version_id: 'v1',
    last_modified: '2026-08-26T08:04:00Z',
    first_uploaded_at: null,
    sample: 'PROBAND01',
    flowcell: null,
    lane: null,
    read_num: null,
  },
  ...readRunsFixture.map(fastqObject),
  {
    file_name: 'WGS_PROBAND01.bcftools-stats.txt',
    object_key: 'derived/WGS_PROBAND01.bcftools-stats.txt',
    location: `${BUCKET}/derived/WGS_PROBAND01.bcftools-stats.txt`,
    kind: 'txt',
    role: 'callset summary',
    description:
      'bcftools stats over the delivered callset: the sectioned text report (SN, TSTV, FILTER, ST, IDD, DP) every callset figure in this app is parsed from.',
    size_bytes: 184_320,
    content_type: 'text/plain',
    sha256: digest('WGS_PROBAND01.bcftools-stats.txt'),
    // Produced here, so the hash proves our own upload round-tripped, not the publisher's bytes.
    sha256_source: 'upload', // the live API's spelling for an own-upload digest
    hash_verified: true,
    version_id: 'v1',
    last_modified: '2026-08-28T09:02:00Z',
    first_uploaded_at: '2026-08-28T09:02:00Z',
    sample: 'PROBAND01',
    flowcell: null,
    lane: null,
    read_num: null,
  },
  {
    file_name: 'checksums.sha256',
    object_key: 'source/checksums.sha256',
    location: `${BUCKET}/source/checksums.sha256`,
    kind: 'sha256',
    role: 'manifest',
    description:
      'The publisher’s checksum manifest — one sha256 per delivered file. It is the authority every other row is checked against, so it has nothing to be checked against itself.',
    size_bytes: 1_024,
    content_type: 'text/plain',
    sha256: null,
    sha256_source: null,
    hash_verified: false,
    version_id: 'v1',
    last_modified: '2026-08-26T08:04:00Z',
    first_uploaded_at: null,
    sample: null,
    flowcell: null,
    lane: null,
    read_num: null,
  },
];

