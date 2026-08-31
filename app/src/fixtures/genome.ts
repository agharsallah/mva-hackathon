import type { AlleleBalanceRow, ContigDensityRow, DensityBinRow } from '../api/types';
import { prng } from './prng';

/**
 * GRCh38 primary-assembly contig lengths. Reference-genome constants (the coordinate
 * system), not patient data.
 */
export const GRCH38_LENGTHS: Record<string, number> = {
  '1': 248_956_422,
  '2': 242_193_529,
  '3': 198_295_559,
  '4': 190_214_555,
  '5': 181_538_259,
  '6': 170_805_979,
  '7': 159_345_973,
  '8': 145_138_636,
  '9': 138_394_717,
  '10': 133_797_422,
  '11': 135_086_622,
  '12': 133_275_309,
  '13': 114_364_328,
  '14': 107_043_718,
  '15': 101_991_189,
  '16': 90_338_345,
  '17': 83_257_441,
  '18': 80_373_285,
  '19': 58_617_616,
  '20': 64_444_167,
  '21': 46_709_983,
  '22': 50_818_468,
  X: 156_040_895,
  Y: 57_227_415,
  MT: 16_569,
};

export const CANONICAL_ORDER: string[] = [
  ...Array.from({ length: 22 }, (_, i) => String(i + 1)),
  'X',
  'Y',
  'MT',
];

/**
 * FIXTURE — allele balance per contig.
 *
 * MEASURED anchors (from the executed exploration): Y n_het 4301, mean_vaf 0.3517,
 * mean_dp 36.3, flagged, dp_vs_autosomal 0.815; X 4858 / 0.4644 / 41.4 / balanced / 0.930;
 * chr20 59467 / 0.472 / 45.5 / balanced / 1.022. The remaining autosomes are known to
 * cluster at 0.472–0.497 VAF and 43.7–46.1 mean depth with a balanced call; their exact
 * per-chromosome values are filled here to that measured envelope so the plot has 25
 * points offline. The live API returns the real pg.results.allele_balance_flags table.
 */
const AB_SEED = 20260831;

function autosomeAlleleBalance(): AlleleBalanceRow[] {
  const rand = prng(AB_SEED);
  return CANONICAL_ORDER.filter((c) => c !== 'X' && c !== 'Y' && c !== 'MT' && c !== '20').map((chrom) => {
    const length = GRCH38_LENGTHS[chrom];
    // het count scales with contig length; chr20 measured 59467 het over 64.4 Mb.
    const nHet = Math.round((length / GRCH38_LENGTHS['20']) * 59_467 * (0.94 + rand() * 0.14));
    const meanVaf = 0.472 + rand() * 0.025;
    const meanDp = 43.7 + rand() * 2.4;
    return {
      chrom,
      n_het: nHet,
      mean_vaf: round(meanVaf, 4),
      mean_dp: round(meanDp, 1),
      pct_in_0_40_0_60: round(76 + rand() * 6, 1),
      vaf_deviation: round(meanVaf - 0.5, 4),
      balance_call: 'balanced',
      dp_vs_autosomal: round(meanDp / 44.5, 3),
    };
  });
}

export const alleleBalanceFixture: AlleleBalanceRow[] = [
  ...autosomeAlleleBalance(),
  {
    chrom: '20',
    n_het: 59_467,
    mean_vaf: 0.472,
    mean_dp: 45.5,
    pct_in_0_40_0_60: 79.4,
    vaf_deviation: -0.028,
    balance_call: 'balanced',
    dp_vs_autosomal: 1.022,
  },
  {
    chrom: 'X',
    n_het: 4858,
    mean_vaf: 0.4644,
    mean_dp: 41.4,
    pct_in_0_40_0_60: 71.2,
    vaf_deviation: -0.0356,
    balance_call: 'balanced',
    dp_vs_autosomal: 0.93,
  },
  {
    chrom: 'Y',
    n_het: 4301,
    mean_vaf: 0.3517,
    mean_dp: 36.3,
    pct_in_0_40_0_60: 41.8,
    vaf_deviation: -0.1483,
    balance_call: 'flagged',
    dp_vs_autosomal: 0.815,
  },
].sort((a, b) => CANONICAL_ORDER.indexOf(a.chrom) - CANONICAL_ORDER.indexOf(b.chrom));

/**
 * FIXTURE — contig density.
 *
 * MEASURED anchors: chr19 1917 var/Mb (highest), chr20 1853.4, chr21 1848.3,
 * chr10 1805.5, chr4 1785.4; chr1 383,428 records over 248,956,422 bp (= 1540.3 var/Mb).
 * Other contigs are filled inside that measured range; the live API returns
 * pg.results.contig_density.
 */
const DENSITY_PER_MB: Record<string, number> = {
  '1': 1540.3,
  '2': 1633.0,
  '3': 1601.5,
  '4': 1785.4,
  '5': 1652.8,
  '6': 1668.1,
  '7': 1704.2,
  '8': 1721.6,
  '9': 1596.4,
  '10': 1805.5,
  '11': 1688.9,
  '12': 1673.2,
  '13': 1740.7,
  '14': 1652.1,
  '15': 1698.4,
  '16': 1766.9,
  '17': 1731.0,
  '18': 1708.8,
  '19': 1917.0,
  '20': 1853.4,
  '21': 1848.3,
  '22': 1699.2,
  X: 1053.6,
  Y: 214.8,
  MT: 1207.7,
};

export const contigDensityFixture: ContigDensityRow[] = (() => {
  const rows = CANONICAL_ORDER.map((chrom) => {
    const length = GRCH38_LENGTHS[chrom];
    const perMb = DENSITY_PER_MB[chrom];
    const nRecords = chrom === '1' ? 383_428 : Math.round((length / 1e6) * perMb);
    return { chrom, length, n_records: nRecords, variants_per_mb: perMb, pct_of_callset: 0 };
  });
  const total = rows.reduce((a, r) => a + r.n_records, 0);
  return rows.map((r) => ({ ...r, pct_of_callset: round((r.n_records / total) * 100, 3) }));
})();

/**
 * FIXTURE — 1 Mb density bins, generated to the per-contig density above with the
 * measured 94.58 % PASS share. Shape only; the live API serves the precomputed
 * pg.results.variant_density_bins table.
 */
export function densityBinsFixture(chrom?: string): DensityBinRow[] {
  const chroms = chrom ? [chrom.replace(/^chr/, '')] : CANONICAL_ORDER.filter((c) => c !== 'MT');
  const out: DensityBinRow[] = [];
  chroms.forEach((c, ci) => {
    const length = GRCH38_LENGTHS[c];
    if (!length) return;
    const perMb = DENSITY_PER_MB[c] ?? 1600;
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
