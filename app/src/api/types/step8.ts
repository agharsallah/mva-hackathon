/**
 * Iteration 2 step 8 — the mosaic aneuploidy bound, served by `GET /api/steps/step-8`.
 *
 * Every row here is a contig, an arm, a model name, a fraction or a count. There is no
 * position on this surface and nothing was filtered to keep it that way: the three
 * `it2_mosaic_*` derivations aggregated the callset to `(chromosome, arm)` before any of
 * these tables existed.
 *
 * Two shapes are worth knowing before reading the page. A **deviation** is meaningless
 * without the **limit** beside it — "no chromosome exceeds its null" is the sentence entry
 * 037 wrote with a statistic that had no power — so the payload always carries both. And a
 * **verdict** carries `call` as well as `best`: `call` is `"not distinguishable"` whenever
 * the margin is under Kong 2018's ten, and it is the column to render.
 */

/** The two constants fitted once across the sample; every number on the page depends on them. */
export interface Step8Constants {
  /** The B-allele fraction a balanced site actually shows — below 0.5, because reference reads map more readily. */
  centre: number;
  /** Beta-binomial over-dispersion, fitted on the pooled autosomal arms and never per arm. */
  rho: number;
  autosomal_het_sites: number;
  autosomal_mean_depth: number;
  seed: number;
  arms_tested: string[];
  note: string;
  /** Each contig's committed centromere against the gap its heterozygous calls actually leave. */
  arm_check?: Step8ArmCheck[];
  arm_disagreements?: string[];
}

export interface Step8ArmCheck {
  chrom: string;
  acrocentric: boolean;
  hemizygous: boolean;
  observed_gap: boolean;
  gap_mb: number | null;
  offset_mb: number | null;
  agrees: boolean;
}

/** One contig's fold-over deviation, beside the null its own depths generate. */
export interface Step8Bdev {
  chrom: string;
  arm: string;
  n_sites: number;
  mean_depth: number;
  bdev: number;
  null_mean: number;
  null_sd: number;
  /** The rejection threshold. Per contig, never shared — a shallow arm gets a wider null. */
  null_p95: number;
  z: number;
  p_value: number;
  rho: number;
  centre: number;
  measurable: boolean;
  exceeds_null: boolean;
}

/** The published fraction estimator, its own value on null draws, and the difference. */
export interface Step8Fraction {
  chrom: string;
  arm: string;
  /** Markello 2012 as written. At this depth it reads far from zero on a balanced contig. */
  f_raw: number;
  /** The same estimator on null draws from the same depths — its bias, measured. */
  f_null: number;
  /** `f_raw − f_null`, floored at zero. The number to quote. */
  f_hat: number;
  f_low: number;
  f_high: number;
  upper_sites: number;
  centre: number;
}

/** One of the five models fitted to one contig. */
export interface Step8ModelFit {
  chrom: string;
  model: string;
  fraction: number;
  tract: number;
  depth_dispersion: number;
  log_likelihood: number;
  parameters: number;
  observations: number;
  bic: number;
}

/** Which model won a contig, by how much, and whether that margin means anything. */
export interface Step8Verdict {
  chrom: string;
  /** The model name, or `"not distinguishable"`. This is the column to render, not `best`. */
  call: string;
  best: string;
  runner_up: string;
  delta_bic: number;
  fraction: number;
  /** Mitotic trisomy against copy-neutral LOH: the pair that differs only by depth. */
  trisomy_vs_cnloh: number;
  confident: boolean;
}

/**
 * One contig's power curve. `power_*` keys are the simulated fractions, so the object is
 * indexed rather than typed field by field — the grid is a parameter of the run.
 */
export interface Step8Limit {
  chrom: string;
  /** `bdev` or `mean_baf` — the two statistics, on identical assumptions. */
  statistic: string;
  n_sites: number;
  mean_depth: number;
  /** The smallest fraction reaching 80% power. `null` is a blind spot, not a small limit. */
  f80: number | null;
  [power: string]: string | number | null;
}

/** Heterozygous calls per megabase and per PASS call — what a monosomy moves. */
export interface Step8Density {
  chrom: string;
  arm: string;
  het_sites: number;
  pass_sites: number;
  arm_bp: number;
  acrocentric: boolean;
  het_per_mb: number;
  het_share: number;
}

/** One multi-chromosome design: what was injected, what was found, what was invented. */
export interface Step8Multi {
  fraction: number;
  affected: string;
  n_affected: number;
  recall: number;
  /** Untouched contigs flagged on the same replicate. Measured, not assumed at 5%. */
  false_positive_rate: number;
  replicates: number;
  chromosomes_tested: number;
  refit_centre: number;
  refit_rho: number;
}

/** The denominator every relative route divides by, and whether one contig holds it up. */
export interface Step8Baseline {
  median?: number;
  robust?: number;
  low?: number;
  high?: number;
  width?: number;
  shifted?: string[];
  stable?: boolean;
  depth_spread?: number;
  depth_spread_note?: string;
  per_chromosome_depth?: Record<string, number>;
  depth_ratio?: Record<string, number>;
  sex_chromosome_ratio?: Record<string, number>;
  without?: Record<string, number>;
}

export interface Step8Payload {
  constants: Step8Constants;
  baseline: Step8Baseline;
  bdev: Step8Bdev[];
  fractions: Step8Fraction[];
  models: Step8ModelFit[];
  verdicts: Step8Verdict[];
  limits: Step8Limit[];
  density: Step8Density[];
  multi: Step8Multi[];
}
