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
  /** `null` on a whole-chromosome row: an empty TSV cell loads as NULL, never as ''. */
  arm: string | null;
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
  /** `null` on a whole-chromosome row, for the same reason as `Step8Bdev.arm`. */
  arm: string | null;
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
  /** Fitted per chromosome here, unlike the genome-wide value the deviation null uses. */
  rho: number;
  /** The share of calls no band claims to explain. Every model carries it, so it cannot decide. */
  noise_share: number;
  depth_dispersion: number;
  log_likelihood: number;
  allele_log_likelihood?: number;
  depth_log_likelihood?: number;
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
  /** The noise share the `normal` model needed — this contig's honest tail burden. */
  noise_share: number;
  /** False when the tails swallow the contig: no band structure survives underneath. */
  measurable: boolean;
  /**
   * True when a parameter of the winning fit is pinned against its own bound. A boundary
   * solution is not an estimate — it says the shape the data wants is outside the family.
   */
  degenerate: boolean;
  leader_rho: number;
  leader_tract: number;
  leader_noise: number;
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

/**
 * One contig's k-mer dosage: how much sequence it contributed, against two denominators.
 *
 * This is the step's **second instrument**, and it shares nothing with the allele-balance
 * route past the FASTQ. It sees what that route cannot (X and Y, which have almost no
 * heterozygous sites in a male proband) and is blind to what that route can see (copy-neutral
 * loss of heterozygosity moves no sequence at all). Where both can see, they must agree.
 */
export interface Step8Dosage {
  chrom: string;
  /** Reference-unique 31-mers assigned to this contig. Nothing else can testify about it. */
  probes: number;
  /** Probes never hit. A large share is a broken probe set, not a chromosome that vanished. */
  silent: number;
  silent_share: number;
  mean_count: number;
  /** Against the autosomal median — the readable denominator, and the one that assumes most autosomes are normal. */
  relative: number;
  low: number;
  high: number;
  /** Against the genome-wide calibration set, which no single chromosome can move. */
  absolute: number;
  /** Where the two denominators part company: the median moved, and by how much. */
  disagreement: number;
  /**
   * How much of the read store this pass swept. Shards are flowcell partitions, not genomic
   * ones, so a subset is a uniform sample of the library: a ratio between chromosomes stays
   * unbiased and only its variance rises. A thinning is a precision statement, not a bias one.
   */
  shards_swept?: number;
  thinning?: number;
}

/** One chromosome after the composition trend is removed. */
export interface Step8CompositionRow {
  chrom: string;
  /** The GC fraction this contig was regressed on. */
  gc: number;
  relative: number;
  /** Dosage with the fitted GC trend removed, recentred on one. */
  residual: number;
  /** Residual in units of the residual spread — the honest precision floor. */
  z: number;
  /** `2 × (residual − 1)`: signed, so a loss reads negative rather than folded. */
  implied_fraction: number;
}

/** One regression of dosage on GC. Both are served; the reported one is `reported`. */
export interface Step8CompositionFit {
  /** `reference chromosome GC` or `probe GC` — which regressor produced this fit. */
  source: string;
  correlation: number;
  slope: number;
  intercept: number;
  /** Spread across the fitted contigs before the trend is removed, and after. */
  spread: number;
  residual_spread: number;
  fitted: string[];
  gc: Record<string, number>;
  residual: Record<string, number>;
}

/**
 * The GC correction, and the alternative it was chosen over.
 *
 * A bootstrap over probes measures counting noise and is blind to a bias every probe on a
 * chromosome shares. GC bias is exactly that, and at a few per cent it is the same size as
 * the low-fraction mosaic gain this step looks for — so the residual spread, not the
 * bootstrap width, is the precision floor for any copy-number claim.
 */
export interface Step8Composition {
  reported?: Step8CompositionFit;
  alternative?: Step8CompositionFit;
  autosomes_tested?: number;
  note?: string;
  rows?: Step8CompositionRow[];
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
  dosage: Step8Dosage[];
  composition?: Step8Composition;
  multi: Step8Multi[];
}
