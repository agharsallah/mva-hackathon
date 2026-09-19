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
 * Where a step's own page is, when it has one.
 *
 * Only some steps earned a detail page: one is built when a step's result needs tables and
 * charts the card cannot hold. `built` is the set of routes the module manifest declares,
 * handed in by the page from the journey context — so a page added to the manifest is linked
 * from here with no second list to keep in step, and a step whose page was never built simply
 * has no link, which is the truth about it.
 *
 * The detail pages are the *current* iteration's — `current` comes from the payload, so the
 * app never keeps its own copy of which iteration that is. A frozen iteration's card must
 * not link to a page rendering another iteration's numbers, so the link appears only for it.
 */
export function detailPath(
  step: StepRow,
  iteration: string,
  current: string,
  built: ReadonlySet<string>,
): string {
  if (iteration !== current) return '';
  const path = `/steps/${step.slug}`;
  return built.has(path) ? path : '';
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
