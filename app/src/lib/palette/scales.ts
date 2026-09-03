/**
 * Colour *scales* — a colour per position on a range, for the charts.
 *
 * A tone answers "what does this value mean" (see `./tones`); a scale answers "where on a
 * range does this value sit". Every stop below is a shade of a generated family, so a scale
 * can never wander off the repo's colour legend the way a hand-picked hex could.
 */

import { themeStore } from '../theme';
import { RAMP } from './ramps.generated';
import { type Ramp, rampFor } from './theme';

/** A Plotly colourscale: `[position 0..1, colour]` stops, interpolated between. */
export type Colorscale = [number, string][];

/**
 * The live ramp — used by the three **sequential** scales, which mirror whole with the theme.
 *
 * A sequential ramp does not encode identity, it encodes distance from the page: its cold end
 * *is* the background (chrome-950 in dark) and its hot end is the furthest thing from it. Both
 * ends therefore have to flip together. Mirroring only the chrome end would leave the hot end
 * a pale lavender painted on a white page — the densest chromosome rendering as the faintest
 * bar, which inverts the reading of the figure.
 *
 * The verdict ramps below (`QUALITY_SCALE`, `DIVERGING_SCALE`) and every categorical list are
 * deliberately *not* mirrored: those encode meaning, and red has to stay the same red.
 */
const live = (): Ramp => rampFor(themeStore.get());

/** Extra severity step between `broken` and `decision`: orange, for a ramp that needs more
 * stops than the three core verdict colours (suppression reasons, base-quality bins). */
export const SEVERITY_ORANGE = RAMP.severity[500];

/** Categorical ramp for "one line per lane/read" series: machinery blue into raw purple. */
export const SERIES = [
  RAMP.machinery[400],
  RAMP.machinery[500],
  RAMP.machinery[600],
  RAMP.machinery[700],
  RAMP.raw[400],
  RAMP.raw[500],
  RAMP.raw[600],
  RAMP.raw[700],
];

/** Sequential ramp for density: page background → blue → pale purple (raw input at the hot end). */
export let DENSITY_SCALE: Colorscale = densityScale();

function densityScale(): Colorscale {
  const R = live();
  return [
    [0, R.chrome[950]],
    [0.15, R.machinery[950]],
    [0.4, R.machinery[700]],
    [0.7, R.raw[600]],
    [1, R.raw[200]],
  ];
}

/** Diverging ramp for quality: red (bad) → yellow → green (good). */
export const QUALITY_SCALE: Colorscale = [
  [0, RAMP.broken[900]],
  [0.35, RAMP.broken[500]],
  [0.6, RAMP.decision[500]],
  [1, RAMP.good[500]],
];

/**
 * Diverging ramp for a signed deviation from a neutral midpoint, e.g. BAF away from 0.5.
 *
 * Green sits at the **centre**, not at an end: for allele balance the goal is the middle of
 * the range, and both directions away from it are the abnormal outcome. Red marks a deficit
 * (fewer variant reads than expected) and purple a surplus, so the sign of the shift is
 * readable and neither direction is quietly privileged.
 */
export const DIVERGING_SCALE: Colorscale = [
  [0, RAMP.broken[900]],
  [0.25, RAMP.broken[500]],
  [0.42, RAMP.good[800]],
  [0.5, RAMP.good[500]],
  [0.58, RAMP.good[800]],
  [0.75, RAMP.raw[500]],
  [1, RAMP.raw[200]],
];

/** Sequential ramp for read depth: page background → blue → white-hot. Neutral machinery. */
export let DEPTH_SCALE: Colorscale = depthScale();

function depthScale(): Colorscale {
  const R = live();
  return [
    [0, R.chrome[950]],
    [0.3, R.machinery[900]],
    [0.65, R.machinery[500]],
    [1, R.machinery[100]],
  ];
}

/**
 * Suppression-reason ramp for `SuppressedCalls`: reds and yellows, heaviest reason first
 * (`PASS` is drawn separately, in the `good` tone). Assigned by rank rather than by reason
 * name so the ordering stays stable if the caller's FILTER vocabulary changes.
 */
export const REASON_RAMP = [
  RAMP.broken[500],
  SEVERITY_ORANGE,
  RAMP.decision[500],
  RAMP.broken[700],
  RAMP.decision[400],
  RAMP.broken[900],
];

/**
 * Unknown-pair shading for `PairMatrix`'s compound-het grid: dark chrome (common pair) →
 * machinery blue → pale (rare × rare — the region a causal pair has to live in).
 */
export let RARITY_SCALE: Colorscale = rarityScale();

function rarityScale(): Colorscale {
  const R = live();
  return [
    [0, R.chrome[900]],
    [0.45, R.machinery[900]],
    [0.75, R.machinery[500]],
    [1, R.machinery[200]],
  ];
}

/**
 * Rebuild the three sequential scales when the theme changes.
 *
 * These three are the only exported *values* in the palette that cannot be a getter: a
 * colourscale is an array a chart reads whole, and ~15 call sites import the binding by name.
 * ES module bindings are live, so reassigning here updates every importer — and this
 * subscription is registered at import time, before React mounts, so the arrays are already
 * rebuilt by the time `AppShell`'s own theme subscriber re-keys the page and the exhibits
 * re-read them.
 */
themeStore.subscribe(() => {
  DENSITY_SCALE = densityScale();
  DEPTH_SCALE = depthScale();
  RARITY_SCALE = rarityScale();
});
