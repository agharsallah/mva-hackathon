/**
 * The one colour generator.
 *
 * Reads the installed `tailwindcss` default theme (`node_modules/tailwindcss/theme.css`,
 * oklch), converts the seven hue ramps this repo uses into sRGB hex, and writes both
 * halves of the design-token system from that single conversion:
 *
 *   src/lib/palette/ramps.generated.ts  the hex ramps TypeScript reads (Plotly canvas, SVG,
 *                                       inline style) — the only file in src/** allowed to
 *                                       contain a raw hex colour literal.
 *   src/theme.generated.css             the same values as Tailwind v4 `@theme` custom
 *                                       properties, so `bg-good-950` and `C.good` are the
 *                                       same number by construction, not by coincidence.
 *
 * Run `pnpm theme` after upgrading tailwindcss. `pnpm theme:check` (and
 * src/test/theme-tokens.test.ts) fails if either committed file has drifted from what this
 * script would write — that check is the proof the two halves cannot diverge.
 *
 * Why hex in the CSS rather than `var(--color-green-500)` aliases: Plotly parses colours in
 * JavaScript (tinycolor) and cannot read an `oklch()` string or a CSS variable, so the
 * canvas half needs concrete hex. Emitting the same hex on the DOM half keeps the two
 * byte-identical instead of "the same colour in two colour spaces".
 */

import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const APP = dirname(fileURLToPath(new URL('.', import.meta.url)));
const THEME_SRC = join(APP, 'node_modules/tailwindcss/theme.css');
const RAMPS_OUT = join(APP, 'src/lib/palette/ramps.generated.ts');
const CSS_OUT = join(APP, 'src/theme.generated.css');

/**
 * Semantic family name -> the Tailwind hue it is cut from. The semantic name is what the
 * repo writes (`bg-good-950`, `RAMP.good[500]`); the Tailwind name never appears in app
 * code, which is why `local/no-builtin-tailwind-color` bans it there.
 *
 * The mapping is the repo's colour legend (see src/lib/palette/index.ts):
 * green = good, red = broken, yellow = a decision point, blue = neutral machinery,
 * purple = the raw input, zinc = chrome (borders, panels, body text), orange = the one
 * extra severity step between broken and decision.
 */
const FAMILIES = {
  chrome: 'zinc',
  good: 'green',
  broken: 'red',
  decision: 'yellow',
  machinery: 'blue',
  raw: 'purple',
  severity: 'orange',
};

const SHADES = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950];

/** oklch -> sRGB hex (Björn Ottosson's Oklab matrices, then the sRGB transfer function). */
export function oklchToHex(lightness, chroma, hueDeg) {
  const h = (hueDeg * Math.PI) / 180;
  const a = chroma * Math.cos(h);
  const b = chroma * Math.sin(h);
  const lp = lightness + 0.3963377774 * a + 0.2158037573 * b;
  const mp = lightness - 0.1055613458 * a - 0.0638541728 * b;
  const sp = lightness - 0.0894841775 * a - 1.291485548 * b;
  const l = lp ** 3;
  const m = mp ** 3;
  const s = sp ** 3;
  const linear = [
    4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s,
  ];
  const channel = (u) => {
    const v = u <= 0.0031308 ? 12.92 * u : 1.055 * u ** (1 / 2.4) - 0.055;
    return Math.round(Math.min(1, Math.max(0, v)) * 255);
  };
  return `#${linear
    .map(channel)
    .map((n) => n.toString(16).padStart(2, '0'))
    .join('')}`;
}

/** Parse `--color-<family>-<shade>: oklch(L% C H);` lines out of Tailwind's theme.css. */
function parseTailwindRamps(css) {
  const out = new Map();
  // Tailwind writes a fully-desaturated stop's hue as the CSS-wide keyword `none`
  // (e.g. `oklch(98.5% 0 none)` for zinc-50); with chroma 0 the hue is irrelevant, so it
  // is read as 0 rather than rejected.
  const re = /--color-([a-z]+)-(\d{2,3}):\s*oklch\(([\d.]+)%\s+([\d.]+)\s+([\d.]+|none)\)/g;
  for (const [, family, shade, l, c, h] of css.matchAll(re)) {
    if (!out.has(family)) out.set(family, new Map());
    const hue = h === 'none' ? 0 : Number(h);
    out.get(family).set(Number(shade), oklchToHex(Number(l) / 100, Number(c), hue));
  }
  return out;
}

function buildRamps() {
  const parsed = parseTailwindRamps(readFileSync(THEME_SRC, 'utf8'));
  const ramps = {};
  for (const [semantic, tailwind] of Object.entries(FAMILIES)) {
    const ramp = parsed.get(tailwind);
    if (!ramp) throw new Error(`tailwindcss theme.css has no --color-${tailwind}-* ramp`);
    ramps[semantic] = {};
    for (const shade of SHADES) {
      const hex = ramp.get(shade);
      if (!hex) throw new Error(`tailwindcss theme.css has no --color-${tailwind}-${shade}`);
      ramps[semantic][shade] = hex;
    }
  }
  return ramps;
}

const BANNER = (target) => `/**
 * GENERATED FILE — do not edit. Run \`pnpm theme\` to regenerate.
 *
 * Source: tailwindcss@${tailwindVersion()} default theme (oklch), converted to sRGB hex by
 * tools/gen-theme.mjs. ${target}
 */`;

function tailwindVersion() {
  const pkg = JSON.parse(readFileSync(join(APP, 'node_modules/tailwindcss/package.json'), 'utf8'));
  return pkg.version;
}

function renderTs(ramps) {
  const families = Object.entries(ramps)
    .map(([family, ramp]) => {
      const rows = SHADES.map((s) => `    ${s}: '${ramp[s]}',`).join('\n');
      return `  ${family}: {\n${rows}\n  },`;
    })
    .join('\n');
  return `${BANNER('The hex half: what Plotly, SVG and inline style read.')}

/** The shade steps every family carries, coarse (50) to deepest (950). */
export const SHADES = [${SHADES.join(', ')}] as const;

export type Shade = (typeof SHADES)[number];

/**
 * Semantic hue ramps. Indexed \`RAMP.good[500]\` and mirrored one-for-one by the
 * \`--color-good-500\` custom properties in src/theme.generated.css.
 */
export const RAMP = {
${families}
} as const satisfies Record<string, Record<Shade, string>>;

export type Family = keyof typeof RAMP;
`;
}

function renderCss(ramps) {
  const vars = Object.entries(ramps)
    .map(([family, ramp]) => SHADES.map((s) => `  --color-${family}-${s}: ${ramp[s]};`).join('\n'))
    .join('\n\n');
  return `${BANNER('The DOM half: the Tailwind v4 @theme utilities.')}

@theme {
${vars}
}
`;
}

function prettify(source, parser) {
  return execFileSync('node_modules/.bin/prettier', ['--parser', parser], {
    cwd: APP,
    input: source,
    encoding: 'utf8',
  });
}

function main() {
  const ramps = buildRamps();
  const artifacts = [
    { path: RAMPS_OUT, text: prettify(renderTs(ramps), 'typescript') },
    { path: CSS_OUT, text: prettify(renderCss(ramps), 'css') },
  ];
  if (process.argv.includes('--check')) {
    const drifted = artifacts.filter(({ path, text }) => readFileSync(path, 'utf8') !== text);
    if (drifted.length) {
      const names = drifted.map((a) => a.path.replace(`${APP}/`, '')).join(', ');
      console.error(`theme tokens drifted from tools/gen-theme.mjs: ${names}\nRun: pnpm theme`);
      process.exit(1);
    }
    console.log('theme tokens in sync');
    return;
  }
  for (const { path, text } of artifacts) {
    writeFileSync(path, text);
    console.log(`wrote ${path.replace(`${APP}/`, '')}`);
  }
}

if (import.meta.url === `file://${process.argv[1]}`) main();
