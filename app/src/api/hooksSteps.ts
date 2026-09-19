/**
 * The research-record hooks: one per step's detail route, plus the journey itself.
 *
 * Split out of `hooks.ts` because there is one of these per research step and the set grows
 * with the science rather than with the platform — the same reason
 * `mva.warehouse.cli_it2` exists on the Python side.
 */

import { useEndpoint } from './hooks';
import type {
  Step1Payload,
  Step2Payload,
  Step3Payload,
  Step4Payload,
  Step5Payload,
  Step6Payload,
  Step8Payload,
  StepEntryPayload,
  StepsPayload,
} from './types';

/**
 * The research journey of one iteration. Omitting `iteration` asks for the current one,
 * which is what every page but the iteration switcher wants.
 */
export const useSteps = (iteration?: string) =>
  useEndpoint<StepsPayload>('/api/steps', iteration ? { iteration } : undefined);

/**
 * One methodology entry, verbatim. The audit log is quoted on the page rather than
 * summarised there: a reader who wants to check a verdict reads the entry that made it,
 * and `enabled` keeps the fetch out of the way until they ask for one.
 */
export const useStepEntry = (iteration: string, slug: string, entry: string | null) =>
  useEndpoint<StepEntryPayload>(`/api/steps/${iteration}/${slug}/entry/${entry ?? ''}`, undefined, {
    enabled: Boolean(entry),
  });

/**
 * Iteration 2 step 2's result tables. Aggregates only — the four tables behind it carry
 * real genomic positions and none of their rows crosses this boundary.
 */
export const useStep2 = () => useEndpoint<Step2Payload>('/api/steps/step-2');

/** Step 3 — what the reads say with no aligner and no caller in the chain. */
export const useStep3 = () => useEndpoint<Step3Payload>('/api/steps/step-3');

/**
 * Step 4 — every gene in the callset ordered by a product of likelihood ratios, with the
 * decoy and permutation nulls that say how much the ordering is worth. Genes, shapes and
 * ratios; no coordinate crosses this boundary.
 */
export const useStep4 = () => useEndpoint<Step4Payload>('/api/steps/step-4');

/**
 * Iteration 2 step 5's knowledge route: the published-allele catalogue keyed on this
 * child's own alleles, the script-derived case-report anchors, the protein domain and
 * structure context, and the two baselines — a matched decoy set and a raw publication
 * count — that decide whether any of it is a measurement. Genes, dbSNP identifiers and
 * fractions of protein length; no coordinate and no residue crosses this boundary.
 */
export const useStep5 = () => useEndpoint<Step5Payload>('/api/steps/step-5');

/**
 * Iteration 2 step 6's fusion: the four routes with the measurement that admitted each one,
 * the agreement matrix, the leave-one-route-out table and the freeze receipt. The decision
 * block stays empty until the unblinding entry is filed, and the page reads that absence.
 */
export const useStep6 = () => useEndpoint<Step6Payload>('/api/steps/step-6');

/**
 * Iteration 2 step 8's mosaic bound: the fold-over deviation per contig with the null its
 * own depths generate, the five-model comparison, and — always in the same payload — the
 * smallest cell fraction each contig could have detected. A deviation without its limit is
 * the sentence entry 037 wrote, and the page has to be unable to render one alone.
 */
export const useStep8 = () => useEndpoint<Step8Payload>('/api/steps/step-8');

/**
 * Iteration 2 step 1's measurements: the recall curve, the tiers, the two-ranker overlap,
 * the decoy null and the four pre-registered gates. No coordinate, no gene symbol.
 */
export const useStep1 = () => useEndpoint<Step1Payload>('/api/steps/step-1');
