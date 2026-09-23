/**
 * The research routes, parsed: `/track1/iteration2/step-4` is a track, an iteration and a
 * step, and three pages need all three.
 *
 * The paths are static — the module manifest declares one per node, generated from the step
 * maps — so there are no router params to read. The address itself carries the identity, and
 * the iteration segment is the *same string* `/api/steps?iteration=` takes, so a page never
 * has to translate between what the URL says and what the API is asked.
 */

/** Which submission a track's pages argue. The nav's two top-level research nodes. */
export type TrackId = 'track1' | 'track2';

export interface ResearchRoute {
  track: TrackId;
  /** An iteration name exactly as the step maps spell it, e.g. `iteration2`. */
  iteration: string;
  /** A step slug, or empty on an iteration's own page. */
  slug: string;
}

const TRACK_LABEL: Record<TrackId, string> = { track1: 'Track 1', track2: 'Track 2' };

/** `Track 1`, for a heading. */
export function trackLabel(track: string): string {
  return TRACK_LABEL[track as TrackId] ?? track;
}

/** `iteration2` -> `iteration 2`. The slug is the API's word; this is the reader's. */
export function iterationLabel(iteration: string): string {
  const digits = iteration.replace(/\D/g, '');
  return digits ? `iteration ${digits}` : iteration;
}

/**
 * An iteration's summary as a reader should see it: the step map's docstring line ends in a
 * citation (`… (docs/iteration4/plan.md).`), right in a docstring and noise in a card. The
 * nav generator strips it the same way (`tools/gen_steps_nav.py` → `summary`).
 */
export function plainSummary(summary: string): string {
  return summary.replace(/\s*\([^)]*\)\s*\.?\s*$/, '.').replace(/\.\.$/, '.');
}

/** `step-4` -> `Step 4`. */
export function stepLabel(slug: string): string {
  const digits = slug.replace(/\D/g, '');
  return digits ? `Step ${digits}` : slug;
}

/**
 * The track, iteration and step a pathname names, or `null` when it names none of them.
 *
 * Deliberately strict: an unknown track or a malformed iteration reads as "not a research
 * route" rather than being passed to the API, so a hand-edited address renders the page's
 * own empty state instead of a 404 from the server.
 */
export function parseResearchPath(pathname: string): ResearchRoute | null {
  const [, track, iteration, slug = ''] = pathname.split('/');
  if (track !== 'track1' && track !== 'track2') return null;
  if (!iteration || !/^iteration\d+$/.test(iteration)) return null;
  if (slug && !/^step-\d+$/.test(slug)) return null;
  return { track, iteration, slug };
}

/** Which step tracks a track's pages collect. `both` is argued where its alleles are. */
export function tracksShownOn(track: TrackId): string[] {
  return track === 'track1' ? ['track1', 'both'] : ['track2'];
}
