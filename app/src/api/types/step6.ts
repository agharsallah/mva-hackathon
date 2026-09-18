/**
 * Iteration 2 step 6 — four instruments, one ranking, and the table that says what carries it.
 *
 * Its own file for the reason `step5.ts` has one: `/api/steps` carries the shape every step
 * shares, and this payload is eight blocks plus two analysis summaries of its own.
 *
 * Two fields are easy to misread and are called out here because the page depends on the
 * distinction. `route_rank` of 51 with `defaulted: true` means *the route never listed this
 * pair* — a weaker statement than "the route ranked it last", and not agreement of any kind.
 * `inherited: true` means the rank came from the pair's gene, so every pair of that gene
 * carries the same number: ties in the fused order are fan-out, never four instruments
 * agreeing.
 */

/** One instrument, and the measurement that admitted or disqualified it. */
export interface Step6Route {
  route: string;
  /** `pair`, `gene` or `allele` — what this route actually ordered. */
  unit: string;
  source_step: string;
  source_table: string;
  /** False for a route measured to order nothing. It is kept at weight 0, never deleted. */
  admitted: boolean;
  weight_primary: number;
  /** The route's own measured error rate, used in the second weighting. */
  weight_sensitivity: number;
  /** The admitting measurement in words, with its interval. */
  statistic: string;
  /** Comma-joined raw sources: `hpo`, `vcf`, `reads`, `literature`. */
  inputs: string;
  reason: string;
  /** The methodology entries that measured it. */
  measured_by: string;
}

/** One edge of the declared route-dependency graph. */
export interface Step6Edge {
  source: string;
  target: string;
  consumed: string;
  /** True when two routes read the same raw source — the edges the evidence count collapses. */
  shared_input: boolean;
}

/** One cell of the agreement matrix: where one route put one leading pair. */
export interface Step6MatrixCell {
  pair_id: string;
  gene: string;
  fused_rank: number;
  route: string;
  unit: string;
  admitted: boolean;
  route_rank: number;
  /** True when `route_rank` is the rank-51 default rather than an opinion. */
  defaulted: boolean;
  inherited: boolean;
  independent_evidence: number;
  is_target: boolean;
  is_decoy: boolean;
  tier: string | null;
}

/** One row of the fused leaderboard. */
export interface Step6Leader {
  fused_rank: number;
  pair_id: string;
  gene: string;
  rrf_score: number;
  /** The same pair's rank under measured-error-rate weights. */
  rank_sensitivity: number | null;
  independent_evidence: number;
  inputs: string;
  read_confirmed: boolean;
  single_copy: boolean;
  no_cn_loss: boolean;
  shape: string | null;
  phase: string | null;
  tier: string | null;
  is_target: boolean;
  is_decoy: boolean;
  curated: boolean;
  reachable: boolean;
  unphaseable: boolean;
  combined_lr: number | null;
  /** How many scored hypotheses this coordinate-free key stood for. */
  collapsed_rows: number;
}

/** What happens to the leader when one route is silenced. */
export interface Step6Stability {
  removed: string;
  unit: string | null;
  statistic: string | null;
  /** Null when the leader fell outside the exported rows entirely. */
  leader_rank: number | null;
  leader_kept_rank_one: boolean;
  pairs_at_rank_one: number;
  genes_at_rank_one: number;
  a_new_leader_gene: string | null;
}

/** The top of the ranking with each of the four disjoint inputs named one by one. */
export interface Step6Evidence {
  fused_rank: number;
  pair_id: string;
  gene: string;
  independent_evidence: number;
  inputs: string;
  has_hpo: boolean;
  has_vcf: boolean;
  has_reads: boolean;
  has_literature: boolean;
  read_confirmed: boolean;
  single_copy: boolean;
  no_cn_loss: boolean;
  confirmation_complete: boolean;
  is_target: boolean;
  is_decoy: boolean;
  tier: string | null;
  unphaseable: boolean;
}

/** The fusion's own decoy null: how far down the matched controls sit. */
export interface Step6Reach {
  class: string;
  pairs: number;
  genes: number;
  best_rank: number;
  median_rank: number;
  pairs_in_top: number;
  genes_in_top: number;
  pairs_in_top_sensitivity: number;
}

/** One route's own ordering of a pair, before fusion. */
export interface Step6Movement {
  route: string;
  pair_id: string;
  gene: string;
  rank: number;
  inherited: boolean;
}

/** The freeze receipt: the artifact whose digest the methodology entry quotes. */
export interface Step6Frozen {
  file: string;
  sha256: string;
  rows: number;
  frozen_at: string;
}

/** The constants the plan fixed before any of this ran. */
export interface Step6Constants {
  k: number;
  top_per_route: number;
  missing_rank: number;
  seed: number;
}

/** `fusion.json` — the numbers no table holds. */
export interface Step6Fusion {
  frozen?: Step6Frozen;
  constants?: Step6Constants;
  pairs?: { keys: number; scored_rows: number };
  confirmation?: { genes_measured: number; pairs_measured: number; pairs_complete: number };
  measurements?: Record<string, unknown>;
  routes?: Array<Record<string, unknown>>;
  leave_one_out?: Record<string, unknown>;
}

/**
 * `decision.json` — absent until the unblinding entry is filed.
 *
 * The page renders nothing about iteration 1 while this is empty. That is the blind
 * protocol expressed as a payload rather than as a promise.
 */
export interface Step6Decision {
  unblinded_at?: string;
  entry?: string;
  outcome_row?: string;
  iteration1_pair?: string;
  fused_rank_of_confirmed?: number | null;
  miss_category?: string | null;
  expected_information_gain_bits?: number;
  upload?: string;
  notes?: string;
}

export interface Step6Payload {
  routes: Step6Route[];
  edges: Step6Edge[];
  matrix: Step6MatrixCell[];
  leaders: Step6Leader[];
  stability: Step6Stability[];
  evidence: Step6Evidence[];
  reach: Step6Reach[];
  movement: Step6Movement[];
  fusion: Step6Fusion;
  decision: Step6Decision;
}
