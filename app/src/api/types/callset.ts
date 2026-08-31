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

/** Whether an observed QC metric lands inside the published healthy-genome band. */
export type OeVerdict = 'within' | 'above' | 'below' | 'unknown';

/**
 * GET /api/callset/observed-expected — one row per comparable QC metric.
 * `expected_low === expected_high` is a point estimate, not a band.
 */
export interface ObservedExpectedRow {
  metric: string;
  label: string;
  observed: number;
  expected_low: number;
  expected_high: number;
  unit: string;
  verdict: OeVerdict;
  /** Short citation for where the expected range comes from. */
  source: string;
}
