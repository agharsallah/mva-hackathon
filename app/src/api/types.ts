/**
 * Types transcribed 1:1 from the viz API contract
 * (scratchpad/viz-api-contract.md). Service: mva-viz-api, FastAPI, 127.0.0.1:8900.
 *
 * Every endpoint answers with the same envelope, so the client can be one function:
 *   { data, cached_at, source }
 * `cached_at` is null for endpoints computed on the spot; `source` names the table,
 * object or file the rows came from (that string is the page's provenance line).
 */

export interface Envelope<T> {
  data: T;
  cached_at: string | null;
  source: string;
}

export interface Health {
  ok: boolean;
  service: string;
}

/** GET /api/overview — one object, the whole case in numbers. */
export interface Overview {
  total_variants: number;
  pass_variants: number;
  snps: number;
  indels: number;
  multiallelic_sites: number;
  tstv: number;
  samples: number;
  total_reads: number;
  read_length: number;
  est_coverage_x: number;
  mean_depth_x: number;
  canonical_contigs: number;
  all_contigs: number;
  delivery_objects: number;
  delivery_bytes: number;
  all_hashes_verified: boolean;
  probe_budget_total: number;
  probe_budget_spent: number;
}

export type BalanceCall = 'balanced' | 'flagged' | string;

/** GET /api/genome/allele-balance — per-chromosome heterozygous allele balance. */
export interface AlleleBalanceRow {
  chrom: string;
  n_het: number;
  mean_vaf: number;
  mean_dp: number;
  pct_in_0_40_0_60: number;
  vaf_deviation: number;
  balance_call: BalanceCall;
  dp_vs_autosomal: number;
}

/** GET /api/genome/contig-density — 25 canonical contigs. */
export interface ContigDensityRow {
  chrom: string;
  length: number;
  n_records: number;
  variants_per_mb: number;
  pct_of_callset: number;
}

/** GET /api/genome/density-bins — precomputed 1 Mb bins. */
export interface DensityBinRow {
  chrom: string;
  mb: number;
  n: number;
  pass_n: number;
  low_qual_n: number;
  mean_qual: number;
}

/** GET /api/callset/filters — the caller's vetoes, ranked by how much they suppress. */
export interface FilterRow {
  filter_value: string;
  count: number;
  pct_of_section: number;
  impact_rank: number;
}

/** GET /api/callset/genotypes */
export interface GenotypeRow {
  label: string;
  count: number;
}

/** GET /api/callset/depth-distribution */
export interface DepthBinRow {
  bin: number;
  count: number;
  pct: number;
}

/** GET /api/callset/substitutions */
export interface SubstitutionRow {
  sub_type: string;
  count: number;
  is_transition: boolean;
}

/** GET /api/callset/tstv */
export interface TsTv {
  ts: number;
  tv: number;
  ratio: number;
}

/** GET /api/callset/indel-lengths — negative length = deletion. */
export interface IndelLengthRow {
  length: number;
  count: number;
}

/** GET /api/panel/genes — the MVA candidate gene panel. */
export interface PanelGeneRow {
  gene: string;
  chrom: string;
  start: number;
  end: number;
  ensembl_id: string;
  note: string;
  n_all: number;
  n_pass: number;
  n_filtered: number;
  span_bp: number;
  variants_per_mb: number;
  pct_pass: number;
}

/**
 * GET /api/panel/locus?gene=… — one row per variant record inside a gene.
 * These are real patient coordinates at runtime. Never persist them to a file
 * in this repo (the fixture uses obviously synthetic positions).
 */
export interface LocusVariant {
  pos: number;
  ref: string;
  alt: string;
  qual: number;
  filter: string;
  gt: string;
  dp: number | null;
  ad_ref: number | null;
  ad_alt: number | null;
  vaf: number | null;
  gq: number | null;
}

/** GET /api/reads/runs — one row per delivered FASTQ file. */
export interface ReadRunRow {
  source: string;
  instrument: string;
  run: string;
  flowcell: string;
  lane: number;
  read_num: number;
  read_length: number;
  reads: number;
  source_bytes: number;
  parquet_bytes: number;
  engine: string;
  seconds: number;
}

/** GET /api/reads/partitions — the read store's shape. */
export interface ReadPartitionRow {
  lane: number;
  read_num: number;
  shards: number;
  reads: number;
  gib: number;
}

/** GET /api/reads/flowcell — x//1000, y//1000 bins for one shard. */
export interface FlowcellBinRow {
  tile: number;
  xb: number;
  yb: number;
  n: number;
}

/** GET /api/reads/cycle-quality — mean phred per sequencing cycle. */
export interface CycleQualityRow {
  lane: number;
  read_num: number;
  cycle: number;
  mean_q: number;
}

/** GET /api/reads/quality-levels — NovaSeq bins every base into 4 phred values. */
export interface QualityLevelRow {
  lane: number;
  read_num: number;
  phred: number;
  count: number;
}

/** GET /api/provenance/lineage */
export interface LineageRow {
  produced_at: string;
  target_schema: string;
  target_table: string;
  target_rows: number;
  source_kind: string;
  source_ref: string;
  source_version: string | null;
  source_sha256: string | null;
  transform: string;
  tool: string;
  notes: string | null;
}

/** GET /api/provenance/derivations */
export interface DerivationRow {
  run_at: string;
  derivation: string;
  question: string;
  n_rows: number;
}

/** GET /api/provenance/sources — the delivery, one row per object. */
export interface SourceObjectRow {
  file_name: string;
  kind: string;
  role: string;
  size_bytes: number;
  hash_verified: boolean;
  sha256_source: string | null;
  version_id: string | null;
  lane: number | null;
  read_num: number | null;
}

/** GET /api/probe/ledger — the 18-probe oracle budget, spend by spend. */
export interface ProbeLedgerRow {
  probe_id: string;
  logged_at: string;
  track: string;
  probe_type: string;
  payload: string;
  n_rows: number | null;
  response: string | null;
  score: number | null;
  rationale: string | null;
}

// ---------------------------------------------------------------------------
// Reads-API proxy: asynchronous jobs over the FASTQ store.
// ---------------------------------------------------------------------------

export type JobState = 'queued' | 'running' | 'done' | 'failed' | 'cancelled' | 'lost';

export interface ProbeSpec {
  name?: string;
  sequence: string;
}

/** verdict is the server's call on a count: present / one-lane / error-level / absent. */
export interface ProbeCount {
  probe: string;
  forward: number;
  reverse: number;
  total: number;
  lanes: number;
  verdict: string;
}

export interface ProbeCountResult {
  root: string;
  seconds: number;
  expected: string;
  counts: ProbeCount[];
}

export interface ProbeScanHit {
  probe: string;
  lane: number;
  read_num: number;
  tile: number;
  x: number;
  y: number;
  position: number;
  strand: string;
  sequence: string;
}

export interface ProbeScanResult {
  root: string;
  probes: number;
  seconds: number;
  hits: ProbeScanHit[];
}

/**
 * Job timestamps come off the upstream reads API as **Unix epoch seconds** (floats), not
 * ISO strings — verified against the live service. `Instant` covers both so the formatter
 * can accept either without a crash if the upstream ever changes.
 */
export type Instant = string | number;

export interface Job<R = unknown> {
  id: string;
  verb: string;
  state: JobState;
  params: Record<string, unknown>;
  submitted_at: Instant;
  started_at: Instant | null;
  finished_at: Instant | null;
  elapsed_seconds: number | null;
  result: R | null;
  error: string | null;
}

export type CountJob = Job<ProbeCountResult>;
