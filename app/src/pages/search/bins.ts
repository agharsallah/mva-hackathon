/**
 * Binning a window's records into human-sized bars: pick a bin width, then count PASS vs
 * suppressed records per bin.
 *
 * Split out of `DensityStrip.tsx` so that module can export components only — Vite's fast
 * refresh only hot-swaps a module whose every export is a component, and a constant or a
 * function export alongside one forces a full reload on every edit.
 */

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
