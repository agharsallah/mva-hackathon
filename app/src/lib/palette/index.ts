/**
 * The repo's visual language, in one place.
 *
 * green  = good / safe / the goal
 * red    = broken / dangerous / lost points
 * yellow = a decision point
 * blue   = neutral machinery
 * purple = the raw input
 * grey   = chrome, or a value that was never measured
 *
 * Every exhibit in the app decodes its own use of these in a Legend line, per the repo's
 * visualization rules. `/style-guide` renders the whole system as one exhibit.
 *
 * ## How the two halves stay one system
 *
 * A colour is needed in two incompatible places: the DOM (a Tailwind class on a `<div>`) and
 * a canvas (a hex string handed to Plotly, an SVG `fill`, an inline style). Those cannot share
 * a mechanism, so they share a *source* instead:
 *
 *   tools/gen-theme.mjs  reads tailwindcss's own default theme, converts oklch to hex, writes
 *     |                  both halves from that one conversion
 *     +-> ./ramps.generated.ts   ->  RAMP.good[500]        (this file's `C`, charts, SVG)
 *     +-> ../../theme.generated.css -> --color-good-500    (`bg-good-500`, lib/ui.ts recipes)
 *
 * `pnpm theme:check` (and src/test/theme-tokens.test.ts) fails if either committed artifact
 * drifts from the generator, so "the badge green" and "the chart green" are the same number by
 * construction. Raw hex outside `ramps.generated.ts` is an eslint error
 * (`local/no-raw-hex-color`), and so is a bare Tailwind hue like `bg-emerald-400`
 * (`local/no-builtin-tailwind-color`) — the semantic families are the only way in.
 */

export {
  balanceColor,
  impactColor,
  impactTone,
  jobStateTone,
  oeVerdictColor,
  oeVerdictTone,
  verdictColor,
  verdictTone,
} from './encode';
export { type Family, RAMP, type Shade, SHADES } from './ramps.generated';
export {
  type Colorscale,
  DENSITY_SCALE,
  DEPTH_SCALE,
  DIVERGING_SCALE,
  QUALITY_SCALE,
  RARITY_SCALE,
  REASON_RAMP,
  SERIES,
  SEVERITY_ORANGE,
} from './scales';
export { type Tone, TONE_FAMILY, TONE_MARK, TONES } from './tones';

import { RAMP } from './ramps.generated';

/**
 * The named single colours, for chart code that wants a meaning rather than a shade number.
 *
 * Every value is a stop on a generated ramp — this object renames, it never invents. Where a
 * chart wants the tone vocabulary instead (`good`/`broken`/...), `TONE_MARK` is the same
 * numbers keyed by tone.
 */
export const C = {
  good: RAMP.good[500],
  goodDim: RAMP.good[800],
  broken: RAMP.broken[500],
  brokenDim: RAMP.broken[900],
  decision: RAMP.decision[500],
  machinery: RAMP.machinery[500],
  machineryDim: RAMP.machinery[900],
  raw: RAMP.raw[500],
  /** A value that was never computed at all. Same grey as the app's chrome, on purpose. */
  absent: RAMP.chrome[500],
  /** Body text, and any label drawn on the page background. */
  ink: RAMP.chrome[200],
  /** Secondary text: axis ticks, legends, captions. */
  inkDim: RAMP.chrome[400],
  /** Chart gridlines and every border in the app. */
  grid: RAMP.chrome[800],
  /** The page background. */
  paper: RAMP.chrome[950],
  /** A panel/card background, one step up from `paper`. */
  panel: RAMP.chrome[900],
  /**
   * A bin/cell that was measured but sits below the confidence floor — distinct from
   * `absent`, which marks a value that was never computed at all. Flat grey on purpose: it
   * must not be mistakable for a point on any of the colour scales in `./scales`.
   */
  unmeasured: RAMP.chrome[700],
  /** The blue stop inside `DENSITY_SCALE` — reused verbatim wherever legend prose spells out
   * the "dark → blue → purple" ramp inline (BAF karyogram, density bins, karyotype, flowcell). */
  densityBlue: RAMP.machinery[700],
  /** Off-white label text drawn directly on a coloured mark (e.g. a treemap tile fill), where
   * `ink`'s grey doesn't read against a saturated background. */
  onFill: RAMP.chrome[100],
  /** `machineryDim` at ~33% alpha — a translucent blue fill behind a "neutral machinery"
   * station box, as opposed to `machineryDim`'s own opaque use as a stroke/line colour. */
  machineryFill: `${RAMP.machinery[900]}55`,
  /** The same 33% alpha in the decision family — a translucent fill behind a "decision point"
   * station box, matching `BOX.decision`'s tint at the same opacity family. */
  decisionFill: `${RAMP.decision[900]}55`,
} as const;
