/**
 * How a step and a claim are coloured, in one place.
 *
 * The repository's colour discipline is fixed: green = the goal reached, red = broken or
 * refuted, yellow = a decision point or work in flight, blue = machinery, grey = not
 * started. Every legend on `/steps` decodes these, and every exhibit reads them from here
 * so two panels cannot disagree about what amber means.
 */

import type { StepRow } from '../../api/types';
import type { Tone } from '../../lib/palette';

/** A step's tone: done is reached, open is in flight, planned has not started. */
export function stepTone(step: StepRow): Tone {
  if (step.kind === 'platform') return 'machinery';
  if (step.status === 'done') return 'good';
  if (step.status === 'open') return 'decision';
  return 'neutral';
}

/** A claim's tone. A refuted claim is red — it is a result, and the register keeps it. */
export function claimTone(status: string): Tone {
  switch (status) {
    case 'supported':
      return 'good';
    case 'refuted':
      return 'broken';
    case 'testing':
      return 'decision';
    case 'superseded':
      return 'neutral';
    default:
      return 'machinery';
  }
}

/** What a step's status means, in the words the page uses for it. */
export function statusLabel(step: StepRow): string {
  if (step.kind === 'platform') return 'platform';
  return step.status;
}

/** Verdicts of one step, counted — the number a reader scans a card for. */
export function verdictCounts(step: StepRow) {
  const counted = { supported: 0, refuted: 0, open: 0 };
  for (const claim of step.hypotheses) {
    if (claim.status === 'supported') counted.supported += 1;
    else if (claim.status === 'refuted') counted.refuted += 1;
    else counted.open += 1;
  }
  return counted;
}
