/**
 * The research journey: `GET /api/steps`.
 *
 * One payload per iteration, assembled server-side from three sources that used to live
 * apart — the step map in `mva.science.steps`, the claims in the register, and the blind
 * gate's reading of each methodology entry. Nothing on the `/steps` page is written by
 * hand, so a new step or a whole new iteration appears the moment it is declared.
 */

import type { HypothesisRow } from './science';

/** `done` | `open` | `planned`. Mirrors `mva.science.steps.STATUSES`. */
export type StepStatus = 'done' | 'open' | 'planned';

/**
 * One methodology entry as the blind gate sees it. Iteration 2 runs blind: every entry
 * declares what it read, and naming an iteration-1 candidate table before the unblinding
 * entry is a violation rather than a note.
 */
export interface StepEntry {
  entry: string;
  path: string;
  /** False when the entry carries no `## Inputs` section — itself a gate failure. */
  declares_inputs: boolean;
  inputs: string[];
  /** True for the entry that performs the comparison and ends the blinding. */
  unblinds: boolean;
  violations: string[];
}

/** One step, with everything known about it. */
export interface StepRow {
  slug: string;
  title: string;
  /** The one question the step exists to answer. */
  goal: string;
  /** `platform` steps record decisions, not claims, and take no hypotheses. */
  kind: 'platform' | 'research' | string;
  status: StepStatus | string;
  unblocks: string[];
  /** Where the step's pages and methodology entries live, e.g. `docs/iteration2/step-1`. */
  docs: string;
  takes_hypotheses: boolean;
  /** Latest revision of every claim filed under this step, in this iteration. */
  hypotheses: HypothesisRow[];
  /** Filenames under `figures/track1/<iteration>/<slug>/`. */
  figures: string[];
  entries: StepEntry[];
}

/** Whether the iteration has read anything it promised not to, and when that ended. */
export interface BlindState {
  still_blind: boolean;
  unblinded_by: string | null;
  problems: string[];
}

/** GET /api/steps */
export interface StepsPayload {
  iteration: string;
  /** Every iteration that has a step map, oldest first. */
  iterations: string[];
  /** The iteration being worked now. */
  current: string;
  /** False when no claim has ever been filed — different from "filed and empty". */
  register_exists: boolean;
  blind: BlindState;
  steps: StepRow[];
}

/**
 * Iteration 2 step 2's result tables: `GET /api/steps/step-2`.
 *
 * **Aggregates only.** Four of the six tables behind this carry real genomic positions of
 * the proband; none of their rows is served. Every block is grouped in SQL before it
 * leaves the database, so there is no coordinate on this surface to withhold.
 */

/** One row of the bait pass funnel, as the loader wrote it. */
export interface Step2Funnel {
  stage: string;
  metric: string;
  value: number;
  note: string | null;
}

/** One tier, counted both ways — the step's central finding is that they disagree. */
export interface Step2Tier {
  tier: string;
  genes: number;
  /** Genes with two rare protein-altering alleles, or one homozygous. */
  biallelic_filtered: number;
  /** The same enumeration with no rarity or consequence filter at all. */
  biallelic_unfiltered: number;
  truncating: number;
  clinvar_flagged: number;
  /** Qualifying alleles the delivered callset never reported. */
  novel_qualifying: number;
  unannotated: number;
}

/** One gene the filter leaves standing, target or decoy. */
export interface Step2Lead {
  symbol: string;
  tier: string;
  rare_het: number;
  rare_hom_alt: number;
  truncating: number;
  clinvar_flagged: number;
  novel_qualifying: number;
  /** Surviving unique k-mers per base: how reachable this gene was. */
  bait_density: number;
  mean_depth: number;
}

/** One caller against the delivered callset, where both emit a genotype. */
export interface Step2Concordance {
  caller: string;
  co_called: number;
  agreed: number;
  concordance: number;
  delivered_pass: number;
  concordance_at_pass: number;
}

/** Structural-variant consensus by type, split by the two artefact controls. */
export interface Step2Sv {
  sv_type: string;
  bait_edge: boolean;
  /** True when the call spans the unbaited gaps the bait itself created. */
  spans_unbaited: boolean;
  consensus_calls: number;
  distinct_events: number;
  /** Kosugi 2019's short-read precision for this type. A prior, not our measurement. */
  precision_prior: number | null;
  median_length: number | null;
  shortest: number | null;
  longest: number | null;
}

/** Depth per gene, never per interval — the interval rows carry coordinates. */
export interface Step2Depth {
  symbol: string;
  tier: string;
  intervals: number;
  mean_depth: number;
  below_floor: number;
}

/** Read-backed phasing as a size distribution. */
export interface Step2Phase {
  blocks: number;
  phased_variants: number;
  median_span: number;
  longest_span: number;
  blocks_with_two_or_more: number;
}

/** A gene the bait could not reach. Carry this beside any "nothing found here". */
export interface Step2Unreachable {
  symbol: string;
  tier: string;
  density: number;
  lost: number;
}

/** Targets against decoys, under one filter. */
export interface Step2Contrast {
  filter: string;
  target_genes: number;
  target_biallelic: number;
  target_rate: number;
  decoy_genes: number;
  decoy_biallelic: number;
  decoy_rate: number;
}

/** GET /api/steps/step-2 */
export interface Step2Payload {
  funnel: Step2Funnel[];
  by_tier: Step2Tier[];
  leads: Step2Lead[];
  concordance: Step2Concordance[];
  sv_consensus: Step2Sv[];
  depth: Step2Depth[];
  phase: Step2Phase[];
  unreachable: Step2Unreachable[];
  contrast: Step2Contrast[];
}
