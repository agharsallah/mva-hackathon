import type { CycleQualityRow, QualityLevelRow } from '../../api/types';
import { rows } from '../loader';
import { prng } from '../prng';

/**
 * FIXTURE — mean phred per sequencing cycle, per partition.
 *
 * MEASURED anchors: 149 cycles; quality is binned to exactly {2, 11, 25, 37} with ~93 %
 * of bases at 37; Q30 share is 92.9 % in R1 against 90.0 % in R2 — R2 genuinely degrades.
 * The per-cycle curve is generated to those anchors; the live API samples 100k rows per
 * partition (~20 s each, cached).
 */
export function cycleQualityFixture(): CycleQualityRow[] {
  const out: CycleQualityRow[] = [];
  for (const lane of [1, 2, 3, 4]) {
    for (const readNum of [1, 2]) {
      const rand = prng(500 + lane * 11 + readNum);
      const start = readNum === 1 ? 35.6 : 35.4;
      const drop = readNum === 1 ? 0.9 : 2.6; // R2 loses much more by the last cycle
      for (let cycle = 1; cycle <= 149; cycle++) {
        const t = (cycle - 1) / 148;
        // First cycles are noisy, then a slow decline that steepens at the end.
        const rampIn = cycle <= 4 ? -0.6 * (5 - cycle) * 0.25 : 0;
        const decline = drop * Math.pow(t, 1.7);
        const q = start + rampIn - decline + (rand() - 0.5) * 0.08 - lane * 0.02;
        out.push({ lane, read_num: readNum, cycle, mean_q: Math.round(q * 100) / 100 });
      }
    }
  }
  return out;
}

/**
 * FIXTURE — the NovaSeq four-level quality binning made explicit.
 * MEASURED: the only phred values present are {2, 11, 25, 37}, ~93 % of bases at 37,
 * Q30 92.9 % R1 vs 90.0 % R2.
 */
export async function qualityLevelsFixture(): Promise<QualityLevelRow[]> {
  const laneReads = await rows<Record<string, number>>('reads-lane-reads');
  const out: QualityLevelRow[] = [];
  for (const lane of [1, 2, 3, 4]) {
    for (const readNum of [1, 2]) {
      const bases = laneReads[lane] * 149;
      const q37 = readNum === 1 ? 0.929 : 0.9;
      const shares: Record<number, number> = {
        37: q37,
        25: (1 - q37) * 0.46,
        11: (1 - q37) * 0.33,
        2: (1 - q37) * 0.21,
      };
      for (const phred of [2, 11, 25, 37]) {
        out.push({ lane, read_num: readNum, phred, count: Math.round(bases * shares[phred]) });
      }
    }
  }
  return out;
}
