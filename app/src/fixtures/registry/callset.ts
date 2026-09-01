/**
 * Callset fixture registry fragment: the bcftools-stats-derived exhibits plus the
 * overview tile and the three small warehouse tables.
 *
 * All rows live in `../data/*.json` (lazy-loaded, see `../loader.ts`). None of these
 * endpoints take params, so there is no `shape/` module for this fragment.
 */

import type { Entry } from '../loader';
import { rows } from '../loader';
import type {
  DepthBinRow,
  FilterRow,
  FunnelStageRow,
  GenotypeRow,
  IndelLengthRow,
  ObservedExpectedRow,
  Overview,
  SubstitutionRow,
  TsTv,
  VcfFieldRow,
  ZygosityRow,
} from '../../api/types';

export const callsetEntries: Record<string, Entry> = {
  // MEASURED. Aggregates from the repo's executed exploration runs (counts and ratios
  // only — no patient sequence, no coordinates).
  '/api/overview': {
    source: 'measured aggregates, executed exploration runs',
    load: () => rows<Overview>('overview'),
  },
  // MEASURED. Top FILTER values from bcftools stats on the delivered VCF.
  '/api/callset/filters': {
    source: 'bcftools stats FILTER section',
    load: () => rows<FilterRow[]>('callset-filters'),
  },
  // MEASURED. 1/2 is a compound heterozygote proven by genotype alone.
  '/api/callset/genotypes': {
    source: 'bcftools stats genotype counts',
    load: () => rows<GenotypeRow[]>('callset-genotypes'),
  },
  // Depth distribution. MEASURED anchors: unimodal, 55 bins, mode ~44x, mean depth
  // 44.0x. The curve itself was generated to those anchors (prng seed 4477) and the
  // resulting 55 rows are transcribed verbatim into JSON; the live API parses the real
  // DP section of bcftools stats.
  '/api/callset/depth-distribution': {
    source: 'bcftools stats DP section',
    load: () => rows<DepthBinRow[]>('callset-depth-distribution'),
  },
  // Substitution spectrum. MEASURED anchors: C>T 692,184; G>A 692,284; A>C 173,731;
  // Ts/Tv 1.94 over 4,086,641 SNPs. The remaining ten cells are filled so the twelve
  // counts sum to the measured SNP total at the measured Ts/Tv.
  '/api/callset/substitutions': {
    source: 'bcftools stats ST section',
    load: () => rows<SubstitutionRow[]>('callset-substitutions'),
  },
  // MEASURED ratio 1.94; ts/tv split derived from the 4,086,641 SNP total.
  '/api/callset/tstv': {
    source: 'bcftools stats TSTV section',
    load: () => rows<TsTv>('callset-tstv'),
  },
  // Indel length spectrum. MEASURED anchors: 930,181 indels, range from about -60 bp,
  // roughly symmetric geometric decay around +-1 bp. Generated to those anchors (prng
  // seed 9301) and the resulting 120 rows are transcribed verbatim into JSON; the live
  // API parses the real IDD section.
  '/api/callset/indel-lengths': {
    source: 'bcftools stats IDD section',
    load: () => rows<IndelLengthRow[]>('callset-indel-lengths'),
  },
  // `observed` is MEASURED for every row (same aggregates as overview/bcftools).
  // `expected_low`/`expected_high`/`source` are PLACEHOLDER plausible published bands
  // with their citation strings, filled so the exhibit is readable offline. The live
  // endpoint supplies the ranges it actually cites. All four verdicts are exercised.
  '/api/callset/observed-expected': {
    source: 'measured aggregates vs PLACEHOLDER published bands',
    load: () => rows<ObservedExpectedRow[]>('callset-observed-expected'),
  },
  // MEASURED, every row. Verbatim output of the `candidate_funnel` derivation executed
  // against the warehouse (docs/step-0/methodology/039), transcribed so the exhibit
  // reads correctly with the API down. Nothing here is shaped or interpolated.
  '/api/callset/funnel': {
    source: 'results.candidate_funnel',
    load: () => rows<FunnelStageRow[]>('callset-funnel'),
  },
  // MEASURED. `results.stats_af`, both rows. `af_bin` is NOT a population frequency:
  // one sample means AN is always 2, so bcftools' two bins are AC=1 and AC=2. Both
  // allele totals match the independent genotype counter exactly.
  '/api/callset/zygosity-split': {
    source: 'results.stats_af',
    load: () => rows<ZygosityRow[]>('callset-zygosity-split'),
  },
  // MEASURED. `warehouse.vcf_fields`, all 31 rows, descriptions verbatim from the
  // delivered VCF header. 7 FILTER, 17 INFO, 7 FORMAT.
  '/api/callset/fields': {
    source: 'warehouse.vcf_fields',
    load: () => rows<VcfFieldRow[]>('callset-fields'),
  },
};
