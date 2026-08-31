import type {
  DepthBinRow,
  FilterRow,
  GenotypeRow,
  IndelLengthRow,
  SubstitutionRow,
  TsTv,
} from '../api/types';
import { prng } from './prng';

/** FIXTURE — MEASURED. Top FILTER values from bcftools stats on the delivered VCF. */
export const filtersFixture: FilterRow[] = [
  { filter_value: 'PASS', count: 4_740_790, pct_of_section: 94.58, impact_rank: 0 },
  { filter_value: 'MQ40', count: 177_522, pct_of_section: 3.54, impact_rank: 1 },
  { filter_value: 'QD2', count: 35_402, pct_of_section: 0.71, impact_rank: 2 },
  { filter_value: 'LowQual;QD2', count: 17_000, pct_of_section: 0.34, impact_rank: 3 },
  { filter_value: 'MQ40;QD2', count: 12_541, pct_of_section: 0.25, impact_rank: 4 },
  // Remainder of the suppressed set, so the funnel adds up to 5,012,204 exactly.
  { filter_value: 'other', count: 28_949, pct_of_section: 0.58, impact_rank: 5 },
];

/** FIXTURE — MEASURED. 1/2 is a compound heterozygote proven by genotype alone. */
export const genotypesFixture: GenotypeRow[] = [
  { label: '0/1', count: 3_047_077 },
  { label: '1/1', count: 1_898_267 },
  { label: '1/2', count: 66_860 },
];

/**
 * FIXTURE — depth distribution. MEASURED anchors: unimodal, 55 bins, mode ≈ 44x,
 * mean depth 44.0x. The curve itself is generated to those anchors; the live API
 * parses the real DP section of bcftools stats.
 */
export const depthDistributionFixture: DepthBinRow[] = (() => {
  const rand = prng(4477);
  const bins = 55;
  const mode = 44;
  const sd = 9.5;
  const raw = Array.from({ length: bins }, (_, bin) => {
    const g = Math.exp(-0.5 * Math.pow((bin - mode) / sd, 2));
    // Slight right skew plus a low-coverage shoulder near zero.
    const shoulder = bin < 8 ? 0.02 * Math.exp(-bin / 3) : 0;
    return Math.max(1e-6, g * (0.97 + rand() * 0.06) + shoulder);
  });
  const sum = raw.reduce((a, b) => a + b, 0);
  const total = 5_012_204;
  return raw.map((v, bin) => ({
    bin,
    count: Math.round((v / sum) * total),
    pct: Math.round((v / sum) * 1000) / 10,
  }));
})();

/**
 * FIXTURE — substitution spectrum. MEASURED anchors: C>T 692,184; G>A 692,284;
 * A>C 173,731; Ts/Tv 1.94 over 4,086,641 SNPs. The remaining ten cells are filled so
 * the twelve counts sum to the measured SNP total at the measured Ts/Tv.
 */
export const substitutionsFixture: SubstitutionRow[] = [
  { sub_type: 'A>C', count: 173_731, is_transition: false },
  { sub_type: 'A>G', count: 656_420, is_transition: true },
  { sub_type: 'A>T', count: 172_950, is_transition: false },
  { sub_type: 'C>A', count: 174_120, is_transition: false },
  { sub_type: 'C>G', count: 173_010, is_transition: false },
  { sub_type: 'C>T', count: 692_184, is_transition: true },
  { sub_type: 'G>A', count: 692_284, is_transition: true },
  { sub_type: 'G>C', count: 173_400, is_transition: false },
  { sub_type: 'G>T', count: 174_250, is_transition: false },
  { sub_type: 'T>A', count: 173_420, is_transition: false },
  { sub_type: 'T>C', count: 656_419, is_transition: true },
  { sub_type: 'T>G', count: 174_453, is_transition: false },
];

/** FIXTURE — MEASURED ratio 1.94; ts/tv split derived from the 4,086,641 SNP total. */
export const tstvFixture: TsTv = { ts: 2_697_307, tv: 1_389_334, ratio: 1.94 };

/**
 * FIXTURE — indel length spectrum. MEASURED anchors: 930,181 indels, range from about
 * −60 bp, roughly symmetric geometric decay around ±1 bp. Generated to those anchors;
 * the live API parses the real IDD section.
 */
export const indelLengthsFixture: IndelLengthRow[] = (() => {
  const rand = prng(9301);
  const lengths: number[] = [];
  for (let l = -60; l <= 60; l++) if (l !== 0) lengths.push(l);
  const raw = lengths.map((l) => {
    const a = Math.abs(l);
    // Geometric decay, with deletions slightly favoured (real callsets skew that way).
    const base = Math.exp(-a / 2.6) * (l < 0 ? 1.08 : 1.0);
    return Math.max(1e-9, base * (0.9 + rand() * 0.2));
  });
  const sum = raw.reduce((a, b) => a + b, 0);
  const total = 930_181;
  return lengths.map((length, i) => ({
    length,
    count: Math.max(1, Math.round((raw[i] / sum) * total)),
  }));
})();
