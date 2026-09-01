/**
 * A mini density strip: how the window's records are spread along it, PASS against
 * suppressed.
 *
 * The table below answers "what is here"; this answers "where in the window is it", which
 * a 5,000-row table cannot. Bins are chosen so the strip stays about 120 bars wide
 * whatever the span — a fixed 1 kb bin would be 5,000 bars on a 5 Mb window and 1 bar on a
 * gene's promoter — and the bin width is stated on the axis and in the legend, because a
 * count per bin means nothing without it.
 */

import { Chip } from '../../components/Exhibit';
import { Plot, baseLayout } from '../../components/Plot';
import { C } from '../../lib/palette';
import type { RegionVariant } from '../../api/types';

/** Roughly how many bars to draw, whatever the span. */
const TARGET_BINS = 120;

/** Round a raw bin width up to something a human reads: 1, 2, 5 × 10ⁿ bp, minimum 1 bp. */
export function niceBin(width: number): number {
  const raw = Math.max(width / TARGET_BINS, 1);
  const power = 10 ** Math.floor(Math.log10(raw));
  for (const step of [1, 2, 5, 10]) {
    if (raw <= step * power) return step * power;
  }
  return 10 * power;
}

export function binLabel(bp: number): string {
  if (bp >= 1e6) return `${bp / 1e6} Mb`;
  if (bp >= 1e3) return `${bp / 1e3} kb`;
  return `${bp} bp`;
}

export interface Bins {
  bp: number;
  starts: number[];
  pass: number[];
  suppressed: number[];
}

export function bin(variants: RegionVariant[], start: number, end: number): Bins {
  const bp = niceBin(end - start + 1);
  const count = Math.max(Math.ceil((end - start + 1) / bp), 1);
  const starts = Array.from({ length: count }, (_, i) => start + i * bp);
  const pass = new Array<number>(count).fill(0);
  const suppressed = new Array<number>(count).fill(0);
  for (const v of variants) {
    const i = Math.min(Math.floor((v.pos - start) / bp), count - 1);
    if (i < 0) continue;
    if (v.filter === 'PASS') pass[i] += 1;
    else suppressed[i] += 1;
  }
  return { bp, starts, pass, suppressed };
}

/** The legend text, exported so the Exhibit wrapping this strip can carry it. */
export function DensityLegend({ bp }: { bp: number }) {
  return (
    <>
      One bar = one {binLabel(bp)} bin of the resolved window, stacked{' '}
      <Chip color={C.good}>PASS</Chip> under <Chip color={C.broken}>suppressed</Chip> (a record the
      caller kept but flagged). Height is the record count in that bin, so the strip reads as
      coverage-and-callability along the window, not as evidence of pathogenicity. An empty stretch
      is a real gap — either nothing was called there, or nothing passed.
    </>
  );
}

export function DensityStrip({
  variants,
  start,
  end,
  height = 150,
}: {
  variants: RegionVariant[];
  start: number;
  end: number;
  height?: number;
}) {
  const b = bin(variants, start, end);
  const hover = `%{y} records<br>bin start %{x:,}<extra>%{fullData.name}</extra>`;
  return (
    <Plot
      height={height}
      data={[
        {
          type: 'bar',
          name: 'PASS',
          x: b.starts,
          y: b.pass,
          marker: { color: C.good },
          hovertemplate: hover,
        },
        {
          type: 'bar',
          name: 'suppressed',
          x: b.starts,
          y: b.suppressed,
          marker: { color: C.broken },
          hovertemplate: hover,
        },
      ]}
      layout={baseLayout({
        barmode: 'stack',
        bargap: 0.05,
        margin: { l: 48, r: 12, t: 6, b: 40 },
        xaxis: {
          title: {
            text: `position along the window · ${binLabel(b.bp)} bins`,
            font: { color: C.inkDim, size: 11 },
          },
          range: [start, end],
          gridcolor: C.grid,
          tickfont: { color: C.inkDim, size: 10 },
        },
        yaxis: {
          title: { text: 'records', font: { color: C.inkDim, size: 11 } },
          gridcolor: C.grid,
          tickfont: { color: C.inkDim, size: 10 },
        },
        legend: { orientation: 'h', y: 1.25, x: 0, font: { color: C.inkDim, size: 10 } },
      })}
    />
  );
}
