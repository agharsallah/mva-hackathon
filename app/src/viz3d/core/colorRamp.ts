/**
 * Sampling the app's generated colour scales, per vertex.
 *
 * Plotly interpolates a `Colorscale`'s stops itself; three needs the colour *per vertex*, so
 * this module reimplements that interpolation over the **existing** `Colorscale` type. It
 * parses hex out of the generated stops and never writes one, so `local/no-raw-hex-color`
 * stays green and a 3D surface and the 2D heat strip of the same data are the same numbers.
 *
 * Everything here is pure and unit-tested. Colours come out as sRGB triples in 0..1 — the
 * space `Colorscale` hex is authored in. `core/scene.ts` converts to three's linear working
 * space on the way into a buffer attribute, which is what keeps a ramped surface and a
 * `new three.Color(C.grid)` line the same green on screen.
 */

import { C, type Colorscale, type Tone, TONE_MARK } from '../../lib/palette';

export type Rgb = [number, number, number];

const HEX = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})/i;

/** `#rrggbb` (or `#rrggbbaa`, alpha ignored) -> sRGB 0..1. Black for anything unparseable. */
export function hexToRgb(hex: string): Rgb {
  const m = HEX.exec(hex.trim());
  if (!m) return [0, 0, 0];
  return [parseInt(m[1], 16) / 255, parseInt(m[2], 16) / 255, parseInt(m[3], 16) / 255];
}

const lerp = (a: number, b: number, t: number): number => a + (b - a) * t;
const clamp01 = (t: number): number => (t < 0 ? 0 : t > 1 ? 1 : t);

/** sRGB triple at position `t` (0..1) on a generated `Colorscale`. */
export function sampleScale(scale: Colorscale, t: number): Rgb {
  if (scale.length === 0) return [0, 0, 0];
  const at = clamp01(Number.isFinite(t) ? t : 0);
  let lo = scale[0];
  for (const stop of scale) {
    if (stop[0] <= at) lo = stop;
    else {
      const a = hexToRgb(lo[1]);
      const b = hexToRgb(stop[1]);
      const span = stop[0] - lo[0];
      const f = span <= 0 ? 0 : (at - lo[0]) / span;
      return [lerp(a[0], b[0], f), lerp(a[1], b[1], f), lerp(a[2], b[2], f)];
    }
  }
  return hexToRgb(lo[1]);
}

/** The one hex a tone is drawn with, as an sRGB triple. */
export const toneRgb = (tone: Tone): Rgb => hexToRgb(TONE_MARK[tone]);

/** The flat grey for "measured but below the floor" / "no value here". */
export const absentRgb = (): Rgb => hexToRgb(C.unmeasured);

/** Normalise a value onto 0..1 over `domain`. A zero-width domain reads as 0. */
export function normalise(value: number, domain: readonly [number, number]): number {
  const span = domain[1] - domain[0];
  return span === 0 ? 0 : clamp01((value - domain[0]) / span);
}

/**
 * Fill an rgb-triple buffer from values + domain — the colour half of every adapter.
 * A `null` value is drawn in `absent` rather than interpolated, so "not measured" can never
 * be mistaken for a point on the ramp.
 */
export function rampColors(
  values: readonly (number | null)[],
  scale: Colorscale,
  domain: readonly [number, number],
  absent: string = C.unmeasured,
): Float32Array {
  const out = new Float32Array(values.length * 3);
  const missing = hexToRgb(absent);
  values.forEach((value, index) => {
    const rgb = value === null ? missing : sampleScale(scale, normalise(value, domain));
    out[index * 3] = rgb[0];
    out[index * 3 + 1] = rgb[1];
    out[index * 3 + 2] = rgb[2];
  });
  return out;
}

/**
 * sRGB component -> three's linear working space. three applies exactly this transform when
 * it parses a `#rrggbb` string (`ColorManagement` has been on by default since r152), so a
 * vertex colour must get it too or the ramped mesh comes out visibly paler than the palette.
 */
export function srgbToLinear(c: number): number {
  return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}

/** `srgbToLinear` over a whole rgb buffer, in place. */
export function linearizeColors(colors: Float32Array): Float32Array {
  for (let i = 0; i < colors.length; i++) colors[i] = srgbToLinear(colors[i]);
  return colors;
}
