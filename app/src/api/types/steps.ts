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
