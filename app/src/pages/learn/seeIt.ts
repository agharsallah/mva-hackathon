/**
 * Where the app shows a word.
 *
 * A dictionary entry says what a term means; this table says where in the app that term is
 * a real chart over this case's data, and which methodology entry measured it. Keyed by the
 * entry's slug. `to` is a route plus an exhibit anchor — `Exhibit` gives every figure an id
 * from its title, and `src/test/learn-links.test.tsx` mounts each page and proves the anchor
 * exists, so a renamed exhibit breaks the build rather than the link.
 *
 * Methodology entries are the append-only audit log in `docs/`; they open on GitHub.
 */

import { REPO_BLOB } from '../../lib/dictionary';
import { SEE_IT_MEASURE } from './seeItMeasure';
import { SEE_IT_PLATFORM } from './seeItPlatform';
import type { SeeIt } from './seeItShared';

export type { SeeIt, SeeItLink } from './seeItShared';

/** Every see-it link, keyed by dictionary slug. Two halves, split only to keep files short. */
export const SEE_IT: Record<string, SeeIt> = { ...SEE_IT_MEASURE, ...SEE_IT_PLATFORM };

export function seeIt(slug: string): SeeIt | undefined {
  return SEE_IT[slug];
}

export function docUrl(path: string): string {
  return REPO_BLOB + path;
}
