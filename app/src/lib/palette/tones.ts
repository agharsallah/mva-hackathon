/**
 * The tone vocabulary — the six meanings a colour is allowed to carry in this app.
 *
 * A *tone* is semantic ("this number is good"), a *family* is the hue ramp that renders it
 * ("green"). Every component that tints something takes a `Tone`, never a hue: that is what
 * keeps a badge and the tile it sits on from disagreeing about what green means, and what
 * makes adding a seventh meaning a compiler error at every site instead of a silent gap.
 *
 * Adding a tone: add it to `Tone` and `TONES` here, point it at a family in `TONE_FAMILY`
 * (adding the family to `tools/gen-theme.mjs` first if it is a new hue), then let
 * `tsc` walk you through the `Record<Tone, string>` maps in `lib/ui.ts` that stop compiling.
 * `/style-guide` renders whatever `TONES` contains, so the new tone shows up there for free.
 */

import { type Family, RAMP } from './ramps.generated';

export type Tone = 'neutral' | 'good' | 'broken' | 'decision' | 'machinery' | 'raw';

/** Declaration order = the order `/style-guide` and any legend renders them in. */
export const TONES: readonly Tone[] = ['neutral', 'good', 'broken', 'decision', 'machinery', 'raw'];

/**
 * Tone -> the generated hue family that renders it. Only `neutral` differs from its own
 * name: it is drawn in `chrome`, the grey that also paints every border, panel and body
 * line, because "no verdict attached" and "app furniture" are the same grey on purpose.
 */
export const TONE_FAMILY: Record<Tone, Family> = {
  neutral: 'chrome',
  good: 'good',
  broken: 'broken',
  decision: 'decision',
  machinery: 'machinery',
  raw: 'raw',
};

/**
 * Tone -> the one hex a chart draws the tone with (the 500 stop of its family).
 *
 * This is the canvas-side twin of `lib/ui.ts`'s class recipes: a Plotly trace or an SVG
 * mark reaches for `TONE_MARK.good`, a `<div>` reaches for `BADGE.good`, and both resolve to
 * the same generated number because both sides come out of `tools/gen-theme.mjs`.
 */
export const TONE_MARK: Record<Tone, string> = {
  neutral: RAMP.chrome[500],
  good: RAMP.good[500],
  broken: RAMP.broken[500],
  decision: RAMP.decision[500],
  machinery: RAMP.machinery[500],
  raw: RAMP.raw[500],
};
