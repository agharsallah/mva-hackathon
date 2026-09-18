/**
 * Iteration 2 step 4 — the genome-wide likelihood-ratio ranking.
 *
 * Its own file rather than another block in `steps.ts`: that file is the shared shape of
 * `/api/steps`, and step 4's payload is eleven blocks of its own. Kept alongside `step1.ts`,
 * which split out for the same reason.
 */

/** One gene's best biallelic hypothesis, with the arithmetic that produced it. */
export interface Step4Leader {
  gene_rank: number;
  gene: string;
  shape: string;
  phase: string;
  tier: string | null;
  is_target: boolean;
  is_decoy: boolean;
  curated: boolean;
  phenotype_rank: number | null;
  hypotheses: number;
  combined_lr: number;
  baseline: number;
  unphaseable: boolean;
  biallelic_confirmed: boolean | null;
  behind_leader: number | null;
  within_one_order: boolean | null;
  p_trans: number | null;
  p_trans_state: string | null;
  /** `name=ratio;name=ratio;…` — every lane that was applied, damped ones included. */
  terms: string;
}

/** How many allele slots each calibrated lane won its correlation group for. */
export interface Step4Lane {
  lane_class: string;
  scored_by: string;
  allele_slots: number;
  percent: number;
}

/** Where a class of gene sits in the ordering — the decoy null, as a table. */
export interface Step4Group {
  grouping: string;
  genes: number;
  median_lr: number;
  p90_lr: number;
  max_lr: number;
  genes_over_100: number;
  genes_over_1000: number;
}

/** A gene the symptom ranker could not score at all, and where it still landed. */
export interface Step4Uncurated {
  gene_rank: number;
  gene: string;
  shape: string;
  combined_lr: number;
  is_decoy: boolean;
  entered_by_network: boolean;
}

/** One bucket of the permutation null: how many random term sets reached this band. */
export interface Step4NullBucket {
  low: number;
  high: number;
  draws: number;
  mean_above_observed: number;
}

/** How many hypotheses of each shape were scored. */
export interface Step4Shape {
  shape: string;
  hypotheses: number;
  genes: number;
  median_lr: number;
  max_lr: number;
}

/** One band of the measured recall curve, read as a likelihood ratio per rank. */
export interface Step4PhenotypeBin {
  low: number;
  high: number;
  causal_mass: number;
  null_mass: number;
  likelihood_ratio: number;
}

/** GET /api/steps/step-4 */
export interface Step4Payload {
  leaders: Step4Leader[];
  lanes: Step4Lane[];
  groups: Step4Group[];
  uncurated: Step4Uncurated[];
  nulls: Step4NullBucket[];
  shapes: Step4Shape[];
  ranking: {
    prior?: number;
    universe?: number;
    alleles?: number;
    hypotheses?: number;
    genes_scored?: number;
    genes_uncurated_scored?: number;
    network_genes?: number;
    inheritance_genes?: number;
    inheritance_applied?: boolean;
    phenotype_unranked_lr?: number;
    phenotype_bins?: Step4PhenotypeBin[];
    counts?: Record<string, number>;
  };
  nulls_summary: {
    /** The same table with the phenotype lane set to 1 — the control, not a null. */
    genotype_only_top?: { gene: string; lr: number; shape: string }[];
    observed_top?: number;
    observed_gene?: string;
    genes?: number;
    decoy_null?: {
      auc: number;
      low: number;
      high: number;
      targets: number;
      decoys: number;
      separates: boolean;
      verdict: string;
    };
    permutation_null?: {
      draws: number;
      exceeded: number;
      p_value: number;
      null_median_top: number;
      expected_false_leads: number;
      seconds: number;
    };
  };
  ptrans_summary: {
    dataset?: string;
    pairs?: number;
    states?: Record<string, number>;
    alleles?: number;
    alleles_with_rsid?: number;
    alleles_resolved_in_dataset?: number;
    prior?: number;
    empirical_base_rate?: number | null;
  };
  coverage: {
    rows?: number;
    skipped?: number;
    coverage?: Record<string, number>;
    unavailable_plugins?: string[];
  };
  network: {
    seeds?: number;
    edges?: number;
    uncurated_neighbours?: number;
    minimum_score?: number;
  };
}
