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
