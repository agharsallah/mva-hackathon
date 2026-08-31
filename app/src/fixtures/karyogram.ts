import type { BafBinRow } from '../api/types';
import { prng } from './prng';
import { CANONICAL_ORDER, GRCH38_LENGTHS } from './genome';

/**
 * FIXTURE — B-allele fraction per 1 Mb bin. **Shape, not measurement.**
 *
 * Every number below is generated. It exists so the karyogram renders and its controls,
 * colour scale and low-confidence styling are exercisable with the API down. The live
 * endpoint serves `pg.results.baf_bins`, and only those rows are evidence.
 *
 * The generator is anchored to the *envelope* the executed derivation reported, so the
 * fixture is not misleading about scale: autosomal bins cluster at mean VAF ~0.497 with a
 * per-bin spread near 0.09, ~77 % of calls inside 0.40–0.60, and mean depth ~42×.
 *
 * SYNTHETIC_ARM below is a deliberate lie: a shifted segment planted on one chromosome so
 * the diverging scale, the hover and the "what a real event would look like" reading have
 * something to show. **No such segment exists in the callset.** The live map is flat, and
 * the fixture is marked `fixture:` in the UI wherever it is used.
 */

/** Per-contig PRNG seed base, so the map is byte-identical on every reload. */
const SEED = 7_000;

/** Autosomal envelope from the executed run — used as generator anchors, not as claims. */
const BASE_VAF = 0.497;
const BASE_SD = 0.092;
const BASE_DP = 42.4;
const BASE_PCT_IN_BAND = 77;

/** The planted event: chromosome, first Mb, last Mb, BAF offset, depth multiplier. */
const SYNTHETIC_ARM = { chrom: '9', from: 12, to: 38, shift: 0.085, dpFactor: 1.48 };

export function bafBinsFixture(chrom?: string): BafBinRow[] {
  const wanted = chrom?.replace(/^chr/i, '');
  const chroms = wanted ? [wanted] : CANONICAL_ORDER.filter((c) => c !== 'MT');
  const out: BafBinRow[] = [];

  chroms.forEach((c, ci) => {
    const length = GRCH38_LENGTHS[c];
    if (!length) return;
    const rand = prng(SEED + ci * 131);
    const bins = Math.ceil(length / 1e6);
    // One copy of X and of Y in a male sample: few heterozygous calls, half the depth.
    const hemizygous = c === 'X' || c === 'Y';
    const perMb = hemizygous ? 45 : 1600;

    for (let mb = 0; mb < bins; mb++) {
      // The centromere calls almost nothing, on every chromosome — a property of the
      // reference, reproduced here so the thin-bin styling has real gaps to render.
      const centro = Math.exp(-(((mb - bins * 0.38) / (bins * 0.05)) ** 2));
      const nHet = Math.max(0, Math.round(perMb * Math.max(0.01, 1 - 0.97 * centro) * (0.7 + rand() * 0.6)));
      if (nHet === 0) continue;

      const planted =
        c === SYNTHETIC_ARM.chrom && mb >= SYNTHETIC_ARM.from && mb <= SYNTHETIC_ARM.to;
      const jitter = (rand() - 0.5) * (hemizygous ? 0.09 : 0.012);
      const meanVaf = clamp(BASE_VAF + jitter + (planted ? SYNTHETIC_ARM.shift : 0), 0.05, 0.95);
      const meanDp = BASE_DP * (hemizygous ? 0.4 : 1) * (0.96 + rand() * 0.08) * (planted ? SYNTHETIC_ARM.dpFactor : 1);
      const spread = BASE_SD * (hemizygous ? 1.8 : 1) * (0.9 + rand() * 0.3);

      out.push({
        chrom: c,
        mb,
        n_het: nHet,
        mean_vaf: round(meanVaf, 4),
        median_vaf: round(meanVaf - 0.002 + rand() * 0.004, 4),
        sd_vaf: nHet < 2 ? null : round(spread, 4),
        vaf_deviation: round(meanVaf - 0.5, 4),
        // Shifting the centre out of the band empties it fast; ~77 % is the flat case.
        pct_in_0_40_0_60: round(
          clamp(BASE_PCT_IN_BAND - 620 * Math.abs(meanVaf - 0.5) ** 1.6 - rand() * 4, 0, 100),
          1,
        ),
        mean_dp: round(meanDp, 1),
        low_confidence: nHet < 20,
      });
    }
  });
  return out;
}

function clamp(x: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, x));
}

function round(x: number, d: number): number {
  const f = 10 ** d;
  return Math.round(x * f) / f;
}
