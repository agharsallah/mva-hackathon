/**
 * GENERATED FILE — do not edit. Run `pnpm theme` to regenerate.
 *
 * Source: tailwindcss@4.3.3 default theme (oklch), converted to sRGB hex by
 * tools/gen-theme.mjs. The hex half: what Plotly, SVG and inline style read.
 */

/** The shade steps every family carries, coarse (50) to deepest (950). */
export const SHADES = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950] as const;

export type Shade = (typeof SHADES)[number];

/**
 * Semantic hue ramps. Indexed `RAMP.good[500]` and mirrored one-for-one by the
 * `--color-good-500` custom properties in src/theme.generated.css.
 */
export const RAMP = {
  chrome: {
    50: '#fafafa',
    100: '#f4f4f5',
    200: '#e4e4e7',
    300: '#d4d4d8',
    400: '#9f9fa9',
    500: '#71717b',
    600: '#52525c',
    700: '#3f3f46',
    800: '#27272a',
    900: '#18181b',
    950: '#09090b',
  },
  good: {
    50: '#f0fdf4',
    100: '#dcfce7',
    200: '#b9f8cf',
    300: '#7bf1a8',
    400: '#05df72',
    500: '#00c950',
    600: '#00a63e',
    700: '#008236',
    800: '#016630',
    900: '#0d542b',
    950: '#032e15',
  },
  broken: {
    50: '#fef2f2',
    100: '#ffe2e2',
    200: '#ffc9c9',
    300: '#ffa2a2',
    400: '#ff6467',
    500: '#fb2c36',
    600: '#e7000b',
    700: '#c10007',
    800: '#9f0712',
    900: '#82181a',
    950: '#460809',
  },
  decision: {
    50: '#fefce8',
    100: '#fef9c2',
    200: '#fff085',
    300: '#ffdf20',
    400: '#fdc700',
    500: '#f0b100',
    600: '#d08700',
    700: '#a65f00',
    800: '#894b00',
    900: '#733e0a',
    950: '#432004',
  },
  machinery: {
    50: '#eff6ff',
    100: '#dbeafe',
    200: '#bedbff',
    300: '#8ec5ff',
    400: '#51a2ff',
    500: '#2b7fff',
    600: '#155dfc',
    700: '#1447e6',
    800: '#193cb8',
    900: '#1c398e',
    950: '#162456',
  },
  raw: {
    50: '#faf5ff',
    100: '#f3e8ff',
    200: '#e9d4ff',
    300: '#dab2ff',
    400: '#c27aff',
    500: '#ad46ff',
    600: '#9810fa',
    700: '#8200db',
    800: '#6e11b0',
    900: '#59168b',
    950: '#3c0366',
  },
  severity: {
    50: '#fff7ed',
    100: '#ffedd4',
    200: '#ffd6a7',
    300: '#ffb86a',
    400: '#ff8904',
    500: '#ff6900',
    600: '#f54900',
    700: '#ca3500',
    800: '#9f2d00',
    900: '#7e2a0c',
    950: '#441306',
  },
} as const satisfies Record<string, Record<Shade, string>>;

export type Family = keyof typeof RAMP;
