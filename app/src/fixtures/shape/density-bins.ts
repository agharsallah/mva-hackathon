import type { DensityBinRow } from '../../api/types';
import { rows } from '../loader';
import { prng } from '../prng';

/**
 * FIXTURE — 1 Mb density bins, generated to the per-contig density measured in
 * `data/genome-density-per-mb.json` with the measured 94.58 % PASS share. Shape only; the
 * live API serves the precomputed pg.results.variant_density_bins table.
 */
export async function densityBinsFixture(chrom?: string): Promise<DensityBinRow[]> {
  const [lengths, order, perMbTable] = await Promise.all([
    rows<Record<string, number>>('genome-grch38-lengths'),
    rows<string[]>('genome-canonical-order'),
    rows<Record<string, number>>('genome-density-per-mb'),
  ]);
  const chroms = chrom ? [chrom.replace(/^chr/, '')] : order.filter((c) => c !== 'MT');
  const out: DensityBinRow[] = [];
  chroms.forEach((c, ci) => {
    const length = lengths[c];
    if (!length) return;
    const perMb = perMbTable[c] ?? 1600;
    const rand = prng(1000 + ci * 97);
    const bins = Math.ceil(length / 1e6);
    for (let mb = 0; mb < bins; mb++) {
      // Centromeric / acrocentric stretches call almost nothing: model a dip.
      const centro = Math.exp(-Math.pow((mb - bins * 0.38) / (bins * 0.05), 2));
      const factor = Math.max(0.02, (1 - 0.9 * centro) * (0.75 + rand() * 0.5));
      const n = Math.round(perMb * factor);
      const passN = Math.round(n * (0.93 + rand() * 0.03));
      out.push({
        chrom: c,
        mb,
        n,
        pass_n: passN,
        low_qual_n: Math.max(0, Math.round((n - passN) * 0.18)),
        mean_qual: round(240 + rand() * 90, 1),
      });
    }
  });
  return out;
}

function round(x: number, d: number): number {
  const f = 10 ** d;
  return Math.round(x * f) / f;
}
