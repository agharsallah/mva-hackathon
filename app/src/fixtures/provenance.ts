import type { DerivationRow, LineageRow, ProbeLedgerRow, SourceObjectRow } from '../api/types';
import { readRunsFixture } from './reads';

/**
 * FIXTURE — the delivery, one row per object.
 * MEASURED: 12 objects, every sha256 verified against the vendor manifest, 78.9 GiB of
 * gzipped FASTQ. File names below are placeholders; the live API reads the real manifest.
 */
export const sourcesFixture: SourceObjectRow[] = [
  ...readRunsFixture.map((r) => ({
    file_name: r.source,
    kind: 'fastq.gz',
    role: 'reads',
    size_bytes: r.source_bytes,
    hash_verified: true,
    sha256_source: 'vendor manifest',
    version_id: 'v1',
    lane: r.lane,
    read_num: r.read_num,
  })),
  {
    file_name: 'proband01.vcf.gz',
    kind: 'vcf.gz',
    role: 'callset',
    size_bytes: 1_412_003_776,
    hash_verified: true,
    sha256_source: 'vendor manifest',
    version_id: 'v1',
    lane: null,
    read_num: null,
  },
  {
    file_name: 'proband01.vcf.gz.tbi',
    kind: 'tbi',
    role: 'callset index',
    size_bytes: 2_310_144,
    hash_verified: true,
    sha256_source: 'vendor manifest',
    version_id: 'v1',
    lane: null,
    read_num: null,
  },
  {
    file_name: 'proband01.bcftools-stats.txt',
    kind: 'txt',
    role: 'callset summary',
    size_bytes: 184_320,
    hash_verified: true,
    sha256_source: 'vendor manifest',
    version_id: 'v1',
    lane: null,
    read_num: null,
  },
  {
    file_name: 'checksums.sha256',
    kind: 'sha256',
    role: 'manifest',
    size_bytes: 1_024,
    hash_verified: true,
    sha256_source: 'self',
    version_id: 'v1',
    lane: null,
    read_num: null,
  },
];

/**
 * FIXTURE — lineage. Every derived table records where it came from, by what transform,
 * with which tool. Shape mirrors pg.meta.lineage; the live API serves the real rows.
 */
export const lineageFixture: LineageRow[] = [
  {
    produced_at: '2026-08-28T09:14:00Z',
    target_schema: 'raw',
    target_table: 'variants_raw',
    target_rows: 5_012_204,
    source_kind: 'object',
    source_ref: 's3://mva/delivery/proband01.vcf.gz',
    source_version: 'v1',
    source_sha256: 'verified',
    transform: 'VCF record stream → columnar rows (one row per ALT record)',
    tool: 'duckdb + polars',
    notes: 'no filtering; suppressed records kept as a search space',
  },
  {
    produced_at: '2026-08-28T10:02:00Z',
    target_schema: 'results',
    target_table: 'contig_density',
    target_rows: 25,
    source_kind: 'table',
    source_ref: 'raw.variants_raw',
    source_version: null,
    source_sha256: null,
    transform: 'group by contig, join GRCh38 lengths, records per Mb',
    tool: 'sql',
    notes: 'canonical contigs only',
  },
  {
    produced_at: '2026-08-28T10:07:00Z',
    target_schema: 'results',
    target_table: 'variant_density_bins',
    target_rows: 3_088,
    source_kind: 'table',
    source_ref: 'raw.variants_raw',
    source_version: null,
    source_sha256: null,
    transform: 'bin position into 1 Mb windows, count all / PASS / LowQual, mean QUAL',
    tool: 'sql',
    notes: 'precomputed so the API can serve it instantly',
  },
  {
    produced_at: '2026-08-28T10:19:00Z',
    target_schema: 'results',
    target_table: 'allele_balance_flags',
    target_rows: 25,
    source_kind: 'table',
    source_ref: 'raw.variants_raw',
    source_version: null,
    source_sha256: null,
    transform: 'heterozygous sites only → mean VAF and depth per contig, deviation from 0.5',
    tool: 'sql',
    notes: 'the aneuploidy screen',
  },
  {
    produced_at: '2026-08-28T10:26:00Z',
    target_schema: 'results',
    target_table: 'panel_gene_density',
    target_rows: 8,
    source_kind: 'table',
    source_ref: 'raw.variants_raw × mva_panel_grch38.bed',
    source_version: null,
    source_sha256: null,
    transform: 'interval join of records onto panel gene spans, PASS split',
    tool: 'sql',
    notes: 'panel from the MVA literature',
  },
  {
    produced_at: '2026-08-30T16:41:00Z',
    target_schema: 'reads',
    target_table: 'store (parquet)',
    target_rows: 1_071_835_104,
    source_kind: 'object',
    source_ref: 's3://mva/delivery/*.fastq.gz (8 files)',
    source_version: 'v1',
    source_sha256: 'verified',
    transform: '4-line FASTQ records → parquet, 272 shards, 8 partitions',
    tool: 'polars',
    notes: '78.9 GiB gzip → 63.03 GiB parquet',
  },
  {
    produced_at: '2026-08-30T17:02:00Z',
    target_schema: 'reads',
    target_table: 'manifest.parquet',
    target_rows: 272,
    source_kind: 'table',
    source_ref: 'reads.store',
    source_version: null,
    source_sha256: null,
    transform: 'one row per shard: partition, rows, bytes',
    tool: 'polars',
    notes: 'the store index',
  },
];

/** FIXTURE — each derivation carries the question it was built to answer. */
export const derivationsFixture: DerivationRow[] = [
  {
    run_at: '2026-08-28T10:02:00Z',
    derivation: 'contig_density',
    question: 'Is the callset spread evenly over the genome, or does some contig dominate?',
    n_rows: 25,
  },
  {
    run_at: '2026-08-28T10:07:00Z',
    derivation: 'variant_density_bins',
    question: 'Where along each chromosome do calls concentrate, and where does the caller go quiet?',
    n_rows: 3_088,
  },
  {
    run_at: '2026-08-28T10:19:00Z',
    derivation: 'allele_balance_flags',
    question: 'Does any chromosome show the allele imbalance an extra or missing copy would cause?',
    n_rows: 25,
  },
  {
    run_at: '2026-08-28T10:26:00Z',
    derivation: 'panel_gene_density',
    question: 'How many records land in each MVA candidate gene, and how many were suppressed?',
    n_rows: 8,
  },
  {
    run_at: '2026-08-30T17:02:00Z',
    derivation: 'reads_manifest',
    question: 'What is the exact read census, and does it match the vendor claim?',
    n_rows: 272,
  },
];

/** FIXTURE — MEASURED: the oracle ledger is empty. 0 of 18 probes spent. */
export const probeLedgerFixture: ProbeLedgerRow[] = [];
