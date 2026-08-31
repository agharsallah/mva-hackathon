import type {
  CycleQualityRow,
  FlowcellBinRow,
  QualityLevelRow,
  ReadPartitionRow,
  ReadRunRow,
} from '../api/types';
import { prng } from './prng';

const GIB = 1024 ** 3;

/**
 * FIXTURE — the delivery's eight FASTQ files (4 lanes × R1/R2).
 *
 * MEASURED: 1,071,835,104 reads in total; read length 149; lane 1 holds exactly
 * 136,586,642 reads in each of R1 and R2; the gzip source is 78.9 GiB and the parquet
 * store 63.03 GiB. Lanes 2–4 are apportioned here so the eight rows sum to the measured
 * grand total; the live API reads the real per-file census from runs.parquet.
 */
const LANE_READS: Record<number, number> = {
  1: 136_586_642, // measured
  2: 134_200_000,
  3: 133_000_000,
  4: 132_130_910,
};

const SOURCE_BYTES_TOTAL = Math.round(78.9 * GIB);
const PARQUET_BYTES_TOTAL = Math.round(63.03 * GIB);
const TOTAL_READS = 1_071_835_104;

export const readRunsFixture: ReadRunRow[] = [1, 2, 3, 4].flatMap((lane) =>
  [1, 2].map((readNum) => {
    const reads = LANE_READS[lane];
    const share = reads / TOTAL_READS;
    return {
      source: `proband01_L00${lane}_R${readNum}_001.fastq.gz`,
      instrument: 'NovaSeq',
      run: 'RUN01',
      flowcell: 'FC01',
      lane,
      read_num: readNum,
      read_length: 149,
      reads,
      source_bytes: Math.round(SOURCE_BYTES_TOTAL * share),
      parquet_bytes: Math.round(PARQUET_BYTES_TOTAL * share),
      engine: 'polars',
      seconds: Math.round(600 + share * 1200),
    };
  }),
);

/** FIXTURE — MEASURED: 272 shards across the eight partitions (34 each), 63.03 GiB. */
export const readPartitionsFixture: ReadPartitionRow[] = readRunsFixture.map((r) => ({
  lane: r.lane,
  read_num: r.read_num,
  shards: 34,
  reads: r.reads,
  gib: Math.round((r.parquet_bytes / GIB) * 100) / 100,
}));

/**
 * FIXTURE — flowcell occupancy for one shard, binned at x//1000, y//1000.
 *
 * MEASURED extents: 27 tiles, x 1,009–32,949, y 1,000–37,059. The per-bin counts are
 * generated to that envelope (a shard is one contiguous slice of the flowcell surface);
 * the live API reads a real shard, column-pruned.
 */
export function flowcellFixture(lane: number, read: number, shard: number): FlowcellBinRow[] {
  const rand = prng(31 * lane + 7 * read + shard + 1);
  const out: FlowcellBinRow[] = [];
  const tiles = Array.from({ length: 27 }, (_, i) => 1101 + i);
  for (const tile of tiles) {
    for (let xb = 1; xb <= 32; xb++) {
      for (let yb = 1; yb <= 37; yb++) {
        // Edge lanes of the flowcell are less densely clustered.
        const edge = Math.min(xb, 33 - xb, yb, 38 - yb);
        const falloff = Math.min(1, 0.45 + edge / 6);
        const n = Math.round(70 * falloff * (0.7 + rand() * 0.6));
        if (n > 0) out.push({ tile, xb, yb, n });
      }
    }
  }
  return out;
}

/**
 * FIXTURE — mean phred per sequencing cycle, per partition.
 *
 * MEASURED anchors: 149 cycles; quality is binned to exactly {2, 11, 25, 37} with ~93 %
 * of bases at 37; Q30 share is 92.9 % in R1 against 90.0 % in R2 — R2 genuinely degrades.
 * The per-cycle curve is generated to those anchors; the live API samples 100k rows per
 * partition (~20 s each, cached).
 */
export const cycleQualityFixture: CycleQualityRow[] = (() => {
  const out: CycleQualityRow[] = [];
  for (const lane of [1, 2, 3, 4]) {
    for (const readNum of [1, 2]) {
      const rand = prng(500 + lane * 11 + readNum);
      const start = readNum === 1 ? 35.6 : 35.4;
      const drop = readNum === 1 ? 0.9 : 2.6; // R2 loses much more by the last cycle
      for (let cycle = 1; cycle <= 149; cycle++) {
        const t = (cycle - 1) / 148;
        // First cycles are noisy, then a slow decline that steepens at the end.
        const rampIn = cycle <= 4 ? -0.6 * (5 - cycle) * 0.25 : 0;
        const decline = drop * Math.pow(t, 1.7);
        const q = start + rampIn - decline + (rand() - 0.5) * 0.08 - lane * 0.02;
        out.push({ lane, read_num: readNum, cycle, mean_q: Math.round(q * 100) / 100 });
      }
    }
  }
  return out;
})();

/**
 * FIXTURE — the NovaSeq four-level quality binning made explicit.
 * MEASURED: the only phred values present are {2, 11, 25, 37}, ~93 % of bases at 37,
 * Q30 92.9 % R1 vs 90.0 % R2.
 */
export const qualityLevelsFixture: QualityLevelRow[] = (() => {
  const out: QualityLevelRow[] = [];
  for (const lane of [1, 2, 3, 4]) {
    for (const readNum of [1, 2]) {
      const bases = LANE_READS[lane] * 149;
      const q37 = readNum === 1 ? 0.929 : 0.9;
      const shares: Record<number, number> = {
        37: q37,
        25: (1 - q37) * 0.46,
        11: (1 - q37) * 0.33,
        2: (1 - q37) * 0.21,
      };
      for (const phred of [2, 11, 25, 37]) {
        out.push({ lane, read_num: readNum, phred, count: Math.round(bases * shares[phred]) });
      }
    }
  }
  return out;
})();
