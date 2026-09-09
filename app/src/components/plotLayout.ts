/**
 * The Plotly template shared by every exhibit.
 *
 * Theme-aware by construction: nothing here is a colour, everything is a `C.*` lookup, and
 * `C`'s structural entries resolve against the live theme at read time (see
 * `lib/palette/index.ts`). That is why `AXIS` is a function rather than a module constant —
 * a constant would freeze whichever theme happened to be current when this module was first
 * imported. The paper/plot backgrounds stay fully transparent in both themes so the page's
 * own background shows through and there is exactly one place a background is decided.
 *
 * Split out of `Plot.tsx`: that file exports the `Plot` component, and
 * `react-refresh/only-export-components` requires a component module to export nothing else
 * runtime-visible — these two template functions live here instead so an edit to either file
 * still hot-swaps instead of forcing a full reload.
 */

import { C } from '../lib/palette';
import { themeStore } from '../lib/theme';
import type { Layout } from './Plot';

/**
 * Must match `--font-sans` in `index.css` and the family that
 * `.js-plotly-plot .plotly text { font-family: ... !important; }` forces onto every Plotly
 * text node. Plotly measures line-height/`dy` offsets for hover labels using this string
 * *before* the CSS override repaints the glyphs in a different font; if the two disagree,
 * the box Plotly draws is sized for one font while the text renders in another, so
 * multi-line hover text sits shifted (typically upward) out of its label. Keep both in sync.
 */
const FONT_SANS = "'Atkinson Hyperlegible Next Variable', ui-sans-serif, system-ui, sans-serif";

/** Built per call, not once: `C.grid` and `C.inkDim` differ between the two themes. */
const axis = () => ({
  gridcolor: C.grid,
  zerolinecolor: C.grid,
  linecolor: C.grid,
  tickfont: { color: C.inkDim, size: 11 },
  titlefont: { color: C.inkDim, size: 12 },
});

/** The template shared by every exhibit. */
export function baseLayout(over: Layout = {}): Layout {
  return {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: C.ink, family: FONT_SANS, size: 12 },
    margin: { l: 60, r: 20, t: 12, b: 48 },
    xaxis: axis(),
    yaxis: axis(),
    legend: { font: { color: C.inkDim, size: 11 }, bgcolor: 'rgba(0,0,0,0)' },
    hoverlabel: {
      bgcolor: C.panel,
      bordercolor: C.grid,
      font: { color: C.ink, family: FONT_SANS },
    },
    ...over,
  };
}

/**
 * The barest lift off the page background for a 3D scene wall — the only place the template
 * needs to know which way "away from the background" points. White at 1.5% over a near-black
 * page and black at 3% over a near-white one read as the same faint plane; a single value
 * would be invisible in one theme and a grey slab in the other.
 */
const wall = () => (themeStore.get() === 'light' ? 'rgba(0,0,0,0.03)' : 'rgba(255,255,255,0.015)');

/**
 * A translucent band drawn on the plot background (e.g. the tolerance band around 0.5 on the
 * allele-balance screen): a barely-there lift that has to darken a light page and lighten a
 * dark one, so it is read from the theme at layout-build time like `scene3d`'s wall.
 */
export function bandTint(): string {
  return themeStore.get() === 'light' ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.045)';
}

/** Template for the 3D views: same idea, but scenes carry their own axis objects. */
export function scene3d(over: Record<string, unknown> = {}): Record<string, unknown> {
  const ax = {
    gridcolor: C.grid,
    zerolinecolor: C.grid,
    showbackground: true,
    backgroundcolor: wall(),
    tickfont: { color: C.inkDim, size: 10 },
    titlefont: { color: C.inkDim, size: 11 },
  };
  return { xaxis: { ...ax }, yaxis: { ...ax }, zaxis: { ...ax }, ...over };
}
