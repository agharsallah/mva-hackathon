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
