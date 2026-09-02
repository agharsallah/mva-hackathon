/**
 * Dark Plotly template shared by every exhibit.
 *
 * Split out of `Plot.tsx`: that file exports the `Plot` component, and
 * `react-refresh/only-export-components` requires a component module to export nothing else
 * runtime-visible — these two template functions live here instead so an edit to either file
 * still hot-swaps instead of forcing a full reload.
 */

import { C } from '../lib/palette';
import type { Layout } from './Plot';

const AXIS = {
  gridcolor: C.grid,
  zerolinecolor: C.grid,
  linecolor: C.grid,
  tickfont: { color: C.inkDim, size: 11 },
  titlefont: { color: C.inkDim, size: 12 },
};

/** Dark template shared by every exhibit. */
export function baseLayout(over: Layout = {}): Layout {
  return {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: C.ink, family: 'ui-sans-serif, system-ui, sans-serif', size: 12 },
    margin: { l: 60, r: 20, t: 12, b: 48 },
    xaxis: AXIS,
    yaxis: AXIS,
    legend: { font: { color: C.inkDim, size: 11 }, bgcolor: 'rgba(0,0,0,0)' },
    hoverlabel: { bgcolor: C.panel, bordercolor: C.grid, font: { color: C.ink } },
    ...over,
  };
}

/** Dark template for the 3D views: same idea, but scenes carry their own axis objects. */
export function scene3d(over: Record<string, unknown> = {}): Record<string, unknown> {
  const ax = {
    gridcolor: C.grid,
    zerolinecolor: C.grid,
    showbackground: true,
    backgroundcolor: 'rgba(255,255,255,0.015)',
    tickfont: { color: C.inkDim, size: 10 },
    titlefont: { color: C.inkDim, size: 11 },
  };
  return { xaxis: { ...ax }, yaxis: { ...ax }, zaxis: { ...ax }, ...over };
}
