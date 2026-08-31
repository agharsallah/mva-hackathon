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

/**
 * Which population a funnel stage is measured over. `genome` = the whole callset;
 * `panel` = inside the eight-gene candidate panel only, which is the sole region VEP
 * annotation exists for. There is no genome-wide annotation and no genome-wide ranking.
 */
export type FunnelScope = 'genome' | 'panel';

/**
 * GET /api/callset/funnel — one row per filter stage of the candidate waterfall.
 *
 * `of_previous_pct` is **null** wherever the row is not a subset of the row above it
 * (the genome→panel scope change), rather than dividing two different populations. The
 * unit of `n` changes down the table — records, then alleles, then pairs — and `note`
 * says which, so a stage that widens is legible rather than a bug.
 */
export interface FunnelStageRow {
  stage_no: number;
  stage: string;
  scope: FunnelScope;
  n: number;
  of_previous_pct: number | null;
  note: string;
}
