/**
 * GET /api/steps/step-1 — iteration 2, step 1: the target set the symptoms alone chose.
 *
 * Counts, fractions and curves only. Step 1 never read the DNA, so no genomic coordinate
 * exists here; gene symbols are withheld too, because step 1 ran blind against iteration
 * 1's candidate and a symbol list is exactly the comparison step 6 exists to make.
 *
 * Served by `src/mva/viz/steps_it2_step1.py` from the files the run wrote under
 * `build/it2/step-1/`.
 */

/** One point of the held-out recall curve, with its bootstrap interval. */
export interface Step1CurvePoint {
  n: number;
  recall: number;
  /** `[low, high]`, a 95% bootstrap interval resampled from the outcomes themselves. */
  interval: [number, number];
}

/** One run of the held-out benchmark: a sample of diseases, or the whole population. */
export interface Step1Benchmark {
  seed: number;
  diseases_run: number;
  diseases_eligible: number;
  recessive_only: boolean;
  median_rank: number | null;
  /** Genes the ranker could not place at all: the held-out disease is their only curation. */
  unrankable: number;
  curve: Step1CurvePoint[];
}

/** One hosted ranker against ours, over the window it actually filled. */
export interface Step1Overlap {
  source: string;
  window: number;
  shared: number;
  unique: number;
  returned: number;
  share: number;
}

/** One promise made before the run, and what the run measured against it. */
export interface Step1Gate {
  claim: string;
  question: string;
  predicted: number;
  unit: string;
  metric: string;
  lower_is_better?: boolean;
  observed: number | null;
  /** Computed from `observed` against `predicted`, never typed. */
  held: boolean | null;
}

export interface Step1Tier {
  tier: string;
  genes: number;
}

export interface Step1Payload {
  target_n: number;
  tiers: Step1Tier[];
  set_sizes: {
    targets: number | null;
    decoys: number | null;
    earned_by_score: number | null;
    by_mechanism_rule: number | null;
  };
  decoys: {
    genes: number | null;
    excluded_by_annotation: number | null;
    matched_on: string[];
    seed: number | null;
  };
  curation: {
    uncurated: number | null;
    protein_coding: number | null;
    fraction: number | null;
    genes_scored: Record<string, number> | null;
  };
  mechanism_term_genes: number | null;
  benchmark: Step1Benchmark | null;
  /** The full-population re-test of the sampled curve (entry 091). */
  benchmark_full: Step1Benchmark | null;
  overlap: Step1Overlap[];
  agreement_retrieved_on: string | null;
  gates: Step1Gate[];
  provenance: {
    built_at: string | null;
    built_by: string | null;
    code_version: string | null;
    hpo_release: string | null;
    parameters: Record<string, number> | null;
    clinical_source: string | null;
    clinical_term_counts: Record<string, number>;
    inputs: { name: string; sha256: string; role: string }[];
    genomic_data_read: string | null;
  };
}
