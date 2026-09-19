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

/** What a track badge says. `both` is a method both submissions quote, not a hedge. */
export const TRACK_LABEL: Record<string, string> = {
  track1: 'Track 1 — the variant',
  track2: 'Track 2 — the drugs',
  both: 'both tracks',
};

/**
 * Where a step's own page is.
 *
 * Every research step of every iteration has one under Track 1 — the generator writes a
 * route per declared step, so the link follows from the tree rather than from a second list
 * that could fall behind it. Track 2's iterations have a single step each and show it in
 * full on the iteration page, so a card there links nowhere; a platform step has no page
 * because it belongs to no iteration.
 */
export function detailPath(step: StepRow, iteration: string, track: string): string {
  if (track !== 'track1' || step.kind === 'platform') return '';
  return `/track1/${iteration}/${step.slug}`;
}

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
