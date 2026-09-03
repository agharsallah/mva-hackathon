/**
 * The colour system's own test: the two halves are one system, or this fails.
 *
 * `lib/palette`'s `RAMP` (hex, read by Plotly and SVG) and `src/theme.generated.css`'s
 * `--color-*` custom properties (read by every Tailwind class in `lib/ui.ts`) are written by
 * the same generator. Nothing in the type system can state that, so it is stated here:
 *
 *  1. the committed artifacts still match what `tools/gen-theme.mjs` would write;
 *  2. every CSS custom property equals its `RAMP` twin, value for value — and the light
 *     theme's block is exactly the shade mirror of it (shade N takes shade 1000 − N), which
 *     is the whole of the light theme's definition;
 *  3. every tone-keyed map covers exactly `TONES` — the cross-file gap a `Record<Tone, …>`
 *     cannot catch, because each map could be typed against its own union;
 *  4. every class recipe names a family and shade that actually exist (Tailwind drops an
 *     unknown utility silently, so a typo is invisible in the browser);
 *  5. every scale stop and mark colour is a value from the ramps, not a stray literal.
 */

import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

import {
  type Colorscale,
  DENSITY_SCALE,
  DEPTH_SCALE,
  DIVERGING_SCALE,
  type Family,
  mirrorShade,
  QUALITY_SCALE,
  RAMP,
  RARITY_SCALE,
  REASON_RAMP,
  SERIES,
  SEVERITY_ORANGE,
  type Shade,
  SHADES,
  TONE_FAMILY,
  TONE_MARK,
  TONES,
} from '../lib/palette';
import { BADGE, BOX, CARD, EMPTY_DASHED, TEXT } from '../lib/ui';

// Paths are relative to the app root: that is vitest's cwd, and the same base the
// generator's own --check invocation below uses. `import.meta.url` is not usable here —
// under jsdom it resolves to an http:// URL, not a file one.
const THEME_CSS = readFileSync('src/theme.generated.css', 'utf8');

/** The selector the generator writes the mirrored (light) values under. */
const LIGHT_SELECTOR = ":root[data-theme='light']";

/**
 * The `--color-*` declarations of one block, as `{ 'good-500': '#00c950' }`.
 *
 * Scoped to a block rather than swept over the whole file, because the file now declares
 * every property twice — once dark, once mirrored — and a whole-file regex would silently
 * report only whichever came last.
 */
function declaredIn(marker: string): Record<string, string> {
  const start = THEME_CSS.indexOf(marker);
  expect(start, `${marker} block is present`).toBeGreaterThanOrEqual(0);
  const open = THEME_CSS.indexOf('{', start);
  const body = THEME_CSS.slice(open, THEME_CSS.indexOf('}', open));
  return Object.fromEntries(
    [...body.matchAll(/--color-([a-z]+)-(\d{2,3}):\s*(#[0-9a-f]{6})/g)].map(
      ([, family, shade, hex]) => [`${family}-${shade}`, hex],
    ),
  );
}

/** Every hex the ramps contain, for "is this colour from the palette at all" checks. */
const RAMP_VALUES = new Set(Object.values(RAMP).flatMap((ramp) => Object.values(ramp)));

const FAMILIES = Object.keys(RAMP) as Family[];

/** `bg-good-950/25`, `hover:border-broken-900` → the `family-shade` pairs a recipe names. */
function classColorTokens(recipe: string): Array<{ family: string; shade: number }> {
  const pattern = new RegExp(`\\b(${FAMILIES.join('|')})-(\\d{2,3})\\b`, 'g');
  return [...recipe.matchAll(pattern)].map(([, family, shade]) => ({
    family,
    shade: Number(shade),
  }));
}

const RECIPES: Record<string, Record<string, string> | string> = {
  CARD,
  BOX,
  BADGE,
  EMPTY_DASHED,
  TEXT,
};

const TONE_MAPS: Record<string, Record<string, unknown>> = {
  BOX,
  BADGE,
  EMPTY_DASHED,
  TEXT,
  TONE_FAMILY,
  TONE_MARK,
};

const SCALES: Record<string, Colorscale> = {
  DENSITY_SCALE,
  DEPTH_SCALE,
  DIVERGING_SCALE,
  QUALITY_SCALE,
  RARITY_SCALE,
};

describe('generated artifacts', () => {
  it('are what tools/gen-theme.mjs would write today', () => {
    // Runs the generator's own --check mode: it re-derives both files from the installed
    // tailwindcss theme and diffs them against what is committed. Throws (non-zero exit)
    // on drift, with "Run: pnpm theme" on stderr.
    expect(() =>
      execFileSync('node', ['tools/gen-theme.mjs', '--check'], { encoding: 'utf8' }),
    ).not.toThrow();
  });

  it('define one CSS custom property per ramp entry, with the same value', () => {
    const expected = FAMILIES.flatMap((family) =>
      SHADES.map((shade: Shade) => [`${family}-${shade}`, RAMP[family][shade]] as const),
    );
    expect(declaredIn('@theme')).toEqual(Object.fromEntries(expected));
  });

  it('mirror every shade in the light block: shade N takes the value of shade 1000 - N', () => {
    const expected = FAMILIES.flatMap((family) =>
      SHADES.map(
        (shade: Shade) => [`${family}-${shade}`, RAMP[family][mirrorShade(shade)]] as const,
      ),
    );
    expect(declaredIn(LIGHT_SELECTOR)).toEqual(Object.fromEntries(expected));
  });

  it('leave the 500 data marks identical in both themes', () => {
    const dark = declaredIn('@theme');
    const light = declaredIn(LIGHT_SELECTOR);
    for (const family of FAMILIES) {
      expect(light[`${family}-500`], `${family}-500`).toBe(dark[`${family}-500`]);
    }
  });
});

describe('tone vocabulary', () => {
  it('is covered exactly once by every tone-keyed map', () => {
    const tones = [...TONES].sort();
    for (const [name, map] of Object.entries(TONE_MAPS)) {
      expect(Object.keys(map).sort(), `${name} keys`).toEqual(tones);
    }
  });

  it('has no duplicate tones', () => {
    expect(new Set(TONES).size).toBe(TONES.length);
  });

  it('renders each tone with its declared family', () => {
    for (const tone of TONES) {
      expect(TONE_MARK[tone], `TONE_MARK.${tone}`).toBe(RAMP[TONE_FAMILY[tone]][500]);
    }
  });

  it('tints each tone in lib/ui with its declared family and nothing else', () => {
    for (const [name, map] of Object.entries({ BOX, BADGE, EMPTY_DASHED, TEXT })) {
      for (const tone of TONES) {
        const families = new Set(classColorTokens(map[tone]).map((t) => t.family));
        expect([...families], `${name}.${tone} families`).toEqual([TONE_FAMILY[tone]]);
      }
    }
  });
});

describe('class recipes', () => {
  it('only name shades the generated theme actually defines', () => {
    const recipes = Object.entries(RECIPES).flatMap(([name, recipe]) =>
      typeof recipe === 'string'
        ? [[name, recipe] as const]
        : Object.entries(recipe).map(([key, value]) => [`${name}.${key}`, value] as const),
    );
    for (const [name, recipe] of recipes) {
      for (const { family, shade } of classColorTokens(recipe)) {
        expect(SHADES, `${name} names ${family}-${shade}`).toContain(shade);
      }
    }
  });
});

describe('chart colours', () => {
  it('take every scale stop from the ramps', () => {
    for (const [name, scale] of Object.entries(SCALES)) {
      for (const [position, hex] of scale) {
        expect(position, `${name} stop position`).toBeGreaterThanOrEqual(0);
        expect(position, `${name} stop position`).toBeLessThanOrEqual(1);
        expect(RAMP_VALUES, `${name} stop ${hex}`).toContain(hex);
      }
    }
  });

  it('order the stops of every scale', () => {
    for (const [name, scale] of Object.entries(SCALES)) {
      const positions = scale.map(([position]) => position);
      expect(positions, `${name} positions`).toEqual([...positions].sort((a, b) => a - b));
      expect(positions[0], `${name} starts at 0`).toBe(0);
      expect(positions.at(-1), `${name} ends at 1`).toBe(1);
    }
  });

  it('take every categorical colour from the ramps', () => {
    for (const hex of [...SERIES, ...REASON_RAMP, SEVERITY_ORANGE, ...Object.values(TONE_MARK)]) {
      expect(RAMP_VALUES, hex).toContain(hex);
    }
  });
});
