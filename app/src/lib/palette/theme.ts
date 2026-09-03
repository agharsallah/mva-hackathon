/**
 * The canvas half of the light theme: the same mirror rule `tools/gen-theme.mjs` writes into
 * `:root[data-theme="light"]`, applied to `RAMP` so Plotly, SVG and three.js follow along.
 *
 * **The rule, once:** shade N in light takes the value of shade (1000 − N) in dark.
 *
 *   50 <-> 950    100 <-> 900    200 <-> 800    300 <-> 700    400 <-> 600    500 -> 500
 *
 * Why a mirror rather than a second hand-picked palette: the shade roles are fixed app-wide —
 * 950 is the page/panel background, 800/900 are borders, 300/400 are text, 500 is the data
 * mark. Mirroring the *values* under those fixed *names* turns every existing
 * `bg-chrome-950` / `border-good-800` / `C.ink` into its light-mode equivalent without one
 * call site changing, and it is a rule short enough to hold in your head, so a new shade
 * cannot be light-mode-wrong by accident.
 *
 * 500 maps to itself, which is the point: `TONE_MARK.good` is the same green in both themes,
 * so a legend that says "green = good" stays true and two screenshots of the same chart in
 * different themes still show the same data colours.
 */

import type { Theme } from '../theme';
import { type Family, RAMP, type Shade, SHADES } from './ramps.generated';

/** A full palette: every family, every shade, as hex. `RAMP`'s shape, named. */
export type Ramp = Record<Family, Record<Shade, string>>;

/** The mirror itself. Total over `SHADES`, because the steps are symmetric around 500. */
export function mirrorShade(shade: Shade): Shade {
  return (1000 - shade) as Shade;
}

/** Mirror every family of a ramp, shade by shade. Pure: the input is never touched. */
export function mirrorRamp(ramp: Ramp): Ramp {
  const out = {} as Ramp;
  for (const family of Object.keys(ramp) as Family[]) {
    const shades = {} as Record<Shade, string>;
    for (const shade of SHADES) shades[shade] = ramp[family][mirrorShade(shade)];
    out[family] = shades;
  }
  return out;
}

/** The dark ramp, as generated. Named so `rampFor` reads symmetrically. */
export const DARK_RAMP: Ramp = RAMP;

/** The dark ramp, mirrored. Computed once — the values cannot change at runtime. */
export const LIGHT_RAMP: Ramp = mirrorRamp(DARK_RAMP);

/** The hex ramp a theme paints with. The one lookup `C` and the scales go through. */
export function rampFor(theme: Theme): Ramp {
  return theme === 'light' ? LIGHT_RAMP : DARK_RAMP;
}
